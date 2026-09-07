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


def _sales_headers(client, db_session):
    user = User(
        name="Test Sales", email="sales@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.SALES
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales@test.local")


def _sport_payload(**overrides):
    payload = {
        "key": "kite_flying",
        "display_order": 999,
        "name": "Kite Flying",
        "category": "outdoor",
        "playing_dims": "custom",
        "build_dims": "custom",
        "governing_body": "NestaPrime standard (no federation)",
    }
    payload.update(overrides)
    return payload


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


def test_director_can_create_a_sport(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post("/sports", json=_sport_payload(), headers=headers)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["key"] == "kite_flying"
    assert body["is_active"] is True

    listed = client.get("/sports", headers=headers).json()
    assert any(s["key"] == "kite_flying" for s in listed)


def test_pm_cannot_create_a_sport(client, director_user, db_session):
    pm_headers = _pm_headers(client, db_session)
    res = client.post("/sports", json=_sport_payload(), headers=pm_headers)
    assert res.status_code == 403


def test_sales_cannot_create_a_sport(client, director_user, db_session):
    sales_headers = _sales_headers(client, db_session)
    res = client.post("/sports", json=_sport_payload(), headers=sales_headers)
    assert res.status_code == 403


def test_duplicate_key_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    client.post("/sports", json=_sport_payload(), headers=headers)
    res = client.post("/sports", json=_sport_payload(key="kite_flying", name="Kite Flying 2"), headers=headers)
    assert res.status_code == 409


def test_creating_a_sport_with_no_recommendation_coverage_still_works(client, director_user):
    """A brand-new key has no row in any of sports.py's _recommend_*
    tables -- the sport itself must still be creatable and listable;
    only its per-project recommendations come back None (unchanged
    'uncovered combination' behaviour, not a new failure mode)."""
    headers = _director_headers(client, director_user)
    res = client.post("/sports", json=_sport_payload(), headers=headers)
    assert res.status_code == 201, res.text


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


def test_director_can_update_a_sport(client, director_user):
    headers = _director_headers(client, director_user)
    sport_id = client.post("/sports", json=_sport_payload(), headers=headers).json()["id"]

    res = client.patch(f"/sports/{sport_id}", json={"governing_body": "World Kite Federation"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["governing_body"] == "World Kite Federation"
    assert res.json()["key"] == "kite_flying"  # unchanged


def test_key_cannot_be_changed_via_update(client, director_user):
    headers = _director_headers(client, director_user)
    sport_id = client.post("/sports", json=_sport_payload(), headers=headers).json()["id"]

    res = client.patch(f"/sports/{sport_id}", json={"key": "renamed_sport"}, headers=headers)
    # Pydantic ignores the unknown field silently (SportUpdate has no `key`), so this
    # succeeds but the key is untouched.
    assert res.status_code == 200, res.text
    assert res.json()["key"] == "kite_flying"


def test_pm_cannot_update_a_sport(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    sport_id = client.post("/sports", json=_sport_payload(), headers=director_headers).json()["id"]

    pm_headers = _pm_headers(client, db_session)
    res = client.patch(f"/sports/{sport_id}", json={"name": "Renamed"}, headers=pm_headers)
    assert res.status_code == 403


def test_update_missing_sport_404s(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.patch(
        "/sports/00000000-0000-0000-0000-000000000000", json={"name": "Ghost"}, headers=headers
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Deactivation
# ---------------------------------------------------------------------------


def test_deactivating_a_sport_hides_it_from_default_listing(client, director_user):
    headers = _director_headers(client, director_user)
    sport_id = client.post("/sports", json=_sport_payload(), headers=headers).json()["id"]

    patch_res = client.patch(f"/sports/{sport_id}", json={"is_active": False}, headers=headers)
    assert patch_res.status_code == 200
    assert patch_res.json()["is_active"] is False

    default_listing = client.get("/sports", headers=headers).json()
    assert not any(s["key"] == "kite_flying" for s in default_listing)

    full_listing = client.get("/sports", params={"include_inactive": True}, headers=headers).json()
    assert any(s["key"] == "kite_flying" for s in full_listing)


def test_deactivated_sport_can_still_be_reactivated(client, director_user):
    headers = _director_headers(client, director_user)
    sport_id = client.post("/sports", json=_sport_payload(), headers=headers).json()["id"]
    client.patch(f"/sports/{sport_id}", json={"is_active": False}, headers=headers)

    res = client.patch(f"/sports/{sport_id}", json={"is_active": True}, headers=headers)
    assert res.status_code == 200
    assert res.json()["is_active"] is True
    assert any(s["key"] == "kite_flying" for s in client.get("/sports", headers=headers).json())


def test_seeded_sports_are_all_active_by_default(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.get("/sports", headers=headers)
    assert res.status_code == 200
    assert len(res.json()) == 30
    assert all(s["is_active"] for s in res.json())
