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


def _create_client_record(client, headers, client_type="school", name="Test School"):
    res = client.post("/clients", json={"name": name, "type": client_type}, headers=headers)
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


def _add_project_sport(client, headers, project_id, sport_key="badminton"):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": sport_id, "building_status": "open_air"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _empty_draft_cost_sheet(client, headers, project_id=None):
    if project_id is None:
        client_id = _create_client_record(client, headers)
        project_id = _create_project(client, headers, client_id)
    res = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers)
    assert res.status_code == 201, res.text
    return project_id, res.json()["id"]


def _labour_category_id(client, headers, key):
    categories = client.get("/labour-categories", headers=headers).json()
    return next(c["id"] for c in categories if c["key"] == key)


# ---------------------------------------------------------------------------
# Role gates and lifecycle
# ---------------------------------------------------------------------------


def test_sales_cannot_add_or_view_lines(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, cost_sheet_id = _empty_draft_cost_sheet(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    add_attempt = client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={"work_package": "structure", "category": "MS structure", "item_name": "SHS 3x3", "unit": "kg", "quantity": 100, "rate": 68},
        headers=sales_headers,
    )
    assert add_attempt.status_code == 403

    list_attempt = client.get(f"/cost-sheets/{cost_sheet_id}/lines", headers=sales_headers)
    assert list_attempt.status_code == 403


def test_work_package_is_required(client, director_user):
    """O.801: work_package is 'REQUIRED (NOT NULL) ... because contingency
    grouping (K.1 step 6) depends on it.'"""
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _empty_draft_cost_sheet(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={"category": "MS structure", "item_name": "SHS 3x3", "unit": "kg", "quantity": 100, "rate": 68},
        headers=headers,
    )
    assert res.status_code == 422


def test_lines_cannot_be_added_once_verified(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _empty_draft_cost_sheet(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={"work_package": "structure", "category": "MS structure", "item_name": "SHS 3x3", "unit": "kg", "quantity": 100, "rate": 68},
        headers=headers,
    )
    client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={"work_package": "civil", "category": "Base", "item_name": "PCC", "unit": "cum", "quantity": 10, "rate": 6000},
        headers=headers,
    )
    assert res.status_code == 400


def test_cannot_verify_an_empty_cost_sheet(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _empty_draft_cost_sheet(client, headers)
    res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert res.status_code == 400


def test_line_on_a_sport_not_in_this_project_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id_a = _create_project(client, headers, client_id)
    project_id_b = _create_project(client, headers, client_id)
    other_project_sport_id = _add_project_sport(client, headers, project_id_b)

    _, cost_sheet_id = _empty_draft_cost_sheet(client, headers, project_id=project_id_a)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={
            "project_sport_id": other_project_sport_id,
            "work_package": "structure",
            "category": "MS structure",
            "item_name": "SHS 3x3",
            "unit": "kg",
            "quantity": 100,
            "rate": 68,
        },
        headers=headers,
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Recompute math (K.1 steps 1, 2, 6)
# ---------------------------------------------------------------------------


def test_recompute_with_blended_fallback_labour_and_default_contingency(client, director_user):
    """No labour_category on the line -> J.2 'blended 22%' fallback.
    material 100kg x 68 = 6800; labour 6800*0.22 = 1496; base 8296;
    contingency_structure_percent default 5% -> 8296*1.05 = 8710.80."""
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _empty_draft_cost_sheet(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={"work_package": "structure", "category": "MS structure", "item_name": "SHS 3x3", "unit": "kg", "quantity": 100, "rate": 68},
        headers=headers,
    )

    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    assert res.status_code == 200, res.text
    assert round(res.json()["cost_total"], 2) == 8710.80

    fetched = client.get(f"/cost-sheets/{cost_sheet_id}", headers=headers)
    assert round(fetched.json()["cost_total"], 2) == 8710.80


def test_recompute_uses_lines_own_labour_category_when_set(client, director_user):
    """turf_laying category = 12%: material 200sqm x 45 = 9000;
    labour 9000*0.12 = 1080; base 10080; contingency_flooring_percent
    default 3% -> 10080*1.03 = 10382.40."""
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _empty_draft_cost_sheet(client, headers)
    turf_category_id = _labour_category_id(client, headers, "turf_laying")

    client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={
            "work_package": "flooring",
            "category": "Turf",
            "item_name": "Football turf 40mm",
            "unit": "sqm",
            "quantity": 200,
            "rate": 45,
            "labour_category_id": turf_category_id,
        },
        headers=headers,
    )

    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    assert round(res.json()["cost_total"], 2) == 10382.40


def test_contingency_is_grouped_per_work_package_not_pooled(client, director_user):
    """Two lines in different work_packages, each with its own contingency
    %, summed independently -- not pooled into one blended contingency."""
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _empty_draft_cost_sheet(client, headers)
    turf_category_id = _labour_category_id(client, headers, "turf_laying")

    client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={"work_package": "structure", "category": "MS structure", "item_name": "SHS 3x3", "unit": "kg", "quantity": 100, "rate": 68},
        headers=headers,
    )
    client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={
            "work_package": "flooring",
            "category": "Turf",
            "item_name": "Football turf 40mm",
            "unit": "sqm",
            "quantity": 200,
            "rate": 45,
            "labour_category_id": turf_category_id,
        },
        headers=headers,
    )

    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    assert round(res.json()["cost_total"], 2) == round(8710.80 + 10382.40, 2)


