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


def _create_client_record(client, headers, client_type="school", name="K1 Overheads Client"):
    res = client.post("/clients", json={"name": name, "type": client_type}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id, **overrides):
    fields = {
        # Bengaluru is seeded at neutral 1.0/1.0/1.0 regional multipliers --
        # this file's math is about K.1 overhead percentages, not regional
        # pricing, so a non-neutral city (e.g. Mumbai) would silently
        # distort every expected total here.
        "client_id": client_id, "city": "Bengaluru", "site_condition": "level", "soil_type": "normal",
        "building_status": "open_air", "site_access": "good", "power_available": "yes",
        "water_available": True, "package": "standard",
        **overrides,
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _draft_cost_sheet(client, headers, project_id=None, client_type="school"):
    if project_id is None:
        client_id = _create_client_record(client, headers, client_type=client_type)
        project_id = _create_project(client, headers, client_id)
    res = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers)
    assert res.status_code == 201, res.text
    return project_id, res.json()["id"]


# ---------------------------------------------------------------------------
# K.1 step 3: Freight & crane
# ---------------------------------------------------------------------------


def test_sales_cannot_add_freight_crane(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/freight-crane",
        json={"trips": 3, "distance_km": 40, "rate_per_km": 50},
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_freight_line_uses_trips_times_km_times_rate(client, director_user):
    """B.1: 'Freight = trips x km x Rs/km.'"""
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/freight-crane",
        json={"trips": 4, "distance_km": 35, "rate_per_km": 60},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["breakdown"]["freight_distance_km"] == 35
    assert body["breakdown"]["freight_total_km"] == 140
    lines = body["lines"]
    assert len(lines) == 1
    line = lines[0]
    assert line["work_package"] == "civil"
    assert line["unit"] == "km"
    assert line["quantity"] == 140
    assert line["rate"] == 60
    assert line["amount"] == 140 * 60


def test_freight_defaults_distance_from_the_project(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id, distance_km=80)
    _, cost_sheet_id = _draft_cost_sheet(client, headers, project_id=project_id)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/freight-crane",
        json={"trips": 2, "rate_per_km": 55},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["breakdown"]["freight_distance_km"] == 80
    assert res.json()["breakdown"]["freight_total_km"] == 160


def test_freight_with_no_distance_and_no_project_default_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)  # project has no distance_km

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/freight-crane",
        json={"trips": 2, "rate_per_km": 55},
        headers=headers,
    )
    assert res.status_code == 422


def test_crane_hire_line(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/freight-crane",
        json={"crane_days": 3, "crane_day_rate": 12000},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    lines = res.json()["lines"]
    assert len(lines) == 1
    assert lines[0]["item_name"] == "Crane hire"
    assert lines[0]["unit"] == "day"
    assert lines[0]["quantity"] == 3
    assert lines[0]["rate"] == 12000


def test_freight_and_crane_together_produce_two_lines(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/freight-crane",
        json={"trips": 2, "distance_km": 30, "rate_per_km": 50, "crane_days": 2, "crane_day_rate": 10000},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert len(res.json()["lines"]) == 2


def test_freight_crane_requires_at_least_one_complete_line(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)

    res = client.post(f"/cost-sheets/{cost_sheet_id}/freight-crane", json={}, headers=headers)
    assert res.status_code == 422


def test_crane_days_without_day_rate_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)

    res = client.post(f"/cost-sheets/{cost_sheet_id}/freight-crane", json={"crane_days": 2}, headers=headers)
    assert res.status_code == 422


def test_freight_crane_only_on_draft_cost_sheet(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/freight-crane",
        json={"trips": 1, "distance_km": 10, "rate_per_km": 40},
        headers=headers,
    )
    client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/freight-crane",
        json={"trips": 1, "distance_km": 10, "rate_per_km": 40},
        headers=headers,
    )
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# K.1 step 4: Design & approvals (CAR / workmen's comp only)
# ---------------------------------------------------------------------------


def test_sales_cannot_add_design_approvals(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/design-approvals", json={"car_policy_premium": 5000}, headers=sales_headers
    )
    assert res.status_code == 403


