-- 02 - Données indispensables au fonctionnement (aucun compte, aucune organisation, aucune démonstration).
--   psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/02_donnees_reference.sql
--
-- Rôles GLOBAUX : ADMIN (super administrateur, niveau ROOT) et UTILISATEUR (tout autre compte).
-- Le NIVEAU se déduit du TITRE de l'agent (une seule source de vérité) : CHEF_DIVISION -> DIVISION,
-- CHEF_SERVICE -> SERVICE (le même rôle que le chef de division, étendu à toutes les divisions de son service).
-- Ces niveaux ajoutent, en code, les permissions utilisateur.* (voir Backend/app/core/permissions.py et core/portee.py).

SET search_path TO rag_sys, public;

INSERT INTO permission (code, libelle) VALUES
    ('document.lister', 'Consulter les fichiers accessibles'),
    ('chat.utiliser', 'Interroger l''assistant'),
    ('utilisateur.lister', 'Lister les comptes de son périmètre'),
    ('utilisateur.creer', 'Créer un compte dans son périmètre'),
    ('utilisateur.modifier', 'Modifier un compte de son périmètre'),
    ('structure.gerer', 'Gérer directions, services, divisions, agents et titres'),
    ('classement.gerer', 'Gérer catégories, types, étiquettes et règles de classement'),
    ('statistiques.globales', 'Consulter les statistiques globales'),
    ('audit.consulter', 'Consulter le journal d''audit technique')
ON CONFLICT (code) DO UPDATE SET libelle = EXCLUDED.libelle;

INSERT INTO _role (code, libelle) VALUES
    ('ADMIN', 'Super administrateur'),
    ('UTILISATEUR', 'Utilisateur (accès par rôles de division)')
ON CONFLICT (code) DO UPDATE SET libelle = EXCLUDED.libelle;

INSERT INTO role_permission (role_id, permission_id)
SELECT r.id, p.id FROM _role r CROSS JOIN permission p WHERE r.code = 'ADMIN'
ON CONFLICT DO NOTHING;

INSERT INTO role_permission (role_id, permission_id)
SELECT r.id, p.id FROM _role r JOIN permission p ON p.code IN ('document.lister', 'chat.utiliser')
WHERE r.code = 'UTILISATEUR'
ON CONFLICT DO NOTHING;
