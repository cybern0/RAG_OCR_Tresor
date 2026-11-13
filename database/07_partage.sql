-- 07 - Partage local des documents : accès direct, liens anonymes/internes et demandes d'accès.
-- À exécuter après 06, sur une base neuve ou déjà remplie.
-- Commande : psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/07_partage.sql

SET search_path TO rag_sys, public;

BEGIN;

CREATE TABLE IF NOT EXISTS document_partage (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    user_id BIGINT REFERENCES _user(id) ON DELETE CASCADE,
    service_id BIGINT REFERENCES _service(id) ON DELETE CASCADE,
    role VARCHAR(15) NOT NULL CHECK (role IN ('LECTEUR', 'CONTRIBUTEUR', 'GESTIONNAIRE_DE_CONTENU')),
    expire_le TIMESTAMPTZ,
    cree_par BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_document_partage_cible CHECK (user_id IS NOT NULL OR service_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_document_partage_document ON document_partage (document_id);
CREATE INDEX IF NOT EXISTS idx_document_partage_user ON document_partage (user_id);
CREATE INDEX IF NOT EXISTS idx_document_partage_service ON document_partage (service_id);

CREATE TABLE IF NOT EXISTS document_lien_partage (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    token_hash VARCHAR(128) NOT NULL UNIQUE,
    role VARCHAR(30) NOT NULL DEFAULT 'LECTEUR' CHECK (role IN ('LECTEUR', 'CONTRIBUTEUR', 'GESTIONNAIRE_DE_CONTENU')),
    est_anonyme BOOLEAN NOT NULL DEFAULT TRUE,
    expire_le TIMESTAMPTZ,
    cree_par BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_document_lien_document ON document_lien_partage (document_id);
CREATE INDEX IF NOT EXISTS idx_document_lien_expire ON document_lien_partage (expire_le);

CREATE TABLE IF NOT EXISTS demande_acces (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sujet_type VARCHAR(20) NOT NULL CHECK (sujet_type IN ('document', 'dossier')),
    sujet_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    role_demande VARCHAR(30) NOT NULL DEFAULT 'LECTEUR' CHECK (role_demande IN ('LECTEUR', 'CONTRIBUTEUR', 'GESTIONNAIRE_DE_CONTENU')),
    message TEXT,
    statut VARCHAR(15) NOT NULL DEFAULT 'pending' CHECK (statut IN ('pending', 'approved', 'rejected')),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_demande_acces_user ON demande_acces (user_id);
CREATE INDEX IF NOT EXISTS idx_demande_acces_sujet ON demande_acces (sujet_type, sujet_id);

COMMIT;