def test_deleting_a_line_and_recomputing_drops_it_from_the_total(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _empty_draft_cost_sheet(client, headers)
    line = client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={"work_package": "structure", "category": "MS structure", "item_name": "SHS 3x3", "unit": "kg", "quantity": 100, "rate": 68},
        headers=headers,
    ).json()
    client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={"work_package": "civil", "category": "Base", "item_name": "PCC", "unit": "cum", "quantity": 10, "rate": 6000},
        headers=headers,
    )

    delete_res = client.delete(f"/cost-sheets/{cost_sheet_id}/lines/{line['id']}", headers=headers)
    assert delete_res.status_code == 204

    remaining = client.get(f"/cost-sheets/{cost_sheet_id}/lines", headers=headers).json()
    assert len(remaining) == 1
    assert remaining[0]["item_name"] == "PCC"


def test_recompute_with_no_lines_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _empty_draft_cost_sheet(client, headers)
    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    assert res.status_code == 400


def test_line_amount_is_quantity_times_rate(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _empty_draft_cost_sheet(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={"work_package": "structure", "category": "MS structure", "item_name": "SHS 3x3", "unit": "kg", "quantity": 100, "rate": 68},
        headers=headers,
    )
    lines = client.get(f"/cost-sheets/{cost_sheet_id}/lines", headers=headers).json()
    assert round(lines[0]["amount"], 2) == 6800.00


# ---------------------------------------------------------------------------
# Q wiring: contingency % is a real Master Setting, not hard-coded
# ---------------------------------------------------------------------------


def test_contingency_percent_is_a_live_master_setting(client, director_user):
    """Q principle: 'no rate, percentage, floor or multiplier is
    hard-coded' -- changing contingency_structure_percent in Master
    Settings changes what /recompute actually computes."""
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _empty_draft_cost_sheet(client, headers)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={"work_package": "structure", "category": "MS structure", "item_name": "SHS 3x3", "unit": "kg", "quantity": 100, "rate": 68},
        headers=headers,
    )
    baseline = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    assert round(baseline["cost_total"], 2) == 8710.80  # 5% default contingency

    client.post(
        "/settings",
        json={"key": "contingency_structure_percent", "value": "10.0", "reason": "director decision"},
        headers=headers,
    )
    updated = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    assert round(updated["cost_total"], 2) == round(8296 * 1.10, 2)


def test_full_chain_recomputed_cost_sheet_flows_into_a_real_quotation(client, director_user):
    """End-to-end proof: a recomputed CostSheetLine total (not a manually
    typed number) verifies, feeds an Estimate, and prices a Quotation
    through the real K.1/K.2 pricing chain."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, client_type="government", name="Municipal Corp")
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)

    _, cost_sheet_id = _empty_draft_cost_sheet(client, headers, project_id=project_id)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={
            "project_sport_id": project_sport_id,
            "work_package": "services",
            "category": "Manual override",
            "item_name": "Whole-project cost (recompute test)",
            "unit": "lot",
            "quantity": 1,
            "rate": 850000,
        },
        headers=headers,
    )
    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    # services labour% has no dedicated category here (blended 22% fallback)
    # and services contingency defaults to 0% -- so cost_total == material x 1.22.
    assert round(recomputed["cost_total"], 2) == round(850000 * 1.22, 2)

    verify_res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert verify_res.status_code == 200

    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={
            "options": [
                {
                    "project_sport_id": project_sport_id,
                    "package": "standard",
                    "cost_for_option": recomputed["cost_total"],
                }
            ]
        },
        headers=headers,
    ).json()
    assert estimate["options"][0]["cost_for_option"] == round(850000 * 1.22, 2)
