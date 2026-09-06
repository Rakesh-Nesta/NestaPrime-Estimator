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
    res = client.post("/clients", json={"name": "Lighting Client", "type": "school"}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id):
    fields = {
        "client_id": client_id,
        "city": "Mumbai",
        "site_condition": "level",
        "soil_type": "normal",
        "building_status": "open_air",
        "site_access": "good",
        "power_available": "yes",
        "water_available": True,
        "package": "standard",
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _add_project_sport(client, headers, project_id, sport_key="box_cricket", building_status="open_air"):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": sport_id, "building_status": building_status},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _setup(client, headers, sport_key="box_cricket", building_status="open_air"):
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id, sport_key=sport_key, building_status=building_status)
    cost_sheet_id = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers).json()["id"]
    return project_id, project_sport_id, cost_sheet_id


def test_sales_cannot_add_lighting(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/lighting",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "lux": 500,
            "lumens_per_fixture": 26000,
            "wattage_per_fixture": 200,
            "fixture_rate_each": 12000,
        },
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_h_worked_example_box_cricket_six_fixtures(client, director_user):
    """H's own worked example: 50x25 ft box cricket (outdoor, UF 0.6,
    MF 0.7) x 500 lux / (26,000 lm fixture) = 5.3 -> 6 fixtures."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/lighting",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "lux": 500,
            "lumens_per_fixture": 26000,
            "wattage_per_fixture": 200,
            "fixture_rate_each": 12000,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]
    assert breakdown["uf"] == 0.6
    assert breakdown["mf"] == 0.7
    assert breakdown["fixtures_by_formula"] == 6
    assert breakdown["fixture_count"] == 6
    assert round(breakdown["total_kw"], 2) == round(6 * 200 / 1000, 2)

    lines = res.json()["lines"]
    assert len(lines) == 1
    assert lines[0]["work_package"] == "electrical"
    assert lines[0]["quantity"] == 6
    assert lines[0]["amount"] == 6 * 12000


def test_indoor_sport_uses_indoor_uf_mf(client, director_user):
    """H: UF 0.7 / MF 0.8 indoor. Badminton 52x30 ft, 500 lux, 26000 lm
    -> raw 4.977, ceil 5 (independently computed)."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="badminton", building_status="new_peb_building")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/lighting",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 52,
            "build_w_ft": 30,
            "lux": 500,
            "lumens_per_fixture": 26000,
            "wattage_per_fixture": 200,
            "fixture_rate_each": 12000,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]
    assert breakdown["uf"] == 0.7
    assert breakdown["mf"] == 0.8
    assert breakdown["fixtures_by_formula"] == 5
    assert breakdown["fixture_count"] == 5  # no poles -- no even-rounding


def test_poles_force_even_fixture_count(client, director_user):
    """H: 'Final fixture count = max(formula result, poles x 1) and
    rounded to an even number when poles are used.' 34x32 ft outdoor,
    formula ceils to 5; 7 poles -> max(5,7)=7 (odd) -> rounds to 8."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/lighting",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 34,
            "build_w_ft": 32,
            "lux": 500,
            "lumens_per_fixture": 26000,
            "wattage_per_fixture": 200,
            "fixture_rate_each": 12000,
            "uses_poles": True,
            "pole_count": 7,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]
    assert breakdown["fixtures_by_formula"] == 5
    assert breakdown["fixture_count"] == 8


def test_uses_poles_requires_pole_count(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/lighting",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "lux": 500,
            "lumens_per_fixture": 26000,
            "wattage_per_fixture": 200,
            "fixture_rate_each": 12000,
            "uses_poles": True,
        },
        headers=headers,
    )
    assert res.status_code == 422


def test_lightning_arrestor_required_above_ten_metre_poles(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    missing_rate = client.post(
        f"/cost-sheets/{cost_sheet_id}/lighting",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "lux": 500,
            "lumens_per_fixture": 26000,
            "wattage_per_fixture": 200,
            "fixture_rate_each": 12000,
            "uses_poles": True,
            "pole_count": 4,
            "pole_height_m": 12,
        },
        headers=headers,
    )
    assert missing_rate.status_code == 422

    with_rate = client.post(
        f"/cost-sheets/{cost_sheet_id}/lighting",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "lux": 500,
            "lumens_per_fixture": 26000,
            "wattage_per_fixture": 200,
            "fixture_rate_each": 12000,
            "uses_poles": True,
            "pole_count": 4,
            "pole_height_m": 12,
            "lightning_arrestor_rate": 8000,
        },
        headers=headers,
    )
    assert with_rate.status_code == 201, with_rate.text
    lines = with_rate.json()["lines"]
    assert any(line["item_name"] == "Lightning arrestor" for line in lines)


def test_pole_under_ten_metres_skips_lightning_arrestor(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/lighting",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "lux": 500,
            "lumens_per_fixture": 26000,
            "wattage_per_fixture": 200,
            "fixture_rate_each": 12000,
            "uses_poles": True,
            "pole_count": 4,
            "pole_height_m": 8,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    lines = res.json()["lines"]
    assert not any(line["item_name"] == "Lightning arrestor" for line in lines)


def test_optional_addons_only_added_when_rates_supplied(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/lighting",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "lux": 500,
            "lumens_per_fixture": 26000,
            "wattage_per_fixture": 200,
            "fixture_rate_each": 12000,
            "cable_length_m": 80,
            "cable_rate_per_m": 150,
            "mcb_panel_rate": 9000,
            "earthing_rate": 5000,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    lines = res.json()["lines"]
    assert len(lines) == 4  # fixtures, cabling, MCB panel, earthing
    categories = {line["item_name"] for line in lines}
    assert {"Lighting cabling", "MCB panel", "Earthing"}.issubset(categories)


def test_monthly_running_cost_is_informational_only(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/lighting",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "lux": 500,
            "lumens_per_fixture": 26000,
            "wattage_per_fixture": 200,
            "fixture_rate_each": 12000,
            "tariff_rate_per_kwh": 9,
            "hours_per_day": 4,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]
    expected_kw = 6 * 200 / 1000
    assert round(breakdown["monthly_running_cost_estimate"], 2) == round(expected_kw * 4 * 30 * 9, 2)
    # It's informational, not a cost line -- still just the one fixture line.
    assert len(res.json()["lines"]) == 1


def test_lighting_can_only_be_added_to_a_draft_cost_sheet(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/lighting",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "lux": 500,
            "lumens_per_fixture": 26000,
            "wattage_per_fixture": 200,
            "fixture_rate_each": 12000,
        },
        headers=headers,
    )
    client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/lighting",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 20,
            "build_w_ft": 10,
            "lux": 200,
            "lumens_per_fixture": 26000,
            "wattage_per_fixture": 150,
            "fixture_rate_each": 9000,
        },
        headers=headers,
    )
    assert res.status_code == 400


def test_lighting_line_feeds_into_recompute(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/lighting",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "lux": 500,
            "lumens_per_fixture": 26000,
            "wattage_per_fixture": 200,
            "fixture_rate_each": 12000,
        },
        headers=headers,
    )
    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    assert recomputed["cost_total"] > 0
    verify_res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert verify_res.status_code == 200
