import pytest

from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _pm_headers(client, db_session):
    user = User(
        name="Test PM", email="pm@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.PM
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "pm@test.local")


def _sport_id(client, headers, sport_key):
    return next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)


def _create_client_record(client, headers, client_type="school", name="Margin Test Client"):
    res = client.post(
        "/clients",
        json={"name": name, "type": client_type, "contact_name": "Jane PM", "phone": "9999999999"},
        headers=headers,
    )
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


def _add_project_sport(client, headers, project_id, sport_key):
    sport_id = _sport_id(client, headers, sport_key)
    res = client.post(
        f"/projects/{project_id}/sports", json={"sport_id": sport_id, "building_status": "open_air"}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _verified_cost_sheet(client, headers, project_id, cost_total):
    cost_sheet_id = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_total}, headers=headers
    ).json()["id"]
    res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert res.status_code == 200, res.text
    return cost_sheet_id


# ---------------------------------------------------------------------------
# Sport margin-floor override CRUD (K.2: Director-defined, replaces the
# client floor for that sport)
# ---------------------------------------------------------------------------


def test_no_sport_overrides_exist_by_default(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.get("/sport-margin-policies", headers=headers)
    assert res.status_code == 200
    assert res.json() == []


def test_director_can_set_a_sport_margin_floor_override(client, director_user):
    headers = _director_headers(client, director_user)
    sport_id = _sport_id(client, headers, "badminton")

    res = client.put(f"/sport-margin-policies/{sport_id}", json={"floor_margin_percent": 15.0}, headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["sport_id"] == sport_id
    assert body["floor_margin_percent"] == 15.0

    listed = client.get("/sport-margin-policies", headers=headers).json()
    assert len(listed) == 1
    assert listed[0]["floor_margin_percent"] == 15.0


def test_pm_cannot_set_a_sport_margin_floor_override(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    sport_id = _sport_id(client, director_headers, "badminton")

    pm_headers = _pm_headers(client, db_session)
    res = client.put(f"/sport-margin-policies/{sport_id}", json={"floor_margin_percent": 15.0}, headers=pm_headers)
    assert res.status_code == 403


def test_director_can_delete_a_sport_margin_floor_override(client, director_user):
    headers = _director_headers(client, director_user)
    sport_id = _sport_id(client, headers, "badminton")
    client.put(f"/sport-margin-policies/{sport_id}", json={"floor_margin_percent": 15.0}, headers=headers)

    res = client.delete(f"/sport-margin-policies/{sport_id}", headers=headers)
    assert res.status_code == 204
    assert client.get("/sport-margin-policies", headers=headers).json() == []


# ---------------------------------------------------------------------------
# /pricing/quote: sport override replaces the client floor
# ---------------------------------------------------------------------------


def test_pricing_quote_falls_back_to_client_floor_when_no_sport_override(client, director_user):
    """School: floor 18%, competitive -> gap 3 -> target 21% (K.2 seed defaults)."""
    headers = _director_headers(client, director_user)
    sport_id = _sport_id(client, headers, "badminton")

    res = client.post(
        "/pricing/quote",
        json={"cost_incl_contingency": 850000, "client_type": "school", "sport_id": sport_id},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["floor_margin_percent"] == 18.0
    assert body["target_margin_percent"] == 21.0


def test_pricing_quote_uses_sport_override_floor_when_director_has_set_one(client, director_user):
    """K.2: 'A sport-type floor ... replaces the client floor for that
    sport when the Director has defined one.' School's own
    competitive_segment gap (+3) still applies on top of the sport floor."""
    headers = _director_headers(client, director_user)
    sport_id = _sport_id(client, headers, "badminton")
    client.put(f"/sport-margin-policies/{sport_id}", json={"floor_margin_percent": 15.0}, headers=headers)

    res = client.post(
        "/pricing/quote",
        json={"cost_incl_contingency": 850000, "client_type": "school", "sport_id": sport_id},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["floor_margin_percent"] == 15.0
    assert body["target_margin_percent"] == 18.0


def test_pricing_quote_sport_override_does_not_affect_an_unrelated_sport(client, director_user):
    headers = _director_headers(client, director_user)
    badminton_id = _sport_id(client, headers, "badminton")
    table_tennis_id = _sport_id(client, headers, "table_tennis")
    client.put(f"/sport-margin-policies/{badminton_id}", json={"floor_margin_percent": 15.0}, headers=headers)

    res = client.post(
        "/pricing/quote",
        json={"cost_incl_contingency": 850000, "client_type": "school", "sport_id": table_tennis_id},
        headers=headers,
    )
    body = res.json()
    assert body["floor_margin_percent"] == 18.0
    assert body["target_margin_percent"] == 21.0


# ---------------------------------------------------------------------------
# Estimate options: each option prices at its OWN effective floor (M.1)
# ---------------------------------------------------------------------------


def test_estimate_option_pricing_uses_its_own_sports_override_not_others(client, director_user):
    headers = _director_headers(client, director_user)
    badminton_id = _sport_id(client, headers, "badminton")
    client.put(f"/sport-margin-policies/{badminton_id}", json={"floor_margin_percent": 15.0}, headers=headers)

    client_id = _create_client_record(client, headers, client_type="school")
    project_id = _create_project(client, headers, client_id)
    badminton_ps_id = _add_project_sport(client, headers, project_id, "badminton")
    tt_ps_id = _add_project_sport(client, headers, project_id, "table_tennis")
    _verified_cost_sheet(client, headers, project_id, 850000 + 500000)

    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={
            "options": [
                {"project_sport_id": badminton_ps_id, "package": "standard", "cost_for_option": 850000},
                {"project_sport_id": tt_ps_id, "package": "standard", "cost_for_option": 500000},
            ]
        },
        headers=headers,
    ).json()

    by_sport = {o["project_sport_id"]: o for o in estimate["options"]}
    badminton_option = by_sport[badminton_ps_id]
    tt_option = by_sport[tt_ps_id]

    gst = 1.18
    range_pct = 0.05
    # Badminton: sport override floor 15% -> target 18% (school's +3 gap)
    badminton_selling_incl_gst = (850000 / (1 - 0.18)) * gst
    assert round(float(badminton_option["price_low"]), 2) == round(badminton_selling_incl_gst * (1 - range_pct), 2)
    assert round(float(badminton_option["price_high"]), 2) == round(badminton_selling_incl_gst * (1 + range_pct), 2)

    # Table tennis: no override -> client (school) floor 18% -> target 21%
    tt_selling_incl_gst = (500000 / (1 - 0.21)) * gst
    assert round(float(tt_option["price_low"]), 2) == round(tt_selling_incl_gst * (1 - range_pct), 2)
    assert round(float(tt_option["price_high"]), 2) == round(tt_selling_incl_gst * (1 + range_pct), 2)


def test_estimate_option_pricing_unaffected_when_no_sport_override_exists(client, director_user):
    """Regression guard: the single-sport, no-override case prices exactly
    as it did before this feature existed."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, client_type="school")
    project_id = _create_project(client, headers, client_id)
    ps_id = _add_project_sport(client, headers, project_id, "badminton")
    _verified_cost_sheet(client, headers, project_id, 850000)

    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": ps_id, "package": "standard", "cost_for_option": 850000}]},
        headers=headers,
    ).json()
    option = estimate["options"][0]

    selling_incl_gst = (850000 / (1 - 0.21)) * 1.18
    assert round(float(option["price_low"]), 2) == round(selling_incl_gst * 0.95, 2)
    assert round(float(option["price_high"]), 2) == round(selling_incl_gst * 1.05, 2)


# ---------------------------------------------------------------------------
# Quotation: multi-sport aggregate floor is a cost-weighted average (K.2)
# ---------------------------------------------------------------------------


def test_quotation_multi_sport_floor_is_cost_weighted_average_of_effective_floors(client, director_user):
    headers = _director_headers(client, director_user)
    badminton_id = _sport_id(client, headers, "badminton")
    client.put(f"/sport-margin-policies/{badminton_id}", json={"floor_margin_percent": 15.0}, headers=headers)

    client_id = _create_client_record(client, headers, client_type="school")
    project_id = _create_project(client, headers, client_id)
    badminton_ps_id = _add_project_sport(client, headers, project_id, "badminton")
    tt_ps_id = _add_project_sport(client, headers, project_id, "table_tennis")
    _verified_cost_sheet(client, headers, project_id, 850000 + 500000)

    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={
            "options": [
                {"project_sport_id": badminton_ps_id, "package": "standard", "cost_for_option": 850000},
                {"project_sport_id": tt_ps_id, "package": "standard", "cost_for_option": 500000},
            ]
        },
        headers=headers,
    ).json()

    option_ids = [o["id"] for o in estimate["options"]]
    for option_id in option_ids:
        client.patch(
            f"/estimates/{estimate['id']}/options/{option_id}/client-status",
            json={"client_status": "approved", "waive_evidence_reason": "test setup"},
            headers=headers,
        )

    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": option_ids},
        headers=headers,
    ).json()

    # Badminton (cost 850000) effective floor 15%, Table Tennis (cost
    # 500000) effective floor 18% (client default, no override):
    expected_floor = (850000 * 15.0 + 500000 * 18.0) / (850000 + 500000)
    expected_target = expected_floor + 3.0  # school is competitive_segment -> +3

    # Quotation.floor_margin_percent/target_margin_percent are Numeric(5,2)
    # columns, so the stored value is rounded to 2 dp on write.
    assert round(quotation["floor_margin_percent"], 2) == round(expected_floor, 2)
    assert round(quotation["target_margin_percent"], 2) == round(expected_target, 2)
    assert quotation["cost_total"] == 1350000.0

    expected_selling_ex_gst = 1350000 / (1 - expected_target / 100)
    assert quotation["selling_price_ex_gst"] == pytest.approx(expected_selling_ex_gst, abs=10)


def test_quotation_single_sport_with_override_matches_pricing_quote_endpoint(client, director_user):
    """Sanity cross-check: a single-sport quotation's floor/target must
    match what /pricing/quote itself computes for that sport."""
    headers = _director_headers(client, director_user)
    badminton_id = _sport_id(client, headers, "badminton")
    client.put(f"/sport-margin-policies/{badminton_id}", json={"floor_margin_percent": 15.0}, headers=headers)

    client_id = _create_client_record(client, headers, client_type="school")
    project_id = _create_project(client, headers, client_id)
    ps_id = _add_project_sport(client, headers, project_id, "badminton")
    _verified_cost_sheet(client, headers, project_id, 850000)

    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": ps_id, "package": "standard", "cost_for_option": 850000}]},
        headers=headers,
    ).json()
    option_id = estimate["options"][0]["id"]
    client.patch(
        f"/estimates/{estimate['id']}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id]},
        headers=headers,
    ).json()

    assert quotation["floor_margin_percent"] == 15.0
    assert quotation["target_margin_percent"] == 18.0
