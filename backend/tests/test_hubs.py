from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _pm_headers(client, db_session):
    user = User(name="Test PM", email="pm@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.PM)
    db_session.add(user)
    db_session.commit()
    return _login(client, "pm@test.local")


def _ca_tax_headers(client, db_session):
    user = User(
        name="Test CA", email="ca@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.CA_TAX
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "ca@test.local")


def _hub_payload(**overrides):
    payload = {"name": "Bhiwandi Depot", "city": "Mumbai", "state_code": "MH"}
    payload.update(overrides)
    return payload


def test_director_can_create_a_hub(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post("/hubs", json=_hub_payload(), headers=headers)
    assert res.status_code == 201, res.text
    assert res.json()["is_active"] is True

    listed = client.get("/hubs", headers=headers).json()
    assert any(h["name"] == "Bhiwandi Depot" for h in listed)


def test_pm_cannot_create_a_hub(client, director_user, db_session):
    pm_headers = _pm_headers(client, db_session)
    res = client.post("/hubs", json=_hub_payload(), headers=pm_headers)
    assert res.status_code == 403


def test_duplicate_hub_name_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    client.post("/hubs", json=_hub_payload(), headers=headers)
    res = client.post("/hubs", json=_hub_payload(city="Pune"), headers=headers)
    assert res.status_code == 409


def test_director_can_update_a_hub(client, director_user):
    headers = _director_headers(client, director_user)
    hub_id = client.post("/hubs", json=_hub_payload(), headers=headers).json()["id"]

    res = client.patch(f"/hubs/{hub_id}", json={"city": "Thane"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["city"] == "Thane"
    assert res.json()["name"] == "Bhiwandi Depot"


def test_pm_cannot_update_a_hub(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    hub_id = client.post("/hubs", json=_hub_payload(), headers=director_headers).json()["id"]

    pm_headers = _pm_headers(client, db_session)
    res = client.patch(f"/hubs/{hub_id}", json={"city": "Thane"}, headers=pm_headers)
    assert res.status_code == 403


def test_update_missing_hub_404s(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.patch("/hubs/00000000-0000-0000-0000-000000000000", json={"city": "Thane"}, headers=headers)
    assert res.status_code == 404


def test_deactivating_a_hub_hides_it_from_default_listing(client, director_user):
    headers = _director_headers(client, director_user)
    hub_id = client.post("/hubs", json=_hub_payload(), headers=headers).json()["id"]

    patch_res = client.patch(f"/hubs/{hub_id}", json={"is_active": False}, headers=headers)
    assert patch_res.status_code == 200
    assert patch_res.json()["is_active"] is False

    default_listing = client.get("/hubs", headers=headers).json()
    assert not any(h["id"] == hub_id for h in default_listing)

    full_listing = client.get("/hubs", params={"include_inactive": True}, headers=headers).json()
    assert any(h["id"] == hub_id for h in full_listing)


def test_ca_tax_cannot_read_hubs(client, director_user, db_session):
    """A.3: CA/Tax has no reason to touch site-logistics reference data --
    matches the ALL_ATTACHMENT_ROLES precedent of excluding this role
    from operational masters it never needs."""
    ca_headers = _ca_tax_headers(client, db_session)
    res = client.get("/hubs", headers=ca_headers)
    assert res.status_code == 403


def test_new_hub_starts_empty(client, director_user):
    """No worked example exists in the blueprint for real hub names
    (unlike RegionalMultiplier's Mumbai/Chennai/Delhi NCR figures) -- the
    table starts empty rather than seeding fabricated hub data."""
    headers = _director_headers(client, director_user)
    res = client.get("/hubs", headers=headers)
    assert res.status_code == 200
    assert res.json() == []


# ---------------------------------------------------------------------------
# Project.hub_id wiring (B.1 field #4)
# ---------------------------------------------------------------------------


def _create_client_record(client, headers):
    res = client.post("/clients", json={"name": "Hub Wiring Test Client", "type": "school"}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _project_fields(client_id, **overrides):
    fields = {
        "client_id": client_id, "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
        "building_status": "open_air", "site_access": "good", "power_available": "yes",
        "water_available": True, "package": "standard",
    }
    fields.update(overrides)
    return fields


def test_project_can_reference_a_hub(client, director_user):
    headers = _director_headers(client, director_user)
    hub_id = client.post("/hubs", json=_hub_payload(), headers=headers).json()["id"]
    client_id = _create_client_record(client, headers)

    res = client.post(
        "/projects", json=_project_fields(client_id, hub_id=hub_id, distance_km=42.5), headers=headers
    )
    assert res.status_code == 201, res.text
    assert res.json()["hub_id"] == hub_id
    assert res.json()["distance_km"] == 42.5


def test_project_creation_rejects_an_unknown_hub(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)

    res = client.post(
        "/projects",
        json=_project_fields(client_id, hub_id="00000000-0000-0000-0000-000000000000"),
        headers=headers,
    )
    assert res.status_code == 404


def test_project_without_a_hub_still_works(client, director_user):
    """hub_id is optional -- a site with no nearby NestaPrime hub, or a
    project created before any hub existed, must remain representable."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)

    res = client.post("/projects", json=_project_fields(client_id), headers=headers)
    assert res.status_code == 201, res.text
    assert res.json()["hub_id"] is None
