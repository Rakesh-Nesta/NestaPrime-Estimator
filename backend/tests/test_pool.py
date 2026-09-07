from app.core.security import hash_password
from app.models.user import User, UserRole

FT_TO_M = 0.3048


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
    res = client.post("/clients", json={"name": "Pool Client", "type": "school"}, headers=headers)
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


def _add_project_sport(client, headers, project_id, sport_key="swimming_pool_25m"):
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


RCC_SHELL = {
    "length_ft": 50, "width_ft": 25, "shallow_depth_ft": 3, "deep_depth_ft": 6,
    "excavation_rate_per_cum": 350, "pcc_rate_per_cum": 6000, "rcc_rate_per_cum": 9500,
    "steel_rate_per_kg": 68, "plaster_rate_per_sqm": 450, "tile_rate_per_sqm": 1200, "coping_rate_per_m": 800,
}


def _expected_shell_geometry():
    L_m = 50 * FT_TO_M
    W_m = 25 * FT_TO_M
    shallow_m = 3 * FT_TO_M
    deep_m = 6 * FT_TO_M
    avg_depth_m = (shallow_m + deep_m) / 2
    perimeter_m = 2 * (L_m + W_m)
    volume_cum = L_m * W_m * avg_depth_m
    wetted_surface_sqm = (L_m * W_m) + 2 * (L_m + W_m) * avg_depth_m
    return volume_cum, wetted_surface_sqm, perimeter_m, avg_depth_m


def test_sales_cannot_add_pool_takeoff(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/pool",
        json={"project_sport_id": project_sport_id, "shell": RCC_SHELL},
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_rcc_shell_requires_all_rates(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    incomplete_shell = {k: v for k, v in RCC_SHELL.items() if k != "steel_rate_per_kg"}
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/pool",
        json={"project_sport_id": project_sport_id, "shell": incomplete_shell},
        headers=headers,
    )
    assert res.status_code == 422
    assert "steel_rate_per_kg" in res.json()["detail"]


def test_rcc_shell_geometry_and_seven_lines(client, director_user):
    """G.1: 'Shell | L x W x depth profile ... | Excavation, RCC M25 +
    waterproofing admixture, steel, PCC, plaster, tiles, coping.'"""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/pool",
        json={"project_sport_id": project_sport_id, "shell": RCC_SHELL},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]
    volume_cum, wetted_surface_sqm, perimeter_m, avg_depth_m = _expected_shell_geometry()
    assert breakdown["volume_cum"] == round(volume_cum, 2)
    assert breakdown["wetted_surface_sqm"] == round(wetted_surface_sqm, 2)
    assert breakdown["perimeter_m"] == round(perimeter_m, 2)
    assert breakdown["avg_depth_m"] == round(avg_depth_m, 2)

    lines = res.json()["lines"]
    assert len(lines) == 7
    item_names = {line["item_name"] for line in lines}
    assert "Excavation" in item_names
    assert "PCC blinding" in item_names
    assert any("RCC M25 shell + waterproofing admixture" in name for name in item_names)
    assert any("Reinforcement steel" in name for name in item_names)
    assert "Waterproof plaster" in item_names
    assert "Pool tiles/mosaic" in item_names
    assert "Coping" in item_names

    coping = next(line for line in lines if line["item_name"] == "Coping")
    assert coping["unit"] == "m"
    assert coping["quantity"] == round(perimeter_m, 2)
    plaster = next(line for line in lines if line["item_name"] == "Waterproof plaster")
    assert plaster["quantity"] == round(wetted_surface_sqm, 2)
    assert all(line["work_package"] == "pool" for line in lines)


