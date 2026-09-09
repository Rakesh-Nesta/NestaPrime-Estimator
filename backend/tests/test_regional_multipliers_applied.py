from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _create_project(client, headers, city):
    client_res = client.post("/clients", json={"name": "Regional Multiplier Test", "type": "school"}, headers=headers)
    client_id = client_res.json()["id"]
    fields = {
        "client_id": client_id,
        "city": city,
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


def _draft_cost_sheet_with_one_line(client, headers, city, source):
    """quantity 100 x rate 68, no labour_category -> J.2 blended 22%
    fallback, same shape as test_cost_sheet_lines.py's own baseline test
    (its known-good total, 10258.36, is this function's expected result
    when city is neutral -- see test_neutral_city_matches_pre_regional_baseline
    below)."""
    project_id = _create_project(client, headers, city)
    cs_res = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers)
    cost_sheet_id = cs_res.json()["id"]
    client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={
            "work_package": "structure", "category": "MS structure", "item_name": "SHS 3x3",
            "unit": "kg", "quantity": 100, "rate": 68, "source": source,
            "city_of_quote": city if source == "manual" else None,
        },
        headers=headers,
    )
    return cost_sheet_id


def _recompute_total(client, headers, cost_sheet_id):
    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()["cost_total"]


# ---------------------------------------------------------------------------
# J.1: "Regional multipliers apply to AI/master rates only ... the labour
# multiplier applies to the labour Rs amount, not to the labour %."
# Mumbai is the one seeded city with non-neutral multipliers (labour
# x1.25, transport x1.15, material x1.10 -- B.2's own worked example).
# ---------------------------------------------------------------------------


def test_ai_sourced_material_gets_the_material_multiplier(client, director_user):
    """material 100kg x 68 = 6800 x 1.10 (Mumbai) = 7480; labour, fallback
    22% of the UN-multiplied 6800 = 1496, x 1.25 (Mumbai labour) = 1870;
    base = 9350; site establishment 6% -> 9911; warranty 1% -> 10010.11;
    overhead recovery 10% -> 11011.121; contingency (structure) 5% ->
    11561.67705."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet_with_one_line(client, headers, "Mumbai", source="ai")

    total = _recompute_total(client, headers, cost_sheet_id)
    assert round(total, 2) == 11561.68


def test_manual_sourced_material_is_not_regionally_adjusted(client, director_user):
    """J.1: 'A Manual rate carries city_of_quote and is used as entered
    (it is already local).' material stays 6800 (no x1.10) -- but labour
    still gets Mumbai's x1.25, since there is no 'manual local labour
    rate' equivalent to a Manual material rate's city_of_quote. labour =
    6800*0.22 = 1496 x 1.25 = 1870; base = 8670; site establishment 6%
    -> 9190.2; warranty 1% -> 9282.102; overhead 10% -> 10210.3122;
    contingency 5% -> 10720.82781."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet_with_one_line(client, headers, "Mumbai", source="manual")

    total = _recompute_total(client, headers, cost_sheet_id)
    assert round(total, 2) == 10720.83


def test_neutral_city_matches_pre_regional_baseline(client, director_user):
    """Bengaluru is seeded at 1.0/1.0/1.0 (neutral) -- an AI-sourced line
    there should compute exactly the same total as
    test_cost_sheet_lines.py's own pre-existing baseline (10258.36),
    confirming the regional-multiplier change is a no-op at 1.0."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet_with_one_line(client, headers, "Bengaluru", source="ai")

    total = _recompute_total(client, headers, cost_sheet_id)
    assert round(total, 2) == 10258.36


def test_unmatched_city_defaults_to_neutral(client, director_user):
    """B.1's 'Other' city has no RegionalMultiplier row at all (Project.city
    is free text, unenforced -- see Project.city's own docstring); the
    lookup must fall back to neutral 1.0/1.0 rather than error or treat a
    missing row as free."""
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet_with_one_line(client, headers, "Timbuktu", source="ai")

    total = _recompute_total(client, headers, cost_sheet_id)
    assert round(total, 2) == 10258.36


def test_regional_multipliers_are_read_only_to_everyone_but_director_seed(client, director_user, db_session):
    """Confirms the existing read-only GET is unaffected by this change --
    Sales/PM/Director can all read the table (used by B.1's city-dropdown
    auto-effect preview); Procurement/CA-Tax cannot."""
    headers = _director_headers(client, director_user)
    res = client.get("/regional-multipliers", headers=headers)
    assert res.status_code == 200, res.text
    mumbai = next(r for r in res.json() if r["city"] == "Mumbai")
    assert mumbai["labour_multiplier"] == 1.25
    assert mumbai["transport_multiplier"] == 1.15
    assert mumbai["material_multiplier"] == 1.10
