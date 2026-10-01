"""P5 review follow-ups (added after the full-suite run at 1a8fa1b; verified in their own commit).

* Ownership scoping (Sales, Amendment 60) is kept separate from team-membership restrictions
  (Procurement / Site Engineer). The approved role matrix (contract revision 7, Section 6) is the oracle:
  with the switch OFF Sales loses ONLY the ownership restriction -- every role limit stays.
* Status codes follow the established authorization order: ownership-concealed records answer 404 (the global
  enforce_own_records dependency runs first); otherwise the route's role gate answers 403.
* Denied writes are checked against a snapshot that spans P5 tables AND related records (Work Orders,
  Attachments, Quotations, Projects, Users, Notifications and the audit log).
* The execution-context route is pinned to its exact fields and proven free of commercial data.
* The migration marker's single-row guarantee is checked through the ORM-created schema here; the
  migration-created schema is checked in test_p5_adoption_and_migration.py and
  scripts/verify_p5_migration.py (real Alembic)."""

from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from app.models.attachment import Attachment
from app.models.audit_log import AuditLogEntry
from app.models.client_signatory import ClientSignatory
from app.models.document import Quotation
from app.models.notification import Notification
from app.models.p5 import (
    Agreement,
    P5MigrationMarker,
    ProjectExecutionAuthorization,
    ProjectMilestone,
    ProjectSiteIssue,
    ProjectTask,
    ProjectTeamMember,
)
from app.models.project import Project
from app.models.user import User
from app.models.work_order import WorkOrder
from tests.p5_helpers import (
    add_signatory,
    authorize,
    client_sign,
    draft_agreement,
    execute_agreement,
    make_user,
    quotation_project,
    staff_site_engineer,
    upload_agreement_document,
    user_headers,
)
from tests.test_work_orders import _director_headers, _won_quotation


def _snapshot(db):
    """Every row a P5 request could plausibly touch, directly or indirectly."""
    db.rollback()
    db.expire_all()
    counts = {
        m.__tablename__: db.query(func.count()).select_from(m).scalar()
        for m in (
            Agreement, ProjectExecutionAuthorization, ProjectTeamMember, ProjectMilestone, ProjectTask,
            ProjectSiteIssue, Attachment, AuditLogEntry, Notification, WorkOrder, Quotation, Project, User,
        )
    }
    detail = {
        "agreements": sorted((str(a.id), a.status, a.evidence_locked_at is not None, a.signed_document_sha256, a.void_reason)
                             for a in db.query(Agreement).all()),
        "authorizations": sorted((str(a.id), a.status, a.invalidated_reason) for a in db.query(ProjectExecutionAuthorization).all()),
        "team": sorted((str(m.id), m.removed_at is None) for m in db.query(ProjectTeamMember).all()),
        "milestones": sorted((str(m.id), m.status, m.name) for m in db.query(ProjectMilestone).all()),
        "tasks": sorted((str(t.id), t.status, str(t.assigned_to_id), t.title) for t in db.query(ProjectTask).all()),
        "issues": sorted((str(i.id), i.status, i.resolution_reason) for i in db.query(ProjectSiteIssue).all()),
        "attachments": sorted((str(a.id), str(a.superseded_by_id), a.original_sha256, str(a.review_status)) for a in db.query(Attachment).all()),
        "work_orders": sorted((str(w.id), w.status.value) for w in db.query(WorkOrder).all()),
        "quotations": sorted((str(q.id), q.status.value) for q in db.query(Quotation).all()),
        "projects": sorted((str(p.id), p.phase.value, str(p.owner_id)) for p in db.query(Project).all()),
        "users": sorted((str(u.id), u.role.value, u.is_active) for u in db.query(User).all()),
    }
    return counts, detail


