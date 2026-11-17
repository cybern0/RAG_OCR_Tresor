-- 10 - Suppression du poste « chef de service » (refonte : toutes ses responsabilités passent au super administrateur).
-- Migration des bases existantes (une seule transaction, répétable). Base neuve : inutile, 01_schema.sql est déjà à jour.
--   psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/10_suppression_chef_service.sql
--
-- Effet :
--   * les agents titrés CHEF_SERVICE perdent leur titre (ils redeviennent agents simples ; sans division, ils n'ont
--     accès à aucun fichier : le super administrateur les réaffecte à une division) ;
--   * les mots de passe de dossier qu'ils détenaient sont supprimés (ils appartiennent désormais aux seuls super administrateurs) ;
--   * leurs déverrouillages actifs sont fermés ;
--   * l'index unique et les contraintes « chef de service » sont retirés.
BEGIN;
SET search_path TO rag_sys, public;

-- 1. Les agents perdent le titre CHEF_SERVICE (idempotent : ne change rien s'il n'y en a plus)
UPDATE agent SET titre = NULL WHERE titre = 'CHEF_SERVICE';

-- 2. Fermer les déverrouillages et retirer les secrets détenus par des comptes non ADMIN (anciens chefs de service)
UPDATE deverrouillage d SET actif = FALSE
WHERE d.actif AND d.secret_unite_id IN (
    SELECT s.id FROM secret_unite s
    JOIN _user u ON u.id = s.admin_user_id
    JOIN _role r ON r.id = u.role_id
    WHERE r.code <> 'ADMIN');
DELETE FROM secret_unite s
USING _user u JOIN _role r ON r.id = u.role_id
WHERE s.admin_user_id = u.id AND r.code <> 'ADMIN';

-- 3. Contraintes : le titre ne peut plus valoir CHEF_SERVICE, l'index unique du service disparaît
ALTER TABLE agent DROP CONSTRAINT IF EXISTS agent_titre_check;
ALTER TABLE agent ADD CONSTRAINT agent_titre_check CHECK (titre IN ('CHEF_DIVISION'));
ALTER TABLE agent DROP CONSTRAINT IF EXISTS ck_agent_titre_division;
ALTER TABLE agent ADD CONSTRAINT ck_agent_titre_division CHECK (
    titre IS NULL
    OR (titre = 'CHEF_DIVISION' AND division_id IS NOT NULL)
);
DROP INDEX IF EXISTS uq_chef_service;

COMMIT;
