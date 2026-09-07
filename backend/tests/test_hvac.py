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
    res = client.post("/clients", json={"name": "HVAC Client", "type": "school"}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id):
    fields = {
        "client_id": client_id,
        "city": "Mumbai",
        "site_condition": "level",
        "soil_type": "normal",
        "building_status": "new_peb_building",
        "site_access": "good",
        "power_available": "yes",
        "water_available": True,
        "package": "standard",
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _add_project_sport(client, headers, project_id, sport_key="badminton"):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": sport_id, "building_status": "new_peb_building"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _setup(client, headers, sport_key="badminton"):
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id, sport_key=sport_key)
    cost_sheet_id = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers).json()["id"]
    return project_id, project_sport_id, cost_sheet_id


def test_sales_cannot_add_hvac(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/hvac",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 60,
            "build_w_ft": 36,
            "height_ft": 24,
            "climate": "hot_humid",
            "ac_rate_per_tr": 55000,
            "ducting_rate_per_sqft": 60,
        },
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_g5_worked_example_badminton_hall_mumbai(client, director_user):
    """G.5's own worked example: 60x36x24 ft badminton hall in Mumbai
    (hot-humid, height factor 1.2 for 16-24ft) = (2160/130) x 1.3 x 1.2
    = 25.92 -> 26 TR."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/hvac",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 60,
            "build_w_ft": 36,
            "height_ft": 24,
            "climate": "hot_humid",
            "ac_rate_per_tr": 55000,
            "ducting_rate_per_sqft": 60,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]
    assert breakdown["floor_area_sqft"] == 2160.0
    assert breakdown["climate_factor"] == 1.3
    assert breakdown["height_factor"] == 1.2
    assert round(breakdown["tonnage_raw"], 2) == 25.92
    assert breakdown["tonnage_tr"] == 26
    assert breakdown["engineer_confirmation_required"] is False

    lines = res.json()["lines"]
    ac_line = next(line for line in lines if line["item_name"].startswith("AC unit"))
    assert ac_line["quantity"] == 26
    assert ac_line["work_package"] == "hvac"
    ducting_line = next(line for line in lines if line["item_name"] == "Ducting")
    assert ducting_line["quantity"] == 2160.0


def test_height_above_24ft_uses_1_4_factor(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/hvac",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 60,
            "build_w_ft": 36,
            "height_ft": 26,
            "climate": "moderate",
            "ac_rate_per_tr": 55000,
            "ducting_rate_per_sqft": 60,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["breakdown"]["height_factor"] == 1.4


def test_large_hall_flags_engineer_confirmation_above_40tr(client, director_user):
    """G.5: 'HVAC engineer to confirm above 40 TR.'"""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/hvac",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 150,
            "build_w_ft": 80,
            "height_ft": 24,
            "climate": "hot_humid",
            "ac_rate_per_tr": 55000,
            "ducting_rate_per_sqft": 60,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]
    assert breakdown["tonnage_tr"] > 40
    assert breakdown["engineer_confirmation_required"] is True


def test_acoustic_panels_use_sport_specific_coverage(client, director_user):
    """G.5: badminton 25%, squash 40%, TT 25%, gym 20%."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="badminton")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/hvac",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 60,
            "build_w_ft": 36,
            "height_ft": 24,
            "climate": "hot_humid",
            "ac_rate_per_tr": 55000,
            "ducting_rate_per_sqft": 60,
            "acoustic_panel_rate_per_sqm": 1200,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]
    assert breakdown["coverage_percent"] == 25.0
    wall_area_sqft = 2 * (60 + 36) * 24
    expected_sqm = wall_area_sqft * 0.25 * 0.09290304
    assert round(breakdown["acoustic_panel_area_sqm"], 2) == round(expected_sqm, 2)

    lines = res.json()["lines"]
    acoustic_line = next(line for line in lines if line["category"] == "Acoustic treatment")
    assert acoustic_line["work_package"] == "hvac"


