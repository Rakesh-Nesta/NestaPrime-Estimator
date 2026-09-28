"""WP5 integration (correction plan, 2026-09-28): the shared write path between a
Client's/Opportunity's legacy next_follow_up_date/follow_up_note columns and the
FollowUp table (app/core/follow_up_sync.py), the org-wide "all" mode list_follow_ups
gained for the central Follow-ups screen, and the read-only containment mode."""
from datetime import date

from app.core.security import hash_password
from app.models.setting import Setting, SettingScope
from app.models.user import User, UserRole


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


def test_creating_an_opportunity_creates_a_matching_primary_follow_up(client, director_user):
    headers = _director_headers(client, director_user)
    opp = _create_opportunity(client, headers, next_follow_up_date="2026-10-15")

    res = client.get(f"/follow-ups?entity_type=opportunity&entity_id={opp['id']}", headers=headers)
    assert res.status_code == 200, res.text
    rows = res.json()
    assert len(rows) == 1
    assert rows[0]["due_date"] == "2026-10-15"
    assert rows[0]["status"] == "open"
    assert rows[0]["owner_id"] == opp["owner_id"]


def test_rescheduling_an_opportunity_follow_up_updates_the_same_row_not_a_duplicate(client, director_user):
    headers = _director_headers(client, director_user)
    opp = _create_opportunity(client, headers)

    res = client.patch(
        f"/opportunities/{opp['id']}/follow-up",
        json={"next_follow_up_date": "2026-11-01", "follow_up_note": "Called, wants a quote"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["next_follow_up_date"] == "2026-11-01"

    rows = client.get(f"/follow-ups?entity_type=opportunity&entity_id={opp['id']}", headers=headers).json()
    assert len(rows) == 1
    assert rows[0]["due_date"] == "2026-11-01"
    assert rows[0]["next_action"] == "Called, wants a quote"


def test_moving_an_opportunity_to_a_terminal_stage_completes_its_primary_follow_up(client, director_user):
    headers = _director_headers(client, director_user)
    opp = _create_opportunity(client, headers)

    res = client.patch(f"/opportunities/{opp['id']}/stage", json={"stage": "won"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["next_follow_up_date"] is None

    rows = client.get(f"/follow-ups?entity_type=opportunity&entity_id={opp['id']}", headers=headers).json()
    assert len(rows) == 1
    assert rows[0]["status"] == "completed"


def test_moving_an_opportunity_to_a_non_terminal_stage_updates_the_due_date_and_keeps_the_note(client, director_user):
    headers = _director_headers(client, director_user)
    opp = _create_opportunity(client, headers)
    client.patch(
        f"/opportunities/{opp['id']}/follow-up",
        json={"next_follow_up_date": "2026-10-20", "follow_up_note": "Waiting on their board"},
        headers=headers,
    )

    res = client.patch(
        f"/opportunities/{opp['id']}/stage",
        json={"stage": "qualified", "next_follow_up_date": "2026-10-25"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["follow_up_note"] == "Waiting on their board"

    rows = client.get(f"/follow-ups?entity_type=opportunity&entity_id={opp['id']}", headers=headers).json()
    assert len(rows) == 1
    assert rows[0]["due_date"] == "2026-10-25"
    assert rows[0]["next_action"] == "Waiting on their board"


def test_setting_a_client_follow_up_creates_a_row_and_clearing_it_completes_that_row(client, director_user):
    headers = _director_headers(client, director_user)
    rec = _create_client_record(client, headers)

    res = client.patch(
        f"/clients/{rec['id']}/follow-up",
        json={"next_follow_up_date": "2026-10-10", "follow_up_note": "Send brochure"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    rows = client.get(f"/follow-ups?entity_type=client&entity_id={rec['id']}", headers=headers).json()
    assert len(rows) == 1
    assert rows[0]["due_date"] == "2026-10-10"
    assert rows[0]["status"] == "open"

    res = client.patch(f"/clients/{rec['id']}/follow-up", json={"next_follow_up_date": None}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["next_follow_up_date"] is None
    rows = client.get(f"/follow-ups?entity_type=client&entity_id={rec['id']}", headers=headers).json()
    assert len(rows) == 1
    assert rows[0]["status"] == "completed"


def _lock_writes(db_session, director):
    db_session.add(
        Setting(
            key="follow_ups_writes_locked",
            scope=SettingScope.GLOBAL,
            value="on",
            effective_from=date(2020, 1, 1),
            changed_by_id=director.id,
        )
    )
    db_session.commit()


def test_containment_lock_blocks_every_client_and_opportunity_sync_route_with_no_partial_change(
    client, director_user, db_session
):
    """Correction-plan clarification, 2026-09-28: read-only containment blocks EVERY
    route that can write follow-up data, including the Client/Opportunity sync routes
    -- not just the /follow-ups API's own endpoints, and not a partial mode where the
    legacy column moves but the shared table freezes. Each rejected attempt below must
    leave the record exactly as it was before the attempt."""
    headers = _director_headers(client, director_user)
    opp = _create_opportunity(client, headers)
    baseline_opp = client.get(f"/opportunities/{opp['id']}", headers=headers).json()
    rec = _create_client_record(client, headers)
    client.patch(
        f"/clients/{rec['id']}/follow-up",
        json={"next_follow_up_date": "2026-10-10", "follow_up_note": "Send brochure"},
        headers=headers,
    )
    baseline_client = client.get(f"/clients/{rec['id']}", headers=headers).json()

    _lock_writes(db_session, director_user)

    # Opportunity's dedicated reschedule endpoint.
    res = client.patch(
        f"/opportunities/{opp['id']}/follow-up",
        json={"next_follow_up_date": "2026-12-01", "follow_up_note": "Locked-mode edit"},
        headers=headers,
    )
    assert res.status_code == 423

    # Opportunity stage change (also a sync route -- it sets/clears the follow-up).
    res = client.patch(f"/opportunities/{opp['id']}/stage", json={"stage": "won"}, headers=headers)
    assert res.status_code == 423

    # Creating a NEW Opportunity, which always writes an initial follow-up too.
    res = client.post(
        "/opportunities", json={"lead_name": "Should be refused", "next_follow_up_date": "2026-10-01"}, headers=headers
    )
    assert res.status_code == 423

    # Client's dedicated reschedule endpoint.
    res = client.patch(f"/clients/{rec['id']}/follow-up", json={"next_follow_up_date": "2026-11-11"}, headers=headers)
    assert res.status_code == 423

    # Nothing above left a partial change -- both records read back exactly as before.
    assert client.get(f"/opportunities/{opp['id']}", headers=headers).json() == baseline_opp
    assert client.get(f"/clients/{rec['id']}", headers=headers).json() == baseline_client

    # Reads are unaffected throughout.
    assert client.get(f"/opportunities/{opp['id']}", headers=headers).status_code == 200
    assert client.get(f"/follow-ups?entity_type=opportunity&entity_id={opp['id']}", headers=headers).status_code == 200


def test_containment_lock_blocks_new_writes_via_the_follow_ups_api_but_not_reads(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    rec = _create_client_record(client, headers)
    existing = client.post(
        "/follow-ups",
        json={"entity_type": "client", "entity_id": rec["id"], "next_action": "Call", "due_date": "2026-10-05"},
        headers=headers,
    ).json()

    _lock_writes(db_session, director_user)

    res = client.post(
        "/follow-ups",
        json={"entity_type": "client", "entity_id": rec["id"], "next_action": "Another", "due_date": "2026-10-06"},
        headers=headers,
    )
    assert res.status_code == 423

    res = client.patch(f"/follow-ups/{existing['id']}", json={"outcome": "left a message"}, headers=headers)
    assert res.status_code == 423

    res = client.delete(f"/follow-ups/{existing['id']}", headers=headers)
    assert res.status_code == 423

    # Reads are unaffected.
    res = client.get(f"/follow-ups?entity_type=client&entity_id={rec['id']}", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_central_list_with_no_filters_is_scoped_for_sales_but_org_wide_for_director(
    client, director_user, db_session
):
    """The Director's own-records switch (Amendment 60) does not govern this list --
    Sales stays scoped to their own follow-ups here whether the switch is on or off (see
    app/api/follow_ups.py's own comment on this)."""
    director_headers = _director_headers(client, director_user)
    sales = _sales_user(db_session)
    sales_headers = _login(client, sales.email)

    mine = _create_opportunity(client, sales_headers, lead_name="Sales-owned lead")
    others = _create_opportunity(client, director_headers, lead_name="Director-owned lead")

    for switch_on in (False, True):
        client.put("/ownership/switch", json={"on": switch_on}, headers=director_headers)

        sales_view = client.get("/follow-ups", headers=sales_headers)
        assert sales_view.status_code == 200, sales_view.text
        sales_ids = {r["entity_id"] for r in sales_view.json()}
        assert mine["id"] in sales_ids
        assert others["id"] not in sales_ids, f"switch_on={switch_on}: sales saw a lead they do not own"

        director_view = client.get("/follow-ups", headers=director_headers)
        assert director_view.status_code == 200, director_view.text
        director_ids = {r["entity_id"] for r in director_view.json()}
        assert mine["id"] in director_ids
        assert others["id"] in director_ids

    client.put("/ownership/switch", json={"on": False}, headers=director_headers)


def test_completing_an_opportunity_follow_up_from_the_central_api_updates_the_source_screen(
    client, director_user
):
    """The reverse direction of the sync: a change made through the generic
    /follow-ups endpoints (what the central Follow-ups screen calls) must show up on
    the Opportunity's own legacy field too, not just stay inside the shared table."""
    headers = _director_headers(client, director_user)
    opp = _create_opportunity(client, headers, next_follow_up_date="2026-10-01")
    fu = client.get(f"/follow-ups?entity_type=opportunity&entity_id={opp['id']}", headers=headers).json()[0]

    res = client.patch(
        f"/follow-ups/{fu['id']}",
        json={
            "status": "completed",
            "replacement": {"next_action": "Second call", "due_date": "2026-10-20"},
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text

    source_screen_view = client.get(f"/opportunities/{opp['id']}", headers=headers).json()
    assert source_screen_view["next_follow_up_date"] == "2026-10-20"
    assert source_screen_view["follow_up_note"] == "Second call"


def test_a_follow_up_created_from_the_central_api_on_a_client_with_no_reminder_yet_appears_on_the_source_screen(
    client, director_user
):
    headers = _director_headers(client, director_user)
    rec = _create_client_record(client, headers)
    assert client.get(f"/clients/{rec['id']}", headers=headers).json()["next_follow_up_date"] is None

    res = client.post(
        "/follow-ups",
        json={"entity_type": "client", "entity_id": rec["id"], "next_action": "Send catalogue", "due_date": "2026-10-08"},
        headers=headers,
    )
    assert res.status_code == 201, res.text

    source_screen_view = client.get(f"/clients/{rec['id']}", headers=headers).json()
    assert source_screen_view["next_follow_up_date"] == "2026-10-08"
    assert source_screen_view["follow_up_note"] == "Send catalogue"
