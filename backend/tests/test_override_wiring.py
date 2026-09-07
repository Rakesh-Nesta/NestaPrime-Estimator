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


def _create_client_record(client, headers, client_type="school", name="Override Wiring Client"):
    res = client.post("/clients", json={"name": name, "type": client_type}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id, **overrides):
    fields = {
        "client_id": client_id, "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
        "building_status": "open_air", "site_access": "good", "power_available": "yes",
        "water_available": True, "package": "standard",
        **overrides,
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _draft_cost_sheet(client, headers, client_type="school"):
    client_id = _create_client_record(client, headers, client_type=client_type)
    project_id = _create_project(client, headers, client_id)
    res = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _add_structure_line(client, headers, cost_sheet_id):
    return client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={"work_package": "structure", "category": "MS structure", "item_name": "SHS 3x3", "unit": "kg", "quantity": 100, "rate": 68},
        headers=headers,
    )


def _create_override(client, headers, cost_sheet_id, key, master_value, override_value, reason="test override"):
    return client.post(
        "/overrides",
        json={
            "document_type": "cost_sheet", "document_id": cost_sheet_id, "setting_key": key,
            "master_value": master_value, "override_value": override_value, "reason": reason,
        },
        headers=headers,
    )


# ---------------------------------------------------------------------------
# GET k1-constants
# ---------------------------------------------------------------------------


def test_k1_constants_lists_defaults_with_no_override(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)

    res = client.get(f"/cost-sheets/{cost_sheet_id}/k1-constants", headers=headers)
    assert res.status_code == 200, res.text
    by_key = {c["key"]: c for c in res.json()}

    assert by_key["site_establishment_percent"]["master_value"] == 6.0
    assert by_key["site_establishment_percent"]["effective_value"] == 6.0
    assert by_key["site_establishment_percent"]["is_overridden"] is False
    assert by_key["company_overhead_recovery_percent"]["master_value"] == 10.0
    assert by_key["warranty_reserve_percent"]["master_value"] == 1.0
    assert by_key["contingency_structure_percent"]["master_value"] == 5.0
    assert by_key["contingency_pool_percent"]["master_value"] == 8.0


def test_k1_constants_excludes_warranty_reserve_for_tender_mode(client, director_user):
    """K.1 4A/4B mutual exclusivity: a tender_mode (Government) project
    never gets the private-client warranty reserve, so it shouldn't even
    be offered as an overridable constant."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers, client_type="government")

    res = client.get(f"/cost-sheets/{cost_sheet_id}/k1-constants", headers=headers)
    keys = {c["key"] for c in res.json()}
    assert "warranty_reserve_percent" not in keys
    assert "site_establishment_percent" in keys


def test_sales_cannot_read_k1_constants(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.get(f"/cost-sheets/{cost_sheet_id}/k1-constants", headers=sales_headers)
    assert res.status_code == 403


def test_k1_constants_for_unknown_cost_sheet_404s(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.get("/cost-sheets/00000000-0000-0000-0000-000000000000/k1-constants", headers=headers)
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Override actually changes what /recompute computes
# ---------------------------------------------------------------------------


def test_override_shows_up_in_k1_constants(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)

    override_res = _create_override(client, headers, cost_sheet_id, "site_establishment_percent", "6.0", "8.0")
    assert override_res.status_code == 201, override_res.text

    res = client.get(f"/cost-sheets/{cost_sheet_id}/k1-constants", headers=headers)
    entry = next(c for c in res.json() if c["key"] == "site_establishment_percent")
    assert entry["is_overridden"] is True
    assert entry["master_value"] == 6.0
    assert entry["effective_value"] == 8.0
    assert entry["override_reason"] == "test override"


def test_override_changes_the_recomputed_total(client, director_user):
    """Q.2 rule 2: an override on THIS document only, not the global
    Master Setting -- proven by comparing against the un-overridden
    hand-computed baseline (10258.36, per test_cost_sheet_lines.py)."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    _add_structure_line(client, headers, cost_sheet_id)

    _create_override(client, headers, cost_sheet_id, "site_establishment_percent", "6.0", "8.0")

    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    # material 6800, blended labour 22% -> 1496, base 8296; site estab
    # OVERRIDDEN to 8% -> 8959.68; warranty 1% -> 9049.2768; overhead 10%
    # -> 9954.20448; structure contingency 5% -> 10451.914704
    expected = 8296 * 1.08 * 1.01 * 1.10 * 1.05
    assert round(res.json()["cost_total"], 2) == round(expected, 2)


