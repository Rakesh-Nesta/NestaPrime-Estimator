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
    res = client.post("/clients", json={"name": "Take-off Client", "type": "school"}, headers=headers)
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


def _setup(client, headers, sport_key="box_cricket"):
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id, sport_key=sport_key)
    cost_sheet_id = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers).json()["id"]
    # E.5: the default city may auto-add a "Structural engineer design &
    # sign-off" line -- removed so these tests see only the structure
    # take-off lines they add themselves.
    for line in client.get(f"/cost-sheets/{cost_sheet_id}/lines", headers=headers).json():
        client.delete(f"/cost-sheets/{cost_sheet_id}/lines/{line['id']}", headers=headers)
    return project_id, project_sport_id, cost_sheet_id


BASE_RATES = {"steel_rate_per_kg": 68, "netting_rate_per_sqm": 45, "concrete_rate_per_cum": 6500}


def test_sales_cannot_add_a_structure(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/structures",
        json={
            "project_sport_id": project_sport_id,
            "structure_type": "a",
            "section": "shs_3",
            "wall_thickness_mm": 2.0,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "height_ft": 12,
            **BASE_RATES,
        },
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_height_below_sport_minimum_is_blocked(client, director_user):
    """E.4: 'structure height must be >= the sport's minimum clear height;
    the app blocks a selection that violates it.' Badminton needs 24 ft."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="badminton")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/structures",
        json={
            "project_sport_id": project_sport_id,
            "structure_type": "b",
            "section": "shs_4",
            "wall_thickness_mm": 2.5,
            "build_l_ft": 52,
            "build_w_ft": 30,
            "height_ft": 12,  # below the 24 ft minimum
            **BASE_RATES,
        },
        headers=headers,
    )
    assert res.status_code == 400
    assert "clear height" in res.json()["detail"]


def test_peb_and_padel_are_rejected_as_vendor_quote_only(client, director_user):
    """E.2a: Types E (PEB) and F (Padel) are priced from a vendor quote,
    not a formula take-off."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)

    for structure_type in ("e", "f"):
        res = client.post(
            f"/cost-sheets/{cost_sheet_id}/structures",
            json={
                "project_sport_id": project_sport_id,
                "structure_type": structure_type,
                "section": "shs_4",
                "wall_thickness_mm": 3.0,
                "build_l_ft": 50,
                "build_w_ft": 25,
                "height_ft": 16,
                **BASE_RATES,
            },
            headers=headers,
        )
        assert res.status_code == 400, res.text


def test_structures_can_only_be_added_to_a_draft_cost_sheet(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/structures",
        json={
            "project_sport_id": project_sport_id,
            "structure_type": "a",
            "section": "shs_3",
            "wall_thickness_mm": 2.0,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "height_ft": 12,
            **BASE_RATES,
        },
        headers=headers,
    )
    client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/structures",
        json={
            "project_sport_id": project_sport_id,
            "structure_type": "d",
            "section": "shs_3",
            "wall_thickness_mm": 2.0,
            "build_l_ft": 20,
            "build_w_ft": 10,
            "height_ft": 10,
            **BASE_RATES,
        },
        headers=headers,
    )
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# Take-off formulas (E.2a), hand-verified independently of the implementation
# ---------------------------------------------------------------------------


