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
    res = client.post("/clients", json={"name": "Flooring Client", "type": "school"}, headers=headers)
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


def _add_project_sport(client, headers, project_id, sport_key="box_cricket"):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": sport_id, "building_status": "open_air"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _setup(client, headers):
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers).json()["id"]
    return project_id, project_sport_id, cost_sheet_id


BASE_RATES = {"turf_rate_per_sqm": 900, "sand_rate_per_kg": 8, "rubber_rate_per_kg": 40}


def test_sales_cannot_add_turf(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/turf",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "pile_height": "40mm",
            **BASE_RATES,
        },
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_f5_worked_example_cut_length_allowed(client, director_user):
    """F.5's own worked example: 50x25 ft box cricket = 15.24 x 7.62 m.
    Cut-length ordering: 2 strips of a 4m-wide roll cut to the 15.24m
    length -> 121.92 sqm ordered (blueprint states ~122 sqm, 5% waste --
    our precision matches (121.92-116.1288)/116.1288 = 4.99%)."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/turf",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "pile_height": "40mm",
            "cut_length_allowed": True,
            **BASE_RATES,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]
    assert breakdown["roll_width_m"] == 4.0
    assert breakdown["orientation"] == "W-across"
    assert breakdown["mode"] == "cut"
    assert breakdown["strips"] == 2
    assert round(breakdown["ordered_sqm"], 2) == 121.92
    assert round(breakdown["build_area_sqm"], 4) == round(116.1288, 4)
    assert round(breakdown["wastage_percent"], 1) == 5.0


def test_f5_worked_example_whole_rolls_only(client, director_user):
    """Same field, cut-length NOT allowed -> forced to whole 25m rolls:
    2 strips x 1 roll x 4m x 25m = 200 sqm, ~72% waste (blueprint's own
    stated figure)."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/turf",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "pile_height": "40mm",
            "cut_length_allowed": False,
            **BASE_RATES,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]
    assert breakdown["mode"] == "whole"
    assert round(breakdown["ordered_sqm"], 2) == 200.00
    assert round(breakdown["wastage_percent"], 0) == 72.0


def test_infill_kg_by_pile_height(client, director_user):
    """F.5: 40mm -> sand 18, rubber 7 kg/sqm; area 116.1288 sqm."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/turf",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "pile_height": "40mm",
            **BASE_RATES,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]
    area = breakdown["build_area_sqm"]
    assert round(breakdown["sand_kg"], 2) == round(area * 18.0, 2)
    assert round(breakdown["rubber_kg"], 2) == round(area * 7.0, 2)

    lines = res.json()["lines"]
    assert {line["category"] for line in lines} == {"Turf", "Infill"}
    assert all(line["work_package"] == "flooring" for line in lines)


def test_padel_pile_height_has_no_rubber_line(client, director_user):
    """F.5: 'padel 12mm -- sand 8, no rubber.'"""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/turf",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "pile_height": "padel_12mm",
            "turf_rate_per_sqm": 900,
            "sand_rate_per_kg": 8,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    lines = res.json()["lines"]
    assert len(lines) == 2  # turf + sand infill only, no rubber line
    assert res.json()["breakdown"]["rubber_kg"] == 0.0


def test_rubber_rate_required_when_pile_height_has_rubber(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/turf",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "pile_height": "40mm",
            "turf_rate_per_sqm": 900,
            "sand_rate_per_kg": 8,
        },
        headers=headers,
    )
    assert res.status_code == 422


def test_line_marking_adds_a_line_when_requested(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/turf",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "pile_height": "40mm",
            "line_marking_sets": 2,
            "line_marking_rate_per_set": 15000,
            **BASE_RATES,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    lines = res.json()["lines"]
    line_marking = next(line for line in lines if line["category"] == "Line marking")
    assert line_marking["quantity"] == 2
    assert line_marking["amount"] == 30000


def test_line_marking_rate_required_when_sets_given(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/turf",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "pile_height": "40mm",
            "line_marking_sets": 2,
            **BASE_RATES,
        },
        headers=headers,
    )
    assert res.status_code == 422


def test_turf_can_only_be_added_to_a_draft_cost_sheet(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/turf",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "pile_height": "40mm",
            **BASE_RATES,
        },
        headers=headers,
    )
    client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/turf",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 20,
            "build_w_ft": 10,
            "pile_height": "30mm",
            **BASE_RATES,
        },
        headers=headers,
    )
    assert res.status_code == 400


def test_turf_lines_feed_into_recompute(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/turf",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "pile_height": "40mm",
            **BASE_RATES,
        },
        headers=headers,
    )
    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    assert recomputed["cost_total"] > 0
    verify_res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert verify_res.status_code == 200
