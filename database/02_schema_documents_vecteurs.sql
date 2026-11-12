-- 2/4 - Tables document et chunk (pgvector). Dépend de 01 (schéma rag_sys).
-- document : un fichier déposé, rattaché à un service, avec son statut d'ingestion.
-- chunk : un extrait de document, avec son embedding et son texte indexé pour la recherche plein texte.
-- La dimension de l'embedding (768) correspond à EmbeddingGemma : à vérifier, et à changer ici si le modèle change.
-- Les embeddings sont TOUJOURS normalisés (norme L2 = 1) : le backend les normalise avant écriture et la contrainte
-- ck_chunk_embedding_normalise refuse tout vecteur qui ne l'est pas. La recherche utilise le produit scalaire
-- (opérateur <#>, index vector_ip_ops), qui n'est équivalent au cosinus que si les vecteurs sont normalisés.

SET search_path TO rag_sys, public;
CREATE EXTENSION IF NOT EXISTS vector SCHEMA public;

-- Met à jour modifie_le à chaque UPDATE
CREATE OR REPLACE FUNCTION maj_modifie_le() RETURNS trigger AS $$
BEGIN
    NEW.modifie_le := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE IF NOT EXISTS document (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    service_id BIGINT NOT NULL REFERENCES _service(id),
    titre VARCHAR(250) NOT NULL,
    nom_fichier VARCHAR(255) NOT NULL,
    type_mime VARCHAR(120),
    taille_octets BIGINT CHECK (taille_octets >= 0),
    hash_sha256 CHAR(64) NOT NULL,
    chemin_stockage TEXT NOT NULL,
    nb_pages INTEGER CHECK (nb_pages >= 0),
    ocr_utilise BOOLEAN NOT NULL DEFAULT FALSE,
    has_tabular BOOLEAN NOT NULL DEFAULT FALSE,
    statut VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (statut IN ('pending', 'processing', 'ready', 'error')),
    message_erreur TEXT,
    cree_par BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    modifie_par BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    modifie_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_document_service_hash UNIQUE (service_id, hash_sha256)
);

DROP TRIGGER IF EXISTS trg_document_modifie_le ON document;
CREATE TRIGGER trg_document_modifie_le
    BEFORE UPDATE ON document
    FOR EACH ROW EXECUTE FUNCTION maj_modifie_le();

CREATE TABLE IF NOT EXISTS chunk (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
    page INTEGER CHECK (page >= 1),
    contenu TEXT NOT NULL,
    est_tableau BOOLEAN NOT NULL DEFAULT FALSE,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(768) NOT NULL,
    contenu_tsv tsvector GENERATED ALWAYS AS (to_tsvector('french', contenu)) STORED,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_chunk_document_index UNIQUE (document_id, chunk_index),
    -- tolérance de 0,1 % : les vecteurs sont stockés en float32
    CONSTRAINT ck_chunk_embedding_normalise CHECK (vector_norm(embedding) BETWEEN 0.999 AND 1.001)
);
