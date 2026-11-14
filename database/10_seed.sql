-- Données de DÉMONSTRATION : organisation, comptes, dossiers avec accès, référentiel de classement et règles.
-- À exécuter après les scripts 01 à 06 et 08, sur la base du projet.
-- Commande : psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/seed.sql
--
-- * Répétable : relancé, il ne crée aucun doublon (chaque ligne est identifiée par son code, son matricule ou son nom).
-- * N'efface et ne modifie rien d'existant : le compte `admin` verrouillé et l'organisation par défaut restent intacts.
-- * NE PAS UTILISER EN PRODUCTION : les comptes ci-dessous partagent un mot de passe de démonstration connu de tous.
--
-- Comptes (mot de passe de démonstration pour tous : Demo-Tresor-2026 ; seuls les hachages sont stockés ici) :
--   demo.admin      administrateur (voit tout, gère tout)
--   rakoto.compta   Service de la Comptabilité         — gestionnaire de « Budget 2026 », lecteur de « Marchés publics 2026 »…
--   rasoa.paie      Service Solde et Pensions          — lecteur de « Budget 2026 » et de « Procédures internes »
--   andry.achats    Service des Marchés Publics        — gestionnaire de « Marchés publics 2026 », contributeur de « Budget 2026 »
--   miora.infra     Service Infrastructure et Réseaux  — contributeur de « Documentation technique », gestionnaire de « Procédures internes »
--   hery.dev        Service Développement              — gestionnaire de « Documentation technique »
--   ancien.agent    compte désactivé (pour montrer cet état)
-- Deux agents (DEMO-006, DEMO-007) n'ont pas de compte : ils servent à tester « Nouvel utilisateur ».
--
-- Aucun fichier n'est inséré : un fichier doit être déposé par l'interface pour être lu, indexé (OCR, vecteurs) et classé.
-- Une fois des fichiers déposés, les règles ci-dessous les classent automatiquement et le tableau de bord se remplit.

SET search_path TO rag_sys, public;

BEGIN;

-- 1. Organisation ------------------------------------------------------------------------------------------------

INSERT INTO direction (code, nom) VALUES
    ('DIR-TRESOR', 'Direction du Trésor'),
    ('DIR-SI',     'Direction des Systèmes d''Information'),
    ('DIR-RH',     'Direction des Ressources Humaines')
ON CONFLICT (code) DO NOTHING;

INSERT INTO _service (direction_id, code, nom, site)
SELECT d.id, v.code, v.nom, v.site
FROM (VALUES
    ('DIR-TRESOR', 'SRV-COMPTA',     'Service de la Comptabilité',        'Antananarivo'),
    ('DIR-TRESOR', 'SRV-SOLDE',      'Service Solde et Pensions',         'Antananarivo'),
    ('DIR-TRESOR', 'SRV-MARCHES',    'Service des Marchés Publics',       'Fianarantsoa'),
    ('DIR-SI',     'SRV-INFRA',      'Service Infrastructure et Réseaux', 'Antananarivo'),
    ('DIR-SI',     'SRV-DEV',        'Service Développement',             'Antananarivo'),
    ('DIR-RH',     'SRV-FORMATION',  'Service Formation',                 'Fianarantsoa')
) AS v (direction_code, code, nom, site)
JOIN direction d ON d.code = v.direction_code
ON CONFLICT (code) DO NOTHING;

