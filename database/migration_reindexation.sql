-- Migration : réindexation d'une version sans nouveau dépôt.
-- Pour les bases EXISTANTES seulement (une base neuve créée avec 01_schema.sql a déjà ces colonnes).
-- Idempotente : peut être rejouée sans effet.
--
-- tableaux_indexes / images_indexes : paramètres utilisés lors de la dernière indexation réussie de la version.
-- NULL = inconnu (version indexée avant cette migration, ou jamais indexée) : l'application se rabat alors sur
-- les cases actuelles du fichier (document.has_tabular / document.has_image).

BEGIN;
SET search_path TO rag_sys, public;
ALTER TABLE document_version ADD COLUMN IF NOT EXISTS tableaux_indexes BOOLEAN;
ALTER TABLE document_version ADD COLUMN IF NOT EXISTS images_indexes BOOLEAN;
COMMIT;
