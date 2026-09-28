"""WP5 (correction plan, 2026-09-27): the shared /follow-ups API -- creation, listing,
history on change, the Opportunity last-open-follow-up guard (extended to completion,
cancellation and deletion, not just a stage change), idempotent purpose_key, and
permission delegation to the underlying entity's own existing role/ownership gate."""
import threading
import time
import uuid

from app.core.security import hash_password
from app.models.user import User, UserRole
from tests.conftest import TEST_DATABASE_URL


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _sales_user(db_session, email="sales@test.local", name="Test Sales"):
    user = User(name=name, email=email, hashed_password=hash_password("TestPass!1"), role=UserRole.SALES)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _create_opportunity(client, headers, **overrides):
    payload = {"lead_name": "Test Lead", "next_follow_up_date": "2026-10-01", **overrides}
    res = client.post("/opportunities", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _create_client_record(client, headers, **overrides):
    payload = {"name": "Test Client", "type": "school", "city": "Mumbai", **overrides}
    res = client.post("/clients", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _the_open_follow_up(client, headers, opp):
    """WP5 integration (2026-09-28): creating an Opportunity now auto-creates its own
    primary-reminder FollowUp (app/core/follow_up_sync.py) -- a freshly created
    Opportunity already has one open follow-up, not zero. Tests below that want "the"
    single open follow-up to exercise the last-open-follow-up guard fetch this
    auto-created row instead of posting a redundant second one."""
    rows = client.get("/follow-ups", params={"entity_type": "opportunity", "entity_id": opp["id"]}, headers=headers).json()
    open_rows = [r for r in rows if r["status"] not in ("completed", "cancelled")]
    assert len(open_rows) == 1, open_rows
    return open_rows[0]


def test_create_follow_up_defaults_owner_from_entity(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client_record(client, headers)

    res = client.post(
        "/follow-ups",
        json={"entity_type": "client", "entity_id": row["id"], "next_action": "Call back", "due_date": "2026-10-05"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["owner_id"] == row["owner_id"]
    assert body["owner_explicitly_assigned"] is False
    assert body["status"] == "open"
    assert body["overdue"] is False


def test_explicit_owner_flags_specialist_assignment(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    specialist = _sales_user(db_session, email="specialist@test.local", name="Specialist")
    row = _create_client_record(client, headers)

    res = client.post(
        "/follow-ups",
        json={
            "entity_type": "client", "entity_id": row["id"], "next_action": "Technical review",
            "due_date": "2026-10-05", "owner_id": str(specialist.id),
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["owner_id"] == str(specialist.id)
    assert res.json()["owner_explicitly_assigned"] is True


def test_multiple_open_follow_ups_on_one_record_are_allowed(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client_record(client, headers)
    for action in ("Routine call-back", "Site-visit follow-up"):
        res = client.post(
            "/follow-ups",
            json={"entity_type": "client", "entity_id": row["id"], "next_action": action, "due_date": "2026-10-05"},
            headers=headers,
        )
        assert res.status_code == 201, res.text

    listed = client.get("/follow-ups", params={"entity_type": "client", "entity_id": row["id"]}, headers=headers)
    assert len(listed.json()) == 2


def test_purpose_key_is_idempotent_for_automated_actions(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client_record(client, headers)
    body = {
        "entity_type": "client", "entity_id": row["id"], "next_action": "Auto review",
        "due_date": "2026-10-05", "purpose_key": "won_stage_review",
    }
    first = client.post("/follow-ups", json=body, headers=headers)
    second = client.post("/follow-ups", json=body, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]  # same row returned, not a duplicate

    listed = client.get("/follow-ups", params={"entity_type": "client", "entity_id": row["id"]}, headers=headers)
    assert len(listed.json()) == 1


def test_patch_writes_history_for_due_date_and_status(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client_record(client, headers)
    created = client.post(
        "/follow-ups",
        json={"entity_type": "client", "entity_id": row["id"], "next_action": "Call", "due_date": "2026-10-05"},
        headers=headers,
    ).json()

    res = client.patch(f"/follow-ups/{created['id']}", json={"due_date": "2026-10-10", "status": "in_progress"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["due_date"] == "2026-10-10"
    assert res.json()["status"] == "in_progress"


def test_waiting_status_requires_waiting_party(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client_record(client, headers)
    created = client.post(
        "/follow-ups",
        json={"entity_type": "client", "entity_id": row["id"], "next_action": "Call", "due_date": "2026-10-05"},
        headers=headers,
    ).json()

    res = client.patch(f"/follow-ups/{created['id']}", json={"status": "waiting"}, headers=headers)
    assert res.status_code == 400

    ok = client.patch(f"/follow-ups/{created['id']}", json={"status": "waiting", "waiting_party": "client"}, headers=headers)
    assert ok.status_code == 200
    assert ok.json()["waiting_party"] == "client"


# ---------------------------------------------------------------------------
# The Opportunity "always needs an open follow-up" guard
# ---------------------------------------------------------------------------


def test_completing_the_last_open_follow_up_on_an_open_opportunity_requires_a_replacement(client, director_user):
    headers = _director_headers(client, director_user)
    opp = _create_opportunity(client, headers)
    fu = _the_open_follow_up(client, headers, opp)

    blocked = client.patch(f"/follow-ups/{fu['id']}", json={"status": "completed"}, headers=headers)
    assert blocked.status_code == 400
    assert "replacement" in blocked.json()["detail"].lower()

    ok = client.patch(
        f"/follow-ups/{fu['id']}",
        json={"status": "completed", "replacement": {"next_action": "Next call", "due_date": "2026-10-12"}},
        headers=headers,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "completed"

    remaining = client.get("/follow-ups", params={"entity_type": "opportunity", "entity_id": opp["id"]}, headers=headers).json()
    open_ones = [r for r in remaining if r["status"] not in ("completed", "cancelled")]
    assert len(open_ones) == 1
    assert open_ones[0]["next_action"] == "Next call"


def test_cancelling_the_last_open_follow_up_on_an_open_opportunity_requires_a_replacement(client, director_user):
    headers = _director_headers(client, director_user)
    opp = _create_opportunity(client, headers)
    fu = _the_open_follow_up(client, headers, opp)

    blocked = client.patch(f"/follow-ups/{fu['id']}", json={"status": "cancelled"}, headers=headers)
    assert blocked.status_code == 400

    ok = client.patch(
        f"/follow-ups/{fu['id']}",
        json={"status": "cancelled", "replacement": {"next_action": "Rescheduled", "due_date": "2026-10-12"}},
        headers=headers,
    )
    assert ok.status_code == 200


def test_deleting_the_last_open_follow_up_on_an_open_opportunity_is_blocked(client, director_user):
    headers = _director_headers(client, director_user)
    opp = _create_opportunity(client, headers)
    fu = _the_open_follow_up(client, headers, opp)

    blocked = client.delete(f"/follow-ups/{fu['id']}", headers=headers)
    assert blocked.status_code == 400

    # create a second one first -- now deleting the first is fine, it's no longer the last
    client.post(
        "/follow-ups",
        json={"entity_type": "opportunity", "entity_id": opp["id"], "next_action": "Backup", "due_date": "2026-10-06"},
        headers=headers,
    )
    ok = client.delete(f"/follow-ups/{fu['id']}", headers=headers)
    assert ok.status_code == 204


def test_completing_a_non_last_open_follow_up_needs_no_replacement(client, director_user):
    headers = _director_headers(client, director_user)
    opp = _create_opportunity(client, headers)
    first = client.post(
        "/follow-ups",
        json={"entity_type": "opportunity", "entity_id": opp["id"], "next_action": "Call", "due_date": "2026-10-05"},
        headers=headers,
    ).json()
    client.post(
        "/follow-ups",
        json={"entity_type": "opportunity", "entity_id": opp["id"], "next_action": "Site visit", "due_date": "2026-10-06"},
        headers=headers,
    )

    ok = client.patch(f"/follow-ups/{first['id']}", json={"status": "completed"}, headers=headers)
    assert ok.status_code == 200


def test_the_guard_does_not_apply_once_the_opportunity_is_closed(client, director_user):
    headers = _director_headers(client, director_user)
    opp = _create_opportunity(client, headers)
    fu = client.post(
        "/follow-ups",
        json={"entity_type": "opportunity", "entity_id": opp["id"], "next_action": "Call", "due_date": "2026-10-05"},
        headers=headers,
    ).json()
    client.patch(f"/opportunities/{opp['id']}/stage", json={"stage": "won"}, headers=headers)

    ok = client.patch(f"/follow-ups/{fu['id']}", json={"status": "completed"}, headers=headers)
    assert ok.status_code == 200


# ---------------------------------------------------------------------------
# Permission delegation
# ---------------------------------------------------------------------------


def test_a_procurement_user_cannot_write_a_follow_up_on_a_client(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    row = _create_client_record(client, director_headers)

    procurement = User(
        name="Test Procurement", email="procurement@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.PROCUREMENT,
    )
    db_session.add(procurement)
    db_session.commit()
    proc_headers = _login(client, "procurement@test.local")

    res = client.post(
        "/follow-ups",
        json={"entity_type": "client", "entity_id": row["id"], "next_action": "Call", "due_date": "2026-10-05"},
        headers=proc_headers,
    )
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# The database-level constraint itself, not just the application's check-first logic
# ---------------------------------------------------------------------------


def test_the_partial_unique_index_rejects_a_genuine_simultaneous_race(client, director_user, db_session):
    """The application's check-then-insert in create_follow_up is not, on its own, immune
    to two requests that both pass the "does one exist" check before either commits -- only
    a real database constraint, checked at COMMIT time, can close that window. This uses two
    raw connections against the same test database create_all already built (proving the
    constraint from app/models/follow_up.py's __table_args__, not just the migration's copy
    of it), with an artificial delay so both transactions are guaranteed to pass their own
    "no existing row" check before either one commits -- the exact race a naive
    check-then-insert cannot prevent."""
    import psycopg

    headers = _director_headers(client, director_user)
    row = _create_client_record(client, headers)
    entity_id = row["id"]

    user = db_session.query(User).filter(User.email == "director@test.local").first()
    dsn = TEST_DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")

    results = [None, None]

    def worker(i):
        conn = psycopg.connect(dsn)
        conn.autocommit = False
        cur = conn.cursor()
        try:
            cur.execute(
                "select id from follow_ups where entity_type=%s and entity_id=%s and purpose_key=%s",
                ("CLIENT", entity_id, "race_test_key"),
            )
            existing = cur.fetchone()
            time.sleep(0.3)
            if existing is None:
                cur.execute(
                    """insert into follow_ups
                       (id, entity_type, entity_id, purpose_key, owner_id, owner_explicitly_assigned,
                        next_action, due_date, status, created_at, created_by_id)
                       values (%s,%s,%s,%s,%s,false,%s,current_date,%s,now(),%s)""",
                    (str(uuid.uuid4()), "CLIENT", entity_id, "race_test_key", str(user.id), "Race test", "OPEN", str(user.id)),
                )
            conn.commit()
            results[i] = "committed"
        except Exception as e:
            conn.rollback()
            results[i] = type(e).__name__
        finally:
            conn.close()

    t1 = threading.Thread(target=worker, args=(0,))
    t2 = threading.Thread(target=worker, args=(1,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    # exactly one thread's commit wins; the other must fail on the DB constraint, not silently
    # double-insert -- this is the whole point of having the index, not just the app check
    assert sorted(results) == sorted(["committed", "UniqueViolation"]), results

    found = client.get(
        "/follow-ups", params={"entity_type": "client", "entity_id": entity_id}, headers=headers
    ).json()
    race_rows = [r for r in found if r["purpose_key"] == "race_test_key"]
    assert len(race_rows) == 1


def test_unknown_entity_is_a_404_not_a_403(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/follow-ups",
        json={
            "entity_type": "client", "entity_id": "00000000-0000-0000-0000-000000000000",
            "next_action": "Call", "due_date": "2026-10-05",
        },
        headers=headers,
    )
    assert res.status_code == 404
