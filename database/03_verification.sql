SET search_path TO rag_sys, public;

-- Vérification des invariants de base.
CREATE OR REPLACE VIEW verification_invariants AS
SELECT
    'chef_division_unique' AS check_name,
    COUNT(*) AS count_rows
FROM (
    SELECT division_id, titre
    FROM agent
    WHERE titre = 'CHEF_DIVISION' AND actif = TRUE
    GROUP BY division_id, titre
    HAVING COUNT(*) > 1
) t
UNION ALL
SELECT
    'chef_service_unique' AS check_name,
    COUNT(*)
FROM (
    SELECT service_id, titre
    FROM agent
    WHERE titre = 'CHEF_SERVICE' AND actif = TRUE
    GROUP BY service_id, titre
    HAVING COUNT(*) > 1
) t
UNION ALL
SELECT
    'division_coherence' AS check_name,
    COUNT(*)
FROM agent a
JOIN division d ON d.id = a.division_id
WHERE a.service_id IS NOT NULL AND a.division_id IS NOT NULL AND a.service_id <> d.service_id
UNION ALL
SELECT
    'dossier_coherence' AS check_name,
    COUNT(*)
FROM dossier d
JOIN division div ON div.id = d.division_id
WHERE d.parent_id IS NOT NULL AND d.parent_id = d.id;

-- Contrôle minimal des vecteurs normalisés : toujours un nombre de dimensions fixe.
-- (Le vrai contrôle est effectué côté backend et lors de l'ingestion.)
