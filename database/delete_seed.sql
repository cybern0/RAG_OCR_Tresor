-- delete_seed - Supprime TOUTES les données de démonstration (préfixe DEMO / demo_).
-- historique_modification n'est pas touché (registre immuable, sans clé étrangère).
--   psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/delete_seed.sql
BEGIN;
SET search_path TO rag_sys, public;
CREATE TEMP TABLE _d_div ON COMMIT DROP AS SELECT id FROM division WHERE code LIKE 'DEMO-%';
CREATE TEMP TABLE _d_user ON COMMIT DROP AS
    SELECT id FROM _user WHERE nom_utilisateur LIKE 'demo\_%'
    UNION SELECT u.id FROM _user u JOIN agent a ON a.id = u.agent_id WHERE a.matricule LIKE 'DEMO-%';
DELETE FROM document WHERE division_id IN (SELECT id FROM _d_div);   -- versions, passages, rôles, étiquettes en cascade
DELETE FROM commentaire WHERE auteur_id IN (SELECT id FROM _d_user);
DELETE FROM dossier WHERE division_id IN (SELECT id FROM _d_div);    -- une seule instruction : parents et enfants ensemble
DELETE FROM demande_acces WHERE division_id IN (SELECT id FROM _d_div) OR demandeur_user_id IN (SELECT id FROM _d_user);
DELETE FROM role_division WHERE division_id IN (SELECT id FROM _d_div);    -- liens user_role_division en cascade
DELETE FROM _user WHERE id IN (SELECT id FROM _d_user);    -- conversations, notifications, préférences en cascade
DELETE FROM agent WHERE matricule LIKE 'DEMO-%';
DELETE FROM division WHERE id IN (SELECT id FROM _d_div);
DELETE FROM _service WHERE code LIKE 'DEMO-%';
DELETE FROM direction WHERE code LIKE 'DEMO-%';
COMMIT;
