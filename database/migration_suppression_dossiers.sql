-- migration_suppression_dossiers - Migration des bases existantes vers « fichiers déposés à plat » (sans dossiers).
--
-- La refonte « /fichiers remplace /dossiers » retire le concept de dossier : les fichiers sont déposés
-- directement dans une division. Base NEUVE : 01_schema.sql est déjà conforme, ce script n'est PAS nécessaire.
-- Base EXISTANTE : appliquer ce script UNE fois avant de démarrer le backend mis à jour.
--   psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/migration_suppression_dossiers.sql
-- Le script est IDEMPOTENT : il peut être réappliqué sans danger (notamment sur une base déjà migrée
-- avec l'ancienne version de ce script, qui laissait la colonne document.dossier_id NOT NULL en place
-- et rendait tout dépôt impossible — 409 « Création impossible : doublon. »).
--
-- Les dépôts physiques (upload_dir) sont déjà à plat : aucune manipulation de fichiers sur le disque.
-- Aucun lien d'accès n'est perdu : les rôles de classement (document_role) portent tout l'accès, comme avant.

BEGIN;
SET search_path TO rag_sys, public;

-- 1. La vue des statistiques cite dossier_id : la recréer sans la colonne.
DROP VIEW IF EXISTS vue_document_stats;

-- 2. La clé composite document -> dossier et son index partent avec le concept de dossier.
ALTER TABLE document DROP CONSTRAINT IF EXISTS fk_document_dossier_division;
DROP INDEX IF EXISTS idx_document_dossier;
-- uq_document_id_division est conservée : document_role y attache chaque rôle à la division du fichier.

-- 2 bis. LA COLONNE dossier_id PART AUSSI. Dans l'ancien schéma elle était NOT NULL sans valeur par
-- défaut : si on ne la retire pas, chaque INSERT du code actuel (qui ne la fournit plus) échoue en
-- violation NOT NULL -> IntegrityError -> 409 « Création impossible : doublon. » À CHAQUE dépôt,
-- quel que soit le compte. (Cause du 409 observé sur les bases migrées avec l'ancienne version de ce script.)
ALTER TABLE document DROP COLUMN IF EXISTS dossier_id;

-- 2 ter. division_id devient NOT NULL (l'ancien schéma la laissait annulable, ON DELETE SET NULL) :
-- les fichiers orphelins (division supprimée) seraient inaccessibles dans le modèle « à plat », on les
-- retire (versions, rôles, étiquettes en cascade) avant de durcir la colonne.
DELETE FROM document WHERE division_id IS NULL;
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'rag_sys' AND table_name = 'document' AND column_name = 'division_id' AND is_nullable = 'YES'
    ) THEN
        ALTER TABLE document ALTER COLUMN division_id SET NOT NULL;
    END IF;
END $$;

-- 2 quater. La contrainte unique (id, division_id), cible des clés composites de document_role, doit
-- exister même si la base date d'avant la refonte des rôles de classement.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'uq_document_id_division' AND conrelid = 'rag_sys.document'::regclass) THEN
        ALTER TABLE document ADD CONSTRAINT uq_document_id_division UNIQUE (id, division_id);
    END IF;
END $$;

-- 3. Les commentaires sur dossier n'existent plus ; le sujet d'un commentaire est toujours un fichier.
DO $$
BEGIN
    ALTER TABLE commentaire DROP CONSTRAINT IF EXISTS commentaire_sujet_type_check;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'commentaire_sujet_type_check') THEN
        ALTER TABLE commentaire ADD CONSTRAINT commentaire_sujet_type_check CHECK (sujet_type IN ('document'));
    END IF;
END $$;

-- 4. La table dossier n'a plus d'usage : les fichiers référencent directement leur division.
DROP TABLE IF EXISTS dossier CASCADE;

-- 5. Recréer la vue des statistiques (sans dossier_id, avec division_id).
CREATE VIEW vue_document_stats AS
SELECT
    d.id AS document_id,
    d.division_id,
    d.categorie_id,
    d.type_document_id,
    d.confidentialite,
    d.corbeille_le,
    d.cree_le,
    d.cree_par,
    dv.service_id,
    s.direction_id,
    v.numero AS version_courante,
    v.statut,
    v.taille_octets,
    v.nb_pages,
    v.ocr_utilise,
    lower(substring(v.nom_fichier from '\.([^.]+)$')) AS extension,
    (SELECT count(*) FROM document_version x WHERE x.document_id = d.id) AS nb_versions
FROM document d
JOIN division dv ON dv.id = d.division_id
JOIN _service s ON s.id = dv.service_id
JOIN LATERAL (
    SELECT * FROM document_version WHERE document_id = d.id ORDER BY numero DESC LIMIT 1
) v ON TRUE;

COMMIT;
