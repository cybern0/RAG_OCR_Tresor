-- 4/4 - Données initiales : 2 rôles (ADMIN, UTILISATEUR), permissions, organisation par défaut et compte administrateur.
-- Aucun des deux rôles ne crée d'agent ni d'utilisateur dans l'application : les comptes sont créés hors application,
-- par l'exploitant technique, avec backend/scripts/creer_compte.py.
-- Périmètre : chaque rôle agit sur les documents de SON service (_user -> agent -> service_id).
-- Script répétable : relancé, il ne crée pas de doublons.
-- Le compte admin est créé verrouillé : son mot_de_passe_hash commence par '!' et ne correspond à aucun mot de passe.
-- Le backend doit refuser toute connexion sur un hash commençant par '!'. Pour l'activer :
--   UPDATE rag_sys._user SET mot_de_passe_hash = '<hash produit par le backend>' WHERE nom_utilisateur = 'admin';
-- Ne jamais écrire un mot de passe en clair dans ce fichier.

SET search_path TO rag_sys, public;

-- Rôles
INSERT INTO _role (code, libelle) VALUES
    ('ADMIN', 'Administrateur'),
    ('UTILISATEUR', 'Utilisateur')
ON CONFLICT (code) DO NOTHING;

-- Permissions
INSERT INTO permission (code, libelle) VALUES
    ('document.lister', 'Voir la liste des documents de son service (métadonnées seulement)'),
    ('document.creer', 'Ajouter un document dans son service'),
    ('document.modifier', 'Modifier un document de son service'),
    ('document.supprimer', 'Supprimer un document de son service'),
    ('chat.utiliser', 'Interroger le chatbot sur les documents de son service'),
    ('audit.consulter', 'Consulter le journal d''audit de son service')
ON CONFLICT (code) DO NOTHING;

-- ADMIN : toutes les permissions
INSERT INTO role_permission (role_id, permission_id)
SELECT r.id, p.id FROM _role r CROSS JOIN permission p
WHERE r.code = 'ADMIN'
ON CONFLICT DO NOTHING;

-- UTILISATEUR : CRUD des documents de son service et chatbot (pas d'audit)
INSERT INTO role_permission (role_id, permission_id)
SELECT r.id, p.id FROM _role r JOIN permission p
    ON p.code IN ('document.lister', 'document.creer', 'document.modifier', 'document.supprimer', 'chat.utiliser')
WHERE r.code = 'UTILISATEUR'
ON CONFLICT DO NOTHING;

-- Organisation par défaut (obligatoire : un document appartient à un service). À renommer ensuite.
INSERT INTO direction (code, nom) VALUES
    ('DIR-DEFAUT', 'Direction par défaut (à renommer)')
ON CONFLICT (code) DO NOTHING;

INSERT INTO _service (direction_id, code, nom)
SELECT d.id, 'SRV-GENERAL', 'Service général (à renommer)'
FROM direction d WHERE d.code = 'DIR-DEFAUT'
ON CONFLICT (code) DO NOTHING;

-- Agent du compte administrateur : sans service, l'admin n'aurait accès à aucun document
INSERT INTO agent (matricule, nom, prenom, fonction, service_id)
SELECT 'ADMIN-0001', 'Administrateur', 'Compte', 'Administrateur applicatif', s.id
FROM _service s WHERE s.code = 'SRV-GENERAL'
ON CONFLICT (matricule) DO NOTHING;

-- Compte administrateur verrouillé (voir l'en-tête)
INSERT INTO _user (agent_id, nom_utilisateur, mot_de_passe_hash, role_id)
SELECT a.id, 'admin', '!A_DEFINIR', r.id
FROM agent a, _role r
WHERE a.matricule = 'ADMIN-0001' AND r.code = 'ADMIN'
ON CONFLICT (nom_utilisateur) DO NOTHING;