@pytest.fixture()
def world(client, director_user, db_session):
    """A Won project loaded with P5 data (executed Agreement + signed file, an authorized quotation, a team
    member with an assigned task, a milestone and a site issue) and its Work Order created."""
    h = _director_headers(client, director_user)
    pid, q = _won_quotation(client, h)
    _, client_id = quotation_project(client, h, q)
    engineer = make_user(db_session, "site_engineer")
    agreement = execute_agreement(client, h, q, client_id)
    _, member = staff_site_engineer(client, h, pid, user={"id": str(engineer.id)})
    assert authorize(client, h, q).status_code == 200
    assert client.post(f"/quotations/{q}/work-order", headers=h).status_code == 201
    milestone = client.post(f"/projects/{pid}/milestones", json={"name": "M"}, headers=h).json()
    task = client.post(f"/projects/{pid}/tasks", json={"title": "T", "assigned_to_id": member["id"]}, headers=h).json()
    issue = client.post(f"/projects/{pid}/site-issues", json={"title": "I"}, headers=h).json()
    return dict(h=h, pid=pid, q=q, client_id=client_id, agreement=agreement, member=member, milestone=milestone,
                task=task, issue=issue, engineer=engineer)


def _routes(w):
    """(category, method, path, body). category: 'sales_read' = the approved matrix lets Sales read it;
    'manager' = PM/Director only (reads or writes); 'write' = a write the matrix gives Sales no part in."""
    pid, q, ag = w["pid"], w["q"], w["agreement"]["id"]
    att = w["agreement"]["signed_document_attachment_id"]
    unknown = "00000000-0000-0000-0000-000000000000"
    return [
        ("sales_read", "GET", f"/quotations/{q}/agreement", None),
        ("sales_read", "GET", f"/quotations/{q}/agreements", None),
        ("sales_read", "GET", f"/agreements/{ag}", None),
        ("sales_read", "GET", f"/projects/{pid}/execution-context", None),
        ("sales_read", "GET", f"/projects/{pid}/team", None),
        ("sales_read", "GET", f"/projects/{pid}/milestones", None),
        ("sales_read", "GET", f"/projects/{pid}/tasks", None),
        ("sales_read", "GET", f"/projects/{pid}/site-issues", None),
        ("sales_read", "GET", f"/attachments/{att}/download", None),  # AGREEMENT_ROLES includes sales (commercial file: matrix row)
        ("manager", "GET", f"/quotations/{q}/execution-readiness", None),
        ("manager", "GET", f"/quotations/{q}/execution-authorizations", None),
        ("manager", "POST", f"/quotations/{q}/execution-authorization", None),
        ("write", "POST", f"/quotations/{q}/agreement", None),
        ("write", "POST", f"/agreements/{ag}/client-sign", {"client_signatory_id": unknown, "signed_on": "2026-01-01", "attachment_id": att}),
        ("write", "POST", f"/agreements/{ag}/execute", None),
        ("write", "POST", f"/agreements/{ag}/void", {"reason": "must never apply"}),
        ("write", "POST", f"/agreements/{ag}/supersede", {"reason": "must never apply"}),
        ("write", "POST", f"/projects/{pid}/team", {"user_id": str(w["engineer"].id), "project_role": "site_engineer"}),
        ("write", "DELETE", f"/projects/{pid}/team/{w['member']['id']}", None),
        ("write", "POST", f"/projects/{pid}/milestones", {"name": "x"}),
        ("write", "PATCH", f"/milestones/{w['milestone']['id']}", {"status": "in_progress"}),
        ("write", "POST", f"/projects/{pid}/tasks", {"title": "x"}),
        ("write", "PATCH", f"/tasks/{w['task']['id']}", {"status": "in_progress"}),
        ("write", "POST", f"/projects/{pid}/site-issues", {"title": "x"}),
        ("write", "PATCH", f"/site-issues/{w['issue']['id']}", {"status": "resolved", "resolution_reason": "never"}),
        ("write", "POST", f"/attachments/{att}/supersede", "FILE"),
        ("write", "POST", f"/attachments/{att}/marketing-reuse/approve", None),
    ]


