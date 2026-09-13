"""Note R1: RateItem.gst_percent lets a line override the Master Settings
global GST rate (e.g. HSN 9506 sports-goods equipment at 5%, not 18%).
Since pricing still works off one aggregate cost figure per Estimate
option/Quotation (not itemized per-line GST), the actual mechanism under
test is the cost-weighted blend in app.api.pricing.effective_gst_rate_percent
/ cost_weighted_gst_rate_percent -- these tests prove that blend reaches
both the Estimate price range and the real Quotation gst_amount/total,
while a sport with no cost-sheet lines yet still falls back to the flat
global rate exactly as before this existed (test_documents.py's own
existing GST tests, unmodified, are the regression check for that)."""


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _create_client_record(client, headers, client_type="government", name="Municipal Corp"):
    res = client.post("/clients", json={"name": name, "type": client_type}, headers=headers)
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


def _add_project_sport(client, headers, project_id, sport_key="badminton"):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": sport_id, "building_status": "open_air"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_rate_item(client, headers, gst_percent=None, item_name="Badminton pole", hsn_sac="9506"):
    payload = {
        "category": "Equipment", "item_name": item_name, "unit": "pair",
        "hsn_sac": hsn_sac, "rate": 1000.0, "gst_percent": gst_percent,
    }
    res = client.post("/rate-items", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _cost_sheet_with_mixed_gst_lines(client, headers, project_id, project_sport_id):
    """One line at a 5%-override RateItem (cost 100,000) and one at the
    18% global default (cost 100,000) -- cost-weighted blend = 11.5%."""
    create_res = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": 200000}, headers=headers)
    assert create_res.status_code == 201, create_res.text
    cost_sheet_id = create_res.json()["id"]

    five_percent_item = _create_rate_item(client, headers, gst_percent=5.0)
    client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={
            "project_sport_id": project_sport_id, "rate_item_id": five_percent_item,
            "work_package": "accessories", "category": "Equipment", "item_name": "Badminton pole",
            "unit": "pair", "quantity": 100, "rate": 1000,
        },
        headers=headers,
    )
    eighteen_percent_item = _create_rate_item(
        client, headers, gst_percent=None, item_name="Acrylic flooring", hsn_sac="3209"
    )
    client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={
            "project_sport_id": project_sport_id, "rate_item_id": eighteen_percent_item,
            "work_package": "flooring", "category": "Flooring", "item_name": "Acrylic flooring",
            "unit": "sqft", "quantity": 1000, "rate": 100,
        },
        headers=headers,
    )

    verify_res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert verify_res.status_code == 200, verify_res.text
    return cost_sheet_id


def test_estimate_price_range_reflects_blended_gst_not_flat_eighteen_percent(client, director_user):
    """Government target margin 15% (floor 12 + 3): cost 850000 -> selling
    ex-GST 1,000,000. With the mixed-rate cost sheet, blended GST is
    (100000*5 + 100000*18) / 200000 = 11.5%, not the flat 18% these two
    lines' sport would otherwise get -- selling incl. GST = 1,115,000,
    +/-5% band = [1,059,250 , 1,170,750]."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _cost_sheet_with_mixed_gst_lines(client, headers, project_id, project_sport_id)

    res = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 850000}]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    option = res.json()["options"][0]
    assert round(option["price_low"], 2) == 1059250.00
    assert round(option["price_high"], 2) == 1170750.00


def test_quotation_gst_amount_reflects_blended_gst_not_flat_eighteen_percent(client, director_user):
    """Same blended-rate cost sheet, carried through to a real Quotation:
    gst_amount/quotation_total must be computed at 11.5%, not 18%."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _cost_sheet_with_mixed_gst_lines(client, headers, project_id, project_sport_id)

    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 850000}]},
        headers=headers,
    ).json()
    option_id = estimate["options"][0]["id"]
    client.patch(
        f"/estimates/{estimate['id']}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=headers,
    )

    res = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert round(body["selling_price_ex_gst"], 2) == 1000000.00
    assert round(body["gst_amount"], 2) == round(1000000.00 * 0.115, 2)
    assert round(body["quotation_total"], 2) == 1115000.00


def test_sport_with_no_cost_sheet_lines_still_uses_flat_global_rate(client, director_user):
    """No lines at all for this sport (matches every pre-existing test
    that never attaches lines) -- effective_gst_rate_percent must fall
    back to the flat 18% exactly as before this feature existed."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": 850000}, headers=headers)
    cost_sheet_id = client.get(f"/projects/{project_id}/cost-sheets", headers=headers).json()[0]["id"]
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)

    res = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 850000}]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    option = res.json()["options"][0]
    assert round(option["price_low"], 2) == 1121000.00
    assert round(option["price_high"], 2) == 1239000.00
