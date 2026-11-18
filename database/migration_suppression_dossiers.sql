-- migration_suppression_dossiers - Migration des bases existantes vers « fichiers déposés à plat » (sans dossiers).
--
-- La refonte « /fichiers remplace /dossiers » retire le concept de dossier : les fichiers sont déposés
-- directement dans une division. Base NEUVE : 01_schema.sql est déjà conforme, ce script n'est PAS nécessaire.
-- Base EXISTANTE : appliquer ce script UNE fois avant de démarrer le backend mis à jour.
--   psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/migration_suppression_dossiers.sql
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

-- 3. Les commentaires sur dossier n'existent plus ; le sujet d'un commentaire est toujours un fichier.
ALTER TABLE commentaire DROP CONSTRAINT IF EXISTS commentaire_sujet_type_check;
ALTER TABLE commentaire ADD CONSTRAINT commentaire_sujet_type_check CHECK (sujet_type IN ('document'));

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
