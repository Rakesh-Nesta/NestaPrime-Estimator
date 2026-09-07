import math

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
    res = client.post("/clients", json={"name": "Athletics Client", "type": "school"}, headers=headers)
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


def _add_project_sport(client, headers, project_id, sport_key="athletic_track_400m"):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports", json={"sport_id": sport_id, "building_status": "open_air"}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _setup(client, headers, sport_key="athletic_track_400m"):
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id, sport_key=sport_key)
    cost_sheet_id = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers).json()["id"]
    return project_id, project_sport_id, cost_sheet_id


BASE_PAYLOAD = {
    "lanes": 8,
    "track_surface_rate_per_sqm": 3500,
    "kerb_rate_per_m": 900,
    "drainage_rate_per_m": 1200,
}


def test_sales_cannot_add_athletics_takeoff(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/athletics",
        json={"project_sport_id": project_sport_id, **BASE_PAYLOAD},
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_standard_8_lane_400m_track_geometry(client, director_user):
    """World Athletics standard 400m/8-lane geometry: straight 84.39 m,
    kerb radius 36.5 m -> kerb perimeter ~=398.1 m (the figure curbing is
    actually ordered to), track width = 8 x 1.22 = 9.76 m."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/athletics",
        json={"project_sport_id": project_sport_id, **BASE_PAYLOAD},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]
    assert breakdown["lanes"] == 8
    assert breakdown["track_width_m"] == round(8 * 1.22, 2)
    assert breakdown["inner_radius_m"] == 36.5
    assert breakdown["straight_length_m"] == 84.39
    assert round(breakdown["kerb_length_m"], 1) == 398.1

    outer_r = 36.5 + 8 * 1.22
    expected_surface = 2 * 84.39 * (8 * 1.22) + math.pi * (outer_r**2 - 36.5**2)
    assert round(breakdown["track_surface_area_sqm"], 1) == round(expected_surface, 1)

    expected_outer_perimeter = 2 * 84.39 + 2 * math.pi * outer_r
    assert round(breakdown["outer_perimeter_m"], 1) == round(expected_outer_perimeter, 1)

    expected_d_zone = math.pi * 36.5**2
    assert round(breakdown["d_zone_area_sqm"], 1) == round(expected_d_zone, 1)


def test_lines_created_match_the_three_core_items(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/athletics",
        json={"project_sport_id": project_sport_id, **BASE_PAYLOAD},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    lines = res.json()["lines"]
    assert len(lines) == 3
    surface = next(line for line in lines if "Synthetic track surface" in line["item_name"])
    kerb = next(line for line in lines if line["item_name"] == "Track kerb (edging)")
    drainage = next(line for line in lines if line["item_name"] == "Drainage ring (perimeter channel)")

    assert surface["work_package"] == "flooring"
    assert surface["unit"] == "sqm"
    assert surface["rate"] == 3500
    assert kerb["work_package"] == "civil"
    assert kerb["unit"] == "m"
    assert kerb["labour_category_id"] is not None
    assert drainage["work_package"] == "civil"
    assert drainage["unit"] == "m"


def test_field_events_checklist_adds_one_line_each(client, director_user):
    """G.3: 'field events checklist (long/triple jump pit, shot put
    circle, discus cage, high jump)' -- optional, named, flat-priced."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/athletics",
        json={
            "project_sport_id": project_sport_id,
            **BASE_PAYLOAD,
            "field_events": [
                {"event_name": "Long jump pit", "rate": 250000},
                {"event_name": "Shot put circle", "rate": 60000},
            ],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    lines = res.json()["lines"]
    assert len(lines) == 5
    field_event_lines = [line for line in lines if line["work_package"] == "accessories"]
    assert len(field_event_lines) == 2
    assert {line["item_name"] for line in field_event_lines} == {
        "Long jump pit (supply & install)",
        "Shot put circle (supply & install)",
    }
    assert all(line["quantity"] == 1 for line in field_event_lines)


def test_no_field_events_selected_still_produces_the_three_core_lines(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/athletics",
        json={"project_sport_id": project_sport_id, **BASE_PAYLOAD, "field_events": []},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert len(res.json()["lines"]) == 3


def test_geometry_overridable_for_a_non_standard_school_track(client, director_user):
    """athletic_track_200_250m has no blueprint-given geometry -- the
    caller must supply its own inner_radius_m/straight_length_m."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="athletic_track_200_250m")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/athletics",
        json={
            "project_sport_id": project_sport_id,
            "lanes": 6,
            "inner_radius_m": 20.0,
            "straight_length_m": 60.0,
            **{k: v for k, v in BASE_PAYLOAD.items() if k != "lanes"},
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]
    assert breakdown["inner_radius_m"] == 20.0
    assert breakdown["straight_length_m"] == 60.0
    assert breakdown["track_width_m"] == round(6 * 1.22, 2)


def test_athletics_can_only_be_added_to_a_draft_cost_sheet(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/athletics",
        json={"project_sport_id": project_sport_id, **BASE_PAYLOAD},
        headers=headers,
    )
    client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/athletics",
        json={"project_sport_id": project_sport_id, **BASE_PAYLOAD},
        headers=headers,
    )
    assert res.status_code == 400


def test_athletics_feeds_into_recompute(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/athletics",
        json={"project_sport_id": project_sport_id, **BASE_PAYLOAD},
        headers=headers,
    )
    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    assert recomputed["cost_total"] > 0
    verify_res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert verify_res.status_code == 200


def test_wrong_project_sport_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    _, _, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/athletics",
        json={"project_sport_id": "00000000-0000-0000-0000-000000000000", **BASE_PAYLOAD},
        headers=headers,
    )
    assert res.status_code == 404
