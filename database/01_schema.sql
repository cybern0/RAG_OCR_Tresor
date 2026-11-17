-- 01 - Schéma complet de la GED hiérarchique : Direction -> Service -> Division -> dossiers et sous-dossiers libres -> fichiers.
--
-- Base NEUVE uniquement (aucune migration). Tout ou rien : une seule transaction, arrêt à la première erreur.
--   psql -U postgres -d rag -v ON_ERROR_STOP=1 -f database/01_schema.sql
-- puis 02_donnees_reference.sql, puis 03_verification.sql (contrôle), puis seed.sql (démonstration, facultatif).
-- Ordre d'exécution complet des six scripts et précautions : docs/ordre_execution_sql.md. Aucune migration :
-- la base naît directement conforme (la refonte « suppression du chef de service » est fusionnée ici, sans ALTER).
--
-- Garanties portées par la BASE (et pas seulement par l'API) :
--   * un seul chef de division actif par division et un seul chef de service actif par service (index uniques partiels) ;
--   * un agent est toujours d'un service ET d'une division de ce service (clé étrangère composite) ;
--   * un dossier, un sous-dossier, un fichier et les rôles d'un fichier restent dans UNE division (clés étrangères composites) ;
--   * l'historique de traçabilité est en ajout seul, chaîné par hash calculé par la base (déclencheurs).
-- La dimension des embeddings (768, EmbeddingGemma) est à changer ici si le modèle change ; ils sont toujours normalisés (norme 1).

BEGIN;

CREATE SCHEMA rag_sys;
SET search_path TO rag_sys, public;
CREATE EXTENSION IF NOT EXISTS vector SCHEMA public;

CREATE FUNCTION maj_modifie_le() RETURNS trigger AS $$
BEGIN
    NEW.modifie_le := NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 1. Organisation -----------------------------------------------------------------------------------------------------

CREATE TABLE direction (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(30) NOT NULL UNIQUE,
    nom VARCHAR(180) NOT NULL,
    actif BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE _service (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    direction_id BIGINT NOT NULL REFERENCES direction(id),
    code VARCHAR(30) NOT NULL UNIQUE,
    nom VARCHAR(180) NOT NULL,
    site VARCHAR(150),
    actif BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX idx_service_direction ON _service (direction_id);

CREATE TABLE division (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    service_id BIGINT NOT NULL REFERENCES _service(id),
    code VARCHAR(30) UNIQUE,
    nom VARCHAR(180) NOT NULL,
    actif BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_division_service_nom UNIQUE (service_id, nom),
    CONSTRAINT uq_division_id_service UNIQUE (id, service_id)  -- cible de la clé composite de agent
);
CREATE INDEX idx_division_service ON division (service_id);

-- Un agent appartient à UN service et, sauf s'il est chef de service, à UNE division de ce service.
-- Le titre vaut rôle d'administration : CHEF_DIVISION (avec division), CHEF_SERVICE (sans division :
-- le même rôle que le chef de division, étendu à toutes les divisions de son service) ou vide.
-- Les mots de passe de dossier restent réservés au super administrateur (rôle global ADMIN).
CREATE TABLE agent (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    matricule VARCHAR(50) NOT NULL UNIQUE,
    nom VARCHAR(100) NOT NULL,
    prenom VARCHAR(100) NOT NULL,
    fonction VARCHAR(150),
    email VARCHAR(180),
    service_id BIGINT NOT NULL REFERENCES _service(id),
    division_id BIGINT,
    titre VARCHAR(30) CHECK (titre IN ('CHEF_DIVISION', 'CHEF_SERVICE')),
    actif BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT fk_agent_division_service FOREIGN KEY (division_id, service_id) REFERENCES division (id, service_id),
    CONSTRAINT ck_agent_titre_division CHECK (
        titre IS NULL
        OR (titre = 'CHEF_DIVISION' AND division_id IS NOT NULL)
        OR (titre = 'CHEF_SERVICE' AND division_id IS NULL)
    )
);
CREATE INDEX idx_agent_service_division ON agent (service_id, division_id);
CREATE UNIQUE INDEX uq_chef_division ON agent (division_id) WHERE titre = 'CHEF_DIVISION' AND actif;
CREATE UNIQUE INDEX uq_chef_service ON agent (service_id) WHERE titre = 'CHEF_SERVICE' AND actif;

-- 2. Comptes, rôles globaux, permissions ------------------------------------------------------------------------------

CREATE TABLE permission (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(80) NOT NULL UNIQUE,
    libelle VARCHAR(180) NOT NULL
);

CREATE TABLE _role (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    code VARCHAR(30) NOT NULL UNIQUE,
    libelle VARCHAR(100) NOT NULL
);

CREATE TABLE role_permission (
    role_id BIGINT NOT NULL REFERENCES _role(id) ON DELETE CASCADE,
    permission_id BIGINT NOT NULL REFERENCES permission(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE _user (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    agent_id BIGINT REFERENCES agent(id),
    nom_utilisateur VARCHAR(80) NOT NULL UNIQUE,
    mot_de_passe_hash TEXT NOT NULL,
    role_id BIGINT NOT NULL REFERENCES _role(id),
    actif BOOLEAN NOT NULL DEFAULT TRUE,
    derniere_connexion TIMESTAMPTZ,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX uq_user_agent ON _user (agent_id) WHERE agent_id IS NOT NULL;  -- un compte par agent
CREATE INDEX idx_user_role ON _user (role_id);

-- 3. Journal d'audit technique (connexions, échecs...) et chat -----------------------------------------------------------

CREATE TABLE journal_audit (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    action VARCHAR(60) NOT NULL,
    entite VARCHAR(60),
    entite_id BIGINT,
    detail JSONB NOT NULL DEFAULT '{}'::jsonb,
    adresse_ip INET,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_audit_user_date ON journal_audit (user_id, cree_le DESC);
CREATE INDEX idx_audit_entite ON journal_audit (entite, entite_id);

CREATE TABLE conversation (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    titre VARCHAR(200),
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_conversation_user_date ON conversation (user_id, cree_le DESC);

CREATE TABLE message (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    conversation_id BIGINT NOT NULL REFERENCES conversation(id) ON DELETE CASCADE,
    emetteur VARCHAR(15) NOT NULL CHECK (emetteur IN ('utilisateur', 'assistant')),
    contenu TEXT NOT NULL,
    sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_message_conversation ON message (conversation_id, cree_le);

CREATE TABLE preference_utilisateur (
    user_id BIGINT PRIMARY KEY REFERENCES _user(id) ON DELETE CASCADE,
    memoire_inter_sessions BOOLEAN NOT NULL DEFAULT FALSE,
    derniere_version_seulement BOOLEAN NOT NULL DEFAULT FALSE
);

-- Résultats retenus d'une session. document_ids : fichiers dont viennent les passages cités ; l'entrée n'est réutilisée que si
-- l'utilisateur a encore accès à TOUS ces fichiers (pas de clé étrangère : un fichier supprimé rend l'entrée muette).
CREATE TABLE memoire_chat (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    conversation_id BIGINT REFERENCES conversation(id) ON DELETE CASCADE,
    resume TEXT NOT NULL,
    document_ids BIGINT[] NOT NULL DEFAULT '{}',
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_memoire_user_date ON memoire_chat (user_id, cree_le DESC);

-- 4. Classement documentaire (catégories, types, étiquettes, règles) --------------------------------------------------------

CREATE TABLE categorie (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    parent_id BIGINT REFERENCES categorie(id) ON DELETE SET NULL,
    nom VARCHAR(120) NOT NULL,
    couleur VARCHAR(9),
    ordre INT NOT NULL DEFAULT 0,
    actif BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE type_document (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nom VARCHAR(120) NOT NULL UNIQUE,
    actif BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE tag (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    nom VARCHAR(60) NOT NULL
);
CREATE UNIQUE INDEX uq_tag_nom ON tag (lower(nom));

CREATE TABLE regle_classement (
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

-- 5. Dossiers, sous-dossiers, fichiers, versions, passages vectoriels ------------------------------------------------------

-- Un dossier appartient à UNE division ; un sous-dossier reste dans la division de son parent (clé composite).
-- Un dossier et ses sous-dossiers n'ont ni login, ni mot de passe, ni rôle : ils sont visibles de toute la division.
CREATE TABLE dossier (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    division_id BIGINT NOT NULL REFERENCES division(id),
    parent_id BIGINT,
    nom VARCHAR(150) NOT NULL,
    description TEXT,
    archive BOOLEAN NOT NULL DEFAULT FALSE,
    cree_par BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    modifie_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_dossier_id_division UNIQUE (id, division_id),
    CONSTRAINT fk_dossier_parent FOREIGN KEY (parent_id, division_id) REFERENCES dossier (id, division_id),
    CONSTRAINT ck_dossier_pas_son_parent CHECK (parent_id IS NULL OR parent_id <> id)
);
CREATE UNIQUE INDEX uq_dossier_nom ON dossier (division_id, COALESCE(parent_id, 0), lower(nom));
CREATE INDEX idx_dossier_parent ON dossier (parent_id);
CREATE TRIGGER trg_dossier_modifie_le BEFORE UPDATE ON dossier FOR EACH ROW EXECUTE FUNCTION maj_modifie_le();

CREATE TABLE document (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dossier_id BIGINT NOT NULL,
    division_id BIGINT NOT NULL REFERENCES division(id),
    titre VARCHAR(250) NOT NULL,
    categorie_id BIGINT REFERENCES categorie(id) ON DELETE SET NULL,
    type_document_id BIGINT REFERENCES type_document(id) ON DELETE SET NULL,
    confidentialite VARCHAR(15) NOT NULL DEFAULT 'INTERNE' CHECK (confidentialite IN ('PUBLIC', 'INTERNE', 'CONFIDENTIEL')),
    classement_source VARCHAR(10) NOT NULL DEFAULT 'aucun' CHECK (classement_source IN ('aucun', 'regle', 'manuel')),
    regle_id BIGINT,
    cree_par_service_id BIGINT REFERENCES _service(id) ON DELETE SET NULL,
    corbeille_le TIMESTAMPTZ,
    has_tabular BOOLEAN NOT NULL DEFAULT FALSE,
    has_image BOOLEAN NOT NULL DEFAULT FALSE,
    cree_par BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    modifie_par BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    modifie_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_document_id_division UNIQUE (id, division_id),
    CONSTRAINT fk_document_dossier_division FOREIGN KEY (dossier_id, division_id) REFERENCES dossier (id, division_id)
);
CREATE INDEX idx_document_dossier ON document (dossier_id);
CREATE INDEX idx_document_division ON document (division_id);
CREATE INDEX idx_document_categorie ON document (categorie_id);
CREATE INDEX idx_document_type_document ON document (type_document_id);
CREATE INDEX idx_document_confidentialite ON document (confidentialite);
CREATE INDEX idx_document_cree_par ON document (cree_par);
CREATE INDEX idx_document_cree_le ON document (cree_le DESC);
CREATE TRIGGER trg_document_modifie_le BEFORE UPDATE ON document FOR EACH ROW EXECUTE FUNCTION maj_modifie_le();

CREATE TABLE document_tag (
    document_id BIGINT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    tag_id BIGINT NOT NULL REFERENCES tag(id) ON DELETE CASCADE,
    source VARCHAR(10) NOT NULL DEFAULT 'manuel' CHECK (source IN ('manuel', 'regle')),
    PRIMARY KEY (document_id, tag_id)
);

-- Chaque dépôt d'un fichier est une version numérotée et datée, jamais supprimée par un nouveau dépôt.
CREATE TABLE document_version (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    numero INTEGER NOT NULL CHECK (numero >= 1),
    nom_fichier VARCHAR(255) NOT NULL,
    type_mime VARCHAR(120),
    taille_octets BIGINT CHECK (taille_octets >= 0),
    hash_sha256 CHAR(64) NOT NULL,
    chemin_stockage TEXT NOT NULL,
    nb_pages INTEGER CHECK (nb_pages >= 0),
    ocr_utilise BOOLEAN NOT NULL DEFAULT FALSE,
    statut VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (statut IN ('pending', 'processing', 'ready', 'error')),
    message_erreur TEXT,
    cree_par BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_version_document_numero UNIQUE (document_id, numero)
);
CREATE INDEX idx_version_document ON document_version (document_id, numero DESC);
CREATE INDEX idx_version_statut ON document_version (statut);
CREATE INDEX idx_version_hash ON document_version (hash_sha256);

CREATE TABLE chunk (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    document_version_id BIGINT NOT NULL REFERENCES document_version(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
    page INTEGER CHECK (page >= 1),
    contenu TEXT NOT NULL,
    est_tableau BOOLEAN NOT NULL DEFAULT FALSE,
    taille_ref INTEGER NOT NULL DEFAULT 0 CHECK (taille_ref >= 0),  -- nombre de chunks de la version (top-k dynamique)
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding vector(768) NOT NULL,
    contenu_tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('french', contenu)) STORED,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_chunk_version_index UNIQUE (document_version_id, chunk_index),
    -- tolérance de 0,1 % : les vecteurs sont stockés en float32
    CONSTRAINT ck_chunk_embedding_normalise CHECK (vector_norm(embedding) BETWEEN 0.999 AND 1.001)
);
CREATE INDEX idx_chunk_version ON chunk (document_version_id);
CREATE INDEX idx_chunk_document ON chunk (document_id);
CREATE INDEX idx_chunk_tsv ON chunk USING gin (contenu_tsv);
CREATE INDEX idx_chunk_metadata ON chunk USING gin (metadata jsonb_path_ops);
-- produit scalaire (<#>), exact pour le classement car les vecteurs sont normalisés ; ne pas mélanger avec <=> ou <->
CREATE INDEX idx_chunk_embedding ON chunk USING hnsw (embedding vector_ip_ops);

CREATE TABLE commentaire (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    sujet_type VARCHAR(20) NOT NULL CHECK (sujet_type IN ('document', 'dossier')),
    sujet_id BIGINT NOT NULL,
    auteur_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    contenu TEXT NOT NULL,
    parent_id BIGINT REFERENCES commentaire(id) ON DELETE CASCADE,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_commentaire_sujet ON commentaire (sujet_type, sujet_id);

-- 6. Rôles métier par division, classement des fichiers ---------------------------------------------------------------------

CREATE TABLE role_division (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    division_id BIGINT NOT NULL REFERENCES division(id),
    code VARCHAR(60) NOT NULL,
    libelle VARCHAR(180) NOT NULL,
    actif BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_role_division_id UNIQUE (id, division_id)
);
CREATE UNIQUE INDEX uq_role_division_code ON role_division (division_id, lower(code));

CREATE TABLE user_role_division (
    user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    role_division_id BIGINT NOT NULL REFERENCES role_division(id) ON DELETE CASCADE,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (user_id, role_division_id)
);
CREATE INDEX idx_user_role_division_role ON user_role_division (role_division_id);

-- Rôles de classement d'un fichier : le rôle et le fichier sont de la MÊME division (clés composites).
CREATE TABLE document_role (
    document_id BIGINT NOT NULL,
    role_division_id BIGINT NOT NULL,
    division_id BIGINT NOT NULL,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (document_id, role_division_id),
    CONSTRAINT fk_document_role_document FOREIGN KEY (document_id, division_id)
        REFERENCES document (id, division_id) ON DELETE CASCADE,
    CONSTRAINT fk_document_role_role FOREIGN KEY (role_division_id, division_id)
        REFERENCES role_division (id, division_id) ON DELETE CASCADE
);
CREATE INDEX idx_document_role_role ON document_role (role_division_id);

-- 7. Demandes d'accès et exceptions ponctuelles -----------------------------------------------------------------------------

CREATE TABLE demande_acces (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    demandeur_user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    division_id BIGINT NOT NULL REFERENCES division(id),
    type_demande VARCHAR(10) NOT NULL CHECK (type_demande IN ('role', 'fichier')),
    role_division_id BIGINT REFERENCES role_division(id) ON DELETE CASCADE,
    document_id BIGINT REFERENCES document(id) ON DELETE CASCADE,
    motif TEXT NOT NULL,
    duree_heures INTEGER CHECK (duree_heures BETWEEN 1 AND 720),
    statut VARCHAR(12) NOT NULL DEFAULT 'en_attente' CHECK (statut IN ('en_attente', 'acceptee', 'refusee', 'annulee')),
    decisionnaire_user_id BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    reponse TEXT,
    date_creation TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    date_decision TIMESTAMPTZ,
    CONSTRAINT ck_demande_cible CHECK (
        (type_demande = 'role' AND role_division_id IS NOT NULL AND document_id IS NULL)
        OR (type_demande = 'fichier' AND document_id IS NOT NULL AND role_division_id IS NULL)
    )
);
CREATE UNIQUE INDEX uq_demande_attente_role ON demande_acces (demandeur_user_id, role_division_id)
    WHERE statut = 'en_attente' AND role_division_id IS NOT NULL;
CREATE UNIQUE INDEX uq_demande_attente_fichier ON demande_acces (demandeur_user_id, document_id)
    WHERE statut = 'en_attente' AND document_id IS NOT NULL;
CREATE INDEX idx_demande_division_statut ON demande_acces (division_id, statut);

-- Accès ponctuel à un fichier : valable jusqu'à expire_le, sans modifier les rôles de l'agent.
CREATE TABLE acces_exception (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    document_id BIGINT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    demande_id BIGINT REFERENCES demande_acces(id) ON DELETE SET NULL,
    accorde_par BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    motif TEXT,
    expire_le TIMESTAMPTZ NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_exception_user_doc ON acces_exception (user_id, document_id) WHERE active;

-- 8. Mots de passe de dossier (divisions) et déverrouillages ---------------------------------------------------------------------

-- Les dossiers protégés existent au niveau des DIVISIONS seulement (aucun dossier ni mot de passe de service) :
-- un secret par couple (division, super administrateur). Les chefs (division ou service) n'en ont pas :
-- le mot de passe de dossier appartient au seul super administrateur, qui le gère pour toutes les divisions.
CREATE TABLE secret_unite (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    division_id BIGINT NOT NULL REFERENCES division(id) ON DELETE CASCADE,
    admin_user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    secret_hash TEXT NOT NULL,
    modifie_par BIGINT REFERENCES _user(id) ON DELETE SET NULL,
    modifie_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX uq_secret_division ON secret_unite (division_id, admin_user_id);

CREATE TABLE deverrouillage (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    secret_unite_id BIGINT NOT NULL REFERENCES secret_unite(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    valide_jusqua TIMESTAMPTZ NOT NULL,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actif BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE INDEX idx_deverrouillage_user ON deverrouillage (user_id) WHERE actif;

-- 9. Historique de traçabilité : en ajout seul, chaîné par hash (calculé par la base) --------------------------------------------
-- Pas de clé étrangère : c'est un registre immuable (supprimer un compte ou une division ne doit ni modifier ni bloquer l'historique).

CREATE TABLE historique_modification (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    rang BIGINT NOT NULL UNIQUE,                 -- position dans la chaîne, attribuée par le déclencheur
    acteur_user_id BIGINT,
    acteur_nom VARCHAR(80),
    concerne_user_id BIGINT,                     -- compte touché par l'action (pour « ce qui me concerne »)
    cible_type VARCHAR(40) NOT NULL,
    cible_id BIGINT,
    action VARCHAR(60) NOT NULL,
    avant TEXT,
    apres TEXT,
    motif TEXT,
    service_id BIGINT,
    division_id BIGINT,
    date_action TIMESTAMPTZ NOT NULL DEFAULT clock_timestamp(),
    hash_precedent CHAR(64),
    hash_courant CHAR(64) NOT NULL
);
CREATE INDEX idx_historique_cible ON historique_modification (cible_type, cible_id);
CREATE INDEX idx_historique_division ON historique_modification (division_id, rang DESC);
CREATE INDEX idx_historique_service ON historique_modification (service_id, rang DESC);
CREATE INDEX idx_historique_concerne ON historique_modification (concerne_user_id, rang DESC);

CREATE FUNCTION calcul_hash_historique(h historique_modification) RETURNS text
LANGUAGE sql STABLE SET search_path = rag_sys, public AS $$
    SELECT encode(sha256(convert_to(jsonb_build_array(
        h.rang, COALESCE(h.hash_precedent, ''), h.acteur_user_id, h.acteur_nom, h.concerne_user_id,
        h.cible_type, h.cible_id, h.action, h.avant, h.apres, h.motif, h.service_id, h.division_id,
        to_char(h.date_action AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US')
    )::text, 'UTF8')), 'hex')
$$;

CREATE FUNCTION trg_historique_chainage() RETURNS trigger
LANGUAGE plpgsql SET search_path = rag_sys, public AS $$
DECLARE
    dernier RECORD;
BEGIN
    -- une seule écriture à la fois dans la chaîne (verrou levé en fin de transaction)
    PERFORM pg_advisory_xact_lock(hashtext('rag_sys.historique_modification'));
    SELECT rang, hash_courant INTO dernier FROM historique_modification ORDER BY rang DESC LIMIT 1;
    IF FOUND THEN
        NEW.rang := dernier.rang + 1;
        NEW.hash_precedent := dernier.hash_courant;
    ELSE
        NEW.rang := 1;
        NEW.hash_precedent := NULL;
    END IF;
    NEW.hash_courant := calcul_hash_historique(NEW);
    RETURN NEW;
END;
$$;
CREATE TRIGGER trg_historique_chainage BEFORE INSERT ON historique_modification
    FOR EACH ROW EXECUTE FUNCTION trg_historique_chainage();

CREATE FUNCTION trg_historique_immuable() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'historique_modification est en ajout seul : % refusé', TG_OP USING ERRCODE = 'restrict_violation';
END;
$$;
CREATE TRIGGER trg_historique_immuable BEFORE UPDATE OR DELETE ON historique_modification
    FOR EACH ROW EXECUTE FUNCTION trg_historique_immuable();
CREATE TRIGGER trg_historique_immuable_truncate BEFORE TRUNCATE ON historique_modification
    FOR EACH STATEMENT EXECUTE FUNCTION trg_historique_immuable();

-- Recalcule toute la chaîne : ok = aucune ligne altérée, aucun trou, chaque hash_precedent égal au hash de la ligne d'avant.
CREATE FUNCTION verifier_historique() RETURNS TABLE (ok boolean, total bigint, premier_rang_invalide bigint)
LANGUAGE sql STABLE SET search_path = rag_sys, public AS $$
    WITH h AS (
        SELECT t AS ligne, t.rang, t.hash_precedent, t.hash_courant,
               LAG(t.hash_courant) OVER (ORDER BY t.rang) AS precedent_reel,
               ROW_NUMBER() OVER (ORDER BY t.rang) AS position
        FROM historique_modification t
    ), mauvais AS (
        SELECT rang FROM h
        WHERE hash_courant IS DISTINCT FROM calcul_hash_historique(ligne)
           OR hash_precedent IS DISTINCT FROM precedent_reel
           OR rang <> position
    )
    SELECT NOT EXISTS (SELECT 1 FROM mauvais),
           (SELECT count(*) FROM historique_modification),
           (SELECT min(rang) FROM mauvais)
$$;

-- 10. Notifications ------------------------------------------------------------------------------------------------------------

CREATE TABLE notification (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    destinataire_user_id BIGINT NOT NULL REFERENCES _user(id) ON DELETE CASCADE,
    type_evenement VARCHAR(60) NOT NULL,
    reference_type VARCHAR(30),
    reference_id BIGINT,
    message TEXT NOT NULL,
    lu BOOLEAN NOT NULL DEFAULT FALSE,
    cree_le TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_notification_destinataire ON notification (destinataire_user_id, lu, cree_le DESC);

-- 11. Vue des statistiques documentaires : une ligne = un fichier avec sa dernière version -------------------------------------

CREATE VIEW vue_document_stats AS
SELECT
    d.id AS document_id,
    d.dossier_id,
    d.division_id,
    d.categorie_id,
    d.type_document_id,
    d.confidentialite,
    d.corbeille_le,
    d.cree_le,
    d.cree_par,
    dv.service_id,
    s.direction_id,
    v.numero AS version_courante,
    v.statut,
    v.taille_octets,
    v.nb_pages,
    v.ocr_utilise,
    lower(substring(v.nom_fichier from '\.([^.]+)$')) AS extension,
    (SELECT count(*) FROM document_version x WHERE x.document_id = d.id) AS nb_versions
FROM document d
JOIN division dv ON dv.id = d.division_id
JOIN _service s ON s.id = dv.service_id
JOIN LATERAL (
    SELECT * FROM document_version WHERE document_id = d.id ORDER BY numero DESC LIMIT 1
) v ON TRUE;

COMMIT;
