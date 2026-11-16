-- Schéma principal de la GED hiérarchique Direction -> Service -> Division -> dossiers libres
-- Compatible avec le backend SQLAlchemy actuel et la logique métier décrite dans le plan.

CREATE SCHEMA IF NOT EXISTS rag_sys;
SET search_path TO rag_sys, public;

CREATE TABLE IF NOT EXISTS direction (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(30) UNIQUE NOT NULL,
    nom VARCHAR(180) NOT NULL,
    actif BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS _service (
    id BIGSERIAL PRIMARY KEY,
    direction_id BIGINT NOT NULL REFERENCES direction(id) ON DELETE CASCADE,
    code VARCHAR(30) UNIQUE NOT NULL,
    nom VARCHAR(180) NOT NULL,
    site VARCHAR(150),
    actif BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS division (
    id BIGSERIAL PRIMARY KEY,
    service_id BIGINT NOT NULL REFERENCES _service(id) ON DELETE CASCADE,
    code VARCHAR(30) UNIQUE,
    nom VARCHAR(180) NOT NULL,
    actif BOOLEAN NOT NULL DEFAULT TRUE,
    UNIQUE (service_id, nom)
);

CREATE TABLE IF NOT EXISTS agent (
    id BIGSERIAL PRIMARY KEY,
    matricule VARCHAR(50) UNIQUE NOT NULL,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    fonction VARCHAR(150),
    email VARCHAR(180),
    service_id BIGINT REFERENCES _service(id),
    division_id BIGINT REFERENCES division(id) ON DELETE SET NULL,
    titre VARCHAR(30),
    actif BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS permission (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(80) UNIQUE NOT NULL,
    libelle VARCHAR(180) NOT NULL
);

CREATE TABLE IF NOT EXISTS _role (
    id BIGSERIAL PRIMARY KEY,
    code VARCHAR(30) UNIQUE NOT NULL,
    libelle VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS role_permission (
    role_id BIGINT NOT NULL REFERENCES _role(id) ON DELETE CASCADE,
    permission_id BIGINT NOT NULL REFERENCES permission(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS _user (
    id BIGSERIAL PRIMARY KEY,
    agent_id BIGINT REFERENCES agent(id) ON DELETE SET NULL,
    nom_utilisateur VARCHAR(80) UNIQUE NOT NULL,
    mot_de_passe_hash TEXT NOT NULL,
    role_id BIGINT NOT NULL REFERENCES _role(id),
    actif BOOLEAN NOT NULL DEFAULT TRUE,
    derniere_connexion TIMESTAMPTZ,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS journal_audit (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    action VARCHAR(60) NOT NULL,
    entite VARCHAR(60),
    entite_id BIGINT,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    adresse_ip INET,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS conversation (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    titre VARCHAR(200),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS message (
    id BIGSERIAL PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES conversation(id) ON DELETE CASCADE,
    emetteur VARCHAR(15) NOT NULL,
    contenu TEXT NOT NULL,
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS categorie (
    id BIGSERIAL PRIMARY KEY,
    parent_id BIGINT REFERENCES categorie(id) ON DELETE SET NULL,
    nom VARCHAR(120) NOT NULL,
    couleur VARCHAR(9),
    ordre INTEGER NOT NULL DEFAULT 0,
    actif BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS type_document (
    id BIGSERIAL PRIMARY KEY,
    nom VARCHAR(120) UNIQUE NOT NULL,
    actif BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS tag (
    id BIGSERIAL PRIMARY KEY,
    nom VARCHAR(60) NOT NULL
);

CREATE TABLE IF NOT EXISTS dossier (
    id BIGSERIAL PRIMARY KEY,
    division_id BIGINT REFERENCES division(id) ON DELETE SET NULL,
    parent_id BIGINT REFERENCES dossier(id) ON DELETE SET NULL,
    nom VARCHAR(150) NOT NULL,
    description TEXT,
    archive BOOLEAN NOT NULL DEFAULT FALSE,
    cree_par BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    modifie_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS document (
    id BIGSERIAL PRIMARY KEY,
    dossier_id BIGINT NOT NULL REFERENCES dossier(id) ON DELETE CASCADE,
    division_id BIGINT REFERENCES division(id) ON DELETE SET NULL,
    titre VARCHAR(250) NOT NULL,
    categorie_id BIGINT REFERENCES categorie(id) ON DELETE SET NULL,
    type_document_id BIGINT REFERENCES type_document(id) ON DELETE SET NULL,
    confidentialite VARCHAR(15) NOT NULL DEFAULT 'INTERNE',
    classement_source VARCHAR(10) NOT NULL DEFAULT 'aucun',
    regle_id BIGINT,
    cree_par_service_id BIGINT REFERENCES _service(id) ON DELETE SET NULL,
    corbeille_le TIMESTAMPTZ,
    has_tabular BOOLEAN NOT NULL DEFAULT FALSE,
    has_image BOOLEAN NOT NULL DEFAULT FALSE,
    cree_par BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    modifie_par BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    modifie_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS document_version (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    numero INTEGER NOT NULL,
    nom_fichier VARCHAR(255) NOT NULL,
    type_mime VARCHAR(120),
    taille_octets BIGINT,
    hash_sha256 VARCHAR(64) NOT NULL,
    chemin_stockage TEXT NOT NULL,
    nb_pages INTEGER,
    ocr_utilise BOOLEAN NOT NULL DEFAULT FALSE,
    statut VARCHAR(20) NOT NULL DEFAULT 'pending',
    message_erreur TEXT,
    cree_par BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chunk (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    document_version_id BIGINT NOT NULL REFERENCES document_version(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    page INTEGER,
    contenu TEXT NOT NULL,
    est_tableau BOOLEAN NOT NULL DEFAULT FALSE,
    taille_ref INTEGER NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(768) NOT NULL,
    contenu_tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('french', contenu)) STORED,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS document_tag (
    document_id BIGINT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    tag_id BIGINT NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
    source VARCHAR(10) NOT NULL DEFAULT 'manuel',
    PRIMARY KEY (document_id, tag_id)
);

CREATE TABLE IF NOT EXISTS regle_classement (
    id BIGSERIAL PRIMARY KEY,
    nom VARCHAR(120) NOT NULL,
    priorite INTEGER NOT NULL DEFAULT 100,
    actif BOOLEAN NOT NULL DEFAULT TRUE,
    critere JSONB NOT NULL DEFAULT '{}'::jsonb,
    categorie_id BIGINT REFERENCES categorie(id) ON DELETE SET NULL,
    type_document_id BIGINT REFERENCES type_document(id) ON DELETE SET NULL,
    tags VARCHAR(60)[] NOT NULL DEFAULT '{}',
    confidentialite VARCHAR(15),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    modifie_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS preference_utilisateur (
    user_id BIGINT PRIMARY KEY REFERENCES _user(id) ON DELETE CASCADE,
    memoire_inter_sessions BOOLEAN NOT NULL DEFAULT FALSE,
    derniere_version_seulement BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS dossier_membre (
    dossier_id BIGINT NOT NULL REFERENCES dossier(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    role VARCHAR(30) NOT NULL,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (dossier_id, user_id)
);

CREATE TABLE IF NOT EXISTS dossier_service (
    dossier_id BIGINT NOT NULL REFERENCES dossier(id) ON DELETE CASCADE,
    service_id BIGINT NOT NULL REFERENCES _service(id),
    role VARCHAR(30) NOT NULL,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (dossier_id, service_id)
);

CREATE TABLE IF NOT EXISTS role_division (
    id BIGSERIAL PRIMARY KEY,
    division_id BIGINT NOT NULL REFERENCES division(id) ON DELETE CASCADE,
    code VARCHAR(60) NOT NULL,
    libelle VARCHAR(180) NOT NULL,
    actif BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS user_role_division (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    role_division_id BIGINT NOT NULL REFERENCES role_division(id) ON DELETE CASCADE,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS document_role (
    id BIGSERIAL PRIMARY KEY,
    document_id BIGINT NOT NULL,
    role_division_id BIGINT NOT NULL REFERENCES role_division(id) ON DELETE CASCADE,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS demande_acces (
    id BIGSERIAL PRIMARY KEY,
    demandeur_user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    type_demande VARCHAR(30) NOT NULL DEFAULT 'role',
    cible_type VARCHAR(30),
    cible_id BIGINT,
    motif TEXT,
    statut VARCHAR(20) NOT NULL DEFAULT 'en_attente',
    decisionnaire_user_id BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    reponse TEXT,
    date_creation TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    date_decision TIMESTAMPTZ,
    expiration TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS acces_exception (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    document_id BIGINT NOT NULL,
    motif TEXT,
    expire_le TIMESTAMPTZ,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS secret_unite (
    id BIGSERIAL PRIMARY KEY,
    service_id BIGINT REFERENCES _service(id) ON DELETE CASCADE,
    division_id BIGINT REFERENCES division(id) ON DELETE CASCADE,
    admin_user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    secret_hash TEXT NOT NULL,
    modifie_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS deverrouillage (
    id BIGSERIAL PRIMARY KEY,
    secret_unite_id BIGINT NOT NULL REFERENCES secret_unite(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    valide_jusqua TIMESTAMPTZ NOT NULL,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actif BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS historique_modification (
    id BIGSERIAL PRIMARY KEY,
    acteur_user_id BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    cible_type VARCHAR(40) NOT NULL,
    cible_id BIGINT,
    action VARCHAR(60) NOT NULL,
    avant TEXT,
    apres TEXT,
    motif TEXT,
    service_id BIGINT REFERENCES _service(id) ON DELETE SET NULL,
    division_id BIGINT REFERENCES division(id) ON DELETE SET NULL,
    date_action TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    hash_precedent VARCHAR(128),
    hash_courant VARCHAR(128)
);

CREATE TABLE IF NOT EXISTS notification (
    id BIGSERIAL PRIMARY KEY,
    destinataire_user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    type_evenement VARCHAR(60) NOT NULL,
    reference_type VARCHAR(30),
    reference_id BIGINT,
    message TEXT,
    lu BOOLEAN NOT NULL DEFAULT FALSE,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS commentaire (
    id BIGSERIAL PRIMARY KEY,
    sujet_type VARCHAR(20) NOT NULL,
    sujet_id BIGINT NOT NULL,
    auteur_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    contenu TEXT NOT NULL,
    parent_id BIGINT REFERENCES commentaire(id) ON DELETE CASCADE,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS memoire_chat (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    conversation_id BIGINT REFERENCES conversation(id) ON DELETE CASCADE,
    resume TEXT NOT NULL,
    document_ids BIGINT[] NOT NULL DEFAULT '{}',
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_agent_service_division ON agent(service_id, division_id);
CREATE INDEX IF NOT EXISTS idx_division_service ON division(service_id);
CREATE INDEX IF NOT EXISTS idx_dossier_parent ON dossier(parent_id);
CREATE INDEX IF NOT EXISTS idx_dossier_division ON dossier(division_id);
CREATE INDEX IF NOT EXISTS idx_notification_destinataire ON notification(destinataire_user_id, lu);
CREATE INDEX IF NOT EXISTS idx_historique_cible ON historique_modification(cible_type, cible_id);