def test_frp_shell_is_a_single_supplied_system_line(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/pool",
        json={
            "project_sport_id": project_sport_id,
            "shell": {
                "length_ft": 50, "width_ft": 25, "shallow_depth_ft": 3, "deep_depth_ft": 6,
                "liner_type": "frp", "frp_shell_rate_per_sqm": 8500,
            },
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    lines = res.json()["lines"]
    assert len(lines) == 1
    assert lines[0]["item_name"] == "FRP liner shell (supplied system)"
    assert lines[0]["rate"] == 8500


def test_frp_shell_without_rate_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/pool",
        json={
            "project_sport_id": project_sport_id,
            "shell": {"length_ft": 50, "width_ft": 25, "shallow_depth_ft": 3, "deep_depth_ft": 6, "liner_type": "frp"},
        },
        headers=headers,
    )
    assert res.status_code == 422


def test_filtration_flow_rate_and_lines(client, director_user):
    """G.1: 'Filtration | Volume (auto) | Turnover 4-6h -> pump kW, sand
    filter size, plant room, pipework, skimmers/overflow gutter,
    balancing tank.'"""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/pool",
        json={
            "project_sport_id": project_sport_id,
            "shell": RCC_SHELL,
            "filtration": {
                "turnover_hours": 5,
                "pump_rate": 180000,
                "sand_filter_rate": 220000,
                "pipework_length_m": 40,
                "pipework_rate_per_m": 900,
                "plant_room_area_sqft": 120,
                "plant_room_rate_per_sqft": 1500,
                "skimmer_count": 3,
                "skimmer_rate_each": 15000,
                "balancing_tank_rate": 90000,
            },
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    volume_cum, *_ = _expected_shell_geometry()
    breakdown = res.json()["breakdown"]
    assert breakdown["flow_rate_m3_per_hr"] == round(volume_cum / 5, 2)

    lines = res.json()["lines"]
    filtration_lines = [line for line in lines if line["category"] == "Filtration"]
    assert len(filtration_lines) == 6
    pump = next(line for line in filtration_lines if "Circulation pump" in line["item_name"])
    assert pump["labour_category_id"] is not None
    skimmers = next(line for line in filtration_lines if line["item_name"] == "Skimmers / overflow gutter")
    assert skimmers["quantity"] == 3
    assert skimmers["rate"] == 15000


def test_filtration_pipework_requires_a_rate(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/pool",
        json={
            "project_sport_id": project_sport_id,
            "shell": RCC_SHELL,
            "filtration": {"pump_rate": 180000, "sand_filter_rate": 220000, "pipework_length_m": 40},
        },
        headers=headers,
    )
    assert res.status_code == 422
    assert "pipework_rate_per_m" in res.json()["detail"]


def test_treatment_lines(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/pool",
        json={
            "project_sport_id": project_sport_id,
            "shell": RCC_SHELL,
            "treatment": {"treatment_type": "salt", "dosing_system_rate": 65000, "test_kit_rate": 3500},
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    treatment_lines = [line for line in res.json()["lines"] if line["category"] == "Treatment"]
    assert len(treatment_lines) == 2
    assert any(line["item_name"] == "Salt dosing system" for line in treatment_lines)
    assert any(line["item_name"] == "Pool test kit" for line in treatment_lines)


def test_deck_area_and_safety_items(client, director_user):
    """G.1: 'Deck & safety | Deck width | Anti-slip tiles, channel drain,
    ladders, lane ropes, blocks, lifeguard chair, ..., depth markers.'"""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/pool",
        json={
            "project_sport_id": project_sport_id,
            "shell": RCC_SHELL,
            "deck": {
                "deck_width_ft": 10,
                "anti_slip_tile_rate_per_sqm": 900,
                "channel_drain_rate_per_m": 700,
                "safety_items": [
                    {"item_name": "Ladder", "quantity": 2, "rate": 12000},
                    {"item_name": "Lane ropes (set)", "quantity": 1, "rate": 45000},
                    {"item_name": "Lifeguard chair", "quantity": 1, "rate": 25000},
                ],
            },
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    _, _, perimeter_m, _ = _expected_shell_geometry()
    deck_width_m = 10 * FT_TO_M
    expected_deck_area = perimeter_m * deck_width_m
    assert res.json()["breakdown"]["deck_area_sqm"] == round(expected_deck_area, 2)

    lines = res.json()["lines"]
    deck_tiles = next(line for line in lines if line["item_name"] == "Anti-slip deck tiles")
    assert deck_tiles["quantity"] == round(expected_deck_area, 2)
    safety_lines = [line for line in lines if line["work_package"] == "accessories"]
    assert len(safety_lines) == 3
    assert all(line["category"] == "Deck & safety" for line in safety_lines)


def test_water_fill_uses_shell_volume(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/pool",
        json={
            "project_sport_id": project_sport_id,
            "shell": RCC_SHELL,
            "water": {"source": "borewell", "water_rate_per_cum": 45},
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    volume_cum, *_ = _expected_shell_geometry()
    water_line = next(line for line in res.json()["lines"] if line["category"] == "Water")
    assert water_line["item_name"] == "Water fill (initial) -- borewell"
    assert water_line["quantity"] == round(volume_cum, 2)


def test_options_and_compliance_lines(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/pool",
        json={
            "project_sport_id": project_sport_id,
            "shell": RCC_SHELL,
            "options": [
                {"option_name": "Heat pump heating", "rate": 350000},
                {"option_name": "Pool cover", "rate": 90000},
            ],
            "compliance": [
                {"item_name": "Pool safety NOC", "rate": 15000},
                {"item_name": "Drowning-prevention signage", "rate": 5000},
            ],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    lines = res.json()["lines"]
    option_lines = [line for line in lines if line["category"] == "Options"]
    compliance_lines = [line for line in lines if line["category"] == "Compliance"]
    assert len(option_lines) == 2
    assert all(line["work_package"] == "pool" for line in option_lines)
    assert len(compliance_lines) == 2
    assert all(line["work_package"] == "scope" for line in compliance_lines)


def test_pool_can_only_be_added_to_a_draft_cost_sheet(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    payload = {"project_sport_id": project_sport_id, "shell": RCC_SHELL}
    client.post(f"/cost-sheets/{cost_sheet_id}/pool", json=payload, headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)

    res = client.post(f"/cost-sheets/{cost_sheet_id}/pool", json=payload, headers=headers)
    assert res.status_code == 400


def test_pool_feeds_into_recompute_with_eight_percent_contingency(client, director_user):
    """K.1 step 6: pool carries an 8% contingency work-package."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/pool", json={"project_sport_id": project_sport_id, "shell": RCC_SHELL}, headers=headers)

    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    assert recomputed["cost_total"] > 0
    verify_res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert verify_res.status_code == 200


def test_wrong_project_sport_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    _, _, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/pool",
        json={"project_sport_id": "00000000-0000-0000-0000-000000000000", "shell": RCC_SHELL},
        headers=headers,
    )
    assert res.status_code == 404
