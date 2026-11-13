-- 06 - Classement, catégories, types, tags, règles et vue de statistiques.
-- À exécuter après 05, sur une base neuve ou déjà remplie.
-- Commande : psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/06_classement_stats.sql
-- Vérification : psql -U postgres -d rag -f database/06_verification.sql
-- Retour arrière : psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/06_retour_arriere.sql

SET search_path TO rag_sys, public;

BEGIN;

CREATE TABLE IF NOT EXISTS categorie (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parent_id BIGINT REFERENCES categorie(id) ON DELETE SET NULL,
    nom VARCHAR(120) NOT NULL,
    couleur VARCHAR(9),
    ordre INT NOT NULL DEFAULT 0,
    actif BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS type_document (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nom VARCHAR(120) UNIQUE NOT NULL,
    actif BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS tag (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nom VARCHAR(60) NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_tag_nom ON tag (lower(nom));

CREATE TABLE IF NOT EXISTS document_tag (
    document_id BIGINT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    tag_id BIGINT NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
    source VARCHAR(10) NOT NULL DEFAULT 'manuel' CHECK (source IN ('manuel', 'regle')),
    PRIMARY KEY (document_id, tag_id)
);

CREATE TABLE IF NOT EXISTS regle_classement (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nom VARCHAR(120) NOT NULL,
    priorite INT NOT NULL DEFAULT 100,
    actif BOOLEAN NOT NULL DEFAULT TRUE,
    critere JSONB NOT NULL DEFAULT '{}',
    categorie_id BIGINT REFERENCES categorie(id) ON DELETE SET NULL,
    type_document_id BIGINT REFERENCES type_document(id) ON DELETE SET NULL,
    tags TEXT[] NOT NULL DEFAULT '{}',
    confidentialite VARCHAR(15) CHECK (confidentialite IN ('PUBLIC', 'INTERNE', 'CONFIDENTIEL')),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    modifie_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE document
    ADD COLUMN IF NOT EXISTS categorie_id BIGINT REFERENCES categorie(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS type_document_id BIGINT REFERENCES type_document(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS confidentialite VARCHAR(15) NOT NULL DEFAULT 'INTERNE'
        CHECK (confidentialite IN ('PUBLIC', 'INTERNE', 'CONFIDENTIEL')),
    ADD COLUMN IF NOT EXISTS classement_source VARCHAR(10) NOT NULL DEFAULT 'aucun'
        CHECK (classement_source IN ('aucun', 'regle', 'manuel')),
    ADD COLUMN IF NOT EXISTS regle_id BIGINT,
    ADD COLUMN IF NOT EXISTS cree_par_service_id BIGINT REFERENCES _service(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS corbeille_le TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_document_categorie ON document (categorie_id);
CREATE INDEX IF NOT EXISTS idx_document_type_document ON document (type_document_id);
CREATE INDEX IF NOT EXISTS idx_document_confidentialite ON document (confidentialite);
CREATE INDEX IF NOT EXISTS idx_document_service ON document (cree_par_service_id);

-- Permissions de la GED.
INSERT INTO permission (code, libelle) VALUES
    ('classement.gerer', 'Gérer les catégories, types, tags et règles de classement'),
    ('statistiques.globales', 'Consulter les statistiques globales et les dimensions sensibles')
ON CONFLICT (code) DO UPDATE SET libelle = EXCLUDED.libelle;

INSERT INTO role_permission (role_id, permission_id)
SELECT r.id, p.id FROM _role r JOIN permission p ON p.code = 'classement.gerer'
WHERE r.code = 'ADMIN'
ON CONFLICT DO NOTHING;

INSERT INTO role_permission (role_id, permission_id)
SELECT r.id, p.id FROM _role r JOIN permission p ON p.code = 'statistiques.globales'
WHERE r.code = 'ADMIN'
ON CONFLICT DO NOTHING;

-- Vue métier des statistiques documentaires : une ligne = un document logique avec la dernière version connue.
CREATE OR REPLACE VIEW vue_document_stats AS
SELECT
    d.id AS document_id,
    d.dossier_id,
    d.categorie_id,
    d.type_document_id,
    d.confidentialite,
    d.corbeille_le,
    d.cree_le,
    d.cree_par,
    d.cree_par_service_id AS service_id,
    s.direction_id,
    v.numero AS version_courante,
    v.statut,
    v.taille_octets,
    v.nb_pages,
    v.ocr_utilise,
    lower(substring(v.nom_fichier from '\.([^.]+)$')) AS extension,
    (SELECT count(*) FROM document_version x WHERE x.document_id = d.id) AS nb_versions
FROM document d
JOIN LATERAL (
    SELECT * FROM document_version
    WHERE document_id = d.id
    ORDER BY numero DESC
    LIMIT 1
) v ON TRUE
LEFT JOIN _service s ON s.id = d.cree_par_service_id;

COMMIT;
