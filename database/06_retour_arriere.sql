-- Retour arrière de la migration 06 : supprime les objets liés au classement.
SET search_path TO rag_sys, public;

BEGIN;

DROP VIEW IF EXISTS vue_document_stats;
DROP TABLE IF EXISTS document_tag;
DROP TABLE IF EXISTS regle_classement;
DROP TABLE IF EXISTS tag;
DROP TABLE IF EXISTS type_document;
DROP TABLE IF EXISTS categorie;

ALTER TABLE document
    DROP COLUMN IF EXISTS categorie_id,
    DROP COLUMN IF EXISTS type_document_id,
    DROP COLUMN IF EXISTS confidentialite,
    DROP COLUMN IF EXISTS classement_source,
    DROP COLUMN IF EXISTS regle_id,
    DROP COLUMN IF EXISTS cree_par_service_id,
    DROP COLUMN IF EXISTS corbeille_le;

DELETE FROM role_permission
WHERE permission_id IN (
    SELECT id FROM permission WHERE code IN ('classement.gerer', 'statistiques.globales')
);

DELETE FROM permission WHERE code IN ('classement.gerer', 'statistiques.globales');

COMMIT;
