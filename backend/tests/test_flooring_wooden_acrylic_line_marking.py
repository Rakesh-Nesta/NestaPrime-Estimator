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
    res = client.post("/clients", json={"name": "Flooring F.3/F.2/F.6 Client", "type": "school"}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id):
    fields = {
        "client_id": client_id,
        # Bengaluru is seeded at neutral 1.0/1.0/1.0 regional multipliers --
        # this file's math is about J.2 activity rates, not regional
        # pricing, so a non-neutral city (e.g. Mumbai) would silently
        # distort every expected total here.
        "city": "Bengaluru",
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


def _add_project_sport(client, headers, project_id, sport_key):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": sport_id, "building_status": "open_air"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _setup(client, headers, sport_key):
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id, sport_key)
    cost_sheet_id = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers).json()["id"]
    # E.5: the default city may auto-add a "Structural engineer design &
    # sign-off" line -- removed so these formula-precision tests see only
    # the flooring take-off line they add themselves.
    for line in client.get(f"/cost-sheets/{cost_sheet_id}/lines", headers=headers).json():
        client.delete(f"/cost-sheets/{cost_sheet_id}/lines/{line['id']}", headers=headers)
    return project_id, project_sport_id, cost_sheet_id


# ---------------------------------------------------------------------------
# F.3 Wooden flooring
# ---------------------------------------------------------------------------


def test_sales_cannot_add_wooden_flooring(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, director_headers, "badminton")

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/wooden",
        json={"project_sport_id": project_sport_id, "hardwood_rate_per_sqft": 350},
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_wooden_flooring_defaults_produce_four_layers(client, director_user):
    """F.3: hardwood -> ply -> battens/cradles -> moisture barrier, all
    covering the sport's own build_l_ft x build_w_ft footprint (badminton
    52 x 30 ft club default)."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, "badminton")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/wooden",
        json={
            "project_sport_id": project_sport_id,
            "hardwood_rate_per_sqft": 350,
            "ply_rate_per_sqft": 60,
            "battens_rate_per_sqft": 90,
            "moisture_barrier_rate_per_sqft": 15,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["breakdown"]["area_sqft"] == 52 * 30
    lines = body["lines"]
    assert len(lines) == 4
    item_names = {line["item_name"] for line in lines}
    assert item_names == {
        "Hardwood 22mm T&G",
        "12mm plywood underlayer",
        "Battens/cradles with rubber pads (sprung layer)",
        "Moisture barrier (DPM)",
    }
    for line in lines:
        assert line["quantity"] == 52 * 30
        assert line["unit"] == "sqft"
        assert line["work_package"] == "flooring"

    hardwood = next(line for line in lines if line["item_name"] == "Hardwood 22mm T&G")
    assert hardwood["labour_category_id"] is not None
    for line in lines:
        if line["item_name"] != "Hardwood 22mm T&G":
            assert line["labour_category_id"] is None


def test_wooden_flooring_layers_are_individually_optional(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, "badminton")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/wooden",
        json={
            "project_sport_id": project_sport_id,
            "hardwood_rate_per_sqft": 350,
            "include_ply": False,
            "include_battens": False,
            "include_moisture_barrier": False,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert len(res.json()["lines"]) == 1
    assert res.json()["lines"][0]["item_name"] == "Hardwood 22mm T&G"


def test_wooden_flooring_requires_a_rate_for_each_included_layer(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, "badminton")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/wooden",
        json={"project_sport_id": project_sport_id, "hardwood_rate_per_sqft": 350},
        headers=headers,
    )
    assert res.status_code == 422
    assert "ply_rate_per_sqft" in res.json()["detail"]


def test_wooden_flooring_uses_activity_rate_once_configured(client, director_user):
    """J.2: 'Rs/sqft wooden floor' activity rate, wired via flooring.py's
    hardwood line only -- confirms wooden_flooring is no longer a
    documented always-fallback gap."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, "badminton")
    client.post("/settings", json={"key": "activity_rate_wooden_flooring_per_sqft", "value": "40.0"}, headers=headers)

    client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/wooden",
        json={
            "project_sport_id": project_sport_id,
            "hardwood_rate_per_sqft": 350,
            "include_ply": False,
            "include_battens": False,
            "include_moisture_barrier": False,
        },
        headers=headers,
    )
    warnings = client.get(f"/cost-sheets/{cost_sheet_id}/labour-warnings", headers=headers).json()
    assert not any("wooden" in w.lower() for w in warnings)

    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    area_sqft = 52 * 30
    material = area_sqft * 350
    labour = area_sqft * 40.0  # activity rate x quantity, not x material
    base = material + labour
    site_estab = base * 1.06  # 6% default
    loaded = site_estab * 1.01 * 1.10  # K.1 4B warranty reserve 1%, 5A overhead recovery 10% defaults
    expected = loaded * 1.03  # flooring contingency 3%
    assert round(recomputed["cost_total"], 2) == round(expected, 2)


