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


def _pm_headers(client, db_session):
    user = User(name="Test PM", email="pm@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.PM)
    db_session.add(user)
    db_session.commit()
    return _login(client, "pm@test.local")


def _procurement_headers(client, db_session):
    user = User(
        name="Test Procurement", email="procurement@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.PROCUREMENT,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "procurement@test.local")


def _badminton_sport_id(client, headers):
    return next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == "badminton")


def _pool_sport_id(client, headers):
    return next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == "swimming_pool_25m")


CONTENT_PAYLOAD = {
    "flooring_description": "22mm interlocking PVC sports tiles",
    "structure_description": "Type C PEB structure, hot-dip galvanised",
    "lighting_description": "6 x 150 lm/W LED floodlights, 300 lux",
    "scope_description": "Full-size court markings\nNet post set\nScoreboard",
    "warranty_years": 5,
}


def test_director_can_create_package_content(client, director_user):
    headers = _director_headers(client, director_user)
    sport_id = _badminton_sport_id(client, headers)

    res = client.put(f"/package-contents/{sport_id}/premium", json=CONTENT_PAYLOAD, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["sport_id"] == sport_id
    assert body["tier"] == "premium"
    assert body["flooring_description"] == CONTENT_PAYLOAD["flooring_description"]
    assert body["warranty_years"] == 5


def test_upsert_replaces_content_rather_than_duplicating(client, director_user):
    headers = _director_headers(client, director_user)
    sport_id = _badminton_sport_id(client, headers)

    client.put(f"/package-contents/{sport_id}/standard", json=CONTENT_PAYLOAD, headers=headers)
    second_payload = {**CONTENT_PAYLOAD, "flooring_description": "Wooden sprung floor"}
    res = client.put(f"/package-contents/{sport_id}/standard", json=second_payload, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["flooring_description"] == "Wooden sprung floor"

    listed = client.get("/package-contents", params={"sport_id": sport_id}, headers=headers).json()
    assert len(listed) == 1


def test_three_tiers_coexist_independently_per_sport(client, director_user):
    headers = _director_headers(client, director_user)
    sport_id = _badminton_sport_id(client, headers)

    for tier in ("budget", "standard", "premium"):
        payload = {**CONTENT_PAYLOAD, "flooring_description": f"{tier} flooring"}
        client.put(f"/package-contents/{sport_id}/{tier}", json=payload, headers=headers)

    listed = client.get("/package-contents", params={"sport_id": sport_id}, headers=headers).json()
    assert len(listed) == 3
    by_tier = {row["tier"]: row for row in listed}
    assert by_tier["budget"]["flooring_description"] == "budget flooring"
    assert by_tier["premium"]["flooring_description"] == "premium flooring"


def test_content_is_scoped_per_sport(client, director_user):
    headers = _director_headers(client, director_user)
    badminton_id = _badminton_sport_id(client, headers)
    pool_id = _pool_sport_id(client, headers)

    client.put(f"/package-contents/{badminton_id}/standard", json=CONTENT_PAYLOAD, headers=headers)
    client.put(
        f"/package-contents/{pool_id}/standard",
        json={**CONTENT_PAYLOAD, "flooring_description": "Pool deck, anti-skid"},
        headers=headers,
    )

    badminton_only = client.get("/package-contents", params={"sport_id": badminton_id}, headers=headers).json()
    assert len(badminton_only) == 1
    assert badminton_only[0]["flooring_description"] == CONTENT_PAYLOAD["flooring_description"]


def test_upsert_requires_an_existing_sport(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.put(
        "/package-contents/00000000-0000-0000-0000-000000000000/standard", json=CONTENT_PAYLOAD, headers=headers
    )
    assert res.status_code == 404


def test_sales_can_read_but_not_write(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    sport_id = _badminton_sport_id(client, director_headers)
    client.put(f"/package-contents/{sport_id}/standard", json=CONTENT_PAYLOAD, headers=director_headers)

    sales_headers = _sales_headers(client, db_session)
    read_res = client.get("/package-contents", params={"sport_id": sport_id}, headers=sales_headers)
    assert read_res.status_code == 200, read_res.text

    write_res = client.put(f"/package-contents/{sport_id}/standard", json=CONTENT_PAYLOAD, headers=sales_headers)
    assert write_res.status_code == 403


def test_pm_can_read_but_not_write(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    sport_id = _badminton_sport_id(client, director_headers)

    pm_headers = _pm_headers(client, db_session)
    read_res = client.get("/package-contents", params={"sport_id": sport_id}, headers=pm_headers)
    assert read_res.status_code == 200, read_res.text

    write_res = client.put(f"/package-contents/{sport_id}/standard", json=CONTENT_PAYLOAD, headers=pm_headers)
    assert write_res.status_code == 403


def test_procurement_cannot_read_or_write(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    sport_id = _badminton_sport_id(client, director_headers)

    procurement_headers = _procurement_headers(client, db_session)
    read_res = client.get("/package-contents", params={"sport_id": sport_id}, headers=procurement_headers)
    assert read_res.status_code == 403

    write_res = client.put(f"/package-contents/{sport_id}/standard", json=CONTENT_PAYLOAD, headers=procurement_headers)
    assert write_res.status_code == 403
