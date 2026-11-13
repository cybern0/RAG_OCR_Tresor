-- Retour arrière de 05_dossiers_versions.sql : revient au schéma de 01 à 04 (documents rattachés à un service).
--
-- Commande :  psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/05_retour_arriere.sql
-- Tout ou rien : à la première erreur, rien n'est modifié.
--
-- ATTENTION, ce que le retour arrière PERD :
--   - les dossiers, les membres, les rôles de dossier, les préférences et la mémoire du chat ;
--   - l'historique des versions : seule la version la plus récente de chaque document est conservée (avec ses chunks) ;
--     les fichiers des anciennes versions restent sur le disque (orphelins, à supprimer à la main si besoin).
-- Le service d'un document est retrouvé dans migration_05_document_service (documents d'avant la migration) ;
-- pour un document créé depuis, on prend un service ayant accès à son dossier, à défaut le premier service.
-- Si deux documents d'un même service ont le même hash, l'ajout de uq_document_service_hash échoue et la
-- transaction est annulée : supprimer l'un des deux doublons puis relancer.
-- Les documents ne portent plus que le texte d'une version : exécuter ce script avec l'API arrêtée.

SET search_path TO rag_sys, public;

BEGIN;

DO $retour$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables WHERE table_schema = 'rag_sys' AND table_name = 'document_version'
    ) THEN
        RAISE NOTICE 'Rien à défaire : 05 n''est pas appliqué.';
        RETURN;
    END IF;

    -- 1. colonnes de document
    ALTER TABLE document
        ADD COLUMN service_id BIGINT REFERENCES _service(id),
        ADD COLUMN nom_fichier VARCHAR(255),
        ADD COLUMN type_mime VARCHAR(120),
        ADD COLUMN taille_octets BIGINT CHECK (taille_octets >= 0),
        ADD COLUMN hash_sha256 CHAR(64),
        ADD COLUMN chemin_stockage TEXT,
        ADD COLUMN nb_pages INTEGER CHECK (nb_pages >= 0),
        ADD COLUMN ocr_utilise BOOLEAN NOT NULL DEFAULT FALSE,
        ADD COLUMN statut VARCHAR(20) NOT NULL DEFAULT 'pending'
            CHECK (statut IN ('pending', 'processing', 'ready', 'error')),
        ADD COLUMN message_erreur TEXT;

    -- 2. on ne garde que la version la plus récente de chaque document
    UPDATE document d SET
        nom_fichier = v.nom_fichier, type_mime = v.type_mime, taille_octets = v.taille_octets,
        hash_sha256 = v.hash_sha256, chemin_stockage = v.chemin_stockage, nb_pages = v.nb_pages,
        ocr_utilise = v.ocr_utilise, statut = v.statut, message_erreur = v.message_erreur
    FROM document_version v
    WHERE v.document_id = d.id
      AND v.numero = (SELECT MAX(numero) FROM document_version WHERE document_id = d.id);

    DELETE FROM document_version v
    WHERE v.numero < (SELECT MAX(numero) FROM document_version WHERE document_id = v.document_id);  -- supprime leurs chunks (cascade)

    -- 3. service de chaque document
    UPDATE document d SET service_id = COALESCE(
        (SELECT b.service_id FROM migration_05_document_service b WHERE b.document_id = d.id),
        (SELECT MIN(ds.service_id) FROM dossier_service ds WHERE ds.dossier_id = d.dossier_id),
        (SELECT MIN(id) FROM _service)
    );

    -- 4. chunks
    ALTER TABLE chunk DROP CONSTRAINT IF EXISTS uq_chunk_version_index;
    ALTER TABLE chunk DROP COLUMN document_version_id, DROP COLUMN taille_ref;
    ALTER TABLE chunk ADD CONSTRAINT uq_chunk_document_index UNIQUE (document_id, chunk_index);

    -- 5. contraintes de document
    ALTER TABLE document
        ALTER COLUMN service_id SET NOT NULL,
        ALTER COLUMN nom_fichier SET NOT NULL,
        ALTER COLUMN hash_sha256 SET NOT NULL,
        ALTER COLUMN chemin_stockage SET NOT NULL;
    ALTER TABLE document ADD CONSTRAINT uq_document_service_hash UNIQUE (service_id, hash_sha256);
    CREATE INDEX IF NOT EXISTS idx_document_statut ON document (statut);
    ALTER TABLE document DROP COLUMN dossier_id, DROP COLUMN has_image;

    -- 6. nouvelles tables
    DROP TABLE document_version;
    DROP TABLE memoire_chat;
    DROP TABLE preference_utilisateur;
    DROP TABLE dossier_service;
    DROP TABLE dossier_membre;
    DROP TABLE dossier;
    DROP TABLE IF EXISTS migration_05_document_service;

    -- 7. permissions : retour à l'état de 04
    DELETE FROM permission WHERE code = 'dossier.gerer';  -- role_permission part en cascade
    INSERT INTO role_permission (role_id, permission_id)
    SELECT r.id, p.id FROM _role r JOIN permission p
        ON p.code IN ('document.creer', 'document.modifier', 'document.supprimer')
    WHERE r.code = 'UTILISATEUR'
    ON CONFLICT DO NOTHING;
    UPDATE _role SET libelle = 'Utilisateur de son service' WHERE code = 'UTILISATEUR';
END
$retour$;

COMMIT;
