SET search_path TO rag_sys, public;

INSERT INTO permission (code, libelle) VALUES
    ('admin.root', 'Accès racine'),
    ('admin.service', 'Accès service'),
    ('admin.division', 'Accès division'),
    ('document.lister', 'Lister les documents'),
    ('chat.utiliser', 'Utiliser le chat'),
    ('utilisateur.lister', 'Lister les comptes'),
    ('utilisateur.creer', 'Créer un compte'),
    ('utilisateur.modifier', 'Modifier un compte'),
    ('structure.gerer', 'Gérer la structure'),
    ('dossier.gerer', 'Gérer les dossiers')
ON CONFLICT (code) DO NOTHING;

INSERT INTO _role (code, libelle) VALUES
    ('ADMIN', 'Super administrateur'),
    ('UTILISATEUR', 'Utilisateur métier')
ON CONFLICT (code) DO NOTHING;

-- Raccorder les permissions de base aux rôles globales.
INSERT INTO role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM _role r
JOIN permission p ON p.code IN (
    'admin.root', 'admin.service', 'admin.division',
    'document.lister', 'chat.utiliser', 'utilisateur.lister',
    'utilisateur.creer', 'utilisateur.modifier', 'structure.gerer',
    'dossier.gerer'
)
WHERE r.code = 'ADMIN'
ON CONFLICT DO NOTHING;

INSERT INTO role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM _role r
JOIN permission p ON p.code IN ('document.lister', 'chat.utiliser')
WHERE r.code = 'UTILISATEUR'
ON CONFLICT DO NOTHING;
