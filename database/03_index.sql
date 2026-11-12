-- 3/4 - Index : clés étrangères, recherche plein texte (config french) et recherche vectorielle (HNSW, produit scalaire).
-- Les contraintes UNIQUE de 01 et 02 créent déjà leurs propres index (code, matricule, hash du fichier, document + chunk_index).
-- L'index vectoriel utilise vector_ip_ops : il sert les requêtes ORDER BY embedding <#> :vecteur (produit scalaire négatif),
-- exactes pour le classement parce que les embeddings sont normalisés (voir 02). Ne pas mélanger avec <=> ou <->.
-- Sur un petit volume, l'index HNSW n'est pas indispensable : le supprimer si la construction pose problème.

SET search_path TO rag_sys, public;

-- Organisation et comptes
CREATE INDEX IF NOT EXISTS idx_service_direction ON _service (direction_id);
CREATE INDEX IF NOT EXISTS idx_agent_service ON agent (service_id);
-- Un agent ne peut avoir qu'un seul compte utilisateur.
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_agent ON _user (agent_id) WHERE agent_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_user_role ON _user (role_id);

-- Documents
CREATE INDEX IF NOT EXISTS idx_document_statut ON document (statut);
CREATE INDEX IF NOT EXISTS idx_document_cree_par ON document (cree_par);
CREATE INDEX IF NOT EXISTS idx_document_cree_le ON document (cree_le DESC);

-- Chunks : plein texte, métadonnées, vecteurs
CREATE INDEX IF NOT EXISTS idx_chunk_tsv ON chunk USING gin (contenu_tsv);
CREATE INDEX IF NOT EXISTS idx_chunk_metadata ON chunk USING gin (metadata jsonb_path_ops);
CREATE INDEX IF NOT EXISTS idx_chunk_embedding ON chunk USING hnsw (embedding vector_ip_ops);

-- Audit et chat
CREATE INDEX IF NOT EXISTS idx_audit_user_date ON journal_audit (user_id, cree_le DESC);
CREATE INDEX IF NOT EXISTS idx_audit_entite ON journal_audit (entite, entite_id);
CREATE INDEX IF NOT EXISTS idx_conversation_user_date ON conversation (user_id, cree_le DESC);
CREATE INDEX IF NOT EXISTS idx_message_conversation ON message (conversation_id, cree_le);
