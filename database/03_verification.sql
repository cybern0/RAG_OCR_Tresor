-- 03 - Contrôle des invariants de la GED hiérarchique. À lancer juste après 02 sur la base vierge (tout doit valoir 0),
-- puis après un import, une restauration, ou à tout moment :
--   psql -U postgres -d rag -f database/03_verification.sql
-- Chaque ligne de verification_invariants doit valoir 0 (anomalies). Les avertissements sont des recommandations, pas des erreurs.

SET search_path TO rag_sys, public;

CREATE OR REPLACE VIEW verification_invariants AS
SELECT 'chef_division_unique' AS controle, count(*) AS anomalies FROM (
    SELECT division_id FROM agent WHERE titre = 'CHEF_DIVISION' AND actif GROUP BY division_id HAVING count(*) > 1) t
UNION ALL
SELECT 'agent_division_du_meme_service', count(*)
FROM agent a JOIN division d ON d.id = a.division_id WHERE d.service_id <> a.service_id
UNION ALL
SELECT 'agent_titre_inconnu', count(*) FROM agent WHERE titre IS NOT NULL AND titre NOT IN ('CHEF_DIVISION', 'CHEF_SERVICE')
UNION ALL
SELECT 'chef_service_unique', count(*) FROM (
    SELECT service_id FROM agent WHERE titre = 'CHEF_SERVICE' AND actif GROUP BY service_id HAVING count(*) > 1) t
UNION ALL
SELECT 'chef_service_avec_division', count(*) FROM agent WHERE titre = 'CHEF_SERVICE' AND division_id IS NOT NULL
UNION ALL
SELECT 'compte_utilisateur_sans_agent', count(*)
FROM _user u JOIN _role r ON r.id = u.role_id WHERE r.code = 'UTILISATEUR' AND u.agent_id IS NULL
UNION ALL
SELECT 'role_utilisateur_hors_de_sa_division', count(*)
FROM user_role_division urd
JOIN role_division rd ON rd.id = urd.role_division_id
JOIN _user u ON u.id = urd.user_id
LEFT JOIN agent a ON a.id = u.agent_id
WHERE a.division_id IS DISTINCT FROM rd.division_id
UNION ALL
SELECT 'role_de_fichier_hors_de_la_division_du_fichier', count(*)
FROM document_role dr JOIN document d ON d.id = dr.document_id WHERE dr.division_id <> d.division_id
UNION ALL
SELECT 'historique_chaine_alteree', CASE WHEN (SELECT ok FROM verifier_historique()) THEN 0 ELSE 1 END
UNION ALL
SELECT 'vecteurs_non_normalises', count(*) FROM chunk WHERE abs(vector_norm(embedding) - 1) > 0.001
UNION ALL
-- conformité du schéma (base créée par 01_schema.sql) : colonnes de réindexation présentes
SELECT 'schema_colonnes_attendues_manquantes', count(*)
FROM (VALUES ('document_version', 'tableaux_indexes'), ('document_version', 'images_indexes')) AS v(t, c)
WHERE NOT EXISTS (
    SELECT 1 FROM information_schema.columns i WHERE i.table_schema = 'rag_sys' AND i.table_name = v.t AND i.column_name = v.c)
UNION ALL
-- conformité du schéma : plus aucun reste du concept de dossier
SELECT 'schema_reste_de_dossiers',
       (SELECT count(*) FROM information_schema.tables WHERE table_schema = 'rag_sys' AND table_name = 'dossier')
     + (SELECT count(*) FROM information_schema.columns WHERE table_schema = 'rag_sys' AND table_name = 'document' AND column_name = 'dossier_id');

SELECT * FROM verification_invariants ORDER BY anomalies DESC, controle;

-- Avertissements (recommandations)
SELECT 'moins_de_2_super_admins_actifs' AS avertissement,
       (SELECT count(*) FROM _user u JOIN _role r ON r.id = u.role_id WHERE r.code = 'ADMIN' AND u.actif) AS valeur
UNION ALL
SELECT 'divisions_actives_sans_chef', count(*) FROM division d
WHERE d.actif AND NOT EXISTS (SELECT 1 FROM agent a WHERE a.division_id = d.id AND a.titre = 'CHEF_DIVISION' AND a.actif)
UNION ALL
SELECT 'fichiers_a_classer', count(*) FROM document d
WHERE d.corbeille_le IS NULL AND NOT EXISTS (SELECT 1 FROM document_role r WHERE r.document_id = d.id);