def test_override_does_not_affect_a_different_cost_sheet(client, director_user):
    headers = _director_headers(client, director_user)
    overridden_id = _draft_cost_sheet(client, headers)
    plain_id = _draft_cost_sheet(client, headers)
    _add_structure_line(client, headers, overridden_id)
    _add_structure_line(client, headers, plain_id)

    _create_override(client, headers, overridden_id, "site_establishment_percent", "6.0", "8.0")

    overridden_total = client.post(f"/cost-sheets/{overridden_id}/recompute", headers=headers).json()["cost_total"]
    plain_total = client.post(f"/cost-sheets/{plain_id}/recompute", headers=headers).json()["cost_total"]

    assert round(overridden_total, 2) == round(8296 * 1.08 * 1.01 * 1.10 * 1.05, 2)
    assert round(plain_total, 2) == 10258.36  # unaffected -- the global 6% default
    assert round(overridden_total, 2) != round(plain_total, 2)


def test_a_later_override_supersedes_an_earlier_one(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    _add_structure_line(client, headers, cost_sheet_id)

    _create_override(client, headers, cost_sheet_id, "site_establishment_percent", "6.0", "8.0", reason="first")
    _create_override(client, headers, cost_sheet_id, "site_establishment_percent", "6.0", "7.0", reason="corrected")

    res = client.get(f"/cost-sheets/{cost_sheet_id}/k1-constants", headers=headers)
    entry = next(c for c in res.json() if c["key"] == "site_establishment_percent")
    assert entry["effective_value"] == 7.0
    assert entry["override_reason"] == "corrected"

    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    expected = 8296 * 1.07 * 1.01 * 1.10 * 1.05
    assert round(recomputed["cost_total"], 2) == round(expected, 2)


def test_contingency_override_only_affects_its_own_work_package(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    _add_structure_line(client, headers, cost_sheet_id)  # structure, 5% default contingency
    client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={"work_package": "flooring", "category": "Turf", "item_name": "Turf", "unit": "sqm", "quantity": 200, "rate": 45},
        headers=headers,
    )

    _create_override(client, headers, cost_sheet_id, "contingency_structure_percent", "5.0", "10.0")

    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    structure_expected = 8296 * 1.06 * 1.01 * 1.10 * 1.10  # overridden 10%
    flooring_material = 200 * 45
    flooring_labour = flooring_material * 0.22  # blended fallback, no labour category on this line
    flooring_base = flooring_material + flooring_labour
    flooring_expected = flooring_base * 1.06 * 1.01 * 1.10 * 1.03  # flooring contingency unchanged at 3%
    assert round(recomputed["cost_total"], 2) == round(structure_expected + flooring_expected, 2)


def test_warranty_reserve_override_for_a_private_client(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers, client_type="school")
    _add_structure_line(client, headers, cost_sheet_id)

    _create_override(client, headers, cost_sheet_id, "warranty_reserve_percent", "1.0", "3.0")

    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    expected = 8296 * 1.06 * 1.03 * 1.10 * 1.05
    assert round(recomputed["cost_total"], 2) == round(expected, 2)


def test_company_overhead_override(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    _add_structure_line(client, headers, cost_sheet_id)

    _create_override(client, headers, cost_sheet_id, "company_overhead_recovery_percent", "10.0", "12.0")

    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    expected = 8296 * 1.06 * 1.01 * 1.12 * 1.05
    assert round(recomputed["cost_total"], 2) == round(expected, 2)
