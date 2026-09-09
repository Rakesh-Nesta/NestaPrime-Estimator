from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _pm_headers(client, db_session):
    user = User(name="Test PM", email="pm@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.PM)
    db_session.add(user)
    db_session.commit()
    return _login(client, "pm@test.local")


def _create_client_record(client, headers):
    res = client.post("/clients", json={"name": "Activity Rate Client", "type": "school"}, headers=headers)
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


def _empty_draft_cost_sheet(client, headers):
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    res = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers)
    assert res.status_code == 201, res.text
    return project_id, res.json()["id"]


def _labour_category_id(client, headers, key):
    categories = client.get("/labour-categories", headers=headers).json()
    return next(c["id"] for c in categories if c["key"] == key)


def _add_line(client, headers, cost_sheet_id, **overrides):
    fields = {
        "work_package": "structure",
        "category": "MS structure",
        "item_name": "SHS 3x3",
        "unit": "kg",
        "quantity": 100,
        "rate": 68,
    }
    fields.update(overrides)
    res = client.post(f"/cost-sheets/{cost_sheet_id}/lines", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------------------
# J.2: activity rate first, category % as fallback
# ---------------------------------------------------------------------------


def test_with_no_activity_rate_configured_the_percent_fallback_still_applies(client, director_user):
    """Regression guard: before any Director configures a real activity
    rate, behaviour must be identical to the pre-J.2 % fallback."""
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _empty_draft_cost_sheet(client, headers)
    _add_line(client, headers, cost_sheet_id, quantity=100, rate=68)  # ms_fabrication_erection via blended fallback

    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    # material 6800, blended fallback 22% labour = 1496, base 8296,
    # site estab 6% -> 8793.76, warranty reserve 1% -> 8881.6976,
    # overhead recovery 10% -> 9769.86736, contingency (structure) 5% -> 10258.36
    assert round(res.json()["cost_total"], 2) == 10258.36


def test_activity_rate_missing_warning_for_named_category(client, director_user):
    """J.2: 'the Cost Sheet shows a warning line "Activity rate missing
    for [category] -- using fallback X%".'"""
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _empty_draft_cost_sheet(client, headers)
    ms_category_id = _labour_category_id(client, headers, "ms_fabrication_erection")
    _add_line(client, headers, cost_sheet_id, labour_category_id=ms_category_id)

    warnings = client.get(f"/cost-sheets/{cost_sheet_id}/labour-warnings", headers=headers).json()
    assert len(warnings) == 1
    assert "MS fabrication & erection" in warnings[0]
    assert "22%" in warnings[0]


def test_configuring_an_activity_rate_removes_the_warning_and_changes_the_total(client, director_user):
    """The core proof: a real Rs/kg activity rate, once configured, is
    actually used instead of the % fallback -- not just displayed."""
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _empty_draft_cost_sheet(client, headers)
    ms_category_id = _labour_category_id(client, headers, "ms_fabrication_erection")
    _add_line(client, headers, cost_sheet_id, labour_category_id=ms_category_id, quantity=100, rate=68)

    baseline = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    assert round(baseline["cost_total"], 2) == 10258.36  # % fallback path

    client.post(
        "/settings",
        json={"key": "activity_rate_ms_per_kg", "value": "25.0", "reason": "director sets real MS labour rate"},
        headers=headers,
    )

    warnings = client.get(f"/cost-sheets/{cost_sheet_id}/labour-warnings", headers=headers).json()
    assert warnings == []

    updated = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    # material 6800, labour = 100kg x Rs25/kg = 2500, base 9300,
    # site estab 6% -> 9858, warranty reserve 1% -> 9956.58, overhead
    # recovery 10% -> 10952.238, contingency 5% -> 11499.85
    material = 100 * 68
    labour = 100 * 25.0
    base = material + labour
    expected = base * 1.06 * 1.01 * 1.10 * 1.05
    assert round(updated["cost_total"], 2) == round(expected, 2)
    assert round(updated["cost_total"], 2) != round(baseline["cost_total"], 2)


def test_activity_rate_only_applies_when_the_units_match(client, director_user):
    """A line categorised as ms_fabrication_erection but priced in a unit
    other than kg (e.g. a lump-sum line) must not pick up the Rs/kg rate --
    it stays on the % fallback and still warns."""
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _empty_draft_cost_sheet(client, headers)
    ms_category_id = _labour_category_id(client, headers, "ms_fabrication_erection")
    client.post(
        "/settings",
        json={"key": "activity_rate_ms_per_kg", "value": "25.0", "reason": "test"},
        headers=headers,
    )
    _add_line(
        client, headers, cost_sheet_id,
        labour_category_id=ms_category_id, unit="lot", quantity=1, rate=50000,
    )

    warnings = client.get(f"/cost-sheets/{cost_sheet_id}/labour-warnings", headers=headers).json()
    assert len(warnings) == 1  # still warns -- the kg-based rate doesn't apply to a "lot" line


def test_netting_and_pool_mep_never_warn(client, director_user):
    """J.2's own table gives no activity-rate alternative for netting or
    pool_mep -- they're always the % fallback, by design, no warning."""
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _empty_draft_cost_sheet(client, headers)
    netting_category_id = _labour_category_id(client, headers, "netting")
    _add_line(
        client, headers, cost_sheet_id,
        category="Netting", item_name="N2 netting", unit="sqm", quantity=50, rate=45,
        labour_category_id=netting_category_id,
    )

    warnings = client.get(f"/cost-sheets/{cost_sheet_id}/labour-warnings", headers=headers).json()
    assert warnings == []


# ---------------------------------------------------------------------------
# J.2: ">3 categories lacking activity rates requires Director confirmation"
# ---------------------------------------------------------------------------


def test_pm_cannot_verify_with_more_than_three_categories_missing_rates(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _empty_draft_cost_sheet(client, headers)

    for key, unit in [
        ("ms_fabrication_erection", "kg"),
        ("civil_base_site_prep", "cum"),
        ("turf_laying", "sqm"),
        ("wooden_flooring", "sqft"),
    ]:
        category_id = _labour_category_id(client, headers, key)
        _add_line(
            client, headers, cost_sheet_id,
            category=key, item_name=key, unit=unit, quantity=10, rate=100,
            labour_category_id=category_id,
        )
    client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)

    pm_headers = _pm_headers(client, db_session)
    pm_attempt = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=pm_headers)
    assert pm_attempt.status_code == 403
    assert "Director confirmation" in pm_attempt.json()["detail"]

    director_attempt = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert director_attempt.status_code == 200


def test_pm_can_verify_once_enough_categories_have_configured_rates(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _empty_draft_cost_sheet(client, headers)

    for key, unit in [
        ("ms_fabrication_erection", "kg"),
        ("civil_base_site_prep", "cum"),
        ("turf_laying", "sqm"),
        ("wooden_flooring", "sqft"),
    ]:
        category_id = _labour_category_id(client, headers, key)
        _add_line(
            client, headers, cost_sheet_id,
            category=key, item_name=key, unit=unit, quantity=10, rate=100,
            labour_category_id=category_id,
        )

    # Configure real rates for 2 of the 4 -- only 2 remain missing (<=3), so a PM may verify.
    client.post("/settings", json={"key": "activity_rate_ms_per_kg", "value": "25.0"}, headers=headers)
    client.post("/settings", json={"key": "activity_rate_concrete_per_cum", "value": "500.0"}, headers=headers)
    client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)

    pm_headers = _pm_headers(client, db_session)
    pm_attempt = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=pm_headers)
    assert pm_attempt.status_code == 200, pm_attempt.text
