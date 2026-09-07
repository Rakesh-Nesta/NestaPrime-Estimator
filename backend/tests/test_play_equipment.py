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
    res = client.post("/clients", json={"name": "Play Equipment Client", "type": "school"}, headers=headers)
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


def _add_project_sport(client, headers, project_id, sport_key="kids_play_area"):
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


def test_sales_cannot_add_play_equipment(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/play-equipment",
        json={
            "project_sport_id": project_sport_id,
            "items": [
                {
                    "item_name": "Swing set", "footprint_l_ft": 10, "footprint_w_ft": 6,
                    "equipment_rate": 80000, "epdm_rate_per_sqm": 3200,
                }
            ],
        },
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_fall_zone_expands_the_epdm_area_by_six_feet_each_side(client, director_user):
    """G.4: 'footprint + 6 ft fall zone each side' -> EPDM area auto-calc."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/play-equipment",
        json={
            "project_sport_id": project_sport_id,
            "items": [
                {
                    "item_name": "Swing set", "footprint_l_ft": 10, "footprint_w_ft": 6,
                    "equipment_rate": 80000, "epdm_rate_per_sqm": 3200,
                }
            ],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]["items"][0]
    expected_sqft = (10 + 2 * 6) * (6 + 2 * 6)  # 22 x 18 = 396 sqft
    expected_sqm = round(expected_sqft * 0.09290304, 2)
    assert breakdown["footprint_sqft"] == 60
    assert breakdown["fall_zone_ft"] == 6.0
    assert breakdown["epdm_area_sqm"] == expected_sqm

    lines = res.json()["lines"]
    assert len(lines) == 2
    equipment_line = next(line for line in lines if line["item_name"] == "Swing set (supply & install)")
    surfacing_line = next(line for line in lines if line["item_name"] == "Swing set EPDM safety surfacing")
    assert equipment_line["work_package"] == "accessories"
    assert equipment_line["quantity"] == 1
    assert equipment_line["rate"] == 80000
    assert surfacing_line["work_package"] == "flooring"
    assert surfacing_line["unit"] == "sqm"
    assert surfacing_line["quantity"] == expected_sqm
    assert surfacing_line["rate"] == 3200


def test_fall_zone_is_overridable_per_item(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/play-equipment",
        json={
            "project_sport_id": project_sport_id,
            "items": [
                {
                    "item_name": "Slide", "footprint_l_ft": 12, "footprint_w_ft": 4, "fall_zone_ft": 8,
                    "equipment_rate": 60000, "epdm_rate_per_sqm": 3200,
                }
            ],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]["items"][0]
    assert breakdown["fall_zone_ft"] == 8.0
    expected_sqft = (12 + 16) * (4 + 16)  # 28 x 20
    assert breakdown["epdm_area_sqm"] == round(expected_sqft * 0.09290304, 2)


def test_is_15650_compliance_note_when_equipment_height_within_cfh(client, director_user):
    """F.2's own worked figure: 40mm EPDM system CFH 1.5 m."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/play-equipment",
        json={
            "project_sport_id": project_sport_id,
            "items": [
                {
                    "item_name": "Climber", "footprint_l_ft": 8, "footprint_w_ft": 8, "equipment_height_m": 1.2,
                    "equipment_rate": 50000, "epdm_rate_per_sqm": 3200,
                }
            ],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]["items"][0]
    assert breakdown["is_15650_compliant"] is True
    assert breakdown["epdm_40mm_cfh_m"] == 1.5


def test_is_15650_compliance_note_when_equipment_height_exceeds_cfh(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/play-equipment",
        json={
            "project_sport_id": project_sport_id,
            "items": [
                {
                    "item_name": "Multi-play unit", "footprint_l_ft": 20, "footprint_w_ft": 15,
                    "equipment_height_m": 2.5, "equipment_rate": 400000, "epdm_rate_per_sqm": 3200,
                }
            ],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]["items"][0]
    assert breakdown["is_15650_compliant"] is False
    assert "EXCEEDS" in breakdown["note"]


def test_compliance_is_null_without_an_equipment_height(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/play-equipment",
        json={
            "project_sport_id": project_sport_id,
            "items": [
                {
                    "item_name": "See-saw", "footprint_l_ft": 8, "footprint_w_ft": 3,
                    "equipment_rate": 30000, "epdm_rate_per_sqm": 3200,
                }
            ],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["breakdown"]["items"][0]["is_15650_compliant"] is None


def test_multiple_items_each_produce_two_lines(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/play-equipment",
        json={
            "project_sport_id": project_sport_id,
            "items": [
                {"item_name": "Swing set", "footprint_l_ft": 10, "footprint_w_ft": 6, "equipment_rate": 80000, "epdm_rate_per_sqm": 3200},
                {"item_name": "Spring rider", "footprint_l_ft": 3, "footprint_w_ft": 3, "equipment_rate": 15000, "epdm_rate_per_sqm": 3200},
                {"item_name": "See-saw", "footprint_l_ft": 8, "footprint_w_ft": 3, "equipment_rate": 30000, "epdm_rate_per_sqm": 3200},
            ],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert len(res.json()["lines"]) == 6
    assert len(res.json()["breakdown"]["items"]) == 3
    assert res.json()["breakdown"]["total_epdm_area_sqm"] == round(
        sum(item["epdm_area_sqm"] for item in res.json()["breakdown"]["items"]), 2
    )


def test_play_equipment_can_only_be_added_to_a_draft_cost_sheet(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    payload = {
        "project_sport_id": project_sport_id,
        "items": [{"item_name": "Slide", "footprint_l_ft": 12, "footprint_w_ft": 4, "equipment_rate": 60000, "epdm_rate_per_sqm": 3200}],
    }
    client.post(f"/cost-sheets/{cost_sheet_id}/play-equipment", json=payload, headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)

    res = client.post(f"/cost-sheets/{cost_sheet_id}/play-equipment", json=payload, headers=headers)
    assert res.status_code == 400


def test_play_equipment_feeds_into_recompute(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    payload = {
        "project_sport_id": project_sport_id,
        "items": [{"item_name": "Slide", "footprint_l_ft": 12, "footprint_w_ft": 4, "equipment_rate": 60000, "epdm_rate_per_sqm": 3200}],
    }
    client.post(f"/cost-sheets/{cost_sheet_id}/play-equipment", json=payload, headers=headers)
    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    assert recomputed["cost_total"] > 0
    verify_res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert verify_res.status_code == 200


def test_wrong_project_sport_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    _, _, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/play-equipment",
        json={
            "project_sport_id": "00000000-0000-0000-0000-000000000000",
            "items": [{"item_name": "Slide", "footprint_l_ft": 12, "footprint_w_ft": 4, "equipment_rate": 60000, "epdm_rate_per_sqm": 3200}],
        },
        headers=headers,
    )
    assert res.status_code == 404


def test_empty_items_list_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/play-equipment",
        json={"project_sport_id": project_sport_id, "items": []},
        headers=headers,
    )
    assert res.status_code == 422
