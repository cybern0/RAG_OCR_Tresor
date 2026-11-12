-- 4/4 - Données initiales : rôles, permissions, organisation par défaut et compte administrateur.
-- Script répétable : relancé, il ne crée pas de doublons.
--
-- Deux rôles seulement :
--   ADMIN        : toutes les permissions (utilisateurs, agents, structure, documents de tous les services, audit).
--   UTILISATEUR  : CRUD sur les documents de SON service + chatbot sur son service.
--                  Il ne peut créer ni agent, ni utilisateur, ni gérer la structure.
-- Le rattachement à un service passe par l'agent lié au compte (_user.agent_id -> agent.service_id) :
-- un UTILISATEUR doit donc être lié à un agent ayant un service (contrôlé par le backend).
--
-- Le compte admin est créé verrouillé : son mot_de_passe_hash commence par '!' et ne correspond à aucun mot de passe.
-- Le backend refuse toute connexion sur un hash commençant par '!'. Pour l'activer, depuis le dossier Backend :
--   uv run python -m app.cli set-password admin
-- Ne jamais écrire un mot de passe en clair dans ce fichier.

SET search_path TO rag_sys, public;

-- Rôles
INSERT INTO _role (code, libelle) VALUES
    ('ADMIN', 'Administrateur'),
    ('UTILISATEUR', 'Utilisateur de son service')
ON CONFLICT (code) DO UPDATE SET libelle = EXCLUDED.libelle;

-- Permissions
INSERT INTO permission (code, libelle) VALUES
    ('document.lister', 'Voir la liste des documents (métadonnées seulement)'),
    ('document.creer', 'Ajouter un document'),
    ('document.modifier', 'Modifier un document'),
    ('document.supprimer', 'Supprimer un document'),
    ('chat.utiliser', 'Interroger le chatbot sur les documents de son service'),
    ('chat.tous_services', 'Interroger le chatbot sur les documents de tous les services'),
    ('utilisateur.lister', 'Voir la liste des utilisateurs'),
    ('utilisateur.creer', 'Créer un utilisateur'),
    ('utilisateur.modifier', 'Modifier ou désactiver un utilisateur'),
    ('structure.gerer', 'Gérer directions, services et agents'),
    ('audit.consulter', 'Consulter le journal d''audit')
ON CONFLICT (code) DO UPDATE SET libelle = EXCLUDED.libelle;

-- ADMIN : toutes les permissions
INSERT INTO role_permission (role_id, permission_id)
SELECT r.id, p.id FROM _role r CROSS JOIN permission p
WHERE r.code = 'ADMIN'
ON CONFLICT DO NOTHING;

-- UTILISATEUR : CRUD sur les documents de son service et chatbot, rien d'autre.
INSERT INTO role_permission (role_id, permission_id)
SELECT r.id, p.id FROM _role r JOIN permission p
    ON p.code IN ('document.lister', 'document.creer', 'document.modifier', 'document.supprimer', 'chat.utiliser')
WHERE r.code = 'UTILISATEUR'
ON CONFLICT DO NOTHING;

-- Organisation par défaut (obligatoire : un document doit appartenir à un service). À renommer ensuite.
INSERT INTO direction (code, nom) VALUES
    ('DIR-DEFAUT', 'Direction par défaut (à renommer)')
ON CONFLICT (code) DO NOTHING;

INSERT INTO _service (direction_id, code, nom)
SELECT d.id, 'SRV-GENERAL', 'Service général (à renommer)'
FROM direction d WHERE d.code = 'DIR-DEFAUT'
ON CONFLICT (code) DO NOTHING;

-- Compte administrateur verrouillé (voir l'en-tête)
INSERT INTO _user (nom_utilisateur, mot_de_passe_hash, role_id)
SELECT 'admin', '!A_DEFINIR', r.id FROM _role r WHERE r.code = 'ADMIN'
ON CONFLICT (nom_utilisateur) DO NOTHING;