INSERT INTO agent (matricule, nom, prenom, fonction, email, service_id, actif)
SELECT v.matricule, v.nom, v.prenom, v.fonction, v.email, s.id, v.actif
FROM (VALUES
    ('DEMO-001', 'RAKOTO',        'Jean-Marc', 'Chef du service Comptabilité',  'jean-marc.rakoto@tresor-demo.example',     'SRV-COMPTA',    TRUE),
    ('DEMO-002', 'RASOAMANANA',   'Hanta',     'Gestionnaire de solde',         'hanta.rasoamanana@tresor-demo.example',    'SRV-SOLDE',     TRUE),
    ('DEMO-003', 'ANDRIAMAHEFA',  'Tojo',      'Chargé des marchés publics',    'tojo.andriamahefa@tresor-demo.example',    'SRV-MARCHES',   TRUE),
    ('DEMO-004', 'RAZAFY',        'Miora',     'Administratrice réseaux',       'miora.razafy@tresor-demo.example',         'SRV-INFRA',     TRUE),
    ('DEMO-005', 'RANDRIA',       'Hery',      'Développeur',                   'hery.randria@tresor-demo.example',         'SRV-DEV',       TRUE),
    ('DEMO-006', 'RAVELO',        'Voahangy',  'Responsable formation',         'voahangy.ravelo@tresor-demo.example',      'SRV-FORMATION', TRUE),
    ('DEMO-007', 'RABE',          'Solo',      'Comptable',                     'solo.rabe@tresor-demo.example',            'SRV-COMPTA',    TRUE),
    ('DEMO-008', 'RAKOTONIRINA',  'Faly',      'Ancien gestionnaire de solde',  'faly.rakotonirina@tresor-demo.example',    'SRV-SOLDE',     FALSE)
) AS v (matricule, nom, prenom, fonction, email, service_code, actif)
JOIN _service s ON s.code = v.service_code
ON CONFLICT (matricule) DO NOTHING;

-- 2. Comptes (hachages scrypt du mot de passe de démonstration, générés par app.core.security.hash_password) -------------

INSERT INTO _user (nom_utilisateur, mot_de_passe_hash, role_id, agent_id, actif)
SELECT v.nom_utilisateur, v.mot_de_passe_hash, r.id, a.id, v.actif
FROM (VALUES
    ('demo.admin',    'scrypt$16384$8$1$iCuPg_x4H5bHT4gqUoHYgA$10VpkkgY4Yv8H-COPxOG2HEJxGIJht2tjHn_H_ldaqA', 'ADMIN',       NULL,       TRUE),
    ('rakoto.compta', 'scrypt$16384$8$1$Cex6Ugp-9VoPOcpLeYhWuQ$uOfgXbAa0b_oMgJ9XLD28eLOoJgQ5jEPkUSAKZr08VI', 'UTILISATEUR', 'DEMO-001', TRUE),
    ('rasoa.paie',    'scrypt$16384$8$1$8I2mIfTc4tI3MJ2A6qTWPw$JtSZg102Mt67BemyKo5bxS4O4ig2nLK8eaiim1B1We0', 'UTILISATEUR', 'DEMO-002', TRUE),
    ('andry.achats',  'scrypt$16384$8$1$CsVhU3EQh9as92ru7ahiqg$irWDdiBvOF5-I0R6jhFdcfSV8gVvtUfWMfl8qB_prQA', 'UTILISATEUR', 'DEMO-003', TRUE),
    ('miora.infra',   'scrypt$16384$8$1$MnrBLZk3AdN96AsRIIwIMg$TbQPFLfsj9k3qpQjGpA10Q6hbTGRIOyEi3TF59xCDkU', 'UTILISATEUR', 'DEMO-004', TRUE),
    ('hery.dev',      'scrypt$16384$8$1$U-G-x71oU-F4QsgFVEgKzA$RqIn7PXDhLgGMVDZkHjKT0h3YHwl__8__rCYMW0b4Wc', 'UTILISATEUR', 'DEMO-005', TRUE),
    ('ancien.agent',  'scrypt$16384$8$1$bCJkwK6r3xDmAy2r_pzzFg$C7Rqe6PeMwyyEa1opjc7VXPsUrWqc_f-309S5nFmJ5g', 'UTILISATEUR', 'DEMO-008', FALSE)
) AS v (nom_utilisateur, mot_de_passe_hash, role_code, matricule, actif)
JOIN _role r ON r.code = v.role_code
LEFT JOIN agent a ON a.matricule = v.matricule
ON CONFLICT (nom_utilisateur) DO NOTHING;

-- 3. Dossiers et accès ---------------------------------------------------------------------------------------------

