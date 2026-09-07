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
    res = client.post("/clients", json={"name": "Consumption Sheet Client", "type": "school"}, headers=headers)
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


def test_sales_cannot_view_consumption_sheet(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    _, _, cost_sheet_id = _setup(client, headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.get(f"/cost-sheets/{cost_sheet_id}/consumption-sheet", headers=sales_headers)
    assert res.status_code == 403


def test_manual_line_has_no_wastage_theoretical_equals_order(client, director_user):
    """A manual line has no wastage concept -- theoretical qty must equal
    the order qty exactly, not a fabricated 0% entry."""
    headers = _director_headers(client, director_user)
    _, _, cost_sheet_id = _setup(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={"work_package": "accessories", "category": "Accessories", "item_name": "Goal posts", "unit": "each", "quantity": 2, "rate": 15000},
        headers=headers,
    )

    rows = client.get(f"/cost-sheets/{cost_sheet_id}/consumption-sheet", headers=headers).json()
    assert len(rows) == 1
    row = rows[0]
    assert row["wastage_percent"] is None
    assert row["theoretical_qty"] == row["order_qty"] == 2.0
    assert row["amount"] == 30000.0
    assert row["vendor"] is None
    assert row["delivery_date"] is None
    assert row["received_qty"] is None


def test_structure_steel_line_backs_out_theoretical_qty_from_five_percent_wastage(client, director_user):
    """E.2: 5% steel wastage. order_qty = theoretical x 1.05, so
    theoretical = order / 1.05."""
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
            "steel_rate_per_kg": 68,
            "netting_rate_per_sqm": 45,
            "concrete_rate_per_cum": 6500,
        },
        headers=headers,
    )

    rows = client.get(f"/cost-sheets/{cost_sheet_id}/consumption-sheet", headers=headers).json()
    steel_row = next(r for r in rows if r["category"] == "MS structure")
    assert steel_row["wastage_percent"] == 5.0
    assert steel_row["order_qty"] == 1229.27
    assert round(steel_row["theoretical_qty"], 2) == round(1229.27 / 1.05, 2)

    netting_row = next(r for r in rows if r["category"] == "Netting")
    assert netting_row["wastage_percent"] == 10.0
    assert round(netting_row["theoretical_qty"], 2) == round(281.03 / 1.10, 2)

    foundation_row = next(r for r in rows if r["category"] == "Foundation")
    assert foundation_row["wastage_percent"] is None
    assert foundation_row["theoretical_qty"] == foundation_row["order_qty"]


def test_base_line_records_two_percent_concrete_wastage(client, director_user):
    """J.3: 'concrete cum = area_sqm x (thickness_in x 0.0254) x 1.02.'"""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    client.post(
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

    rows = client.get(f"/cost-sheets/{cost_sheet_id}/consumption-sheet", headers=headers).json()
    assert len(rows) == 1
    assert rows[0]["wastage_percent"] == 2.0
    assert round(rows[0]["theoretical_qty"], 3) == round(rows[0]["order_qty"] / 1.02, 3)


def test_turf_line_records_the_roll_layout_algorithms_own_wastage(client, director_user):
    """F.5's worked example: cut-length ordering wastage is ~4.99%, not a
    fixed constant -- the consumption sheet should reflect whatever the
    algorithm actually computed for this specific field."""
    headers = _director_headers(client, director_user)
    _, project_sport_id, cost_sheet_id = _setup(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/flooring/turf",
        json={
            "project_sport_id": project_sport_id,
            "build_l_ft": 50,
            "build_w_ft": 25,
            "pile_height": "40mm",
            "cut_length_allowed": True,
            "turf_rate_per_sqm": 900,
            "sand_rate_per_kg": 8,
            "rubber_rate_per_kg": 40,
        },
        headers=headers,
    )

    rows = client.get(f"/cost-sheets/{cost_sheet_id}/consumption-sheet", headers=headers).json()
    turf_row = next(r for r in rows if r["category"] == "Turf")
    assert round(turf_row["wastage_percent"], 2) == 4.99
    infill_row = next(r for r in rows if r["category"] == "Infill")
    assert infill_row["wastage_percent"] is None  # exact kg from area x rate, no wastage concept


def test_consumption_sheet_math_is_internally_consistent(client, director_user):
    """theoretical_qty x (1 + wastage%/100) must round-trip back to
    order_qty for every wasted line."""
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
            "steel_rate_per_kg": 68,
            "netting_rate_per_sqm": 45,
            "concrete_rate_per_cum": 6500,
        },
        headers=headers,
    )

    rows = client.get(f"/cost-sheets/{cost_sheet_id}/consumption-sheet", headers=headers).json()
    for row in rows:
        if row["wastage_percent"]:
            recomputed_order = row["theoretical_qty"] * (1 + row["wastage_percent"] / 100)
            assert round(recomputed_order, 1) == round(row["order_qty"], 1)
