-- 05 - Dossiers partagés, rôles de dossier, versions de fichiers, préférences et mémoire du chat.
-- À exécuter APRÈS 01 à 04, sur une base neuve (installation) comme sur une base déjà remplie (migration).
-- Les scripts 01 à 04 ne sont pas modifiés.
--
-- Commande (depuis la racine du dépôt), tout ou rien (une seule transaction, arrêt à la première erreur) :
--   psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/05_dossiers_versions.sql
-- Contrôle ensuite :  psql -U postgres -d rag -f database/05_verification.sql
-- Retour arrière    :  psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/05_retour_arriere.sql
--
-- Ce que fait le script
--   1. Crée dossier, dossier_membre (rôle direct d'un utilisateur), dossier_service (rôle donné à un service entier),
--      document_version, preference_utilisateur et memoire_chat.
--   2. Ajoute la permission globale dossier.gerer (ADMIN) et retire à UTILISATEUR les droits document.creer|modifier|supprimer :
--      ses droits sur les fichiers viennent désormais de ses rôles de dossier.
--   3. Migre les données existantes (une seule fois, détectée par la présence de document.service_id) :
--        - un dossier est créé pour chaque service existant et ouvert à ce service avec le rôle GESTIONNAIRE_DE_CONTENU
--          (c'est exactement ce que pouvait faire un UTILISATEUR de ce service avant : ajouter, modifier, supprimer) ;
--        - chaque document existant est rangé dans le dossier de son ancien service ;
--        - chaque document reçoit une version 1 (nom de fichier, hash, chemin, statut... déplacés de document vers document_version) ;
--        - chaque chunk est rattaché à la version 1 de son document ; embeddings et chunks ne sont PAS recalculés ;
--        - l'ancienne colonne document.service_id est sauvegardée dans migration_05_document_service (utile au retour arrière).
--      Les fichiers sur disque ne bougent pas. Un administrateur peut ensuite renommer les dossiers et changer les accès.
--   3 bis. Sur une base neuve, la même étape crée un dossier pour le service du seed (SRV-GENERAL).
--
-- Le script est répétable : relancé après migration, il ne change plus rien.

SET search_path TO rag_sys, public;

BEGIN;

-- 1. Dossiers ---------------------------------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dossier (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nom VARCHAR(150) NOT NULL,
    description TEXT,
    archive BOOLEAN NOT NULL DEFAULT FALSE,
    cree_par BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    modifie_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_dossier_nom ON dossier (lower(nom));

DROP TRIGGER IF EXISTS trg_dossier_modifie_le ON dossier;
CREATE TRIGGER trg_dossier_modifie_le
    BEFORE UPDATE ON dossier
    FOR EACH ROW EXECUTE FUNCTION maj_modifie_le();

-- Rôle direct d'un utilisateur dans un dossier (au plus un par couple).
CREATE TABLE IF NOT EXISTS dossier_membre (
    dossier_id BIGINT NOT NULL REFERENCES dossier(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    role VARCHAR(30) NOT NULL CHECK (role IN ('LECTEUR', 'CONTRIBUTEUR', 'GESTIONNAIRE_DE_CONTENU')),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (dossier_id, user_id)
);

-- Rôle donné à un service entier : tous les agents (actifs) du service ont ce rôle dans le dossier.
-- Le rôle effectif d'un utilisateur est le plus élevé entre son rôle direct et celui de son service.
CREATE TABLE IF NOT EXISTS dossier_service (
    dossier_id BIGINT NOT NULL REFERENCES dossier(id) ON DELETE CASCADE,
    service_id BIGINT NOT NULL REFERENCES _service(id),
    role VARCHAR(30) NOT NULL CHECK (role IN ('LECTEUR', 'CONTRIBUTEUR', 'GESTIONNAIRE_DE_CONTENU')),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (dossier_id, service_id)
);

-- 2. Versions de fichiers --------------------------------------------------------------------------------------
-- document (02) devient le fichier « logique » ; chaque dépôt est une ligne de document_version, jamais supprimée
-- par un nouveau dépôt. La date de la version est cree_le.

CREATE TABLE IF NOT EXISTS document_version (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    numero INTEGER NOT NULL CHECK (numero >= 1),
    nom_fichier VARCHAR(255) NOT NULL,
    type_mime VARCHAR(120),
    taille_octets BIGINT CHECK (taille_octets >= 0),
    hash_sha256 CHAR(64) NOT NULL,
    chemin_stockage TEXT NOT NULL,
    nb_pages INTEGER CHECK (nb_pages >= 0),
    ocr_utilise BOOLEAN NOT NULL DEFAULT FALSE,
    statut VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (statut IN ('pending', 'processing', 'ready', 'error')),
    message_erreur TEXT,
    cree_par BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_version_document_numero UNIQUE (document_id, numero)
);

-- 3. Préférences et mémoire du chat -----------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS preference_utilisateur (
    user_id BIGINT PRIMARY KEY REFERENCES _user(id) ON DELETE CASCADE,
    memoire_inter_sessions BOOLEAN NOT NULL DEFAULT FALSE,
    derniere_version_seulement BOOLEAN NOT NULL DEFAULT FALSE
);

-- Résultats retenus d'une session pour enrichir les suivantes (si l'option est active).
-- dossier_ids : dossiers dont viennent les passages cités ; une entrée n'est réutilisée que si l'utilisateur a encore
-- accès à TOUS ces dossiers (pas de clé étrangère : un dossier supprimé rend l'entrée inutilisable, donc muette).
CREATE TABLE IF NOT EXISTS memoire_chat (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    conversation_id BIGINT REFERENCES conversation(id) ON DELETE CASCADE,
    resume TEXT NOT NULL,
    dossier_ids BIGINT[] NOT NULL DEFAULT '{}',
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Permissions globales ---------------------------------------------------------------------------------------

INSERT INTO permission (code, libelle) VALUES
    ('dossier.gerer', 'Créer, renommer, archiver, supprimer les dossiers et gérer leurs membres et rôles')
ON CONFLICT (code) DO UPDATE SET libelle = EXCLUDED.libelle;

INSERT INTO role_permission (role_id, permission_id)
SELECT r.id, p.id FROM _role r JOIN permission p ON p.code = 'dossier.gerer'
WHERE r.code = 'ADMIN'
ON CONFLICT DO NOTHING;

-- Les droits sur les fichiers d'un UTILISATEUR viennent de ses rôles de dossier, plus de son rôle global.
DELETE FROM role_permission
WHERE role_id = (SELECT id FROM _role WHERE code = 'UTILISATEUR')
  AND permission_id IN (SELECT id FROM permission WHERE code IN ('document.creer', 'document.modifier', 'document.supprimer'));

UPDATE _role SET libelle = 'Utilisateur (accès par dossiers)' WHERE code = 'UTILISATEUR';

-- 5. Migration des données existantes (une seule fois) ---------------------------------------------------------

DO $migration$
DECLARE
    srv RECORD;
    new_dossier BIGINT;
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'rag_sys' AND table_name = 'document' AND column_name = 'service_id'
    ) THEN
        RAISE NOTICE 'Migration des données déjà faite : rien à changer.';
        RETURN;
    END IF;

    -- sauvegarde de l'ancien rattachement (retour arrière)
    CREATE TABLE IF NOT EXISTS migration_05_document_service AS
        SELECT id AS document_id, service_id FROM document;

    ALTER TABLE document ADD COLUMN IF NOT EXISTS dossier_id BIGINT REFERENCES dossier(id);
    ALTER TABLE document ADD COLUMN IF NOT EXISTS has_image BOOLEAN NOT NULL DEFAULT FALSE;

    -- un dossier par service, ouvert à ce service (même pouvoir qu'avant : ajouter, modifier, supprimer)
    FOR srv IN SELECT id, code, nom FROM _service ORDER BY id LOOP
        INSERT INTO dossier (nom, description)
        VALUES (left(srv.nom, 120) || ' (' || srv.code || ')', 'Dossier créé par la migration 05 pour le service ' || srv.code)
        RETURNING id INTO new_dossier;
        INSERT INTO dossier_service (dossier_id, service_id, role)
        VALUES (new_dossier, srv.id, 'GESTIONNAIRE_DE_CONTENU');
        UPDATE document SET dossier_id = new_dossier WHERE service_id = srv.id;
    END LOOP;

    -- version 1 de chaque document : les informations du fichier quittent document
    INSERT INTO document_version (
        document_id, numero, nom_fichier, type_mime, taille_octets, hash_sha256, chemin_stockage,
        nb_pages, ocr_utilise, statut, message_erreur, cree_par, cree_le
    )
    SELECT id, 1, nom_fichier, type_mime, taille_octets, hash_sha256, chemin_stockage,
           nb_pages, ocr_utilise, statut, message_erreur, cree_par, cree_le
    FROM document;

    -- chunks rattachés à la version 1 ; taille_ref = nombre de chunks de la version (sert au top-k dynamique)
    ALTER TABLE chunk ADD COLUMN IF NOT EXISTS document_version_id BIGINT REFERENCES document_version(id) ON DELETE CASCADE;
    ALTER TABLE chunk ADD COLUMN IF NOT EXISTS taille_ref INTEGER NOT NULL DEFAULT 0 CHECK (taille_ref >= 0);
    UPDATE chunk c SET document_version_id = v.id FROM document_version v WHERE v.document_id = c.document_id AND v.numero = 1;
    UPDATE chunk c SET taille_ref = t.n FROM (
        SELECT document_version_id, COUNT(*) AS n FROM chunk GROUP BY document_version_id
    ) t WHERE t.document_version_id = c.document_version_id;
    ALTER TABLE chunk ALTER COLUMN document_version_id SET NOT NULL;
    ALTER TABLE chunk DROP CONSTRAINT IF EXISTS uq_chunk_document_index;
    ALTER TABLE chunk ADD CONSTRAINT uq_chunk_version_index UNIQUE (document_version_id, chunk_index);

    ALTER TABLE document ALTER COLUMN dossier_id SET NOT NULL;

    -- la suppression de service_id retire aussi uq_document_service_hash ; celle de statut retire idx_document_statut
    ALTER TABLE document
        DROP COLUMN service_id,
        DROP COLUMN nom_fichier,
        DROP COLUMN type_mime,
        DROP COLUMN taille_octets,
        DROP COLUMN hash_sha256,
        DROP COLUMN chemin_stockage,
        DROP COLUMN nb_pages,
        DROP COLUMN ocr_utilise,
        DROP COLUMN statut,
        DROP COLUMN message_erreur;
END
$migration$;

-- 6. Index ------------------------------------------------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_document_dossier ON document (dossier_id);
CREATE INDEX IF NOT EXISTS idx_version_document ON document_version (document_id, numero DESC);
CREATE INDEX IF NOT EXISTS idx_version_statut ON document_version (statut);
CREATE INDEX IF NOT EXISTS idx_version_hash ON document_version (hash_sha256);
CREATE INDEX IF NOT EXISTS idx_chunk_version ON chunk (document_version_id);
CREATE INDEX IF NOT EXISTS idx_chunk_document ON chunk (document_id);
CREATE INDEX IF NOT EXISTS idx_dossier_membre_user ON dossier_membre (user_id);
CREATE INDEX IF NOT EXISTS idx_dossier_service_service ON dossier_service (service_id);
CREATE INDEX IF NOT EXISTS idx_memoire_user_date ON memoire_chat (user_id, cree_le DESC);

COMMIT;
