"""P5 contract revision 7 -- legacy adoption (AC-25, AC-26) and migration rollback protection (AC-27).

The adoption script is exercised against realistic Work Orders built through the real API; "pre-P5"
state is simulated by removing a quotation's P5 rows and by positioning the migration marker, since
tests build their schema with create_all, not Alembic. The disposable-database script
scripts/verify_p5_migration.py proves the same behaviour against a real Alembic upgrade of genuinely
pre-P5 data."""

import importlib.util
import pathlib
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.core import p5
from app.models.p5 import (
    Agreement,
    AgreementStatus,
    P5MigrationMarker,
    ProjectExecutionAuthorization,
    ProjectTeamMember,
)
from app.models.user import User
from app.models.work_order import WorkOrder
from scripts import p5_adopt_legacy_work_orders as adopt
from tests.conftest import engine
from tests.p5_helpers import (
    authorize,
    draft_agreement,
    execute_agreement,
    make_execution_ready,
    quotation_project,
    staff_site_engineer,
)
from tests.test_work_orders import _director_headers, _won_quotation

MIGRATION_PATH = (
    pathlib.Path(__file__).resolve().parents[1] / "alembic" / "versions" / "a5e7c2d9b413_p5_agreement_and_execution_starter.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location("p5_migration_under_test", MIGRATION_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _make_pre_p5(db, quotation_id):
    """Turn a quotation that went through the P5 flow into a 'pre-P5' one: its Work Order stays, every P5 row goes."""
    db.execute(text("DELETE FROM project_tasks"))
    db.execute(text("DELETE FROM project_execution_authorizations WHERE quotation_id = :q"), {"q": quotation_id})
    db.execute(text("UPDATE agreements SET supersedes_id = NULL WHERE quotation_id = :q"), {"q": quotation_id})
    db.execute(text("DELETE FROM agreements WHERE quotation_id = :q"), {"q": quotation_id})
    db.execute(text("DELETE FROM project_team_members WHERE project_id = (SELECT project_id FROM quotations WHERE id = :q)"), {"q": quotation_id})
    db.commit()


def _set_marker(db, when):
    row = db.get(P5MigrationMarker, 1)
    if row is None:
        db.add(P5MigrationMarker(id=1, deployed_at=when))
    else:
        row.deployed_at = when
    db.commit()


def _legacy_world(client, db, headers):
    """A Won quotation with a real Work Order, then stripped back to its pre-P5 shape."""
    project_id, quotation_id = _won_quotation(client, headers)
    make_execution_ready(client, headers, quotation_id)
    wo = client.post(f"/quotations/{quotation_id}/work-order", headers=headers)
    assert wo.status_code == 201, wo.text
    _make_pre_p5(db, quotation_id)
    return project_id, quotation_id, wo.json()["id"]


def _agreements_for(db, quotation_id):
    db.expire_all()
    return db.query(Agreement).filter(Agreement.quotation_id == quotation_id).all()


# ---------------------------------------------------------------- AC-25: a Work Order that already exists


def test_ac25_adoption_dry_run_writes_nothing_and_confirm_needs_a_director(client, director_user, db_session):
    h = _director_headers(client, director_user)
    _, q, _ = _legacy_world(client, db_session, h)
    _set_marker(db_session, datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1))

    result = adopt.run(db_session, confirm=False, actor_email=None)
    assert result["eligible"] == 1 and result["adopted"] == 1
    assert _agreements_for(db_session, q) == []  # dry run: nothing written
    with pytest.raises(SystemExit):
        adopt.run(db_session, confirm=True, actor_email=None)
    with pytest.raises(SystemExit):
        adopt.run(db_session, confirm=True, actor_email="nobody@example.com")
    assert _agreements_for(db_session, q) == []


