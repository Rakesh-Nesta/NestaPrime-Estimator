"""Amendment 37 (Section 43): an optional structured `city` on Client, so Project
Setup can pre-fill a new project's city from an existing client instead of always
defaulting to "Mumbai".

Deliberately optional, never backfilled from the free-text billing_address, and
never allowed to change an existing project."""
from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _role_headers(client, db_session, role, email):
    user = User(name=f"Test {role.value}", email=email, hashed_password=hash_password("TestPass!1"), role=role)
    db_session.add(user)
    db_session.commit()
    return _login(client, email)


def _create_client(client, headers, **overrides):
    payload = {"name": "City Test Client", "type": "school", **overrides}
    res = client.post("/clients", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


# --- creating ---------------------------------------------------------------


def test_city_defaults_to_null_and_is_always_in_the_response(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client(client, headers)
    assert "city" in row
    assert row["city"] is None


def test_a_client_can_be_created_with_a_city_and_it_is_trimmed(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client(client, headers, city="  Pune  ")
    assert row["city"] == "Pune"
    assert client.get(f"/clients/{row['id']}", headers=headers).json()["city"] == "Pune"


def test_a_blank_city_on_create_is_stored_as_null(client, director_user):
    headers = _director_headers(client, director_user)
    assert _create_client(client, headers, city="   ")["city"] is None
    assert _create_client(client, headers, city="")["city"] is None


def test_the_client_list_includes_city(client, director_user):
    headers = _director_headers(client, director_user)
    with_city = _create_client(client, headers, name="Has City", city="Nagpur")
    without = _create_client(client, headers, name="No City")
    rows = {r["id"]: r for r in client.get("/clients", headers=headers).json()}
    assert rows[with_city["id"]]["city"] == "Nagpur"
    assert rows[without["id"]]["city"] is None


def test_an_over_long_city_is_refused(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post("/clients", json={"name": "Long", "type": "school", "city": "x" * 101}, headers=headers)
    assert res.status_code == 422
    row = _create_client(client, headers, name="Fits", city="x" * 100)
    assert len(row["city"]) == 100


# --- editing ----------------------------------------------------------------


def test_city_can_be_added_to_an_existing_client_via_details(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client(client, headers)
    assert row["city"] is None

    res = client.patch(
        f"/clients/{row['id']}/details", json={"name": "City Test Client", "city": " Surat "}, headers=headers
    )
    assert res.status_code == 200, res.text
    assert res.json()["city"] == "Surat"


def test_city_omitted_from_an_edit_is_left_alone_and_blank_or_null_clears_it(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client(client, headers, city="Indore", phone="9000000001")

    # Sent without city: unchanged.
    res = client.patch(f"/clients/{row['id']}/details", json={"name": "City Test Client", "phone": "9111111111"}, headers=headers)
    assert res.json()["city"] == "Indore"
    assert res.json()["phone"] == "9111111111"

    # Blank string clears it; null clears it.
    res = client.patch(f"/clients/{row['id']}/details", json={"name": "City Test Client", "city": "  "}, headers=headers)
    assert res.json()["city"] is None
    client.patch(f"/clients/{row['id']}/details", json={"name": "City Test Client", "city": "Indore"}, headers=headers)
    res = client.patch(f"/clients/{row['id']}/details", json={"name": "City Test Client", "city": None}, headers=headers)
    assert res.json()["city"] is None


def test_an_over_long_city_on_edit_is_refused_and_changes_nothing(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client(client, headers, city="Thane")
    res = client.patch(f"/clients/{row['id']}/details", json={"name": "City Test Client", "city": "y" * 101}, headers=headers)
    assert res.status_code == 422
    assert client.get(f"/clients/{row['id']}", headers=headers).json()["city"] == "Thane"


def test_a_city_change_is_not_audit_logged_like_phone_and_email(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client(client, headers)
    client.patch(f"/clients/{row['id']}/details", json={"name": "City Test Client", "city": "Nashik"}, headers=headers)

    res = client.get("/audit-log", params={"document_type": "client", "document_id": row["id"]}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json() == []


def test_sales_can_edit_city_but_procurement_cannot(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    row = _create_client(client, headers)

    sales = _role_headers(client, db_session, UserRole.SALES, "sales-city@test.local")
    res = client.patch(f"/clients/{row['id']}/details", json={"name": "City Test Client", "city": "Goa"}, headers=sales)
    assert res.status_code == 200, res.text
    assert res.json()["city"] == "Goa"

    procurement = _role_headers(client, db_session, UserRole.PROCUREMENT, "proc-city@test.local")
    res = client.patch(f"/clients/{row['id']}/details", json={"name": "City Test Client", "city": "Hacked"}, headers=procurement)
    assert res.status_code == 403
    assert client.get(f"/clients/{row['id']}", headers=headers).json()["city"] == "Goa"


# --- what it must NOT do ----------------------------------------------------


def test_setting_a_clients_city_never_changes_an_existing_project(client, director_user):
    """The amendment only affects what the Project Setup form pre-fills with."""
    headers = _director_headers(client, director_user)
    row = _create_client(client, headers)
    fields = {
        "client_id": row["id"], "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
        "building_status": "open_air", "site_access": "good", "power_available": "yes",
        "water_available": True, "package": "standard",
    }
    project = client.post("/projects", json=fields, headers=headers)
    assert project.status_code == 201, project.text
    project_id = project.json()["id"]

    client.patch(f"/clients/{row['id']}/details", json={"name": "City Test Client", "city": "Pune"}, headers=headers)

    assert client.get(f"/projects/{project_id}", headers=headers).json()["city"] == "Mumbai"


def test_city_is_not_derived_from_the_billing_address(client, director_user):
    """No backfill: free-text address parsing could silently give a real client the wrong city."""
    headers = _director_headers(client, director_user)
    row = _create_client(client, headers, billing_address="12 MG Road, Bengaluru 560001")
    assert row["city"] is None


def test_editing_details_without_city_keeps_type_and_flags_untouched(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client(client, headers, city="Kochi")
    res = client.patch(f"/clients/{row['id']}/details", json={"name": "Renamed City Client"}, headers=headers)
    body = res.json()
    assert body["name"] == "Renamed City Client"
    assert body["city"] == "Kochi"
    assert body["type"] == "school"
    assert body["overdue_flag"] is False and body["blacklist_flag"] is False
