-- 08 - Collaboration locale : commentaires, notifications et favoris.
-- À exécuter après 07, sur une base neuve ou déjà remplie.
-- Commande : psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/08_collaboration.sql

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

CREATE TABLE IF NOT EXISTS notification_interne (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    type_notification VARCHAR(25) NOT NULL DEFAULT 'info' CHECK (type_notification IN ('info', 'share', 'access_request', 'comment')),
    sujet_type VARCHAR(20) NOT NULL CHECK (sujet_type IN ('document', 'dossier')),
    sujet_id BIGINT NOT NULL,
    message TEXT NOT NULL,
    lu BOOLEAN NOT NULL DEFAULT FALSE,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_notification_user ON notification_interne (user_id, lu, cree_le DESC);

CREATE TABLE IF NOT EXISTS favori (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    sujet_type VARCHAR(20) NOT NULL CHECK (sujet_type IN ('document', 'dossier')),
    sujet_id BIGINT NOT NULL,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, sujet_type, sujet_id)
);

CREATE INDEX IF NOT EXISTS idx_favori_user ON favori (user_id, sujet_type);

COMMIT;