INSERT INTO dossier (nom, description, archive, cree_par)
SELECT v.nom, v.description, v.archive, (SELECT id FROM _user WHERE nom_utilisateur = 'demo.admin')
FROM (VALUES
    ('Budget 2026',             'Loi de finances, exécution budgétaire, factures et pièces comptables de l''exercice 2026.', FALSE),
    ('Marchés publics 2026',    'Appels d''offres, contrats, avenants et procès-verbaux de la commission des marchés.',      FALSE),
    ('Documentation technique', 'Architecture, procédures d''exploitation et fiches techniques des systèmes d''information.', FALSE),
    ('Procédures internes',     'Notes de service, procédures et comptes rendus applicables à tous les services.',          FALSE),
    ('Formation et carrières',  'Plans de formation, évaluations et parcours de carrière.',                                  FALSE),
    ('Archives 2024',           'Dossiers de l''exercice 2024, clos : consultation seulement.',                              TRUE)
) AS v (nom, description, archive)
ON CONFLICT (lower(nom)) DO NOTHING;

-- accès par service (tous les agents actifs du service ont ce rôle)
INSERT INTO dossier_service (dossier_id, service_id, role)
SELECT d.id, s.id, v.role
FROM (VALUES
    ('Budget 2026',             'SRV-COMPTA',    'GESTIONNAIRE_DE_CONTENU'),
    ('Budget 2026',             'SRV-SOLDE',     'LECTEUR'),
    ('Budget 2026',             'SRV-MARCHES',   'LECTEUR'),
    ('Marchés publics 2026',    'SRV-MARCHES',   'GESTIONNAIRE_DE_CONTENU'),
    ('Marchés publics 2026',    'SRV-COMPTA',    'LECTEUR'),
    ('Documentation technique', 'SRV-INFRA',     'CONTRIBUTEUR'),
    ('Documentation technique', 'SRV-DEV',       'GESTIONNAIRE_DE_CONTENU'),
    ('Procédures internes',     'SRV-COMPTA',    'LECTEUR'),
    ('Procédures internes',     'SRV-SOLDE',     'LECTEUR'),
    ('Procédures internes',     'SRV-MARCHES',   'LECTEUR'),
    ('Procédures internes',     'SRV-INFRA',     'LECTEUR'),
    ('Procédures internes',     'SRV-DEV',       'LECTEUR'),
    ('Procédures internes',     'SRV-FORMATION', 'CONTRIBUTEUR'),
    ('Formation et carrières',  'SRV-FORMATION', 'GESTIONNAIRE_DE_CONTENU'),
    ('Archives 2024',           'SRV-COMPTA',    'LECTEUR')
) AS v (dossier_nom, service_code, role)
JOIN dossier d ON lower(d.nom) = lower(v.dossier_nom)
JOIN _service s ON s.code = v.service_code
ON CONFLICT (dossier_id, service_id) DO NOTHING;

-- accès directs à un utilisateur (le rôle effectif est le plus élevé entre le rôle direct et celui du service)
INSERT INTO dossier_membre (dossier_id, user_id, role)
SELECT d.id, u.id, v.role
FROM (VALUES
    ('Budget 2026',             'andry.achats',  'CONTRIBUTEUR'),
    ('Marchés publics 2026',    'rakoto.compta', 'CONTRIBUTEUR'),
    ('Procédures internes',     'miora.infra',   'GESTIONNAIRE_DE_CONTENU')
) AS v (dossier_nom, nom_utilisateur, role)
JOIN dossier d ON lower(d.nom) = lower(v.dossier_nom)
JOIN _user u ON u.nom_utilisateur = v.nom_utilisateur
ON CONFLICT (dossier_id, user_id) DO NOTHING;

-- 4. Référentiel de classement ---------------------------------------------------------------------------------------

INSERT INTO categorie (nom, couleur, ordre)
SELECT v.nom, v.couleur, v.ordre
FROM (VALUES
    ('Finance',              '#d9a92b', 1),
    ('Juridique',            '#7fb5e6', 2),
    ('Ressources humaines',  '#a7c957', 3),
    ('Technique',            '#e08e6b', 4),
    ('Administratif',        '#c8b6e2', 5)
) AS v (nom, couleur, ordre)
WHERE NOT EXISTS (SELECT 1 FROM categorie c WHERE lower(c.nom) = lower(v.nom));

