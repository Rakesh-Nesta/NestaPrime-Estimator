"""Amendment 44 (Section E step 5): the Opportunity entity -- pipeline
stages, mandatory-follow-up-date discipline, Lead/Client distinction."""
from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _sales_headers(client, db_session):
    user = User(name="Test Sales", email="sales@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.SALES)
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales@test.local")


def _procurement_headers(client, db_session):
    user = User(
        name="Test Procurement", email="procurement@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.PROCUREMENT,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "procurement@test.local")


def _create_client_record(client, headers, name="Opportunity Test Client"):
    res = client.post("/clients", json={"name": name, "type": "school"}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _create_opportunity(client, headers, **overrides):
    payload = {"lead_name": "Test Lead", "next_follow_up_date": "2026-10-01", **overrides}
    res = client.post("/opportunities", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def test_add_enquiry_creates_lead_only_opportunity(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_opportunity(client, headers, lead_name="Jane Doe", lead_phone="9990001111")
    assert row["client_id"] is None
    assert row["lead_name"] == "Jane Doe"
    assert row["stage"] == "new"
    assert row["next_follow_up_date"] == "2026-10-01"


def test_create_opportunity_requires_next_follow_up_date(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post("/opportunities", json={"lead_name": "No Date Lead"}, headers=headers)
    assert res.status_code == 422


def test_create_opportunity_rejects_a_past_follow_up_date(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/opportunities", json={"lead_name": "Late Lead", "next_follow_up_date": "2020-01-01"}, headers=headers
    )
    assert res.status_code == 400


def test_create_opportunity_can_link_an_existing_client(client, director_user):
    headers = _director_headers(client, director_user)
    client_row = _create_client_record(client, headers)
    row = _create_opportunity(client, headers, client_id=client_row["id"])
    assert row["client_id"] == client_row["id"]


def test_create_opportunity_with_unknown_client_id_is_404(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/opportunities",
        json={
            "lead_name": "Ghost Client Lead",
            "next_follow_up_date": "2026-10-01",
            "client_id": "00000000-0000-0000-0000-000000000000",
        },
        headers=headers,
    )
    assert res.status_code == 404


def test_sales_can_create_opportunity(client, director_user, db_session):
    sales_headers = _sales_headers(client, db_session)
    row = _create_opportunity(client, sales_headers)
    assert row["stage"] == "new"


def test_procurement_cannot_create_opportunity(client, director_user, db_session):
    procurement_headers = _procurement_headers(client, db_session)
    res = client.post(
        "/opportunities",
        json={"lead_name": "Blocked Lead", "next_follow_up_date": "2026-10-01"},
        headers=procurement_headers,
    )
    assert res.status_code == 403


def test_procurement_can_list_opportunities(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _create_opportunity(client, director_headers)

    procurement_headers = _procurement_headers(client, db_session)
    res = client.get("/opportunities", headers=procurement_headers)
    assert res.status_code == 200, res.text
    assert len(res.json()) == 1


def test_stage_change_to_non_terminal_requires_a_follow_up_date(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_opportunity(client, headers)
    res = client.patch(f"/opportunities/{row['id']}/stage", json={"stage": "contacted"}, headers=headers)
    assert res.status_code == 400


def test_stage_change_to_non_terminal_rejects_a_past_follow_up_date(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_opportunity(client, headers)
    res = client.patch(
        f"/opportunities/{row['id']}/stage",
        json={"stage": "contacted", "next_follow_up_date": "2020-01-01"},
        headers=headers,
    )
    assert res.status_code == 400


def test_stage_change_to_non_terminal_sets_the_new_follow_up_date(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_opportunity(client, headers)
    res = client.patch(
        f"/opportunities/{row['id']}/stage",
        json={"stage": "contacted", "next_follow_up_date": "2026-10-15"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["stage"] == "contacted"
    assert res.json()["next_follow_up_date"] == "2026-10-15"


def test_stage_change_to_won_clears_the_follow_up_date(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_opportunity(client, headers)
    res = client.patch(f"/opportunities/{row['id']}/stage", json={"stage": "won"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["stage"] == "won"
    assert res.json()["next_follow_up_date"] is None


def test_stage_change_to_lost_clears_the_date_and_records_the_reason(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_opportunity(client, headers)
    res = client.patch(
        f"/opportunities/{row['id']}/stage",
        json={"stage": "lost", "lost_reason": "Went with a competitor"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["stage"] == "lost"
    assert res.json()["next_follow_up_date"] is None
    assert res.json()["lost_reason"] == "Went with a competitor"


def test_stage_update_on_nonexistent_opportunity_is_404(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.patch(
        "/opportunities/00000000-0000-0000-0000-000000000000/stage",
        json={"stage": "won"},
        headers=headers,
    )
    assert res.status_code == 404


def test_follow_up_endpoint_pushes_the_date_out(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_opportunity(client, headers)
    res = client.patch(
        f"/opportunities/{row['id']}/follow-up",
        json={"next_follow_up_date": "2026-11-01", "follow_up_note": "Call back after Diwali"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["next_follow_up_date"] == "2026-11-01"
    assert res.json()["follow_up_note"] == "Call back after Diwali"


def test_follow_up_endpoint_rejects_a_past_date(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_opportunity(client, headers)
    res = client.patch(
        f"/opportunities/{row['id']}/follow-up", json={"next_follow_up_date": "2020-01-01"}, headers=headers
    )
    assert res.status_code == 400


def test_follow_up_endpoint_rejects_null_date(client, director_user):
    """Unlike Client's own same-named endpoint, this one can never clear
    the date to null -- only a WON/LOST stage change can."""
    headers = _director_headers(client, director_user)
    row = _create_opportunity(client, headers)
    res = client.patch(f"/opportunities/{row['id']}/follow-up", json={"next_follow_up_date": None}, headers=headers)
    assert res.status_code == 422


def test_follow_up_endpoint_blocked_on_a_closed_opportunity(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_opportunity(client, headers)
    client.patch(f"/opportunities/{row['id']}/stage", json={"stage": "won"}, headers=headers)

    res = client.patch(
        f"/opportunities/{row['id']}/follow-up", json={"next_follow_up_date": "2026-11-01"}, headers=headers
    )
    assert res.status_code == 400


def test_link_client_attaches_an_existing_client(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_opportunity(client, headers)
    client_row = _create_client_record(client, headers)

    res = client.patch(f"/opportunities/{row['id']}/link-client", json={"client_id": client_row["id"]}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["client_id"] == client_row["id"]


def test_link_client_with_unknown_client_is_404(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_opportunity(client, headers)
    res = client.patch(
        f"/opportunities/{row['id']}/link-client",
        json={"client_id": "00000000-0000-0000-0000-000000000000"},
        headers=headers,
    )
    assert res.status_code == 404


def test_list_filters_by_relationship_lead_vs_client(client, director_user):
    headers = _director_headers(client, director_user)
    _create_opportunity(client, headers, lead_name="Lead Only")
    client_row = _create_client_record(client, headers)
    _create_opportunity(client, headers, lead_name="Linked Lead", client_id=client_row["id"])

    leads = client.get("/opportunities", params={"relationship": "lead"}, headers=headers).json()
    assert [o["lead_name"] for o in leads] == ["Lead Only"]

    clients_ = client.get("/opportunities", params={"relationship": "client"}, headers=headers).json()
    assert [o["lead_name"] for o in clients_] == ["Linked Lead"]


def test_list_filters_by_stage(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_opportunity(client, headers, lead_name="Won Lead")
    client.patch(f"/opportunities/{row['id']}/stage", json={"stage": "won"}, headers=headers)
    _create_opportunity(client, headers, lead_name="New Lead")

    won = client.get("/opportunities", params={"stage": "won"}, headers=headers).json()
    assert [o["lead_name"] for o in won] == ["Won Lead"]


def test_opportunity_changes_are_not_audit_logged(client, director_user):
    """Same convention as Client's own follow-up endpoint (Amendment 42):
    routine workflow, not a governance-relevant fact."""
    headers = _director_headers(client, director_user)
    row = _create_opportunity(client, headers)
    client.patch(f"/opportunities/{row['id']}/stage", json={"stage": "won"}, headers=headers)

    entries = client.get(
        "/audit-log", params={"document_type": "opportunity", "document_id": row["id"]}, headers=headers
    ).json()
    assert entries == []


# ---------------------------------------------------------------------------
# Amendment 44 Phase C: Won -> Start Project hand-off
# ---------------------------------------------------------------------------

_PROJECT_FIELDS = {
    "city": "Mumbai",
    "site_condition": "level",
    "soil_type": "normal",
    "building_status": "open_air",
    "site_access": "good",
    "power_available": "yes",
    "water_available": True,
    "package": "standard",
}


def _won_linked_opportunity(client, headers):
    client_row = _create_client_record(client, headers)
    opp = _create_opportunity(client, headers, client_id=client_row["id"])
    res = client.patch(f"/opportunities/{opp['id']}/stage", json={"stage": "won"}, headers=headers)
    assert res.status_code == 200, res.text
    return client_row, res.json()


def test_start_project_from_a_won_linked_opportunity(client, director_user):
    headers = _director_headers(client, director_user)
    client_row, opp = _won_linked_opportunity(client, headers)

    res = client.post(
        "/projects",
        json={"client_id": client_row["id"], "opportunity_id": opp["id"], **_PROJECT_FIELDS},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    project = res.json()
    assert project["opportunity_id"] == opp["id"]

    back = client.get(f"/opportunities/{opp['id']}", headers=headers).json()
    assert back["project_id"] == project["id"]


def test_start_project_rejects_a_non_won_opportunity(client, director_user):
    headers = _director_headers(client, director_user)
    client_row = _create_client_record(client, headers)
    opp = _create_opportunity(client, headers, client_id=client_row["id"])  # still "new"

    res = client.post(
        "/projects",
        json={"client_id": client_row["id"], "opportunity_id": opp["id"], **_PROJECT_FIELDS},
        headers=headers,
    )
    assert res.status_code == 400


def test_start_project_rejects_a_lead_only_opportunity(client, director_user):
    headers = _director_headers(client, director_user)
    client_row = _create_client_record(client, headers)
    opp = _create_opportunity(client, headers)  # no client_id
    client.patch(f"/opportunities/{opp['id']}/stage", json={"stage": "won"}, headers=headers)

    res = client.post(
        "/projects",
        json={"client_id": client_row["id"], "opportunity_id": opp["id"], **_PROJECT_FIELDS},
        headers=headers,
    )
    assert res.status_code == 400


def test_start_project_rejects_a_client_mismatch(client, director_user):
    headers = _director_headers(client, director_user)
    _, opp = _won_linked_opportunity(client, headers)
    other_client = _create_client_record(client, headers, name="Some Other Client")

    res = client.post(
        "/projects",
        json={"client_id": other_client["id"], "opportunity_id": opp["id"], **_PROJECT_FIELDS},
        headers=headers,
    )
    assert res.status_code == 400


def test_an_opportunity_can_only_start_one_project(client, director_user):
    headers = _director_headers(client, director_user)
    client_row, opp = _won_linked_opportunity(client, headers)
    payload = {"client_id": client_row["id"], "opportunity_id": opp["id"], **_PROJECT_FIELDS}

    assert client.post("/projects", json=payload, headers=headers).status_code == 201
    assert client.post("/projects", json=payload, headers=headers).status_code == 400


def test_start_project_with_unknown_opportunity_is_404(client, director_user):
    headers = _director_headers(client, director_user)
    client_row = _create_client_record(client, headers)
    res = client.post(
        "/projects",
        json={
            "client_id": client_row["id"],
            "opportunity_id": "00000000-0000-0000-0000-000000000000",
            **_PROJECT_FIELDS,
        },
        headers=headers,
    )
    assert res.status_code == 404


def test_an_ordinary_project_has_no_opportunity_id(client, director_user):
    headers = _director_headers(client, director_user)
    client_row = _create_client_record(client, headers)
    res = client.post("/projects", json={"client_id": client_row["id"], **_PROJECT_FIELDS}, headers=headers)
    assert res.status_code == 201, res.text
    assert res.json()["opportunity_id"] is None
