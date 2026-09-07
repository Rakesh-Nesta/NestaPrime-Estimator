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


def _scope_item_payload(**overrides):
    payload = {"key": "drone_landing_pad", "display_order": 999, "group": "external", "name": "Drone landing pad"}
    payload.update(overrides)
    return payload


def test_director_can_create_a_scope_item(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post("/scope-items", json=_scope_item_payload(), headers=headers)
    assert res.status_code == 201, res.text
    assert res.json()["is_active"] is True

    listed = client.get("/scope-items", headers=headers).json()
    assert any(i["key"] == "drone_landing_pad" for i in listed)


def test_pm_cannot_create_a_scope_item(client, director_user, db_session):
    pm_headers = _pm_headers(client, db_session)
    res = client.post("/scope-items", json=_scope_item_payload(), headers=pm_headers)
    assert res.status_code == 403


def test_duplicate_key_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    client.post("/scope-items", json=_scope_item_payload(), headers=headers)
    res = client.post(
        "/scope-items", json=_scope_item_payload(key="drone_landing_pad", name="Other"), headers=headers
    )
    assert res.status_code == 409


def test_director_can_update_a_scope_item(client, director_user):
    headers = _director_headers(client, director_user)
    item_id = client.post("/scope-items", json=_scope_item_payload(), headers=headers).json()["id"]

    res = client.patch(f"/scope-items/{item_id}", json={"name": "Drone pad (helipad style)"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["name"] == "Drone pad (helipad style)"
    assert res.json()["key"] == "drone_landing_pad"


def test_pm_cannot_update_a_scope_item(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    item_id = client.post("/scope-items", json=_scope_item_payload(), headers=director_headers).json()["id"]

    pm_headers = _pm_headers(client, db_session)
    res = client.patch(f"/scope-items/{item_id}", json={"name": "Renamed"}, headers=pm_headers)
    assert res.status_code == 403


def test_update_missing_scope_item_404s(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.patch(
        "/scope-items/00000000-0000-0000-0000-000000000000", json={"name": "Ghost"}, headers=headers
    )
    assert res.status_code == 404


def test_deactivating_a_scope_item_hides_it_from_default_listing(client, director_user):
    headers = _director_headers(client, director_user)
    item_id = client.post("/scope-items", json=_scope_item_payload(), headers=headers).json()["id"]

    patch_res = client.patch(f"/scope-items/{item_id}", json={"is_active": False}, headers=headers)
    assert patch_res.status_code == 200
    assert patch_res.json()["is_active"] is False

    default_listing = client.get("/scope-items", headers=headers).json()
    assert not any(i["key"] == "drone_landing_pad" for i in default_listing)

    full_listing = client.get("/scope-items", params={"include_inactive": True}, headers=headers).json()
    assert any(i["key"] == "drone_landing_pad" for i in full_listing)


def test_seeded_scope_items_are_all_active_by_default(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.get("/scope-items", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 30
    assert all(i["is_active"] for i in res.json())