def test_type_a_box_cricket_take_off(client, director_user):
    """Box cricket 50x25 ft, S=10 (default), H=12, D=3 (default), 3x3 SHS
    2.0mm (4.6 kg/m). Independently computed: columns 14, trusses 6,
    purlins 106.68 m, steel length 254.508 m -> theoretical 1170.7368 kg,
    ordered (x1.05) 1229.27364 kg; envelope 2750 sqft = 255.48336 sqm,
    ordered (x1.10) 281.031696 sqm; foundations 14 x 1.5x1.5x3 ft
    = 2.6759376 cum."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="box_cricket")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/structures",
        json={
            "project_sport_id": project_sport_id,
            "structure_type": "a",
            "section": "shs_3",
            "wall_thickness_mm": 2.0,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "height_ft": 12,
            **BASE_RATES,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]
    assert breakdown["columns"] == 14
    assert breakdown["trusses"] == 6
    assert breakdown["foundations_count"] == 14
    assert round(breakdown["steel_length_m"], 2) == round(254.508, 2)
    assert round(breakdown["steel_kg_theoretical"], 2) == round(1170.7368, 2)
    assert round(breakdown["steel_kg_ordered"], 2) == round(1229.27364, 2)
    assert round(breakdown["envelope_area_sqm"], 2) == round(255.48336, 2)
    assert round(breakdown["envelope_area_ordered_sqm"], 2) == round(281.031696, 2)
    assert round(breakdown["foundation_volume_cum"], 3) == round(2.6759376, 3)

    lines = res.json()["lines"]
    assert len(lines) == 3  # steel, netting, foundation -- no finish line requested
    steel_line = next(line for line in lines if line["unit"] == "kg" and line["category"] == "MS structure")
    assert steel_line["work_package"] == "structure"
    netting_line = next(line for line in lines if line["category"] == "Netting")
    assert netting_line["work_package"] == "structure"
    foundation_line = next(line for line in lines if line["category"] == "Foundation")
    assert foundation_line["work_package"] == "civil"


def test_type_b_fully_closed_take_off(client, director_user):
    """30x20 ft, S=9 (default), H=14, D=4 (default), 4x4 SHS 2.5mm
    (7.6 kg/m). Independently computed: columns 14, trusses 5,
    steel length 192.6336 m -> theoretical 1464.01536 kg, ordered
    1537.216128 kg; envelope 2000 sqft = 185.80608 sqm, ordered
    204.386688 sqm; foundations 14 x 2x2x4 ft = 6.3429632 cum."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="box_cricket")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/structures",
        json={
            "project_sport_id": project_sport_id,
            "structure_type": "b",
            "section": "shs_4",
            "wall_thickness_mm": 2.5,
            "build_l_ft": 30,
            "build_w_ft": 20,
            "height_ft": 14,
            **BASE_RATES,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]
    assert breakdown["columns"] == 14
    assert breakdown["trusses"] == 5
    assert round(breakdown["steel_length_m"], 3) == round(192.6336, 3)
    assert round(breakdown["steel_kg_theoretical"], 2) == round(1464.01536, 2)
    assert round(breakdown["steel_kg_ordered"], 2) == round(1537.216128, 2)
    assert round(breakdown["envelope_area_sqm"], 2) == round(185.80608, 2)
    assert round(breakdown["envelope_area_ordered_sqm"], 2) == round(204.386688, 2)
    assert round(breakdown["foundation_volume_cum"], 3) == round(6.3429632, 3)


