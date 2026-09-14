"""Amendment 5 Phase 2 (Section 6): "admin sets each field compulsory/
optional/hidden from Master Settings" -- New Project Setup's governed
fields (soil_type, distance_km, number_of_courts, site_access,
power_available)."""

from app.core.security import hash_password
from app.models.user import User, UserRole


def _director_headers(client, director_user):
    res = client.post("/auth/login", data={"username": "director@test.local", "password": "TestPass!1"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _sales_headers(client, db_session):
    user = User(
        name="Test Sales", email="sales@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.SALES
    )
    db_session.add(user)
    db_session.commit()
    res = client.post("/auth/login", data={"username": "sales@test.local", "password": "TestPass!1"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _create_client(client, headers, name="Field Settings Client"):
    res = client.post("/clients", json={"name": name, "type": "school"}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


BASE_PROJECT_FIELDS = {
    "city": "Mumbai",
    "site_condition": "level",
    "soil_type": "normal",
    "building_status": "open_air",
    "site_access": "good",
    "power_available": "yes",
    "water_available": True,
    "package": "standard",
}


def _create_project(client, headers, client_id, **overrides):
    fields = {"client_id": client_id, **BASE_PROJECT_FIELDS, **overrides}
    return client.post("/projects", json=fields, headers=headers)


# ---------------------------------------------------------------------------
# GET /field-settings
# ---------------------------------------------------------------------------


def test_field_settings_default_to_compulsory(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.get("/field-settings", headers=headers)
    assert res.status_code == 200, res.text
    body = {r["field_key"]: r["state"] for r in res.json()}
    assert body == {
        "soil_type": "compulsory",
        "distance_km": "compulsory",
        "number_of_courts": "compulsory",
        "site_access": "compulsory",
        "power_available": "compulsory",
    }


def test_sales_can_read_field_settings(client, db_session):
    """Sales needs this to render New Project Setup correctly."""
    headers = _sales_headers(client, db_session)
    res = client.get("/field-settings", headers=headers)
    assert res.status_code == 200, res.text


def test_field_settings_require_auth(client):
    assert client.get("/field-settings").status_code == 401


# ---------------------------------------------------------------------------
# PATCH /field-settings/{field_key}
# ---------------------------------------------------------------------------


def test_director_can_change_a_field_setting(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.patch("/field-settings/soil_type", json={"state": "optional"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json() == {"field_key": "soil_type", "state": "optional"}

    listed = {r["field_key"]: r["state"] for r in client.get("/field-settings", headers=headers).json()}
    assert listed["soil_type"] == "optional"


def test_sales_cannot_change_a_field_setting(client, db_session):
    headers = _sales_headers(client, db_session)
    res = client.patch("/field-settings/soil_type", json={"state": "hidden"}, headers=headers)
    assert res.status_code == 403


def test_unknown_field_key_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.patch("/field-settings/client_type", json={"state": "hidden"}, headers=headers)
    assert res.status_code == 404


def test_changing_a_field_setting_writes_an_audit_log_entry(client, director_user):
    headers = _director_headers(client, director_user)
    client.patch("/field-settings/power_available", json={"state": "hidden"}, headers=headers)

    entries = client.get("/audit-log", params={"document_type": "field_setting"}, headers=headers).json()
    assert len(entries) == 1
    assert entries[0]["field"] == "power_available"
    assert entries[0]["old_value"] == "compulsory"
    assert entries[0]["new_value"] == "hidden"


# ---------------------------------------------------------------------------
# Enforcement on project creation
# ---------------------------------------------------------------------------


def test_missing_governed_field_is_rejected_while_compulsory(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client(client, headers)

    res = _create_project(client, headers, client_id, soil_type=None)
    assert res.status_code == 422, res.text
    assert "soil_type" in res.json()["detail"]


def test_missing_governed_field_is_accepted_once_optional(client, director_user):
    headers = _director_headers(client, director_user)
    client.patch("/field-settings/soil_type", json={"state": "optional"}, headers=headers)
    client_id = _create_client(client, headers)

    res = _create_project(client, headers, client_id, soil_type=None)
    assert res.status_code == 201, res.text


def test_missing_governed_field_is_accepted_once_hidden(client, director_user):
    headers = _director_headers(client, director_user)
    client.patch("/field-settings/site_access", json={"state": "hidden"}, headers=headers)
    client_id = _create_client(client, headers)

    res = _create_project(client, headers, client_id, site_access=None)
    assert res.status_code == 201, res.text


def test_setting_a_field_back_to_compulsory_restores_the_original_behaviour(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client(client, headers)

    client.patch("/field-settings/power_available", json={"state": "optional"}, headers=headers)
    ok = _create_project(client, headers, client_id, power_available=None)
    assert ok.status_code == 201, ok.text

    client.patch("/field-settings/power_available", json={"state": "compulsory"}, headers=headers)
    rejected = _create_project(client, headers, client_id, power_available=None)
    assert rejected.status_code == 422, rejected.text


def test_all_three_backend_enforced_fields_independently_gated(client, director_user):
    """soil_type, site_access, power_available each gate independently --
    marking one Optional doesn't loosen the other two."""
    headers = _director_headers(client, director_user)
    client.patch("/field-settings/soil_type", json={"state": "optional"}, headers=headers)
    client_id = _create_client(client, headers)

    res = _create_project(client, headers, client_id, soil_type=None, site_access=None)
    assert res.status_code == 422, res.text
    assert "site_access" in res.json()["detail"]


def test_distance_km_and_number_of_courts_never_blocked_regardless_of_setting(client, director_user):
    """These two were already nullable/defaulted before this amendment --
    a field-setting only controls whether New Project Setup shows them,
    never whether the API accepts their absence."""
    headers = _director_headers(client, director_user)
    client_id = _create_client(client, headers)

    res = _create_project(client, headers, client_id, distance_km=None)
    assert res.status_code == 201, res.text
    assert res.json()["number_of_courts"] == 1


def test_created_project_stores_null_for_an_optional_field_left_blank(client, director_user):
    headers = _director_headers(client, director_user)
    client.patch("/field-settings/soil_type", json={"state": "optional"}, headers=headers)
    client_id = _create_client(client, headers)

    res = _create_project(client, headers, client_id, soil_type=None)
    assert res.status_code == 201, res.text
    assert res.json()["soil_type"] is None
    # Derived D.4 site-prep flags degrade safely rather than crash on a
    # null soil_type.
    assert res.json()["soil_test_required"] is False
    assert res.json()["rock_breaking_required"] is False
