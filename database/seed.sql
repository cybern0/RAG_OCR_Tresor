-- seed - Données de DÉMONSTRATION (facultatif, après 01 et 02). Tout porte le préfixe DEMO / demo_ : supprimable par delete_seed.sql.
--   psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/seed.sql
-- Mot de passe de tous les comptes demo_* : Demo@2026  (à ne jamais utiliser en production).
-- Fichiers : déposer ensuite des documents par l'API ou scripts/seed_fichiers.py (aucun fichier n'est créé ici).
BEGIN;
SET search_path TO rag_sys, public;

INSERT INTO direction (code, nom) VALUES ('DEMO-DIR', 'DEMO - Direction générale');
INSERT INTO _service (direction_id, code, nom, site)
SELECT d.id, v.code, v.nom, 'DEMO' FROM direction d,
     (VALUES ('DEMO-SRV-A', 'DEMO - Service Finances'), ('DEMO-SRV-B', 'DEMO - Service Ressources humaines')) v(code, nom)
WHERE d.code = 'DEMO-DIR';
INSERT INTO division (service_id, code, nom)
SELECT s.id, v.code, v.nom FROM _service s JOIN
     (VALUES ('DEMO-SRV-A', 'DEMO-DIV-A1', 'DEMO - Budget'), ('DEMO-SRV-A', 'DEMO-DIV-A2', 'DEMO - Comptabilité'),
             ('DEMO-SRV-B', 'DEMO-DIV-B1', 'DEMO - Recrutement')) v(srv, code, nom) ON v.srv = s.code;

-- matricule, nom, prénom, service, division, titre
INSERT INTO agent (matricule, nom, prenom, fonction, service_id, division_id, titre)
SELECT v.mat, v.nom, v.prenom, v.fonction, s.id, dv.id, v.titre
FROM (VALUES
  ('DEMO-001', 'Demo', 'Admin',   'Super administrateur', NULL,         NULL,          NULL),
  ('DEMO-010', 'Demo', 'ChefA',   'Chef de service',      'DEMO-SRV-A', NULL,          'CHEF_SERVICE'),
  ('DEMO-011', 'Demo', 'ChefB',   'Chef de service',      'DEMO-SRV-B', NULL,          'CHEF_SERVICE'),
  ('DEMO-020', 'Demo', 'ChefA1',  'Chef de division',     'DEMO-SRV-A', 'DEMO-DIV-A1', 'CHEF_DIVISION'),
  ('DEMO-021', 'Demo', 'ChefA2',  'Chef de division',     'DEMO-SRV-A', 'DEMO-DIV-A2', 'CHEF_DIVISION'),
  ('DEMO-022', 'Demo', 'ChefB1',  'Chef de division',     'DEMO-SRV-B', 'DEMO-DIV-B1', 'CHEF_DIVISION'),
  ('DEMO-030', 'Demo', 'AgentA1', 'Agent',                'DEMO-SRV-A', 'DEMO-DIV-A1', NULL),
  ('DEMO-031', 'Demo', 'AgentA1b','Agent',                'DEMO-SRV-A', 'DEMO-DIV-A1', NULL),
  ('DEMO-032', 'Demo', 'AgentA2', 'Agent',                'DEMO-SRV-A', 'DEMO-DIV-A2', NULL),
  ('DEMO-033', 'Demo', 'AgentB1', 'Agent',                'DEMO-SRV-B', 'DEMO-DIV-B1', NULL)
) v(mat, nom, prenom, fonction, srv, div, titre)
LEFT JOIN _service s ON s.code = v.srv
LEFT JOIN division dv ON dv.code = v.div
WHERE v.srv IS NOT NULL;   -- l'administrateur global n'a pas d'agent (ligne ignorée ici)

-- Comptes : l'admin global sans agent, les autres liés à leur agent.
INSERT INTO _user (agent_id, nom_utilisateur, mot_de_passe_hash, role_id)
SELECT NULL, 'demo_admin', 'scrypt$16384$8$1$IGftoiQdwJ32z51m_H9SLw$Yik2syX_qWzn_Wsq6WWYzGNPuJg8tVt-lwNMZELBBSM', r.id FROM _role r WHERE r.code = 'ADMIN';
INSERT INTO _user (agent_id, nom_utilisateur, mot_de_passe_hash, role_id)
SELECT a.id, 'demo_' || lower(a.prenom), 'scrypt$16384$8$1$IGftoiQdwJ32z51m_H9SLw$Yik2syX_qWzn_Wsq6WWYzGNPuJg8tVt-lwNMZELBBSM', r.id
FROM agent a, _role r WHERE a.matricule LIKE 'DEMO-%' AND r.code = 'UTILISATEUR';

-- Rôles métier par division, attribués aux agents
INSERT INTO role_division (division_id, code, libelle)
SELECT dv.id, v.code, v.libelle FROM division dv JOIN
     (VALUES ('DEMO-DIV-A1', 'LECTEUR', 'DEMO - Lecteur'), ('DEMO-DIV-A1', 'PAIE', 'DEMO - Paie'),
             ('DEMO-DIV-A2', 'LECTEUR', 'DEMO - Lecteur'), ('DEMO-DIV-B1', 'LECTEUR', 'DEMO - Lecteur')) v(div, code, libelle)
     ON v.div = dv.code;
INSERT INTO user_role_division (user_id, role_division_id)
SELECT u.id, rd.id FROM _user u, role_division rd JOIN division dv ON dv.id = rd.division_id
WHERE u.nom_utilisateur = 'demo_agenta1' AND dv.code = 'DEMO-DIV-A1' AND rd.code = 'LECTEUR';

-- Dossiers et sous-dossiers
INSERT INTO dossier (division_id, nom, description)
SELECT dv.id, v.nom, 'DEMO' FROM division dv JOIN
     (VALUES ('DEMO-DIV-A1', 'DEMO - Budget 2026'), ('DEMO-DIV-A2', 'DEMO - Factures'), ('DEMO-DIV-B1', 'DEMO - Offres d''emploi')) v(div, nom)
     ON v.div = dv.code;
INSERT INTO dossier (division_id, parent_id, nom, description)
SELECT p.division_id, p.id, 'DEMO - Trimestre 1', 'DEMO' FROM dossier p WHERE p.nom = 'DEMO - Budget 2026';

COMMIT;