def _call(client, method, path, body, headers):
    if body == "FILE":
        return client.post(path, data={"tag": "signed_document"}, files={"file": ("x.pdf", b"x", "application/pdf")}, headers=headers)
    return client.request(method, path, json=body, headers=headers)


def _assert_no_leak(res):
    """A refusal body carries only a message -- never record data, ids of other records or commercial fields."""
    if res.status_code >= 400:
        assert set(res.json()) <= {"detail"}, res.text[:120]
        text = res.text.lower()
        for forbidden in ("sha256", "total", "margin", "cost", "price", "signatory"):
            assert forbidden not in text, (res.text[:120], forbidden)


# ============================================================ Sales: ownership scoping, BOTH switch states


@pytest.mark.parametrize("switch_on", [False, True])
def test_sales_ownership_scoping_is_the_only_thing_the_switch_changes(client, db_session, world, switch_on):
    w = world
    h = w["h"]
    sales_owner = make_user(db_session, "sales", name="Owner A")
    sales_other = make_user(db_session, "sales", name="Outsider B")
    ha, hb = user_headers(client, sales_owner), user_headers(client, sales_other)
    assert client.put("/ownership/switch", json={"on": switch_on}, headers=h).status_code == 200
    assert client.patch(f"/ownership/project/{w['pid']}", json={"owner_id": str(sales_owner.id), "cascade": True}, headers=h).status_code == 200

    before = _snapshot(db_session)
    for category, method, path, body in _routes(w):
        for who, headers in (("owner", ha), ("other", hb)):
            res = _call(client, method, path, body, headers)
            _assert_no_leak(res)
            if category == "sales_read":
                # the role allows it; only ownership can hide it (and only while the switch is on)
                expected = 404 if (who == "other" and switch_on) else 200
            else:
                # the role never allows it. Established order: the global ownership dependency answers first,
                # so a concealed record is a 404; otherwise the route's role gate answers 403.
                expected = 404 if (who == "other" and switch_on) else 403
            assert res.status_code == expected, f"switch={'on' if switch_on else 'off'} {who} {method} {path}: {res.status_code} {res.text[:100]}"
    assert _snapshot(db_session) == before  # no denied request changed ANY related record


def test_sales_never_gains_pm_director_privileges_with_the_switch_off(client, db_session, world):
    """The correction in review: switching ownership off removes ONLY the ownership restriction."""
    w = world
    assert client.put("/ownership/switch", json={"on": False}, headers=w["h"]).status_code == 200
    hb = user_headers(client, make_user(db_session, "sales"))
    for category, method, path, body in _routes(w):
        if category != "sales_read":
            assert _call(client, method, path, body, hb).status_code == 403, f"{method} {path}"
    # field limits: P5 payloads carry no commercial columns for Sales (or anyone)
    for path in (f"/agreements/{w['agreement']['id']}", f"/projects/{w['pid']}/execution-context", f"/projects/{w['pid']}/tasks"):
        text = client.get(path, headers=hb).text.lower()
        assert not any(t in text for t in ("total", "margin", "cost", "price", "gst", "rate")), path
    # the existing restriction on the quotation's own commercial record is untouched by P5
    sales_view = client.get(f"/quotations/{w['q']}", headers=hb).json()
    assert sales_view["cost_total"] is None and sales_view["margin_percent"] is None  # K.3 stripping, unchanged


# ============================================================ Procurement / Site Engineer: team membership (a different restriction)


