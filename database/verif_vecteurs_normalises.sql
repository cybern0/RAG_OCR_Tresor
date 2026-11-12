-- Vérification facultative : aucun embedding ne doit être non normalisé (norme L2 = 1, tolérance 0,1 %).
-- Résultat attendu : non_normalises = 0. Une valeur > 0 est impossible tant que la contrainte
-- ck_chunk_embedding_normalise existe ; ce contrôle sert à s'en assurer après une restauration ou un import.
--   psql -U postgres -d rag -f database/verif_vecteurs_normalises.sql

SET search_path TO rag_sys, public;

SELECT count(*)                                                          AS total,
       count(*) FILTER (WHERE abs(vector_norm(embedding) - 1) > 0.001)  AS non_normalises,
       min(vector_norm(embedding))                                       AS norme_min,
       max(vector_norm(embedding))                                       AS norme_max
FROM chunk;