def test_squash_uses_forty_percent_coverage(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="squash")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/hvac",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 32,
            "build_w_ft": 21,
            "height_ft": 20,
            "climate": "moderate",
            "ac_rate_per_tr": 55000,
            "ducting_rate_per_sqft": 60,
            "acoustic_panel_rate_per_sqm": 1200,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["breakdown"]["coverage_percent"] == 40.0


def test_sport_without_coverage_default_requires_explicit_override(client, director_user):
    """Box cricket has no G.5 coverage entry -- requesting an acoustic
    line without an override must be rejected, not guessed."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="box_cricket")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/hvac",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "height_ft": 14,
            "climate": "hot_humid",
            "ac_rate_per_tr": 55000,
            "ducting_rate_per_sqft": 60,
            "acoustic_panel_rate_per_sqm": 1200,
        },
        headers=headers,
    )
    assert res.status_code == 422

    with_override = client.post(
        f"/cost-sheets/{cost_sheet_id}/hvac",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "height_ft": 14,
            "climate": "hot_humid",
            "ac_rate_per_tr": 55000,
            "ducting_rate_per_sqft": 60,
            "acoustic_panel_rate_per_sqm": 1200,
            "coverage_percent": 30.0,
        },
        headers=headers,
    )
    assert with_override.status_code == 201, with_override.text
    assert with_override.json()["breakdown"]["coverage_percent"] == 30.0


def test_no_acoustic_line_when_no_rate_supplied(client, director_user):
    """The informational area still shows in the breakdown (badminton has
    a G.5 coverage default) -- it just isn't priced into a line without a
    rate."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/hvac",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 60,
            "build_w_ft": 36,
            "height_ft": 24,
            "climate": "hot_humid",
            "ac_rate_per_tr": 55000,
            "ducting_rate_per_sqft": 60,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["breakdown"]["acoustic_panel_area_sqm"] is not None
    lines = res.json()["lines"]
    assert len(lines) == 2  # AC unit + ducting only -- no acoustic line without a rate
    assert not any(line["category"] == "Acoustic treatment" for line in lines)


def test_fresh_air_line_requires_occupancy(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/hvac",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 60,
            "build_w_ft": 36,
            "height_ft": 24,
            "climate": "hot_humid",
            "ac_rate_per_tr": 55000,
            "ducting_rate_per_sqft": 60,
            "fresh_air_unit_rate": 40,
        },
        headers=headers,
    )
    assert res.status_code == 422


def test_fresh_air_cfm_matches_occupancy(client, director_user):
    """G.5: 'fresh air 15 CFM/person.'"""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/hvac",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 60,
            "build_w_ft": 36,
            "height_ft": 24,
            "climate": "hot_humid",
            "ac_rate_per_tr": 55000,
            "ducting_rate_per_sqft": 60,
            "occupancy": 40,
            "fresh_air_unit_rate": 40,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["breakdown"]["fresh_air_cfm"] == 600
    lines = res.json()["lines"]
    fresh_air_line = next(line for line in lines if line["item_name"] == "Fresh air handling")
    assert fresh_air_line["quantity"] == 600


def test_hvac_can_only_be_added_to_a_draft_cost_sheet(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/hvac",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 60,
            "build_w_ft": 36,
            "height_ft": 24,
            "climate": "hot_humid",
            "ac_rate_per_tr": 55000,
            "ducting_rate_per_sqft": 60,
        },
        headers=headers,
    )
    client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/hvac",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 20,
            "build_w_ft": 10,
            "height_ft": 12,
            "climate": "moderate",
            "ac_rate_per_tr": 55000,
            "ducting_rate_per_sqft": 60,
        },
        headers=headers,
    )
    assert res.status_code == 400


def test_hvac_lines_feed_into_recompute(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/hvac",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 60,
            "build_w_ft": 36,
            "height_ft": 24,
            "climate": "hot_humid",
            "ac_rate_per_tr": 55000,
            "ducting_rate_per_sqft": 60,
        },
        headers=headers,
    )
    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    assert recomputed["cost_total"] > 0
    verify_res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert verify_res.status_code == 200
