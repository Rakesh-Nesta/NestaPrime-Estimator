from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _sales_headers(client, db_session):
    user = User(
        name="Test Sales", email="sales@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.SALES
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales@test.local")


def _create_client_record(client, headers):
    res = client.post("/clients", json={"name": "Gym Client", "type": "school"}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id):
    fields = {
        "client_id": client_id, "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
        "building_status": "open_air", "site_access": "good", "power_available": "yes",
        "water_available": True, "package": "standard",
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _add_project_sport(client, headers, project_id, sport_key="gymnasium"):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports", json={"sport_id": sport_id, "building_status": "open_air"}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _setup(client, headers):
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers).json()["id"]
    return project_id, project_sport_id, cost_sheet_id


def test_sales_cannot_add_gym_takeoff(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/gym",
        json={
            "project_sport_id": project_sport_id,
            "zones": [{"zone_name": "Cardio", "area_sqft": 500, "flooring_rate_per_sqft": 120}],
        },
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_zone_flooring_lines(client, director_user):
    """G.2: 'Area | sqft, zones ... -> Flooring per zone.'"""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/gym",
        json={
            "project_sport_id": project_sport_id,
            "zones": [
                {"zone_name": "Cardio", "area_sqft": 500, "flooring_rate_per_sqft": 120},
                {"zone_name": "Free weights", "area_sqft": 300, "flooring_rate_per_sqft": 180},
            ],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    lines = res.json()["lines"]
    assert len(lines) == 2
    cardio = next(line for line in lines if line["item_name"] == "Cardio flooring")
    free_weights = next(line for line in lines if line["item_name"] == "Free weights flooring")
    assert cardio["work_package"] == "flooring"
    assert cardio["unit"] == "sqft"
    assert cardio["quantity"] == 500
    assert cardio["rate"] == 120
    assert free_weights["quantity"] == 300
    assert free_weights["rate"] == 180
    assert res.json()["breakdown"]["zones"][0]["amount"] == 500 * 120


def test_equipment_requires_electrical_point_rate(client, director_user):
    """G.2 services: 'electrical points per machine.'"""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/gym",
        json={
            "project_sport_id": project_sport_id,
            "equipment": [{"item_name": "Treadmill", "brand_tier": "Standard", "quantity": 4, "rate": 85000}],
        },
        headers=headers,
    )
    assert res.status_code == 422
    assert "electrical_point_rate" in res.json()["detail"]


def test_equipment_and_electrical_points_lines(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/gym",
        json={
            "project_sport_id": project_sport_id,
            "equipment": [
                {"item_name": "Treadmill", "brand_tier": "Standard", "quantity": 4, "rate": 85000},
                {"item_name": "Multi-station rig", "brand_tier": "Premium", "quantity": 2, "rate": 220000},
            ],
            "electrical_point_rate": 2500,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    lines = res.json()["lines"]
    assert len(lines) == 3
    treadmill = next(line for line in lines if line["item_name"] == "Treadmill (Standard)")
    rig = next(line for line in lines if line["item_name"] == "Multi-station rig (Premium)")
    electrical = next(line for line in lines if line["item_name"] == "Electrical points (1 per machine)")

    assert treadmill["work_package"] == "accessories"
    assert treadmill["quantity"] == 4
    assert rig["quantity"] == 2
    assert electrical["work_package"] == "electrical"
    assert electrical["unit"] == "point"
    assert electrical["quantity"] == 6  # 4 + 2, one point per machine
    assert electrical["rate"] == 2500
    assert electrical["labour_category_id"] is not None


def test_equipment_without_brand_tier_has_a_plain_item_name(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/gym",
        json={
            "project_sport_id": project_sport_id,
            "equipment": [{"item_name": "Yoga mats (set of 20)", "quantity": 1, "rate": 15000}],
            "electrical_point_rate": 2500,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["lines"][0]["item_name"] == "Yoga mats (set of 20)"


def test_capacity_is_recorded_but_not_used_to_derive_quantity(client, director_user):
    """G.2's own 'Inputs' column names capacity (users/hour), but the
    blueprint gives no catalogue/formula to compute equipment qty from
    it -- it's echoed in the breakdown, never used in a calculation."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/gym",
        json={
            "project_sport_id": project_sport_id,
            "equipment": [{"item_name": "Treadmill", "quantity": 4, "rate": 85000}],
            "electrical_point_rate": 2500,
            "capacity_users_per_hour": 40,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["breakdown"]["capacity_users_per_hour"] == 40
    # quantity is exactly what was entered, not derived from capacity
    assert res.json()["lines"][0]["quantity"] == 4


def test_at_least_one_zone_or_equipment_item_is_required(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/gym",
        json={"project_sport_id": project_sport_id},
        headers=headers,
    )
    assert res.status_code == 422
    assert "Provide at least one zone or one equipment item" in res.json()["detail"]


def test_gym_can_only_be_added_to_a_draft_cost_sheet(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    payload = {
        "project_sport_id": project_sport_id,
        "zones": [{"zone_name": "Cardio", "area_sqft": 500, "flooring_rate_per_sqft": 120}],
    }
    client.post(f"/cost-sheets/{cost_sheet_id}/gym", json=payload, headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)

    res = client.post(f"/cost-sheets/{cost_sheet_id}/gym", json=payload, headers=headers)
    assert res.status_code == 400


def test_gym_feeds_into_recompute(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    payload = {
        "project_sport_id": project_sport_id,
        "zones": [{"zone_name": "Cardio", "area_sqft": 500, "flooring_rate_per_sqft": 120}],
        "equipment": [{"item_name": "Treadmill", "quantity": 4, "rate": 85000}],
        "electrical_point_rate": 2500,
    }
    client.post(f"/cost-sheets/{cost_sheet_id}/gym", json=payload, headers=headers)
    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    assert recomputed["cost_total"] > 0
    verify_res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert verify_res.status_code == 200


def test_wrong_project_sport_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    _, _, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/gym",
        json={
            "project_sport_id": "00000000-0000-0000-0000-000000000000",
            "zones": [{"zone_name": "Cardio", "area_sqft": 500, "flooring_rate_per_sqft": 120}],
        },
        headers=headers,
    )
    assert res.status_code == 404
