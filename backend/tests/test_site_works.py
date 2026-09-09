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
    res = client.post("/clients", json={"name": "Site Works Client", "type": "school"}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id, soil_type="normal"):
    fields = {
        "client_id": client_id,
        "city": "Mumbai",
        "site_condition": "level",
        "soil_type": soil_type,
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


def _setup(client, headers, soil_type="normal"):
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id, soil_type=soil_type)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers).json()["id"]
    return project_id, project_sport_id, cost_sheet_id


# ---------------------------------------------------------------------------
# D.1 Base / sub-base
# ---------------------------------------------------------------------------


def test_sales_cannot_add_base_or_drainage(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    base_res = client.post(
        f"/cost-sheets/{cost_sheet_id}/base",
        json={"project_sport_id": project_sport_id, "base_type": "pcc", "thickness_in": 4, "build_l_ft": 50, "build_w_ft": 25, "material_rate_per_cum": 6000},
        headers=sales_headers,
    )
    assert base_res.status_code == 403

    drainage_res = client.post(
        f"/cost-sheets/{cost_sheet_id}/drainage",
        json={"project_sport_id": project_sport_id, "build_l_ft": 50, "build_w_ft": 25, "rainfall_intensity_mm_per_hr": 75, "drain_rate_per_m": 500, "catch_pit_rate_each": 3000},
        headers=sales_headers,
    )
    assert drainage_res.status_code == 403


def test_pcc_base_take_off(client, director_user):
    """D.1/J.3: volume cum = area_sqm x (thickness_in x 0.0254) x 1.02.
    Box cricket 50x25 ft, PCC 4in -> area 116.1288 sqm, volume 12.0347 cum
    (independently computed)."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/base",
        json={
            "project_sport_id": project_sport_id,
            "base_type": "pcc",
            "thickness_in": 4,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "material_rate_per_cum": 6000,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]
    assert round(breakdown["area_sqm"], 2) == round(116.1288, 2)
    assert round(breakdown["volume_cum"], 3) == round(12.034659801600002, 3)
    assert breakdown["steel_kg"] is None

    lines = res.json()["lines"]
    assert len(lines) == 1
    assert lines[0]["work_package"] == "civil"
    assert lines[0]["category"] == "Base/sub-base"


def test_rcc_base_requires_steel_rate(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/base",
        json={
            "project_sport_id": project_sport_id,
            "base_type": "rcc",
            "thickness_in": 6,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "material_rate_per_cum": 7500,
        },
        headers=headers,
    )
    assert res.status_code == 422


def test_rcc_base_produces_a_material_line_and_a_reinforcement_line(client, director_user):
    """J.3: 'steel kg/cum by element (slab 80...)' -- default slab rate."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/base",
        json={
            "project_sport_id": project_sport_id,
            "base_type": "rcc",
            "thickness_in": 4,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "material_rate_per_cum": 7500,
            "steel_rate_per_kg": 68,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]
    expected_volume = 12.034659801600002
    assert round(breakdown["steel_kg"], 2) == round(expected_volume * 80.0, 2)

    lines = res.json()["lines"]
    assert len(lines) == 2
    categories = {line["category"] for line in lines}
    assert categories == {"Base/sub-base", "Base reinforcement"}


def test_base_can_only_be_added_to_a_draft_cost_sheet(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/base",
        json={"project_sport_id": project_sport_id, "base_type": "pcc", "thickness_in": 4, "build_l_ft": 50, "build_w_ft": 25, "material_rate_per_cum": 6000},
        headers=headers,
    )
    client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/base",
        json={"project_sport_id": project_sport_id, "base_type": "wbm", "thickness_in": 8, "build_l_ft": 20, "build_w_ft": 10, "material_rate_per_cum": 3000},
        headers=headers,
    )
    assert res.status_code == 400


def test_base_line_feeds_into_recompute(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/base",
        json={"project_sport_id": project_sport_id, "base_type": "pcc", "thickness_in": 4, "build_l_ft": 50, "build_w_ft": 25, "material_rate_per_cum": 6000},
        headers=headers,
    )
    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    assert recomputed["cost_total"] > 0
    verify_res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert verify_res.status_code == 200


# ---------------------------------------------------------------------------
# D.3 Drainage
# ---------------------------------------------------------------------------