# ---------------------------------------------------------------------------
# F.2/F.3 Acrylic / PU surfacing
# ---------------------------------------------------------------------------


def test_sales_cannot_add_acrylic_pu(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, director_headers, "tennis")

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/acrylic-pu",
        json={"project_sport_id": project_sport_id, "surface_type": "acrylic", "coats": 6, "rate_per_sqft_per_coat": 25},
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_acrylic_coats_multiply_quantity(client, director_user):
    """F.2: 'Acrylic 3-5 mm (5-8 coats)' -- each coat is one more unit of
    quantity, so 6 coats over a tennis court's own build area."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, "tennis")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/acrylic-pu",
        json={"project_sport_id": project_sport_id, "surface_type": "acrylic", "coats": 6, "rate_per_sqft_per_coat": 25},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    area_sqft = 120 * 60  # tennis build dims
    assert body["breakdown"]["area_sqft"] == area_sqft
    assert body["breakdown"]["quantity_sqft_coats"] == area_sqft * 6
    line = body["lines"][0]
    assert line["quantity"] == area_sqft * 6
    assert line["item_name"] == "Acrylic surfacing (6 coats)"
    assert line["labour_category_id"] is not None


def test_pu_defaults_to_a_single_coat(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, "volleyball_outdoor")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/acrylic-pu",
        json={"project_sport_id": project_sport_id, "surface_type": "pu", "rate_per_sqft_per_coat": 180},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    line = res.json()["lines"][0]
    assert line["item_name"] == "PU surfacing (1 coat)"
    area_sqft = 79 * 49  # volleyball_outdoor build dims
    assert line["quantity"] == area_sqft


def test_acrylic_pu_uses_activity_rate_once_configured(client, director_user):
    """J.2: 'Rs/sqft acrylic (per coat)' -- confirms acrylic_pu is no
    longer a documented always-fallback gap."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, "tennis")
    client.post("/settings", json={"key": "activity_rate_acrylic_pu_per_sqft", "value": "18.0"}, headers=headers)

    client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/acrylic-pu",
        json={"project_sport_id": project_sport_id, "surface_type": "acrylic", "coats": 6, "rate_per_sqft_per_coat": 25},
        headers=headers,
    )
    warnings = client.get(f"/cost-sheets/{cost_sheet_id}/labour-warnings", headers=headers).json()
    assert not any("acrylic" in w.lower() for w in warnings)


# ---------------------------------------------------------------------------
# F.6 Line marking (standalone, multi-set)
# ---------------------------------------------------------------------------


def test_sales_cannot_add_line_marking(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, director_headers, "multipurpose_court")

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/line-marking",
        json={
            "project_sport_id": project_sport_id,
            "sets": [{"sport_label": "Basketball (white)", "style": "painted", "rate_per_set": 12000}],
        },
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_multipurpose_court_can_add_up_to_four_sets(client, director_user):
    """F.6: 'Multipurpose: up to 4 (basketball white, volleyball yellow,
    badminton green, pickleball blue).'"""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, "multipurpose_court")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/line-marking",
        json={
            "project_sport_id": project_sport_id,
            "sets": [
                {"sport_label": "Basketball (white)", "style": "painted", "rate_per_set": 12000},
                {"sport_label": "Volleyball (yellow)", "style": "painted", "rate_per_set": 10000},
                {"sport_label": "Badminton (green)", "style": "painted", "rate_per_set": 9000},
                {"sport_label": "Pickleball (blue)", "style": "painted", "rate_per_set": 9500},
            ],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    lines = res.json()["lines"]
    assert len(lines) == 4
    assert all(line["unit"] == "set" and line["quantity"] == 1 for line in lines)
    assert all(line["work_package"] == "flooring" for line in lines)


def test_more_than_four_sets_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, "multipurpose_court")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/line-marking",
        json={
            "project_sport_id": project_sport_id,
            "sets": [{"sport_label": f"Sport {i}", "style": "painted", "rate_per_set": 9000} for i in range(5)],
        },
        headers=headers,
    )
    assert res.status_code == 422


