"""PDF export controls: no selected image is dropped silently; exclusions are explicit, document-specific and attributed.

Contract under test:
  * Generation (download, send, or a direct API call) REFUSES with a structured 409 naming each excluded image and the
    reason, until the user replaces the image or explicitly removes it from THIS document.
  * /pdf-check previews the same decision but is advisory only: generation re-checks, so a stale preview cannot let an
    omission through.
  * An exclusion is a separate record for one document; the Attachment, its file and its hash are never touched, and
    other documents are unaffected. Closed documents are not changed.
  * Existing evidence rules are not changed: an image that is not part of the document cannot be 'excluded'.
"""

import hashlib
import uuid
from pathlib import Path

import pytest

from app.models.attachment import Attachment
from app.models.audit_log import AuditLogEntry
from app.models.document import Quotation, QuotationStatus
from app.models.pdf_image_exclusion import PdfImageExclusion
from tests.db_snapshot import full_snapshot
from tests.test_estimate_pdf_product_images import _draft_estimate
from tests.test_pdf_documents import _png_bytes, _sent_quotation
from tests.test_work_orders import _director_headers
from tests.valid_files import valid_png


def _photo(client, headers, quotation_id, name="p.png", content=None):
    res = client.post(
        "/attachments", data={"doc_type": "quotation", "doc_id": quotation_id, "tag": "photo"},
        files={"file": (name, content or _png_bytes(), "image/png")}, headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _stored_path(db, attachment_id):
    db.rollback()
    return Path(db.get(Attachment, uuid.UUID(attachment_id)).storage_path)


def _exclude(client, headers, doc_type, doc_id, attachment_id, reason=None):
    return client.post("/pdf-image-exclusions", json={"doc_type": doc_type, "doc_id": doc_id, "attachment_id": attachment_id, "reason": reason}, headers=headers)


@pytest.fixture()
def q(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers)
    return dict(client=client, h=headers, id=quotation["id"], db=db_session)


# ---------------------------------------------------------------- preview (advisory)


def test_preview_is_complete_for_a_clean_document_and_lists_every_exclusion_with_its_reason(q, monkeypatch):
    import app.api.pdf_documents as pdf_module

    client, h, db = q["client"], q["h"], q["db"]
    clean = client.get(f"/quotations/{q['id']}/pdf-check", headers=h).json()
    assert clean["complete"] is True and clean["excluded"] == [] and clean["included_images"] == 0

    good = _photo(client, h, q["id"], "good.png", valid_png(color=(1, 2, 3), size=(4, 4)))
    corrupt = _photo(client, h, q["id"], "corrupt.png", valid_png(color=(9, 9, 9), size=(4, 4)))
    missing = _photo(client, h, q["id"], "missing.png", valid_png(color=(5, 5, 5), size=(4, 4)))
    _stored_path(db, corrupt).write_bytes(b"not an image at all")
    _stored_path(db, missing).unlink()
    check = client.get(f"/quotations/{q['id']}/pdf-check", headers=h).json()
    reasons = {e["attachment_id"]: e["reason"] for e in check["excluded"]}
    assert reasons == {corrupt: "unreadable", missing: "file_missing"}
    assert check["complete"] is False and check["included_images"] == 1 and "preview" in check["note"].lower()
    assert good not in reasons

    monkeypatch.setattr(pdf_module, "MAX_EMBED_PIXELS", 1)
    over = {e["attachment_id"]: e["reason"] for e in client.get(f"/quotations/{q['id']}/pdf-check", headers=h).json()["excluded"]}
    assert over[good] == "over_image_budget"


def test_a_stale_preview_cannot_let_an_omission_through_generation_rechecks(q):
    """The preview said complete; the file is damaged afterwards; the real generation (a direct API call) still refuses."""
    client, h, db = q["client"], q["h"], q["db"]
    attachment = _photo(client, h, q["id"])
    assert client.get(f"/quotations/{q['id']}/pdf-check", headers=h).json()["complete"] is True
    _stored_path(db, attachment).write_bytes(b"damaged after the preview")
    res = client.get(f"/quotations/{q['id']}/pdf", headers=h)
    assert res.status_code == 409 and res.json()["detail"]["excluded"][0]["reason"] == "unreadable"
    assert not res.content.startswith(b"%PDF")  # no document was produced at all


def test_estimate_generation_enforces_the_same_rule(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    estimate = _draft_estimate(client, headers)
    option_id = estimate["options"][0]["id"]
    res = client.post(
        "/attachments", data={"doc_type": "estimate_option", "doc_id": option_id, "tag": "product_image"},
        files={"file": ("opt.png", _png_bytes(), "image/png")}, headers=headers,
    )
    assert res.status_code == 201, res.text
    _stored_path(db_session, res.json()["id"]).write_bytes(b"damaged")
    check = client.get(f"/estimates/{estimate['id']}/pdf-check", headers=headers).json()
    assert check["complete"] is False and check["excluded"][0]["reason"] == "unreadable"
    refused = client.get(f"/estimates/{estimate['id']}/pdf", headers=headers)
    assert refused.status_code == 409 and refused.json()["detail"]["code"] == "pdf_images_excluded"


# ---------------------------------------------------------------- explicit, document-specific exclusion


def test_an_exclusion_is_explicit_attributed_audited_and_leaves_the_original_untouched(q, director_user):
    client, h, db = q["client"], q["h"], q["db"]
    attachment = _photo(client, h, q["id"])
    path = _stored_path(db, attachment)
    path.write_bytes(b"damaged legacy file")
    sha_before = hashlib.sha256(path.read_bytes()).hexdigest()
    attachments_before = full_snapshot(db)["attachments"]

    res = _exclude(client, h, "quotation", q["id"], attachment, reason="blurry; client will send a new one")
    assert res.status_code == 201, res.text
    db.rollback()
    row = db.query(PdfImageExclusion).one()
    assert (str(row.doc_id), str(row.attachment_id), row.excluded_by_id) == (q["id"], attachment, director_user.id)
    assert row.reason == "blurry; client will send a new one"
    assert full_snapshot(db)["attachments"] == attachments_before  # the Attachment row is byte-for-byte unchanged (no flag)
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha_before  # and so is the stored file
    entries = db.query(AuditLogEntry).filter(AuditLogEntry.field == "pdf_image_excluded").all()
    assert len(entries) == 1 and entries[0].reason == "blurry; client will send a new one"

    again = _exclude(client, h, "quotation", q["id"], attachment)
    assert again.status_code == 201 and again.json()["id"] == res.json()["id"]  # idempotent
    assert db.query(PdfImageExclusion).count() == 1

    pdf = client.get(f"/quotations/{q['id']}/pdf", headers=h)
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"
    check = client.get(f"/quotations/{q['id']}/pdf-check", headers=h).json()
    assert check["complete"] is True  # an explicit removal is a choice, not a blocker
    assert [(e["reason"], e["user_removed"]) for e in check["excluded"]] == [("removed_by_user", True)]


def test_restoring_an_image_blocks_generation_again_and_is_audited(q):
    client, h, db = q["client"], q["h"], q["db"]
    attachment = _photo(client, h, q["id"])
    _stored_path(db, attachment).write_bytes(b"damaged")
    exclusion = _exclude(client, h, "quotation", q["id"], attachment).json()["id"]
    assert client.get(f"/quotations/{q['id']}/pdf", headers=h).status_code == 200
    assert client.delete(f"/pdf-image-exclusions/{exclusion}", headers=h).status_code == 204
    assert client.get(f"/quotations/{q['id']}/pdf", headers=h).status_code == 409
    db.rollback()
    assert db.query(AuditLogEntry).filter(AuditLogEntry.field == "pdf_image_excluded").count() == 2


def test_an_exclusion_applies_to_one_document_only(q, client_factory=None):
    """The same decision is not inherited by another document: a second quotation's own damaged photo still blocks it."""
    client, h, db = q["client"], q["h"], q["db"]
    first = _photo(client, h, q["id"])
    _stored_path(db, first).write_bytes(b"damaged")
    assert _exclude(client, h, "quotation", q["id"], first).status_code == 201
    other = _sent_quotation(client, h)
    second = _photo(client, h, other["id"])
    _stored_path(db, second).write_bytes(b"damaged too")
    assert client.get(f"/quotations/{q['id']}/pdf", headers=h).status_code == 200
    assert client.get(f"/quotations/{other['id']}/pdf", headers=h).status_code == 409  # not covered by the first decision
    db.rollback()
    assert db.query(PdfImageExclusion).count() == 1


def test_only_an_image_that_the_document_actually_includes_can_be_excluded(q):
    client, h = q["client"], q["h"]
    evidence = client.post(
        "/attachments", data={"doc_type": "quotation", "doc_id": q["id"], "tag": "reference"},
        files={"file": ("ref.png", _png_bytes(), "image/png")}, headers=h,
    ).json()["id"]
    res = _exclude(client, h, "quotation", q["id"], evidence)
    assert res.status_code == 400 and "not one of the images" in res.json()["detail"]
    assert _exclude(client, h, "quotation", q["id"], str(uuid.uuid4())).status_code == 400


def test_a_closed_document_is_not_changed_by_an_exclusion(q):
    client, h, db = q["client"], q["h"], q["db"]
    attachment = _photo(client, h, q["id"])
    db.rollback()
    quotation = db.get(Quotation, uuid.UUID(q["id"]))
    quotation.status = QuotationStatus.WON
    db.commit()
    res = _exclude(client, h, "quotation", q["id"], attachment)
    assert res.status_code == 409 and "closed" in res.json()["detail"]
    db.rollback()
    assert db.query(PdfImageExclusion).count() == 0


def test_only_document_roles_can_exclude_images(q, db_session):
    from tests.test_upload_hardening import make_user, user_headers

    client, h = q["client"], q["h"]
    attachment = _photo(client, h, q["id"])
    engineer = make_user(db_session, "site_engineer")
    res = _exclude(client, user_headers(client, engineer), "quotation", q["id"], attachment)
    assert res.status_code == 403


# ---------------------------------------------------------------- the send path uses the same enforcement


def test_sending_the_pdf_is_refused_while_a_selected_image_is_excluded_and_records_no_attempt(q):
    from app.models.message import Message

    client, h, db = q["client"], q["h"], q["db"]
    attachment = _photo(client, h, q["id"])
    _stored_path(db, attachment).write_bytes(b"damaged")
    db.rollback()
    before = db.query(Message).count()
    res = client.post(
        "/messages", json={"doc_type": "quotation", "doc_id": q["id"], "channel": "email", "recipient": "x@test.local", "include_document": True},
        headers=h,
    )
    assert res.status_code == 409 and res.json()["detail"]["code"] == "pdf_images_excluded", res.text
    db.rollback()
    assert db.query(Message).count() == before  # nothing was recorded or sent
