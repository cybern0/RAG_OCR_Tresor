from app.services.partage import (
    add_comment,
    add_notification,
    create_document_link_share,
    hash_share_token,
    make_share_payload,
    normalize_access_decision,
    normalize_access_role,
    request_access,
    resolve_access_request,
    toggle_favorite,
)


def test_hash_share_token_ne_rend_pas_le_token_clair():
    token = "token-secret-local-123"
    hashed = hash_share_token(token)
    assert hashed != token
    assert hashed.startswith("sha256:")
    assert len(hashed) > 40


def test_normalize_access_role_renvoie_une_valeur_standardisee():
    assert normalize_access_role("lecteur") == "LECTEUR"
    assert normalize_access_role("CONTRIBUTEUR") == "CONTRIBUTEUR"
    assert normalize_access_role("  gestionnaire_de_contenu  ") == "GESTIONNAIRE_DE_CONTENU"


def test_make_share_payload_produit_un_lien_local_standardise():
    payload = make_share_payload(42, role="lecture", user_id=7, base_url="https://local.test")
    assert payload["document_id"] == 42
    assert payload["role"] == "LECTEUR"
    assert payload["user_id"] == 7
    assert payload["token_hash"].startswith("sha256:")
    assert payload["link"].startswith("https://local.test/partage/")


def test_request_access_and_collaboration_helpers_are_consistent():
    demande = request_access(subject_type="document", subject_id=42, requested_by=7, requested_role="gestionnaire")
    commentaire = add_comment(entity_type="document", entity_id=42, author_id=7, content="À relire")
    notification = add_notification(user_id=7, kind="share", subject_type="document", subject_id=42, message="Partage validé")
    favori = toggle_favorite(user_id=7, entity_type="document", entity_id=42)

    assert demande.requested_role == "GESTIONNAIRE_DE_CONTENU"
    assert commentaire.content == "À relire"
    assert notification.kind == "share"
    assert favori.entity_type == "document"


def test_access_request_decision_helpers_are_consistent():
    approved = resolve_access_request(
        request_access(subject_type="document", subject_id=42, requested_by=7, requested_role="gestionnaire"),
        decision="approved",
        granted_role="contributeur",
    )
    rejected = resolve_access_request(
        request_access(subject_type="document", subject_id=42, requested_by=7, requested_role="gestionnaire"),
        decision="refusé",
    )

    assert normalize_access_decision("validé") == "accepted"
    assert approved.status == "accepted"
    assert approved.requested_role == "CONTRIBUTEUR"
    assert rejected.status == "rejected"


def test_dossier_access_request_is_same_workflow_for_dossier_subjects():
    demande = request_access(subject_type="dossier", subject_id=9, requested_by=7, requested_role="contributeur")
    accepted = resolve_access_request(demande, decision="approved", granted_role="gestionnaire")

    assert demande.subject_type == "dossier"
    assert accepted.subject_type == "dossier"
    assert accepted.requested_role == "GESTIONNAIRE_DE_CONTENU"
    assert accepted.status == "accepted"


def test_create_document_link_share_builds_a_local_share_link():
    share = create_document_link_share(document_id=42, token="link-local-abc", role="lecture", est_anonyme=False)

    assert share.document_id == 42
    assert share.role == "LECTEUR"
    assert share.est_anonyme is False
    assert share.token_hash.startswith("sha256:")


def test_toggle_favorite_is_a_real_toggle():
    class FakeSession:
        def __init__(self):
            self.items = []
            self.deleted = []

        def scalar(self, stmt):
            for item in self.items:
                if item.user_id == 7 and item.sujet_type == "document" and item.sujet_id == 42:
                    return item
            return None

        def add(self, obj):
            self.items.append(obj)

        def delete(self, obj):
            self.deleted.append(obj)
            self.items = [item for item in self.items if item is not obj]

        def commit(self):
            return None

        def refresh(self, obj):
            return None

    db = FakeSession()
    first = toggle_favorite(db, user_id=7, entity_type="document", entity_id=42)
    assert first is not None
    assert first.user_id == 7
    assert db.scalar(None) is not None

    second = toggle_favorite(db, user_id=7, entity_type="document", entity_id=42)
    assert second is None
    assert db.scalar(None) is None