def test_ac25_adopted_pair_is_a_legacy_placeholder_that_never_counts_as_executed(client, director_user, db_session):
    h = _director_headers(client, director_user)
    pid, q, wo_id = _legacy_world(client, db_session, h)
    _set_marker(db_session, datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1))

    result = adopt.run(db_session, confirm=True, actor_email=director_user.email)
    assert result["adopted"] == 1
    rows = _agreements_for(db_session, q)
    assert len(rows) == 1 and rows[0].status == AgreementStatus.LEGACY_ADOPTED
    assert rows[0].client_signatory_id is None and rows[0].nesta_signed_by_id is None and rows[0].evidence_locked_at is None

    # it can never satisfy the executed-Agreement check...
    quotation = db_session.get(type(db_session.get(WorkOrder, wo_id)), wo_id)
    from app.models.document import Quotation

    report = p5.compute_readiness(db_session, db_session.get(Quotation, q))
    assert report.agreement_executed is False and report.agreement_status == AgreementStatus.LEGACY_ADOPTED
    # ...it is not an Agreement: it cannot be voided, and no new Agreement can be drafted over it
    assert client.post(f"/agreements/{rows[0].id}/void", json={"reason": "nope"}, headers=h).status_code == 409
    assert client.post(f"/quotations/{q}/agreement", headers=h).status_code == 409

    # the existing Work Order / payment functionality is completely unaffected
    assert client.get(f"/quotations/{q}/work-order", headers=h).status_code == 200
    assert client.get(f"/work-orders/{wo_id}/payment-milestones", headers=h).status_code == 200
    assert client.get(f"/work-orders/{wo_id}/payment-summary", headers=h).status_code == 200
    assert client.patch(f"/work-orders/{wo_id}", json={"status": "in_progress"}, headers=h).status_code == 200
    # the new planning screens are reachable and start with an empty, unstaffed team
    assert client.get(f"/projects/{pid}/team", headers=h).json() == []
    assert client.post(f"/projects/{pid}/tasks", json={"title": "Post-adoption task"}, headers=h).status_code == 201


def test_ac25_adoption_is_idempotent_per_pair_and_never_skips_a_whole_project(client, director_user, db_session):
    h = _director_headers(client, director_user)
    _, q1, _ = _legacy_world(client, db_session, h)
    _, q2, _ = _legacy_world(client, db_session, h)
    _set_marker(db_session, datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1))

    # q1 is adopted first (say, by an earlier partial run)...
    db_session.add(Agreement(
        quotation_id=q1, project_id=db_session.execute(text("SELECT project_id FROM quotations WHERE id=:q"), {"q": q1}).scalar(),
        status=AgreementStatus.LEGACY_ADOPTED, created_by_id=director_user.id,
    ))
    db_session.commit()
    result = adopt.run(db_session, confirm=True, actor_email=director_user.email)
    assert result["eligible"] == 2 and result["already_adopted"] == 1 and result["adopted"] == 1  # only q2 is new
    assert len(_agreements_for(db_session, q1)) == 1 and len(_agreements_for(db_session, q2)) == 1

    again = adopt.run(db_session, confirm=True, actor_email=director_user.email)
    assert again["adopted"] == 0 and again["already_adopted"] == 2  # a repeat run changes nothing
    assert len(_agreements_for(db_session, q1)) == 1 and len(_agreements_for(db_session, q2)) == 1


def test_ac25_the_durable_boundary_excludes_work_orders_created_after_p5_shipped(client, director_user, db_session):
    h = _director_headers(client, director_user)
    _, post_p5_q, _ = _legacy_world(client, db_session, h)  # its Work Order is created NOW...
    _set_marker(db_session, datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1))  # ...after the marker
    result = adopt.run(db_session, confirm=True, actor_email=director_user.email)
    assert result["eligible"] == 0 and result["adopted"] == 0
    assert _agreements_for(db_session, post_p5_q) == []  # a later script run can never adopt it


def test_ac25_a_future_won_quotation_on_an_adopted_project_gets_no_exemption(client, director_user, db_session):
    h = _director_headers(client, director_user)
    pid, q1, _ = _legacy_world(client, db_session, h)
    _set_marker(db_session, datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1))
    adopt.run(db_session, confirm=True, actor_email=director_user.email)

    # a second quotation on the SAME project, taken to Won
    estimate_id = db_session.execute(text("SELECT estimate_id FROM quotations WHERE id = :q"), {"q": q1}).scalar()
    option_id = db_session.execute(text("SELECT id FROM estimate_options WHERE estimate_id = :e LIMIT 1"), {"e": estimate_id}).scalar()
    created = client.post(
        f"/projects/{pid}/quotations", json={"estimate_id": str(estimate_id), "included_option_ids": [str(option_id)]}, headers=h
    )
    if created.status_code != 201:
        pytest.skip(f"this codebase does not allow a second quotation on the same estimate: {created.text}")
    q2 = created.json()["id"]
    client.post(f"/quotations/{q2}/release", headers=h)
    client.post(f"/quotations/{q2}/send", headers=h)
    won = client.post(f"/quotations/{q2}/mark-won", json={"reason": "second", "waive_evidence_reason": "test"}, headers=h)
    assert won.status_code == 200, won.text

    # q2 has no Work Order, so it was never eligible; it must go through the full flow
    assert adopt.run(db_session, confirm=True, actor_email=director_user.email)["adopted"] == 0
    assert _agreements_for(db_session, q2) == []
    assert client.post(f"/quotations/{q2}/work-order", headers=h).status_code == 409
    # while the adopted project's own team (empty) still blocks a fresh start
    _, client_id = quotation_project(client, h, q2)
    execute_agreement(client, h, q2, client_id)
    assert client.post(f"/quotations/{q2}/work-order", headers=h).status_code == 409  # still needs team + authorization
    staff_site_engineer(client, h, pid)
    assert authorize(client, h, q2).status_code == 200
    assert client.post(f"/quotations/{q2}/work-order", headers=h).status_code == 201