def test_inlaid_style_for_a_turf_court(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, "box_cricket")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/line-marking",
        json={
            "project_sport_id": project_sport_id,
            "sets": [{"sport_label": "Box cricket", "style": "inlaid", "rate_per_set": 15000}],
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["lines"][0]["item_name"] == "Box cricket line marking (inlaid)"


def test_line_marking_rejects_a_project_sport_from_another_project(client, director_user):
    headers = _director_headers(client, director_user)
    _, _, cost_sheet_id = _setup(client, headers, "multipurpose_court")
    _, other_project_sport_id, _ = _setup(client, headers, "badminton")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/line-marking",
        json={
            "project_sport_id": other_project_sport_id,
            "sets": [{"sport_label": "Badminton (green)", "style": "painted", "rate_per_set": 9000}],
        },
        headers=headers,
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Amendment 9: project-level custom court size (Court size step)
# ---------------------------------------------------------------------------


def test_custom_build_size_applies_to_a_take_off_with_no_per_line_override(client, director_user):
    """Badminton's own standard build is 52x30 -- a project-level custom
    size of 50x25 (still >= the 44x20 playing floor) must flow through to
    a take-off that specifies no build_l_ft/build_w_ft of its own."""
    headers = _director_headers(client, director_user)
    project_id, project_sport_id, cost_sheet_id = _setup(client, headers, "badminton")

    size_res = client.patch(
        f"/projects/{project_id}/sports/{project_sport_id}/build-size",
        json={"custom_build_l_ft": 50, "custom_build_w_ft": 25},
        headers=headers,
    )
    assert size_res.status_code == 200, size_res.text
    assert size_res.json()["custom_build_l_ft"] == 50
    assert size_res.json()["custom_build_w_ft"] == 25

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/acrylic-pu",
        json={"project_sport_id": project_sport_id, "surface_type": "acrylic", "coats": 1, "rate_per_sqft_per_coat": 25},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["breakdown"]["area_sqft"] == 50 * 25  # not badminton's 52x30 standard


def test_per_line_override_still_beats_the_project_level_custom_size(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, project_sport_id, cost_sheet_id = _setup(client, headers, "badminton")
    client.patch(
        f"/projects/{project_id}/sports/{project_sport_id}/build-size",
        json={"custom_build_l_ft": 50, "custom_build_w_ft": 25},
        headers=headers,
    )

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/acrylic-pu",
        json={
            "project_sport_id": project_sport_id, "surface_type": "acrylic", "coats": 1,
            "rate_per_sqft_per_coat": 25, "build_l_ft": 44, "build_w_ft": 20,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["breakdown"]["area_sqft"] == 44 * 20


def test_custom_build_size_cannot_go_below_the_sports_playing_dimensions(client, director_user):
    """Only the build (surround/clearance) is adjustable -- the federation
    playing dimensions (BWF: 44x20 for badminton) are a hard floor."""
    headers = _director_headers(client, director_user)
    project_id, project_sport_id, _ = _setup(client, headers, "badminton")

    res = client.patch(
        f"/projects/{project_id}/sports/{project_sport_id}/build-size",
        json={"custom_build_l_ft": 40, "custom_build_w_ft": 25},
        headers=headers,
    )
    assert res.status_code == 422
    assert "playing length" in res.text


def test_custom_build_size_can_be_cleared_back_to_the_sport_standard(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, project_sport_id, _ = _setup(client, headers, "badminton")
    client.patch(
        f"/projects/{project_id}/sports/{project_sport_id}/build-size",
        json={"custom_build_l_ft": 50, "custom_build_w_ft": 25},
        headers=headers,
    )

    res = client.patch(
        f"/projects/{project_id}/sports/{project_sport_id}/build-size",
        json={"custom_build_l_ft": None, "custom_build_w_ft": None},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["custom_build_l_ft"] is None
    assert res.json()["custom_build_w_ft"] is None


def test_sales_can_set_custom_build_size(client, director_user, db_session):
    """Same write-role gate as adding the sport in the first place
    (sales/pm/director) -- Amendment 2's own Quick setup form is a Sales
    flow, so whoever adds a sport must also be able to set its size."""
    headers = _director_headers(client, director_user)
    project_id, project_sport_id, _ = _setup(client, headers, "badminton")

    sales_headers = _sales_headers(client, db_session)
    res = client.patch(
        f"/projects/{project_id}/sports/{project_sport_id}/build-size",
        json={"custom_build_l_ft": 50, "custom_build_w_ft": 25},
        headers=sales_headers,
    )
    assert res.status_code == 200, res.text