def test_type_g_fence_take_off(client, director_user):
    """40x20 ft perimeter fence, S=10 (default), H=10, D=2 (default),
    round 2.5in posts (5.1 kg/m). Independently computed: perimeter 120 ft,
    posts (columns) 12, steel length 117.0432 m -> theoretical
    596.92032 kg, ordered 626.766336 kg; chain-link 1200 sqft
    = 111.483648 sqm, ordered 122.63201... sqm; foundations 12 x
    0.75x0.75x2 ft = 0.3822768 cum."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="box_cricket")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/structures",
        json={
            "project_sport_id": project_sport_id,
            "structure_type": "g",
            "section": "round_2_5",
            "build_l_ft": 40,
            "build_w_ft": 20,
            "height_ft": 10,
            **BASE_RATES,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]
    assert breakdown["columns"] == 12
    assert breakdown["trusses"] == 0
    assert round(breakdown["steel_length_m"], 3) == round(117.0432, 3)
    assert round(breakdown["steel_kg_theoretical"], 2) == round(596.92032, 2)
    assert round(breakdown["steel_kg_ordered"], 2) == round(626.766336, 2)
    assert round(breakdown["envelope_area_sqm"], 2) == round(111.483648, 2)
    assert round(breakdown["envelope_area_ordered_sqm"], 2) == round(122.632013, 2)
    assert round(breakdown["foundation_volume_cum"], 3) == round(0.3822768, 3)

    lines = res.json()["lines"]
    chain_link_line = next(line for line in lines if line["category"] == "Chain-link")
    assert chain_link_line["unit"] == "sqm"


def test_round_section_ignores_a_supplied_wall_thickness(client, director_user):
    """Round sections carry a single IS 1239 medium-class weight -- a
    stray wall_thickness_mm must not 422 the request."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="box_cricket")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/structures",
        json={
            "project_sport_id": project_sport_id,
            "structure_type": "g",
            "section": "round_2_5",
            "wall_thickness_mm": 2.0,  # should be ignored, not looked up
            "build_l_ft": 40,
            "build_w_ft": 20,
            "height_ft": 10,
            **BASE_RATES,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["breakdown"]["resolved_wall_thickness_mm"] is None


# ---------------------------------------------------------------------------
# E.5 auto-enhancements
# ---------------------------------------------------------------------------


def test_wind_zone_four_upsizes_section_and_thickness(client, director_user):
    """E.2: wind-zone upsize steps to the next row for section and the next
    column for wall thickness. Requested shs_3 @ 2.0mm with wind_zone=4
    resolves to shs_4 @ 2.5mm (7.6 kg/m), not the requested 4.6 kg/m."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="box_cricket")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/structures",
        json={
            "project_sport_id": project_sport_id,
            "structure_type": "a",
            "section": "shs_3",
            "wall_thickness_mm": 2.0,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "height_ft": 12,
            "wind_zone": 4,
            **BASE_RATES,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    breakdown = res.json()["breakdown"]
    assert breakdown["resolved_section"] == "shs_4"
    assert breakdown["resolved_wall_thickness_mm"] == 2.5
    # Same geometry as the plain Type A test, but heavier steel per metre.
    assert round(breakdown["steel_kg_theoretical"], 2) == round(254.508 * 7.6, 2)


def test_coastal_uplifts_the_effective_steel_rate(client, director_user):
    """E.5: 'Coastal -> Hot-dip galvanise; +15% MS.' The steel line's rate
    should reflect the 15% uplift plus the folded-in 2% consumables --
    68 x 1.15 x 1.02 = 79.764 -- while the netting rate is untouched."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="box_cricket")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/structures",
        json={
            "project_sport_id": project_sport_id,
            "structure_type": "a",
            "section": "shs_3",
            "wall_thickness_mm": 2.0,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "height_ft": 12,
            "coastal": True,
            "finish_rate_per_kg": 12,
            **BASE_RATES,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    lines = res.json()["lines"]
    steel_line = next(line for line in lines if line["category"] == "MS structure")
    assert round(steel_line["rate"], 2) == round(68 * 1.15 * 1.02, 2)
    assert "coastal" in steel_line["item_name"].lower()
    finish_line = next(line for line in lines if line["category"] == "Finish")
    assert finish_line["item_name"] == "Hot-dip galvanising"
    assert finish_line["rate"] == 12


def test_seismic_zone_adds_half_foot_to_foundation_depth(client, director_user):
    """E.5: 'Seismic IV-V -> Foundation +0.5 ft depth & width.' Depth-only
    is implemented; a 3 ft default becomes 3.5 ft for Type A."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="box_cricket")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/structures",
        json={
            "project_sport_id": project_sport_id,
            "structure_type": "a",
            "section": "shs_3",
            "wall_thickness_mm": 2.0,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "height_ft": 12,
            "seismic_zone": "V",
            **BASE_RATES,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    # 14 foundations x 1.5 x 1.5 x 3.5 ft (was 3.0 ft) x 0.0283168
    expected_cum = 14 * 1.5 * 1.5 * 3.5 * 0.0283168
    assert round(res.json()["breakdown"]["foundation_volume_cum"], 3) == round(expected_cum, 3)


# ---------------------------------------------------------------------------
# Feeds straight into a real, recomputable Cost Sheet
# ---------------------------------------------------------------------------


def test_structure_lines_feed_into_recompute(client, director_user):
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers, sport_key="box_cricket")

    client.post(
        f"/cost-sheets/{cost_sheet_id}/structures",
        json={
            "project_sport_id": project_sport_id,
            "structure_type": "a",
            "section": "shs_3",
            "wall_thickness_mm": 2.0,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "height_ft": 12,
            **BASE_RATES,
        },
        headers=headers,
    )
    lines = client.get(f"/cost-sheets/{cost_sheet_id}/lines", headers=headers).json()
    assert len(lines) == 3  # steel, netting, foundation

    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    assert recomputed["cost_total"] > 0

    verify_res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert verify_res.status_code == 200