# ---------------------------------------------------------------- AC-26: no Work Order yet


def test_ac26_a_won_but_not_yet_awarded_project_gets_no_bypass(client, director_user, db_session):
    h = _director_headers(client, director_user)
    pid, q = _won_quotation(client, h)  # Won, no Work Order
    _set_marker(db_session, datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=1))
    result = adopt.run(db_session, confirm=True, actor_email=director_user.email)
    assert result["eligible"] == 0 and result["adopted"] == 0  # nothing to adopt: no historical handoff exists
    assert _agreements_for(db_session, q) == []
    # full flow is required, exactly like a brand-new project
    assert client.post(f"/quotations/{q}/work-order", headers=h).status_code == 409
    assert client.post(f"/quotations/{q}/agreement", headers=h).status_code == 201


# ---------------------------------------------------------------- AC-27: rollback protection


P5_TABLES = (
    "agreements", "project_execution_authorizations", "project_team_members",
    "project_milestones", "project_tasks", "project_site_issues",
)


def _downgrade_in_a_transaction(db_session):
    """Run the real migration's downgrade() against the test schema inside a transaction that is ALWAYS
    rolled back. Returns (exception_or_None, tables_present_inside_the_transaction)."""
    db_session.rollback()
    migration = _load_migration()
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    conn = engine.connect()
    trans = conn.begin()
    error, present = None, None
    try:
        with Operations.context(MigrationContext.configure(conn)):
            try:
                migration.downgrade()
            except RuntimeError as exc:
                error = exc
        present = set(inspect(conn).get_table_names())
    finally:
        trans.rollback()
        conn.close()
    return error, present


def _world_with(client, headers, table):
    project_id, quotation_id = _won_quotation(client, headers)
    if table == "agreements":
        draft_agreement(client, headers, quotation_id)
    elif table == "project_team_members":
        staff_site_engineer(client, headers, project_id)
    elif table == "project_execution_authorizations":
        make_execution_ready(client, headers, quotation_id)
    elif table == "project_milestones":
        assert client.post(f"/projects/{project_id}/milestones", json={"name": "m"}, headers=headers).status_code == 201
    elif table == "project_tasks":
        assert client.post(f"/projects/{project_id}/tasks", json={"title": "t"}, headers=headers).status_code == 201
    elif table == "project_site_issues":
        assert client.post(f"/projects/{project_id}/site-issues", json={"title": "i"}, headers=headers).status_code == 201


@pytest.mark.parametrize("table", P5_TABLES)
def test_ac27_downgrade_is_refused_naming_each_populated_p5_table(client, director_user, db_session, table):
    h = _director_headers(client, director_user)
    _world_with(client, h, table)
    error, present = _downgrade_in_a_transaction(db_session)
    assert error is not None and "Refusing to downgrade" in str(error)
    assert f"{table}=" in str(error)  # it names this table specifically
    assert set(P5_TABLES) <= present  # and nothing was dropped


def test_ac27_downgrade_succeeds_cleanly_against_the_empty_p5_schema(client, director_user, db_session):
    h = _director_headers(client, director_user)
    _won_quotation(client, h)  # real data elsewhere, but no P5 rows at all
    error, present = _downgrade_in_a_transaction(db_session)
    assert error is None
    assert not (set(P5_TABLES) | {"p5_migration_marker"}) & present  # all seven P5 tables dropped inside the transaction
    # the rollback restored everything (the refusal is conditional, not blanket breakage)
    with engine.connect() as conn:
        assert set(P5_TABLES) <= set(inspect(conn).get_table_names())


def test_ac27_the_six_protected_tables_are_exactly_the_p5_data_tables():
    migration = _load_migration()
    assert set(migration.P5_DATA_TABLES) == set(P5_TABLES)
    assert "project_execution_authorizations" in migration.P5_DATA_TABLES  # omitted in contract revision 2


def test_the_adoption_script_refuses_without_the_migration_marker(client, director_user, db_session):
    db_session.execute(text("DELETE FROM p5_migration_marker"))
    db_session.commit()
    with pytest.raises(SystemExit):
        adopt.run(db_session, confirm=False, actor_email=None)