def test_drainage_take_off_with_pipe_and_catch_pits(client, director_user):
    """Box cricket 50x25 ft, C=0.9, i=75 mm/hr (Mumbai): perimeter 150 ft
    = 45.72 m, Q = 2.1792 l/s -> needs a 100mm pipe (independently
    computed); catch pits = ceil(150/50) = 3."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/drainage",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "rainfall_intensity_mm_per_hr": 75,
            "drain_rate_per_m": 500,
            "pipe_rate_per_m": 350,
            "catch_pit_rate_each": 3000,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]
    assert round(breakdown["perimeter_m"], 2) == 45.72
    assert round(breakdown["q_l_s"], 3) == round(2.179156932, 3)
    assert breakdown["pipe_size_mm"] == 100
    assert breakdown["catch_pits"] == 3

    lines = res.json()["lines"]
    assert len(lines) == 3  # drain, catch pits, pipe
    assert {line["category"] for line in lines} == {"Drainage"}
    assert all(line["work_package"] == "civil" for line in lines)


def test_drainage_pipe_rate_required_when_q_at_least_one(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/drainage",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "rainfall_intensity_mm_per_hr": 75,
            "drain_rate_per_m": 500,
            "catch_pit_rate_each": 3000,
        },
        headers=headers,
    )
    assert res.status_code == 422


def test_low_runoff_needs_no_pipe(client, director_user):
    """A small, low-rainfall field keeps Q under 1 l/s -- 'perimeter drain
    alone suffices' (D.3), no pipe line and no pipe_rate_per_m needed."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/drainage",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 10,
            "build_w_ft": 10,
            "rainfall_intensity_mm_per_hr": 30,
            "drain_rate_per_m": 500,
            "catch_pit_rate_each": 3000,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["breakdown"]["pipe_size_mm"] is None
    lines = res.json()["lines"]
    assert len(lines) == 2  # drain + catch pits only


def test_subsurface_turf_drainage_uses_project_soil_type(client, director_user):
    """D.3: 'normal 5 m c/c.' Box cricket 50x25 ft, normal soil ->
    W=25ft=7.62m, runs=ceil(7.62/5)=2, pipe length=2 x 15.24m=30.48m."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, soil_type="normal")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/drainage",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "rainfall_intensity_mm_per_hr": 75,
            "drain_rate_per_m": 500,
            "pipe_rate_per_m": 350,
            "catch_pit_rate_each": 3000,
            "subsurface_turf_drainage": True,
            "subsurface_pipe_rate_per_m": 120,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    subsurface = res.json()["breakdown"]["subsurface"]
    assert subsurface["spacing_m"] == 5.0
    assert subsurface["runs"] == 2
    assert round(subsurface["pipe_m"], 2) == 30.48

    lines = res.json()["lines"]
    assert len(lines) == 4  # drain, catch pits, pipe, sub-surface


def test_subsurface_turf_drainage_uses_sandy_spacing(client, director_user):
    """D.3: 'sandy 8 m c/c.'"""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, soil_type="sandy")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/drainage",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "rainfall_intensity_mm_per_hr": 75,
            "drain_rate_per_m": 500,
            "pipe_rate_per_m": 350,
            "catch_pit_rate_each": 3000,
            "subsurface_turf_drainage": True,
            "subsurface_pipe_rate_per_m": 120,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["breakdown"]["subsurface"]["spacing_m"] == 8.0


def test_subsurface_turf_drainage_requires_its_own_rate(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/drainage",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "rainfall_intensity_mm_per_hr": 75,
            "drain_rate_per_m": 500,
            "pipe_rate_per_m": 350,
            "catch_pit_rate_each": 3000,
            "subsurface_turf_drainage": True,
        },
        headers=headers,
    )
    assert res.status_code == 422


def test_drainage_line_feeds_into_recompute(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/drainage",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "rainfall_intensity_mm_per_hr": 75,
            "drain_rate_per_m": 500,
            "pipe_rate_per_m": 350,
            "catch_pit_rate_each": 3000,
        },
        headers=headers,
    )
    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    assert recomputed["cost_total"] > 0


# ---------------------------------------------------------------------------
# D.4 Site preparation & establishment
# ---------------------------------------------------------------------------


def test_sales_cannot_add_site_prep(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/site-prep",
        json={"cut_fill_volume_cum": 50, "cut_fill_rate_per_cum": 200},
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_cut_fill_line(client, director_user):
    headers = _director_headers(client, director_user)
    _, _, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/site-prep",
        json={"cut_fill_volume_cum": 50, "cut_fill_rate_per_cum": 200},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    lines = res.json()["lines"]
    assert len(lines) == 1
    assert lines[0]["item_name"] == "Cut/fill earthwork"
    assert lines[0]["unit"] == "cum"
    assert lines[0]["quantity"] == 50
    assert lines[0]["rate"] == 200
    assert lines[0]["category"] == "Site preparation"
    assert lines[0]["work_package"] == "civil"


def test_rock_breaking_line(client, director_user):
    headers = _director_headers(client, director_user)
    _, _, cost_sheet_id = _setup(client, headers, soil_type="rocky")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/site-prep",
        json={"rock_breaking_volume_cum": 20, "rock_breaking_rate_per_cum": 800},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["lines"][0]["item_name"] == "Rock breaking"


def test_dewatering_line(client, director_user):
    headers = _director_headers(client, director_user)
    _, _, cost_sheet_id = _setup(client, headers, soil_type="filled")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/site-prep",
        json={"dewatering_days": 5, "dewatering_rate_per_day": 4000},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    line = res.json()["lines"][0]
    assert line["item_name"] == "Dewatering"
    assert line["unit"] == "day"
    assert line["quantity"] == 5


def test_debris_removal_line(client, director_user):
    headers = _director_headers(client, director_user)
    _, _, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/site-prep",
        json={"debris_removal_trips": 3, "debris_removal_rate_per_trip": 2500},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["lines"][0]["item_name"] == "Debris removal"


def test_anti_termite_with_explicit_area(client, director_user):
    headers = _director_headers(client, director_user)
    _, _, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/site-prep",
        json={"anti_termite_area_sqft": 1000, "anti_termite_rate_per_sqft": 12},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    line = res.json()["lines"][0]
    assert line["item_name"] == "Anti-termite treatment"
    assert line["quantity"] == 1000
    assert line["rate"] == 12


def test_anti_termite_defaults_area_from_project_sport(client, director_user):
    """Box cricket's default build footprint (56 x 31 ft build_l_ft/build_w_ft,
    the same fields D.1's base take-off uses -- includes the 3 ft buffer each
    side around the 50 x 25 play area) -> 1736 sqft treated area when no
    explicit area is given."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/site-prep",
        json={"project_sport_id": project_sport_id, "anti_termite_rate_per_sqft": 12},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    line = res.json()["lines"][0]
    assert line["quantity"] == 1736
    assert res.json()["breakdown"]["anti_termite_area_sqft"] == 1736


