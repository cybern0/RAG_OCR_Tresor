-- 04 - MIGRATION : de l'ancien modèle « classes par rôle » (table document_role) au nouveau modèle
-- « affectation manuelle des fichiers aux agents » (table document_affectation), introduit en 11/2026
-- (voir MODIFICATIONS.md). Le chef de division ou de service affecte désormais chaque fichier à un ou
-- plusieurs agents de SA division ; l'agent affecté lit le fichier, sans affectation l'accès se demande.
--
-- À exécuter UNE fois sur une base créée avec l'ANCIEN 01_schema.sql (celui qui contient encore
-- document_role), avec le NOUVEAU code de l'application arrêté :
--   psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/04_migration_affectation.sql
--
-- Tout ou rien (une seule transaction, arrêt à la première erreur) et RÉEXÉCUTABLE sans dommage :
-- la conversion n'a lieu que si document_role existe encore ; les doublons (agent déjà affecté) sont ignorés.
-- La règle « agents de la division du fichier » est garantie par la BASE : clés composites
-- document(id, division_id) et agent(id, division_id) — un agent d'une autre division est impossible.
-- Règle de conversion : un fichier classé « rôle R » est affecté aux agents qui portent R via leur compte
-- (user_role_division -> _user.agent_id) dans la division du fichier. Les comptes SANS agent (impossibles
-- pour un rôle dans une base saine : invariant role_utilisateur_hors_de_sa_division) sont écartés et signalés.
-- En fin de script, la vue de contrôle verification_invariants est recréée avec la DÉFINITION DU NOUVEAU
-- 03_verification.sql (relancer 03 ensuite reste sans risque : CREATE OR REPLACE).
-- Aucune action sur l'historique : il est en ajout seul et chaîné par hash (déclencheur), on ne le réécrit pas.
--
-- Après la migration : démarrer le backend avec le NOUVEAU code (l'ancien code ne connaît pas document_affectation).

BEGIN;
SET search_path TO rag_sys, public;

-- 1. Cible de la clé étrangère composite (agent_id, division_id) : UNIQUE (id, division_id) sur agent
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint
                   WHERE conname = 'uq_agent_id_division' AND conrelid = 'rag_sys.agent'::regclass) THEN
        ALTER TABLE agent ADD CONSTRAINT uq_agent_id_division UNIQUE (id, division_id);
    END IF;
END $$;

-- 2. La table des affectations (définition identique au NOUVEAU 01_schema.sql)
CREATE TABLE IF NOT EXISTS document_affectation (
    document_id BIGINT NOT NULL,
    agent_id BIGINT NOT NULL,
    division_id BIGINT NOT NULL,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    cree_par_user_id BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    PRIMARY KEY (document_id, agent_id),
    CONSTRAINT fk_document_affectation_document FOREIGN KEY (document_id, division_id)
        REFERENCES document (id, division_id) ON DELETE CASCADE,
    CONSTRAINT fk_document_affectation_agent FOREIGN KEY (agent_id, division_id)
        REFERENCES agent (id, division_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_document_affectation_agent ON document_affectation (agent_id);

-- 3. Conversion des classes en affectations, puis suppression de document_role
DO $$
DECLARE
    nb_crees    integer;
    nb_ecartes  integer;
    nb_classes  integer;
BEGIN
    IF to_regclass('document_role') IS NULL THEN
        RAISE NOTICE 'Table document_role absente : base déjà migrée ou déjà au nouveau format — rien à convertir.';
        RETURN;
    END IF;

    -- l'ancienne vue des invariants référence document_role : elle est recréée plus bas (définition du nouveau 03)
    DROP VIEW IF EXISTS verification_invariants;

    SELECT count(*) INTO nb_classes FROM document_role;

    INSERT INTO document_affectation (document_id, agent_id, division_id)
    SELECT DISTINCT dr.document_id, u.agent_id, d.division_id
    FROM document_role dr
    JOIN document d ON d.id = dr.document_id
    JOIN user_role_division urd ON urd.role_division_id = dr.role_division_id
    JOIN _user u ON u.id = urd.user_id
    JOIN agent a ON a.id = u.agent_id
    WHERE u.agent_id IS NOT NULL
      AND a.division_id = d.division_id          -- l'agent porte le rôle dans la division du fichier
    ON CONFLICT (document_id, agent_id) DO NOTHING;
    GET DIAGNOSTICS nb_crees = ROW_COUNT;

    -- liens non convertibles, pour information : compte sans agent, ou agent d'une autre division
    SELECT count(*) INTO nb_ecartes
    FROM document_role dr
    JOIN user_role_division urd ON urd.role_division_id = dr.role_division_id
    JOIN _user u ON u.id = urd.user_id
    LEFT JOIN agent a ON a.id = u.agent_id
    WHERE u.agent_id IS NULL OR a.division_id IS DISTINCT FROM dr.division_id;
    IF nb_ecartes > 0 THEN
        RAISE WARNING '% lien(s) classe-compte non convertible(s) (compte sans agent ou agent hors de la division du fichier) : ces agents ne sont pas affectés — utilisez « Affecter » dans l''interface.', nb_ecartes;
    END IF;

    DROP TABLE document_role;

    -- ancien événement de notification renommé (l'historique, lui, n'est pas réécrit)
    UPDATE notification SET type_evenement = 'fichier_a_affecter' WHERE type_evenement = 'fichier_a_classer';

    RAISE NOTICE '% classe(s) de fichier traitée(s) : % affectation(s) agent créée(s), % lien(s) écarté(s).', nb_classes, nb_crees, nb_ecartes;
    RAISE NOTICE 'Table document_role supprimée ; événement fichier_a_classer renommé fichier_a_affecter.';
END $$;

-- 4. Vue de contrôle, définition IDENTIQUE au NOUVEAU 03_verification.sql (le relancer ensuite reste sans risque)
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
SELECT 'affectation_hors_de_la_division_du_fichier', count(*)
FROM document_affectation da JOIN document d ON d.id = da.document_id WHERE da.division_id <> d.division_id
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

COMMIT;

-- Contrôle final (à lancer après la migration) : chaque contrôle doit valoir 0, sauf
-- fichiers_a_affecter (avertissement : fichiers migrés sans affectation, l'accès se demande désormais).
-- SELECT * FROM verification_invariants ORDER BY anomalies DESC, controle;