def test_team_membership_restriction_is_separate_from_ownership_and_ignores_the_switch(client, db_session, world):
    w = world
    off_engineer = make_user(db_session, "site_engineer")
    off_procurement = make_user(db_session, "procurement")
    on_procurement = make_user(db_session, "procurement")
    assert client.post(f"/projects/{w['pid']}/team", json={"user_id": str(on_procurement.id), "project_role": "procurement"}, headers=w["h"]).status_code == 200
    on_engineer_headers = user_headers(client, w["engineer"])
    for switch_on in (False, True):  # the Sales switch must not change membership behaviour at all
        assert client.put("/ownership/switch", json={"on": switch_on}, headers=w["h"]).status_code == 200
        before = _snapshot(db_session)
        for who, user in (("off-team engineer", off_engineer), ("off-team procurement", off_procurement)):
            headers = user_headers(client, user)
            for category, method, path, body in _routes(w):
                res = _call(client, method, path, body, headers)
                _assert_no_leak(res)
                # a team gate (or the role gate) always answers 403 for them -- never 200, never 404
                assert res.status_code == 403, f"{who} {method} {path}: {res.status_code} {res.text[:100]}"
        assert _snapshot(db_session) == before
        # on the team, the VIEW routes open up exactly as far as the matrix allows (and no further)
        for category, method, path, body in _routes(w):
            if category != "sales_read":
                continue
            eng = _call(client, method, path, body, on_engineer_headers).status_code
            proc = _call(client, method, path, body, user_headers(client, on_procurement)).status_code
            is_file = "download" in path  # the signed document itself: never for Procurement / Site Engineer
            assert eng == (403 if is_file else 200), f"engineer {path}: {eng}"
            assert proc == (403 if is_file else 200), f"procurement {path}: {proc}"
        # manager-only and write routes stay closed to a team member (a task status on their OWN task excepted)
        for category, method, path, body in _routes(w):
            if category in ("manager", "write") and path != f"/tasks/{w['task']['id']}" and not path.endswith("/site-issues"):
                assert _call(client, method, path, body, on_engineer_headers).status_code == 403, f"{method} {path}"


# ============================================================ execution-context: exact fields, checks, no commercial data


CONTEXT_FIELDS = {"project_id", "phase", "quotation_id", "quotation_no", "work_order_exists", "work_order_id", "work_order_status"}


def test_execution_context_exposes_exactly_seven_fields_and_nothing_commercial(client, db_session, world):
    w = world
    eh = user_headers(client, w["engineer"])
    res = client.get(f"/projects/{w['pid']}/execution-context", headers=eh)
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == CONTEXT_FIELDS  # the exact response contract
    assert body["quotation_id"] == w["q"] and body["quotation_no"].startswith("NPQ-") and body["work_order_exists"] is True
    assert body["work_order_id"] is None and body["work_order_status"] is None  # Work Order id/status: managers only
    manager = client.get(f"/projects/{w['pid']}/execution-context", headers=w["h"]).json()
    assert set(manager) == CONTEXT_FIELDS and manager["work_order_id"] and manager["work_order_status"] == "awarded"

    raw = res.text.lower()
    quotation = client.get(f"/quotations/{w['q']}", headers=w["h"]).json()
    commercial_keys = [k for k in quotation if any(t in k for t in ("total", "cost", "margin", "price", "rate", "amount", "gst", "discount"))]
    assert commercial_keys, "sanity: the quotation payload does carry commercial fields"
    for key in commercial_keys:
        value = quotation[key]
        if isinstance(value, (int, float)) and abs(value) >= 1000:
            assert str(int(value)) not in raw and f"{value:,.2f}" not in raw, key
        assert key.lower() not in raw, key
    for forbidden in ("sha256", "attachment", "signatory", "signed_document", "margin", "cost", "price", "total", "agreement"):
        assert forbidden not in raw, forbidden
    # and the engineer reaches neither the agreement FILE nor the quotation itself through any route
    att = w["agreement"]["signed_document_attachment_id"]
    assert client.get(f"/attachments/{att}/download", headers=eh).status_code == 403
    assert client.get(f"/quotations/{w['q']}", headers=eh).status_code == 403