def test_anti_termite_requires_area_or_project_sport_id(client, director_user):
    headers = _director_headers(client, director_user)
    _, _, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/site-prep",
        json={"anti_termite_rate_per_sqft": 12},
        headers=headers,
    )
    assert res.status_code == 422


def test_multiple_site_prep_lines_in_one_call(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/site-prep",
        json={
            "project_sport_id": project_sport_id,
            "cut_fill_volume_cum": 50, "cut_fill_rate_per_cum": 200,
            "debris_removal_trips": 2, "debris_removal_rate_per_trip": 2500,
            "anti_termite_rate_per_sqft": 12,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    items = {line["item_name"] for line in res.json()["lines"]}
    assert items == {"Cut/fill earthwork", "Debris removal", "Anti-termite treatment"}


def test_site_prep_requires_at_least_one_pair(client, director_user):
    headers = _director_headers(client, director_user)
    _, _, cost_sheet_id = _setup(client, headers)

    res = client.post(f"/cost-sheets/{cost_sheet_id}/site-prep", json={}, headers=headers)
    assert res.status_code == 422


def test_site_prep_rejects_a_lone_quantity_without_its_rate(client, director_user):
    headers = _director_headers(client, director_user)
    _, _, cost_sheet_id = _setup(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/site-prep", json={"cut_fill_volume_cum": 50}, headers=headers
    )
    assert res.status_code == 422


def test_site_prep_can_only_be_added_to_a_draft_cost_sheet(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/base",
        json={"project_sport_id": project_sport_id, "base_type": "pcc", "thickness_in": 4, "build_l_ft": 50, "build_w_ft": 25, "material_rate_per_cum": 6000},
        headers=headers,
    )
    client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/site-prep",
        json={"cut_fill_volume_cum": 50, "cut_fill_rate_per_cum": 200},
        headers=headers,
    )
    assert res.status_code == 400


def test_site_prep_line_feeds_into_recompute(client, director_user):
    headers = _director_headers(client, director_user)
    _, _, cost_sheet_id = _setup(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/site-prep",
        json={"cut_fill_volume_cum": 50, "cut_fill_rate_per_cum": 200},
        headers=headers,
    )
    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    assert recomputed["cost_total"] > 0
    verify_res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert verify_res.status_code == 200