-- sous-catégories
INSERT INTO categorie (nom, parent_id, couleur, ordre)
SELECT v.nom, p.id, v.couleur, v.ordre
FROM (VALUES
    ('Budget',      'Finance',   '#f2d680', 1),
    ('Comptabilité','Finance',   '#e9c24f', 2)
) AS v (nom, parent_nom, couleur, ordre)
JOIN categorie p ON lower(p.nom) = lower(v.parent_nom)
WHERE NOT EXISTS (SELECT 1 FROM categorie c WHERE lower(c.nom) = lower(v.nom));

INSERT INTO type_document (nom) VALUES
    ('Facture'), ('Contrat'), ('Rapport'), ('Procédure'), ('Note de service'),
    ('Compte rendu'), ('Décision'), ('Fiche technique')
ON CONFLICT (nom) DO NOTHING;

INSERT INTO tag (nom) VALUES
    ('budget'), ('urgent'), ('2026'), ('marché public'), ('audit'), ('sécurité'), ('formation')
ON CONFLICT (lower(nom)) DO NOTHING;

-- 5. Règles de classement automatique (appliquées à l'indexation ; la plus prioritaire fixe catégorie, type et confidentialité) --

INSERT INTO regle_classement (nom, priorite, critere, categorie_id, type_document_id, tags, confidentialite)
SELECT v.nom, v.priorite, v.critere::jsonb,
       (SELECT id FROM categorie WHERE lower(nom) = lower(v.categorie)),
       (SELECT id FROM type_document WHERE nom = v.type_nom),
       v.tags, v.confidentialite
FROM (VALUES
    ('Factures',
        10,  '[{"champ": "texte", "op": "contient_un_de", "valeur": ["facture", "montant à payer"]}]',
        'Comptabilité',  'Facture',         ARRAY['budget']::text[],       'INTERNE'),
    ('Contrats et marchés',
        20,  '[{"champ": "nom_fichier", "op": "contient_un_de", "valeur": ["contrat", "marche", "marché", "avenant"]}]',
        'Juridique',     'Contrat',         ARRAY['marché public']::text[], 'CONFIDENTIEL'),
    ('Procédures',
        30,  '[{"champ": "nom_fichier", "op": "contient_un_de", "valeur": ["procedure", "procédure"]}]',
        'Administratif', 'Procédure',       ARRAY[]::text[],               'INTERNE'),
    ('Notes de service',
        40,  '[{"champ": "texte", "op": "contient_un_de", "valeur": ["note de service"]}]',
        'Administratif', 'Note de service', ARRAY[]::text[],               'PUBLIC'),
    ('Comptes rendus de réunion',
        50,  '[{"champ": "texte", "op": "contient_un_de", "valeur": ["compte rendu", "compte-rendu", "ordre du jour"]}]',
        'Administratif', 'Compte rendu',    ARRAY[]::text[],               'INTERNE'),
    ('Documents techniques',
        60,  '[{"champ": "nom_fichier", "op": "contient_un_de", "valeur": ["architecture", "schema", "schéma", "technique"]}]',
        'Technique',     'Fiche technique', ARRAY['sécurité']::text[],     'INTERNE'),
    ('Plans de formation',
        70,  '[{"champ": "texte", "op": "contient_un_de", "valeur": ["plan de formation", "session de formation"]}]',
        'Ressources humaines', 'Rapport',   ARRAY['formation']::text[],    'INTERNE')
) AS v (nom, priorite, critere, categorie, type_nom, tags, confidentialite)
WHERE NOT EXISTS (SELECT 1 FROM regle_classement r WHERE r.nom = v.nom);

COMMIT;

-- Contrôle rapide (à lancer à la main) :
--   SELECT u.nom_utilisateur, r.code AS role, a.matricule, s.code AS service, u.actif
--   FROM _user u JOIN _role r ON r.id = u.role_id LEFT JOIN agent a ON a.id = u.agent_id LEFT JOIN _service s ON s.id = a.service_id ORDER BY u.id;