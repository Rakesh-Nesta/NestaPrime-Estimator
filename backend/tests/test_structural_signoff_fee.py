def _login(client, director_user):
    res = client.post("/auth/login", data={"username": "director@test.local", "password": "TestPass!1"})
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _create_client_record(client, headers, client_type="school", name="Signoff Fee Client"):
    res = client.post("/clients", json={"name": name, "type": client_type}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id, **overrides):
    fields = {
        "client_id": client_id, "city": "Bengaluru", "site_condition": "level", "soil_type": "normal",
        "building_status": "open_air", "site_access": "good", "power_available": "yes",
        "water_available": True, "package": "standard",
        **overrides,
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _sport_id(client, headers, key):
    res = client.get("/sports", headers=headers)
    return next(s["id"] for s in res.json() if s["key"] == key)


def _add_sport(client, headers, project_id, sport_key, building_status="open_air"):
    sport_id = _sport_id(client, headers, sport_key)
    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": sport_id, "building_status": building_status},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_cost_sheet(client, headers, project_id, **payload):
    res = client.post(f"/projects/{project_id}/cost-sheets", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _lines(client, headers, cost_sheet_id):
    res = client.get(f"/cost-sheets/{cost_sheet_id}/lines", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _signoff_line(client, headers, cost_sheet_id):
    lines = _lines(client, headers, cost_sheet_id)
    return next((l for l in lines if l["item_name"] == "Structural engineer design & sign-off"), None)


# ---------------------------------------------------------------------------
# No sign-off required -- no line added
# ---------------------------------------------------------------------------


def test_no_line_added_when_signoff_not_required(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id, building_status="covered_shed")
    _add_sport(client, headers, project_id, "badminton", building_status="covered_shed")

    cost_sheet_id = _create_cost_sheet(client, headers, project_id)
    assert _signoff_line(client, headers, cost_sheet_id) is None


def test_no_line_added_when_project_has_no_sports_yet(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)

    cost_sheet_id = _create_cost_sheet(client, headers, project_id)
    assert _signoff_line(client, headers, cost_sheet_id) is None


# ---------------------------------------------------------------------------
# Tier 1: simple (Rs 15,000 default)
# ---------------------------------------------------------------------------


def test_simple_tier_for_black_cotton_soil(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id, soil_type="black_cotton", building_status="covered_shed")
    _add_sport(client, headers, project_id, "badminton", building_status="covered_shed")

    cost_sheet_id = _create_cost_sheet(client, headers, project_id)
    line = _signoff_line(client, headers, cost_sheet_id)
    assert line is not None
    assert line["rate"] == 15000.0
    assert line["quantity"] == 1.0
    assert line["amount"] == 15000.0
    assert line["work_package"] == "structure"
    assert line["source"] == "manual"


# ---------------------------------------------------------------------------
# Tier 2: PEB / Padel / pool (Rs 35,000 default)
# ---------------------------------------------------------------------------


def test_peb_padel_pool_tier(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id, building_status="new_peb_building")
    _add_sport(client, headers, project_id, "badminton", building_status="new_peb_building")

    cost_sheet_id = _create_cost_sheet(client, headers, project_id)
    line = _signoff_line(client, headers, cost_sheet_id)
    assert line is not None
    assert line["rate"] == 35000.0


def test_pool_tier(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    _add_sport(client, headers, project_id, "swimming_pool_25m")

    cost_sheet_id = _create_cost_sheet(client, headers, project_id)
    line = _signoff_line(client, headers, cost_sheet_id)
    assert line is not None
    assert line["rate"] == 35000.0


# ---------------------------------------------------------------------------
# Tier 3: multi-court or government (Rs 50,000 default)
# ---------------------------------------------------------------------------


def test_government_client_tier(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client_record(client, headers, client_type="government", name="Municipal Corp")
    project_id = _create_project(client, headers, client_id, building_status="covered_shed")
    _add_sport(client, headers, project_id, "badminton", building_status="covered_shed")

    cost_sheet_id = _create_cost_sheet(client, headers, project_id)
    line = _signoff_line(client, headers, cost_sheet_id)
    assert line is not None
    assert line["rate"] == 50000.0


def test_multi_court_tier(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(
        client, headers, client_id, soil_type="black_cotton", building_status="covered_shed", number_of_courts=3
    )
    _add_sport(client, headers, project_id, "badminton", building_status="covered_shed")

    cost_sheet_id = _create_cost_sheet(client, headers, project_id)
    line = _signoff_line(client, headers, cost_sheet_id)
    assert line is not None
    assert line["rate"] == 50000.0


def test_government_peb_project_gets_the_higher_tier_not_peb_tier(client, director_user):
    """Ties are broken toward the higher fee -- never under-estimate."""
    headers = _login(client, director_user)
    client_id = _create_client_record(client, headers, client_type="government", name="Municipal Sports Complex")
    project_id = _create_project(client, headers, client_id, building_status="new_peb_building")
    _add_sport(client, headers, project_id, "badminton", building_status="new_peb_building")

    cost_sheet_id = _create_cost_sheet(client, headers, project_id)
    line = _signoff_line(client, headers, cost_sheet_id)
    assert line is not None
    assert line["rate"] == 50000.0


# ---------------------------------------------------------------------------
# Master Setting overrides the default; PM can reprice with the real quote
# ---------------------------------------------------------------------------


def test_director_set_master_setting_overrides_the_default(client, director_user):
    headers = _login(client, director_user)
    client.post(
        "/settings", json={"key": "structural_signoff_fee_simple_rs", "value": "22000"}, headers=headers
    )
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id, soil_type="black_cotton", building_status="covered_shed")
    _add_sport(client, headers, project_id, "badminton", building_status="covered_shed")

    cost_sheet_id = _create_cost_sheet(client, headers, project_id)
    line = _signoff_line(client, headers, cost_sheet_id)
    assert line["rate"] == 22000.0


def test_pm_can_reprice_the_line_with_the_engineers_actual_quote(client, director_user):
    """Q.1: 'PM overrides on the Cost Sheet with engineer's actual quote.'"""
    headers = _login(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id, soil_type="black_cotton", building_status="covered_shed")
    _add_sport(client, headers, project_id, "badminton", building_status="covered_shed")
    cost_sheet_id = _create_cost_sheet(client, headers, project_id)
    line = _signoff_line(client, headers, cost_sheet_id)

    res = client.patch(
        f"/cost-sheets/{cost_sheet_id}/lines/{line['id']}", json={"rate": 18500}, headers=headers
    )
    assert res.status_code == 200, res.text
    assert res.json()["rate"] == 18500.0


def test_signoff_fee_is_included_in_recompute(client, director_user):
    headers = _login(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id, soil_type="black_cotton", building_status="covered_shed")
    _add_sport(client, headers, project_id, "badminton", building_status="covered_shed")
    cost_sheet_id = _create_cost_sheet(client, headers, project_id)

    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["cost_total"] > 0