def test_execution_context_membership_and_role_checks(client, db_session, world):
    w = world
    path = f"/projects/{w['pid']}/execution-context"
    for user in (make_user(db_session, "site_engineer"), make_user(db_session, "procurement")):  # on no team
        res = client.get(path, headers=user_headers(client, user))
        assert res.status_code == 403 and "not on this project's team" in res.json()["detail"]
    for role in ("admin", "marketing", "ca_tax"):
        assert client.get(path, headers=user_headers(client, make_user(db_session, role))).status_code == 403, role
    assert client.get(path).status_code == 401
    # a REMOVED member is refused: membership must be active
    assert client.get(path, headers=user_headers(client, w["engineer"])).status_code == 200
    assert client.delete(f"/projects/{w['pid']}/team/{w['member']['id']}", headers=w["h"]).status_code == 200
    assert client.get(path, headers=user_headers(client, w["engineer"])).status_code == 403
    # Sales: ownership applies (switch on) and the payload is the same seven non-commercial fields
    sales_owner, sales_other = make_user(db_session, "sales"), make_user(db_session, "sales")
    assert client.put("/ownership/switch", json={"on": True}, headers=w["h"]).status_code == 200
    assert client.patch(f"/ownership/project/{w['pid']}", json={"owner_id": str(sales_owner.id), "cascade": True}, headers=w["h"]).status_code == 200
    assert client.get(path, headers=user_headers(client, sales_other)).status_code == 404
    owner_view = client.get(path, headers=user_headers(client, sales_owner))
    assert owner_view.status_code == 200 and set(owner_view.json()) == CONTEXT_FIELDS


# ============================================================ signing-date tolerance (found by the full-suite run)


def test_signing_date_accepts_a_local_today_that_is_ahead_of_utc_but_not_two_days_ahead(client, director_user):
    """Found at 1a8fa1b: a strict UTC comparison refused 'today' for a user whose local date was already
    tomorrow in UTC terms (India, 00:00-05:30 local). One day of tolerance; two days ahead is still refused."""
    h = _director_headers(client, director_user)
    _, q = _won_quotation(client, h)
    _, client_id = quotation_project(client, h, q)
    agreement = draft_agreement(client, h, q)
    attachment = upload_agreement_document(client, h, agreement["id"])
    signatory = add_signatory(client, h, client_id)
    utc_today = datetime.now(UTC).date()
    refused = client_sign(client, h, agreement["id"], signatory["id"], attachment["id"], signed_on=utc_today + timedelta(days=2))
    assert refused.status_code == 422 and "future" in refused.json()["detail"]
    ok = client_sign(client, h, agreement["id"], signatory["id"], attachment["id"], signed_on=utc_today + timedelta(days=1))
    assert ok.status_code == 200, ok.text


# ============================================================ the migration marker: uniqueness, persistence (ORM-created schema)


def test_marker_is_a_single_immutable_row_in_the_orm_created_schema(client, director_user, db_session):
    from scripts import p5_adopt_legacy_work_orders as adopt

    db_session.add(P5MigrationMarker(id=1, deployed_at=datetime(2026, 1, 1)))
    db_session.commit()
    db_session.add(P5MigrationMarker(id=1, deployed_at=datetime(2026, 2, 2)))  # the primary key refuses a duplicate
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    db_session.add(P5MigrationMarker(id=2, deployed_at=datetime(2026, 2, 2)))  # the single-row CHECK refuses any other id
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    # persistence: real P5 activity and repeated adoption runs never move it
    h = _director_headers(client, director_user)
    _, q = _won_quotation(client, h)
    draft_agreement(client, h, q)
    adopt.run(db_session, confirm=True, actor_email=director_user.email)
    adopt.run(db_session, confirm=True, actor_email=director_user.email)
    db_session.expire_all()
    assert db_session.get(P5MigrationMarker, 1).deployed_at == datetime(2026, 1, 1)
    assert db_session.query(func.count()).select_from(P5MigrationMarker).scalar() == 1
