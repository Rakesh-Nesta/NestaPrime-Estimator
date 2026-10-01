"""Local-only check for scripts/delete_confirmed_test_records.py -- never runs in CI, never touches
production. Builds one client with a full real record chain (enquiry, project, cost sheet, estimate,
option, quotation, work order, an attachment, a message) through the real API, points the script at that
one client, and confirms --confirm removes it and everything under it with no FK error, leaving another
client and its own quotation untouched."""
import importlib.util
import io
import uuid
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "delete_confirmed_test_records.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("delete_confirmed_test_records", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _director_headers(client, director_user):
    from tests.test_work_orders import _login

    return _login(client, "director@test.local")


def test_deletes_the_named_client_and_everything_under_it_leaves_others_alone(client, director_user, db_session):
    from tests.test_work_orders import (
        _add_project_sport,
        _create_client_record,
        _create_project,
        _satisfy_project_readiness,
    )

    headers = _director_headers(client, director_user)

    # The client we will delete: enquiry -> project -> cost sheet -> estimate -> option -> quotation ->
    # work order, plus an attachment and a message on it.
    doomed_client_id = _create_client_record(client, headers, name="Harness Delete Test (delete me)")
    opp = client.post(
        "/opportunities", json={"lead_name": "Harness lead", "next_follow_up_date": "2099-01-01"}, headers=headers
    ).json()
    # Lost, not Won: WP6 (tightened after review) refuses a direct PATCH straight to Won
    # unconditionally now -- this test only needs a closed Opportunity in the deletion
    # chain, not specifically a Won one.
    client.patch(f"/opportunities/{opp['id']}/stage", json={"stage": "lost"}, headers=headers)
    client.patch(f"/opportunities/{opp['id']}/link-client", json={"client_id": doomed_client_id}, headers=headers)
    project_id = _create_project(client, headers, doomed_client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": 500000}, headers=headers
    ).json()["id"]
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    _satisfy_project_readiness(client, headers, project_id)
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 500000}]},
        headers=headers,
    ).json()
    option_id = estimate["options"][0]["id"]
    client.patch(
        f"/estimates/{estimate['id']}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    quotation_id = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id]},
        headers=headers,
    ).json()["id"]
    client.post(f"/quotations/{quotation_id}/release", headers=headers)
    client.post(f"/quotations/{quotation_id}/send", headers=headers)
    client.post(
        f"/quotations/{quotation_id}/mark-won", json={"reason": "test", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    work_order = client.post(f"/quotations/{quotation_id}/work-order", headers=headers).json()
    att = client.post(
        "/attachments",
        data={"doc_type": "work_order", "doc_id": work_order["id"], "tag": "signed_document"},
        files={"file": ("wo.pdf", io.BytesIO(b"%PDF-1.4 fake"), "application/pdf")},
        headers=headers,
    )
    assert att.status_code == 201, att.text
    msg = client.post(
        "/messages",
        json={"doc_type": "cost_sheet", "doc_id": cost_sheet_id, "channel": "email", "recipient": "x@test.local"},
        headers=headers,
    )
    assert msg.status_code == 201, msg.text

    # A second doomed client with no project/opportunity at all -- covers the bare-client case (most of
    # the real "Home Solutions" duplicates have no project), and confirms deleting several clients in one
    # run works, not just one.
    bare_client_id = _create_client_record(client, headers, name="Bare Duplicate (delete me)")

    # A third, unrelated client with its own quotation -- must survive untouched.
    safe_client_id = _create_client_record(client, headers, name="Safe Client -- must survive")
    safe_project_id = _create_project(client, headers, safe_client_id)
    safe_sport_id = _add_project_sport(client, headers, safe_project_id)
    safe_cost_sheet_id = client.post(
        f"/projects/{safe_project_id}/cost-sheets", json={"cost_total": 200000}, headers=headers
    ).json()["id"]
    client.post(f"/cost-sheets/{safe_cost_sheet_id}/verify", headers=headers)
    safe_estimate = client.post(
        f"/projects/{safe_project_id}/estimates",
        json={"options": [{"project_sport_id": safe_sport_id, "package": "standard", "cost_for_option": 200000}]},
        headers=headers,
    ).json()

    module = _load_script()
    module.CLIENT_IDS = [doomed_client_id, bare_client_id]

    module.run(db_session, confirm=False)  # dry run must not touch anything

    from app.models.client import Client
    from app.models.document import CostSheet, Estimate, Quotation
    from app.models.project import Project

    assert db_session.query(Client).filter(Client.id == uuid.UUID(doomed_client_id)).first() is not None

    module.run(db_session, confirm=True)

    assert db_session.query(Client).filter(Client.id == uuid.UUID(doomed_client_id)).first() is None
    assert db_session.query(Project).filter(Project.id == uuid.UUID(project_id)).first() is None
    assert db_session.query(CostSheet).filter(CostSheet.id == uuid.UUID(cost_sheet_id)).first() is None
    assert db_session.query(Client).filter(Client.id == uuid.UUID(bare_client_id)).first() is None

    # the untouched client/project/cost sheet/estimate are all still there
    assert db_session.query(Client).filter(Client.id == uuid.UUID(safe_client_id)).first() is not None
    assert db_session.query(Project).filter(Project.id == uuid.UUID(safe_project_id)).first() is not None
    assert db_session.query(CostSheet).filter(CostSheet.id == uuid.UUID(safe_cost_sheet_id)).first() is not None
    assert db_session.query(Estimate).filter(Estimate.id == uuid.UUID(safe_estimate["id"])).first() is not None


def test_deletes_a_completed_upload_session_and_its_stages_without_fk_error(client, director_user, db_session):
    """Found while auditing the script for P4's new FK paths: project_construction_stages (every
    project now seeds 6 of them) and attachment_upload_sessions.resulting_attachment_id (a
    completed chunked upload points straight at an Attachment row) can each block a delete with
    the same kind of FK violation the stages gap already caused once. This drives a real chunked
    upload to completion against the doomed project's own cost sheet, then confirms --confirm
    still deletes cleanly and the session/chunks/stages are all gone afterward."""
    import hashlib

    from tests.test_work_orders import _create_client_record, _create_project
    from app.models.attachment_upload_session import AttachmentUploadChunk, AttachmentUploadSession
    from app.models.project import Project
    from app.models.project_construction_stage import ProjectConstructionStage

    headers = _director_headers(client, director_user)
    doomed_client_id = _create_client_record(client, headers, name="Upload Session Delete Test (delete me)")
    project_id = _create_project(client, headers, doomed_client_id)
    cost_sheet_id = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": 100000}, headers=headers
    ).json()["id"]

    content = b"A" * 30 + b"B" * 10  # 2 chunks of 30/10 against chunk_size=30
    sha = hashlib.sha256(content).hexdigest()
    session = client.post(
        "/attachments/upload-sessions",
        json={
            "doc_type": "cost_sheet", "doc_id": cost_sheet_id, "filename": "evidence.bin",
            "declared_size": len(content), "declared_sha256": sha, "chunk_size": 30,
        },
        headers=headers,
    ).json()
    for index, start in enumerate((0, 30)):
        res = client.post(
            f"/attachments/upload-sessions/{session['id']}/chunks/{index}",
            files={"file": ("chunk", content[start:start + 30], "application/octet-stream")},
            headers=headers,
        )
        assert res.status_code == 200, res.text
    complete = client.post(f"/attachments/upload-sessions/{session['id']}/complete", headers=headers)
    assert complete.status_code == 200, complete.text
    resulting_attachment_id = complete.json()["id"]

    assert db_session.query(AttachmentUploadSession).filter(
        AttachmentUploadSession.id == uuid.UUID(session["id"])
    ).first() is not None
    assert db_session.query(ProjectConstructionStage).filter(
        ProjectConstructionStage.project_id == uuid.UUID(project_id)
    ).count() == 6

    module = _load_script()
    module.CLIENT_IDS = [doomed_client_id]
    module.run(db_session, confirm=True)

    assert db_session.query(Project).filter(Project.id == uuid.UUID(project_id)).first() is None
    assert db_session.query(AttachmentUploadSession).filter(
        AttachmentUploadSession.id == uuid.UUID(session["id"])
    ).first() is None
    assert db_session.query(AttachmentUploadChunk).filter(
        AttachmentUploadChunk.session_id == uuid.UUID(session["id"])
    ).count() == 0
    assert db_session.query(ProjectConstructionStage).filter(
        ProjectConstructionStage.project_id == uuid.UUID(project_id)
    ).count() == 0
    from app.models.attachment import Attachment

    assert db_session.query(Attachment).filter(Attachment.id == uuid.UUID(resulting_attachment_id)).first() is None


def test_refuses_to_run_if_an_id_is_not_found(db_session):
    module = _load_script()
    module.CLIENT_IDS = [str(uuid.uuid4())]
    try:
        module.run(db_session, confirm=True)
        assert False, "should have refused"
    except SystemExit as exc:
        assert "not found" in str(exc)
