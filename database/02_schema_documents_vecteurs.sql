-- 2/4 - Tables document et chunk (pgvector). Dépend de 01 (schéma rag_sys). Les tables sont encore vides : à définir.
-- À prévoir : document (service, auteur vers _user, hash du fichier, statut d'ingestion, drapeau tableaux) ;
-- chunk (document_id, page, contenu, embedding : dimension du modèle choisi, 768 attendu pour EmbeddingGemma, à vérifier).

SET search_path TO rag_sys, public;
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE document();
CREATE TABLE chunk();