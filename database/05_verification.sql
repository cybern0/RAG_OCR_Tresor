-- Contrôles à lancer après 05_dossiers_versions.sql :
--   psql -U postgres -d rag -f database/05_verification.sql
-- Chaque ligne affiche un contrôle et son résultat ; la colonne « attendu » dit quoi viser.

SET search_path TO rag_sys, public;

SELECT 'documents sans dossier' AS controle, COUNT(*) AS resultat, '0' AS attendu FROM document WHERE dossier_id IS NULL
UNION ALL
SELECT 'documents sans aucune version', COUNT(*), '0' FROM document d
    WHERE NOT EXISTS (SELECT 1 FROM document_version v WHERE v.document_id = d.id)
UNION ALL
SELECT 'chunks sans version', COUNT(*), '0' FROM chunk WHERE document_version_id IS NULL
UNION ALL
SELECT 'chunks dont document_id differe de celui de leur version', COUNT(*), '0' FROM chunk c
    JOIN document_version v ON v.id = c.document_version_id WHERE v.document_id <> c.document_id
UNION ALL
SELECT 'chunks dont taille_ref differe du nombre de chunks de la version', COUNT(*), '0' FROM chunk c
    JOIN (SELECT document_version_id, COUNT(*) AS n FROM chunk GROUP BY 1) t ON t.document_version_id = c.document_version_id
    WHERE t.n <> c.taille_ref
UNION ALL
SELECT 'versions « ready » sans chunk', COUNT(*), '0' FROM document_version v
    WHERE v.statut = 'ready' AND NOT EXISTS (SELECT 1 FROM chunk c WHERE c.document_version_id = v.id)
UNION ALL
SELECT 'vecteurs non normalisés', COUNT(*), '0' FROM chunk WHERE vector_norm(embedding) NOT BETWEEN 0.999 AND 1.001
UNION ALL
SELECT 'dossiers', COUNT(*), 'au moins 1 (un par service, après migration)' FROM dossier
UNION ALL
SELECT 'services sans dossier ouvert', COUNT(*), '0 juste après la migration' FROM _service s
    WHERE NOT EXISTS (SELECT 1 FROM dossier_service ds WHERE ds.service_id = s.id)
UNION ALL
SELECT 'permission dossier.gerer donnée à ADMIN', COUNT(*), '1' FROM role_permission rp
    JOIN _role r ON r.id = rp.role_id JOIN permission p ON p.id = rp.permission_id
    WHERE r.code = 'ADMIN' AND p.code = 'dossier.gerer'
UNION ALL
SELECT 'UTILISATEUR avec document.creer|modifier|supprimer', COUNT(*), '0' FROM role_permission rp
    JOIN _role r ON r.id = rp.role_id JOIN permission p ON p.id = rp.permission_id
    WHERE r.code = 'UTILISATEUR' AND p.code IN ('document.creer', 'document.modifier', 'document.supprimer');

-- Aperçu : documents par dossier et nombre de versions
SELECT d.id AS dossier_id, d.nom, COUNT(DISTINCT doc.id) AS documents, COUNT(v.id) AS versions
FROM dossier d
LEFT JOIN document doc ON doc.dossier_id = d.id
LEFT JOIN document_version v ON v.document_id = doc.id
GROUP BY d.id, d.nom ORDER BY d.id;
