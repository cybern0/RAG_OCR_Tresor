-- 08 - Commentaires sur les fichiers.
-- À exécuter après 06, sur une base neuve ou déjà remplie.
-- Commande : psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/08_commentaires.sql

SET search_path TO rag_sys, public;

BEGIN;

CREATE TABLE IF NOT EXISTS commentaire (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sujet_type VARCHAR(20) NOT NULL CHECK (sujet_type IN ('document', 'dossier')),
    sujet_id BIGINT NOT NULL,
    auteur_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    contenu TEXT NOT NULL,
    parent_id BIGINT REFERENCES commentaire(id) ON DELETE CASCADE,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_commentaire_sujet ON commentaire (sujet_type, sujet_id);
CREATE INDEX IF NOT EXISTS idx_commentaire_parent ON commentaire (parent_id);

COMMIT;
