"""P4 contract rev 7, Section 5 -- review and marketing-reuse approval are audit-logged on EVERY successful call.

Contract text under test: "a PM/Director may re-review an attachment at any time (the review action simply overwrites
review_status/reviewed_by_id/reviewed_at again, audit-logged each time it's called, not only the first)" and "the
complete approve/revoke/approve history lives in the audit log, never in the columns alone".

Scope: POST /attachments/{id}/review, /marketing-reuse/approve, /marketing-reuse/revoke. Each successful call writes one
audit row (document_type "attachment", document_id = that attachment version's own id, field = review_status or
marketing_reuse) in the SAME transaction as the change. A refused request changes nothing and writes no audit row.
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from app.api.attachments import AttachmentOut
from app.core.security import hash_password
from app.models.attachment import Attachment
from app.models.audit_log import AuditLogEntry
from app.models.user import User, UserRole
from tests.test_p4_document_library import _director_headers, _draft_cost_sheet, _login, _supersede, _upload

DOC_TYPE = "attachment"


def _entries(db: Session, attachment_id) -> list[AuditLogEntry]:
    db.expire_all()
    return (
        db.query(AuditLogEntry)
        .filter(AuditLogEntry.document_type == DOC_TYPE, AuditLogEntry.document_id == uuid.UUID(str(attachment_id)))
        .order_by(AuditLogEntry.timestamp)
        .all()
    )


def _all_attachment_entries(db: Session) -> int:
    db.expire_all()
    return db.query(AuditLogEntry).filter(AuditLogEntry.document_type == DOC_TYPE).count()


def _attachment(db: Session, attachment_id) -> Attachment:
    db.expire_all()
    return db.get(Attachment, uuid.UUID(str(attachment_id)))


def _state(db: Session, attachment_id) -> dict:
    a = _attachment(db, attachment_id)
    return {
        "review_status": a.review_status, "reviewed_by_id": a.reviewed_by_id, "reviewed_at": a.reviewed_at,
        "approved_at": a.marketing_reuse_approved_at, "approved_by": a.marketing_reuse_approved_by_id,
        "revoked_at": a.marketing_reuse_revoked_at, "revoked_by": a.marketing_reuse_revoked_by_id,
    }


def _setup(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id, _ = _draft_cost_sheet(client, headers)
    attachment = _upload(client, headers, "cost_sheet", cost_sheet_id, "photo").json()
    return headers, attachment


def _user_headers(client, db_session, role: UserRole):
    email = f"{role.value}-p4audit@test.local"
    if not db_session.query(User).filter(User.email == email).first():
        db_session.add(User(name=f"Test {role.value}", email=email, hashed_password=hash_password("TestPass!1"), role=role))
        db_session.commit()
    return _login(client, email)


# ---------------------------------------------------------------------------
# Every successful call is audited, including repeats
# ---------------------------------------------------------------------------


def test_every_review_call_is_audited_including_repeats(client, director_user, db_session):
    headers, attachment = _setup(client, director_user)
    aid = attachment["id"]
    assert _entries(db_session, aid) == []

    for status in ("approved", "approved", "rejected"):  # the second call repeats the first, unchanged
        assert client.post(f"/attachments/{aid}/review", json={"status": status}, headers=headers).status_code == 200

    rows = _entries(db_session, aid)
    assert [(r.field, r.old_value, r.new_value) for r in rows] == [
        ("review_status", None, "approved"),
        ("review_status", "approved", "approved"),  # a repeat is still an audited call, not silently skipped
        ("review_status", "approved", "rejected"),
    ]
    director = db_session.query(User).filter(User.email == "director@test.local").one()
    for row in rows:
        assert row.user_id == director.id and row.role == "director"
        assert row.timestamp is not None
        assert row.ip == "testclient"
        assert "version 1" in (row.reason or "")


def test_marketing_reuse_approve_revoke_approve_history_is_in_the_audit_log(client, director_user, db_session):
    headers, attachment = _setup(client, director_user)
    aid = attachment["id"]
    calls = ["approve", "approve", "revoke", "approve"]  # approve twice in a row, then revoke, then re-approve
    for call in calls:
        assert client.post(f"/attachments/{aid}/marketing-reuse/{call}", headers=headers).status_code == 200

    rows = _entries(db_session, aid)
    assert [(r.field, r.old_value, r.new_value) for r in rows] == [
        ("marketing_reuse", None, "approved"),
        ("marketing_reuse", "approved", "approved"),
        ("marketing_reuse", "approved", "revoked"),
        ("marketing_reuse", "revoked", "approved"),
    ]
    # The columns only hold the LAST state (the re-approval cleared the revocation); the history is in the log.
    state = _state(db_session, aid)
    assert state["revoked_at"] is None and state["approved_at"] is not None


def test_review_and_marketing_reuse_are_independent_in_the_log(client, director_user, db_session):
    headers, attachment = _setup(client, director_user)
    aid = attachment["id"]
    client.post(f"/attachments/{aid}/review", json={"status": "approved"}, headers=headers)
    client.post(f"/attachments/{aid}/marketing-reuse/approve", headers=headers)
    assert [r.field for r in _entries(db_session, aid)] == ["review_status", "marketing_reuse"]


def test_the_audit_entry_names_the_exact_version_it_was_made_on(client, director_user, db_session):
    headers, v1 = _setup(client, director_user)
    v2 = _supersede(client, headers, v1["id"]).json()
    assert client.post(f"/attachments/{v2['id']}/review", json={"status": "approved"}, headers=headers).status_code == 200

    assert _entries(db_session, v1["id"]) == []  # the superseded version is untouched
    (row,) = _entries(db_session, v2["id"])
    assert row.document_id == uuid.UUID(v2["id"]) and "version 2" in (row.reason or "")


def test_an_admin_sees_the_entry_but_not_its_values(client, director_user, db_session):
    """Amendment 59: 'attachment' is not an Admin-visible document type, so the generic masking hides old/new values."""
    headers, attachment = _setup(client, director_user)
    client.post(f"/attachments/{attachment['id']}/review", json={"status": "approved"}, headers=headers)
    admin = User(name="A", email="admin-p4audit@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.ADMIN)
    db_session.add(admin)
    db_session.commit()
    res = client.get("/audit-log", headers=_login(client, "admin-p4audit@test.local"))
    assert res.status_code == 200, res.text
    mine = [e for e in res.json() if e["document_type"] == DOC_TYPE]
    assert mine and all(e["new_value"] == "(hidden for your role)" for e in mine)


# ---------------------------------------------------------------------------
# Refused requests change nothing and write no successful-action entry
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("role", [UserRole.SALES, UserRole.PROCUREMENT, UserRole.SITE_ENGINEER, UserRole.CA_TAX,
                                  UserRole.ADMIN, UserRole.MARKETING])
def test_roles_outside_pm_and_director_are_refused_without_a_trace(client, director_user, db_session, role):
    headers, attachment = _setup(client, director_user)
    aid = attachment["id"]
    before = _state(db_session, aid)
    other = _user_headers(client, db_session, role)

    for res in (
        client.post(f"/attachments/{aid}/review", json={"status": "approved"}, headers=other),
        client.post(f"/attachments/{aid}/marketing-reuse/approve", headers=other),
        client.post(f"/attachments/{aid}/marketing-reuse/revoke", headers=other),
    ):
        assert res.status_code == 403, res.text
    assert _state(db_session, aid) == before
    assert _all_attachment_entries(db_session) == 0


def test_unauthenticated_requests_are_refused_without_a_trace(client, director_user, db_session):
    _, attachment = _setup(client, director_user)
    aid = attachment["id"]
    for path, body in ((f"/attachments/{aid}/review", {"status": "approved"}),
                       (f"/attachments/{aid}/marketing-reuse/approve", None),
                       (f"/attachments/{aid}/marketing-reuse/revoke", None)):
        assert client.post(path, json=body).status_code == 401
    assert _all_attachment_entries(db_session) == 0


def test_unknown_attachment_and_invalid_input_write_nothing(client, director_user, db_session):
    headers, attachment = _setup(client, director_user)
    aid = attachment["id"]
    before = _state(db_session, aid)
    missing = uuid.uuid4()

    assert client.post(f"/attachments/{missing}/review", json={"status": "approved"}, headers=headers).status_code == 404
    assert client.post(f"/attachments/{missing}/marketing-reuse/approve", headers=headers).status_code == 404
    assert client.post(f"/attachments/{missing}/marketing-reuse/revoke", headers=headers).status_code == 404
    assert client.post(f"/attachments/{aid}/review", json={"status": "bogus"}, headers=headers).status_code == 422
    # Revoking something never approved is refused by the existing rule, not audited.
    assert client.post(f"/attachments/{aid}/marketing-reuse/revoke", headers=headers).status_code == 400

    assert _state(db_session, aid) == before
    assert _all_attachment_entries(db_session) == 0


def test_an_agreement_file_cannot_be_approved_for_marketing_and_nothing_is_written(client, director_user, db_session):
    """Existing P5 rule: a signed Agreement is not marketing material. Uses a real Agreement (drafted for a Won
    quotation) with a real uploaded signed-document file -- no rewritten rows -- and expects exactly HTTP 409, with no
    change to the attachment and no audit entry."""
    from tests.p5_helpers import draft_agreement, upload_agreement_document
    from tests.test_work_orders import _won_quotation

    headers = _director_headers(client, director_user)
    _project_id, quotation_id = _won_quotation(client, headers)
    agreement = draft_agreement(client, headers, quotation_id)
    attachment = upload_agreement_document(client, headers, agreement["id"])
    assert attachment["doc_type"] == "agreement" and attachment["doc_id"] == agreement["id"]
    before = _state(db_session, attachment["id"])

    res = client.post(f"/attachments/{attachment['id']}/marketing-reuse/approve", headers=headers)

    assert res.status_code == 409, res.text
    assert "not marketing material" in res.json()["detail"]
    assert _state(db_session, attachment["id"]) == before
    assert before["approved_at"] is None
    assert _all_attachment_entries(db_session) == 0


# ---------------------------------------------------------------------------
# One transaction: the change and its audit entry stand or fall together
# ---------------------------------------------------------------------------

_CALLS = [
    ("review", lambda c, aid, h: c.post(f"/attachments/{aid}/review", json={"status": "approved"}, headers=h)),
    ("approve", lambda c, aid, h: c.post(f"/attachments/{aid}/marketing-reuse/approve", headers=h)),
]


@pytest.mark.parametrize("name,call", _CALLS, ids=[c[0] for c in _CALLS])
def test_a_failing_audit_write_rolls_the_business_change_back(client, director_user, db_session, monkeypatch, name, call):
    """If the audit entry cannot be written, the attachment change must not be committed either."""
    headers, attachment = _setup(client, director_user)
    aid = attachment["id"]
    before = _state(db_session, aid)

    def boom(*args, **kwargs):
        raise RuntimeError("audit store unavailable")

    monkeypatch.setattr("app.api.attachments.write_audit_log_entry", boom)
    with pytest.raises(RuntimeError, match="audit store unavailable"):
        call(client, aid, headers)
    db_session.rollback()  # what closing the request's session does in production (app/db/session.py get_db)

    monkeypatch.undo()
    assert _state(db_session, aid) == before
    assert _all_attachment_entries(db_session) == 0


@pytest.mark.parametrize("name,call", _CALLS, ids=[c[0] for c in _CALLS])
def test_a_failing_commit_leaves_neither_the_change_nor_an_audit_row(client, director_user, db_session, monkeypatch, name, call):
    """If the commit itself fails, the audit row that was staged with the change must not survive either."""
    headers, attachment = _setup(client, director_user)
    aid = attachment["id"]
    before = _state(db_session, aid)

    real_commit = db_session.commit

    def failing_commit():
        raise RuntimeError("commit failed")

    monkeypatch.setattr(db_session, "commit", failing_commit)
    with pytest.raises(RuntimeError, match="commit failed"):
        call(client, aid, headers)
    monkeypatch.setattr(db_session, "commit", real_commit)
    db_session.rollback()

    assert _state(db_session, aid) == before
    assert _all_attachment_entries(db_session) == 0


def test_the_audit_row_is_staged_with_the_change_before_the_single_commit(client, director_user, db_session, monkeypatch):
    """At the moment of the one commit, the audit row is already in the same session as the change."""
    headers, attachment = _setup(client, director_user)
    aid = attachment["id"]
    seen = {}
    real_commit = db_session.commit

    def spying_commit():
        seen["pending_audit"] = [o for o in db_session.new if isinstance(o, AuditLogEntry)]
        seen["dirty_attachment"] = any(isinstance(o, Attachment) for o in db_session.dirty)
        return real_commit()

    monkeypatch.setattr(db_session, "commit", spying_commit)
    assert client.post(f"/attachments/{aid}/review", json={"status": "approved"}, headers=headers).status_code == 200
    assert len(seen["pending_audit"]) == 1 and seen["dirty_attachment"] is True


# ---------------------------------------------------------------------------
# Existing contracts are unchanged
# ---------------------------------------------------------------------------


def test_response_contract_and_state_changes_are_unchanged(client, director_user, db_session):
    headers, attachment = _setup(client, director_user)
    aid = attachment["id"]

    for res in (
        client.post(f"/attachments/{aid}/review", json={"status": "approved"}, headers=headers),
        client.post(f"/attachments/{aid}/marketing-reuse/approve", headers=headers),
        client.post(f"/attachments/{aid}/marketing-reuse/revoke", headers=headers),
    ):
        assert res.status_code == 200, res.text
        assert set(res.json().keys()) == set(AttachmentOut.model_fields.keys())

    state = _state(db_session, aid)
    director = db_session.query(User).filter(User.email == "director@test.local").one()
    assert state["review_status"] == "approved" and state["reviewed_by_id"] == director.id
    assert state["revoked_at"] is not None and state["revoked_by"] == director.id