def test_design_approvals_produces_named_service_lines(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/design-approvals",
        json={"car_policy_premium": 8000, "workmens_comp_premium": 4500},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    lines = res.json()["lines"]
    assert len(lines) == 2
    assert all(line["work_package"] == "services" for line in lines)
    names = {line["item_name"] for line in lines}
    assert names == {"CAR (Contractor's All Risk) policy", "Workmen's compensation insurance"}
    car_line = next(line for line in lines if "CAR" in line["item_name"])
    assert car_line["rate"] == 8000
    assert car_line["quantity"] == 1


def test_design_approvals_accepts_only_one_of_the_two(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/design-approvals", json={"workmens_comp_premium": 3000}, headers=headers
    )
    assert res.status_code == 201, res.text
    assert len(res.json()["lines"]) == 1


def test_design_approvals_requires_at_least_one_field(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)

    res = client.post(f"/cost-sheets/{cost_sheet_id}/design-approvals", json={}, headers=headers)
    assert res.status_code == 422


def test_design_approvals_feeds_into_recompute(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/design-approvals",
        json={"car_policy_premium": 10000, "workmens_comp_premium": 5000},
        headers=headers,
    )
    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    assert recomputed["cost_total"] > 0


# ---------------------------------------------------------------------------
# K.1 step 4B: Warranty reserve % (private clients only)
# ---------------------------------------------------------------------------


def _add_structure_line(client, headers, cost_sheet_id):
    return client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={"work_package": "structure", "category": "MS structure", "item_name": "SHS 3x3", "unit": "kg", "quantity": 100, "rate": 68},
        headers=headers,
    )


def test_warranty_reserve_applies_by_default_for_private_clients(client, director_user):
    """K.1 4B: 'Warranty reserve 1% (private clients; Appendix B).'
    material 6800, blended labour 22% -> 1496, base 8296; site estab 6%
    -> 8793.76; warranty 1% -> 8881.6976; overhead 10% -> 9769.86736;
    structure contingency 5% -> 10258.36."""
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers, client_type="school")
    _add_structure_line(client, headers, cost_sheet_id)

    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    assert round(res.json()["cost_total"], 2) == 10258.36


def test_warranty_reserve_is_replaced_by_dlp_reserve_for_tender_mode_projects(client, director_user):
    """K.1 4A/4B: the Tender Mode DLP reserve and the private-client
    warranty reserve are mutually exclusive -- a Government (tender_mode)
    project gets 4A's DLP reserve (1% by default) instead of 4B's warranty
    reserve, never both. Both default to 1%, so the final total happens to
    match test_warranty_reserve_applies_by_default_for_private_clients --
    that's a coincidence of the shared default, not proof the mechanism is
    a no-op (see test_dlp_reserve_percent_is_a_live_master_setting in
    test_tender_overheads.py, which changes the rate and shows the total
    move)."""
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers, client_type="government")
    _add_structure_line(client, headers, cost_sheet_id)

    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    # DLP reserve 1% instead of warranty reserve 1%, no BOCW cess (subtotal
    # well under the Rs 10 L threshold): 8296 * 1.06 * 1.01 (DLP) * 1.10 (overhead) * 1.05 (contingency)
    expected = 8296 * 1.06 * 1.01 * 1.10 * 1.05
    assert round(res.json()["cost_total"], 2) == round(expected, 2)


def test_warranty_reserve_percent_is_a_live_master_setting(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers, client_type="school")
    _add_structure_line(client, headers, cost_sheet_id)

    client.post(
        "/settings", json={"key": "warranty_reserve_percent", "value": "2.0", "reason": "director decision"},
        headers=headers,
    )
    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    expected = 8296 * 1.06 * 1.02 * 1.10 * 1.05
    assert round(res.json()["cost_total"], 2) == round(expected, 2)


# ---------------------------------------------------------------------------
# K.1 step 5A: Company overhead recovery %
# ---------------------------------------------------------------------------


def test_company_overhead_recovery_percent_is_a_live_master_setting(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers, client_type="school")
    _add_structure_line(client, headers, cost_sheet_id)

    client.post(
        "/settings",
        json={"key": "company_overhead_recovery_percent", "value": "15.0", "reason": "director decision"},
        headers=headers,
    )
    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    expected = 8296 * 1.06 * 1.01 * 1.15 * 1.05
    assert round(res.json()["cost_total"], 2) == round(expected, 2)
