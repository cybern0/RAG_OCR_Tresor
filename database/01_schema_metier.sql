-- 1/4 - Schéma rag_sys : organisation (direction, _service, agent), comptes (_role, permission, _user),
-- journal d'audit et conversations du chatbot.
-- À exécuter en premier : crée le schéma utilisé par les scripts suivants.

CREATE SCHEMA IF NOT EXISTS rag_sys;
SET search_path TO rag_sys, public;

-- 1. Organisation administrative
CREATE TABLE IF NOT EXISTS direction (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(30) UNIQUE NOT NULL,
    nom VARCHAR(180) NOT NULL,
    actif BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS _service (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    direction_id BIGINT NOT NULL REFERENCES direction(id),
    code VARCHAR(30) UNIQUE NOT NULL,
    nom VARCHAR(180) NOT NULL,
    site VARCHAR(150),
    actif BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS agent (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    matricule VARCHAR(50) UNIQUE NOT NULL,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    fonction VARCHAR(150),
    email VARCHAR(180),
    service_id BIGINT REFERENCES _service(id),
    actif BOOLEAN NOT NULL DEFAULT TRUE
);

-- 2. Comptes et autorisations
CREATE TABLE IF NOT EXISTS _role (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(30) UNIQUE NOT NULL,
    libelle VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS permission (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(80) UNIQUE NOT NULL,
    libelle VARCHAR(180) NOT NULL
);

CREATE TABLE IF NOT EXISTS role_permission (
    role_id BIGINT REFERENCES _role(id) ON DELETE CASCADE,
    permission_id BIGINT REFERENCES permission(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS _user (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    agent_id BIGINT REFERENCES agent(id),
    nom_utilisateur VARCHAR(80) UNIQUE NOT NULL,
    mot_de_passe_hash TEXT NOT NULL,
    role_id BIGINT NOT NULL REFERENCES _role(id),
    actif BOOLEAN NOT NULL DEFAULT TRUE,
    derniere_connexion TIMESTAMPTZ,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Journal d'audit (qui a fait quoi : ajout, modification, suppression, connexion...)
CREATE TABLE IF NOT EXISTS journal_audit (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    action VARCHAR(60) NOT NULL,          -- ex. document.creer, connexion.echec
    entite VARCHAR(60),                   -- ex. document, utilisateur
    entite_id BIGINT,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    adresse_ip INET,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Conversations du chatbot
CREATE TABLE IF NOT EXISTS conversation (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    titre VARCHAR(200),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS message (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES conversation(id) ON DELETE CASCADE,
    emetteur VARCHAR(10) NOT NULL CHECK (emetteur IN ('utilisateur', 'assistant')),
    contenu TEXT NOT NULL,
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,   -- documents cités : id, titre, page, extrait court
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
