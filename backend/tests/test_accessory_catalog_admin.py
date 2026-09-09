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


def _squash_sport_id(client, headers):
    return next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == "squash")


def _badminton_sport_id(client, headers):
    return next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == "badminton")


def test_seeded_catalog_matches_the_former_hardcoded_dict(client, director_user):
    """20 rows total across the 19 sports the old ACCESSORY_CATALOG dict
    named (padel alone has 2 items) -- confirms the migration/seed
    preserved the existing working defaults exactly, not just the CRUD
    mechanism."""
    headers = _director_headers(client, director_user)
    res = client.get("/accessory-catalog", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 20
    assert all(row["is_active"] for row in res.json())


def test_squash_has_no_seeded_catalog_entry(client, director_user):
    """The old dict never had a squash row either -- confirms this isn't
    a silent behaviour change for sports with no catalog."""
    headers = _director_headers(client, director_user)
    sport_id = _squash_sport_id(client, headers)
    res = client.get("/accessory-catalog", params={"sport_id": sport_id}, headers=headers)
    assert res.status_code == 200
    assert res.json() == []


def test_director_can_add_a_catalog_item(client, director_user):
    headers = _director_headers(client, director_user)
    sport_id = _squash_sport_id(client, headers)

    res = client.post(
        "/accessory-catalog",
        json={"sport_id": sport_id, "item_name": "Squash racket rack", "unit": "nos", "quantity_per_court": 1},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["is_active"] is True

    listed = client.get("/accessory-catalog", params={"sport_id": sport_id}, headers=headers).json()
    assert len(listed) == 1
    assert listed[0]["item_name"] == "Squash racket rack"


def test_pm_cannot_add_a_catalog_item(client, director_user, db_session):
    pm_headers = _pm_headers(client, db_session)
    sport_id = _squash_sport_id(client, pm_headers)
    res = client.post(
        "/accessory-catalog",
        json={"sport_id": sport_id, "item_name": "Squash racket rack", "unit": "nos", "quantity_per_court": 1},
        headers=pm_headers,
    )
    assert res.status_code == 403


def test_ca_tax_cannot_read_the_catalog(client, director_user, db_session):
    ca_headers = _ca_tax_headers(client, db_session)
    res = client.get("/accessory-catalog", headers=ca_headers)
    assert res.status_code == 403


def test_duplicate_item_name_for_the_same_sport_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    sport_id = _badminton_sport_id(client, headers)

    res = client.post(
        "/accessory-catalog",
        json={"sport_id": sport_id, "item_name": "Badminton net + post set", "unit": "set", "quantity_per_court": 1},
        headers=headers,
    )
    assert res.status_code == 409


def test_create_requires_an_existing_sport(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/accessory-catalog",
        json={
            "sport_id": "00000000-0000-0000-0000-000000000000", "item_name": "Ghost item",
            "unit": "nos", "quantity_per_court": 1,
        },
        headers=headers,
    )
    assert res.status_code == 404


def test_director_can_update_a_catalog_item(client, director_user):
    headers = _director_headers(client, director_user)
    sport_id = _badminton_sport_id(client, headers)
    item_id = next(
        r["id"] for r in client.get("/accessory-catalog", params={"sport_id": sport_id}, headers=headers).json()
        if r["item_name"] == "Badminton net + post set"
    )

    res = client.patch(f"/accessory-catalog/{item_id}", json={"quantity_per_court": 2}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["quantity_per_court"] == 2.0


def test_deactivating_hides_from_default_listing_and_from_a_new_takeoff(client, director_user):
    """Deactivating a catalog item retires it from new take-offs -- the
    real point of is_active, beyond just the listing filter."""
    headers = _director_headers(client, director_user)
    sport_id = _badminton_sport_id(client, headers)
    item_id = next(
        r["id"] for r in client.get("/accessory-catalog", params={"sport_id": sport_id}, headers=headers).json()
        if r["item_name"] == "Badminton net + post set"
    )

    patch_res = client.patch(f"/accessory-catalog/{item_id}", json={"is_active": False}, headers=headers)
    assert patch_res.status_code == 200
    assert patch_res.json()["is_active"] is False

    default_listing = client.get("/accessory-catalog", params={"sport_id": sport_id}, headers=headers).json()
    assert default_listing == []
    full_listing = client.get(
        "/accessory-catalog", params={"sport_id": sport_id, "include_inactive": True}, headers=headers
    ).json()
    assert len(full_listing) == 1

    # a new take-off for badminton now has no catalog left -- must fall
    # back to the same "no catalog, use custom_items" behaviour as squash
    client_id = client.post("/clients", json={"name": "Deactivated Catalog Test", "type": "school"}, headers=headers).json()["id"]
    project_id = client.post(
        "/projects",
        json={
            "client_id": client_id, "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
            "building_status": "open_air", "site_access": "good", "power_available": "yes",
            "water_available": True, "package": "standard",
        },
        headers=headers,
    ).json()["id"]
    project_sport_id = client.post(
        f"/projects/{project_id}/sports", json={"sport_id": sport_id, "building_status": "open_air"}, headers=headers
    ).json()["id"]
    cost_sheet_id = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers).json()["id"]

    takeoff_res = client.post(
        f"/cost-sheets/{cost_sheet_id}/accessories", json={"project_sport_id": project_sport_id}, headers=headers
    )
    assert takeoff_res.status_code == 422
    assert "No accessories catalog for Badminton" in takeoff_res.json()["detail"]


def test_update_missing_item_404s(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.patch(
        "/accessory-catalog/00000000-0000-0000-0000-000000000000", json={"quantity_per_court": 2}, headers=headers
    )
    assert res.status_code == 404


def test_accessory_catalog_requires_auth(client):
    assert client.get("/accessory-catalog").status_code == 401
    assert client.post("/accessory-catalog", json={}).status_code == 401
