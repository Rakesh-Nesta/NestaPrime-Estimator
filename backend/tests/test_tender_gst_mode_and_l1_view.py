"""Part L 'Price basis' row: 'Inclusive/exclusive GST toggle; L1 mode
shows margin at proposed price live.' Built despite K.4's later, more
authoritative 'GST is never a per-document override' simplification, per
an explicit, informed decision to treat Tender Mode as a deliberate
carve-out (the same kind of override tender.py's own GST-TDS net-
receivable calculator already applies to a different K.1b retirement
note)."""

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
        name="Test Sales", email="sales-l1@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.SALES
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales-l1@test.local")


def _create_client_record(client, headers, client_type="government", name="L1 Municipal Corp"):
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


def _add_project_sport(client, headers, project_id, sport_key="badminton"):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports", json={"sport_id": sport_id, "building_status": "open_air"}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _quotation_setup(client, headers, client_type="government", cost=850000.0):
    """Government client -> floor 12%, target 15% (K.2's own worked
    example, reused throughout this codebase's tests)."""
    client_id = _create_client_record(client, headers, client_type=client_type)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": cost}, headers=headers
    ).json()["id"]
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost}]},
        headers=headers,
    ).json()
    option_id = estimate["options"][0]["id"]
    client.patch(
        f"/estimates/{estimate['id']}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    return project_id, estimate["id"], option_id


# ---------------------------------------------------------------------------
# GST mode (Price basis toggle)
# ---------------------------------------------------------------------------


def test_gst_mode_defaults_to_exclusive(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, estimate_id, option_id = _quotation_setup(client, headers)

    res = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["gst_mode"] == "exclusive"


def test_gst_mode_inclusive_rejected_for_a_non_tender_project(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, estimate_id, option_id = _quotation_setup(client, headers, client_type="school")

    res = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id], "gst_mode": "inclusive"},
        headers=headers,
    )
    assert res.status_code == 422
    assert "tender mode" in res.json()["detail"].lower()


def test_gst_mode_inclusive_accepted_for_a_tender_project(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, estimate_id, option_id = _quotation_setup(client, headers, client_type="government")

    res = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id], "gst_mode": "inclusive"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["gst_mode"] == "inclusive"


def test_inclusive_and_exclusive_give_the_same_total_with_no_discount(client, director_user):
    """cost 850000, target 15% -> ex-GST base 1,000,000 either way; with
    no discount the two modes only differ in bookkeeping, not in the
    final total: 1,000,000 * 1.18 = 1,180,000 both ways."""
    headers = _director_headers(client, director_user)

    project_id1, est_excl, opt_excl = _quotation_setup(client, headers)
    excl = client.post(
        f"/projects/{project_id1}/quotations", json={"estimate_id": est_excl, "included_option_ids": [opt_excl]}, headers=headers
    ).json()

    project_id2, est_incl, opt_incl = _quotation_setup(client, headers)
    incl = client.post(
        f"/projects/{project_id2}/quotations",
        json={"estimate_id": est_incl, "included_option_ids": [opt_incl], "gst_mode": "inclusive"},
        headers=headers,
    ).json()

    assert round(excl["quotation_total"], 2) == round(incl["quotation_total"], 2) == 1180000.0
    assert round(excl["margin_percent"], 2) == round(incl["margin_percent"], 2) == 15.0


def test_inclusive_and_exclusive_diverge_with_a_flat_discount_amount(client, director_user):
    """A flat Rs discount taken off the inclusive figure vs. the ex-GST
    figure produces genuinely different totals and margins -- this is
    the actual behavioural difference the toggle is for.
    EXCLUSIVE: 1,000,000 - 50,000 = 950,000 ex-GST -> total 1,121,000,
      margin (950,000-850,000)/950,000 = 10.5263...%.
    INCLUSIVE: 1,180,000 - 50,000 = 1,130,000 total -> ex-GST base
      1,130,000/1.18 = 957,627.1186..., margin
      (957,627.1186-850,000)/957,627.1186 = 11.2378...%."""
    headers = _director_headers(client, director_user)

    project_id, estimate_id, option_id = _quotation_setup(client, headers)
    excl = client.post(
        f"/projects/{project_id}/quotations",
        json={
            "estimate_id": estimate_id, "included_option_ids": [option_id],
            "discount_type": "amount", "discount_value": 50000,
        },
        headers=headers,
    ).json()
    assert round(excl["quotation_total"], 2) == 1121000.0
    # margin_percent is stored Numeric(6,2) -- compare at that precision.
    assert excl["margin_percent"] == round(10.526315789473685, 2)

    project_id2, estimate_id2, option_id2 = _quotation_setup(client, headers)
    incl = client.post(
        f"/projects/{project_id2}/quotations",
        json={
            "estimate_id": estimate_id2, "included_option_ids": [option_id2],
            "discount_type": "amount", "discount_value": 50000, "gst_mode": "inclusive",
        },
        headers=headers,
    ).json()
    assert round(incl["quotation_total"], 2) == 1130000.0
    assert incl["margin_percent"] == round(11.237769328763523, 2)


def test_revise_quotation_can_switch_gst_mode(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, estimate_id, option_id = _quotation_setup(client, headers)
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    client.post(f"/quotations/{quotation['id']}/release", headers=headers)

    res = client.post(
        f"/quotations/{quotation['id']}/revise",
        json={"included_option_ids": [option_id], "gst_mode": "inclusive"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["gst_mode"] == "inclusive"


def test_revise_quotation_rejects_inclusive_for_a_private_client(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, estimate_id, option_id = _quotation_setup(client, headers, client_type="school")
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    client.post(f"/quotations/{quotation['id']}/release", headers=headers)

    res = client.post(
        f"/quotations/{quotation['id']}/revise",
        json={"included_option_ids": [option_id], "gst_mode": "inclusive"},
        headers=headers,
    )
    assert res.status_code == 422


def test_pricing_quote_calculator_supports_gst_mode_inclusive(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/pricing/quote",
        json={
            "cost_incl_contingency": 850000, "client_type": "government",
            "discount_type": "amount", "discount_value": 50000, "gst_mode": "inclusive",
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert round(res.json()["quotation_total"], 2) == 1130000.0
    assert res.json()["gst_mode"] == "inclusive"


# ---------------------------------------------------------------------------
# Live L1 view
# ---------------------------------------------------------------------------


def _tender_quotation(client, headers, discount_amount=0.0):
    project_id, estimate_id, option_id = _quotation_setup(client, headers)
    client.post(
        f"/projects/{project_id}/tender-details",
        json={"retention_percent": 7.5, "performance_bg_percent": 4.0, "dlp_months": 12},
        headers=headers,
    )
    payload = {"estimate_id": estimate_id, "included_option_ids": [option_id]}
    if discount_amount:
        payload["discount_type"] = "amount"
        payload["discount_value"] = discount_amount
    quotation = client.post(f"/projects/{project_id}/quotations", json=payload, headers=headers).json()
    return project_id, quotation


def test_l1_view_rejected_for_a_non_tender_quotation(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, estimate_id, option_id = _quotation_setup(client, headers, client_type="school")
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id]},
        headers=headers,
    ).json()

    res = client.get(f"/quotations/{quotation['id']}/l1-view", headers=headers)
    assert res.status_code == 400


def test_l1_view_with_no_competitor_bids_has_no_rank_or_l1_verdict(client, director_user):
    headers = _director_headers(client, director_user)
    _, quotation = _tender_quotation(client, headers)

    res = client.get(f"/quotations/{quotation['id']}/l1-view", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["our_price"] == quotation["quotation_total"]
    assert body["competitor_bids"] == []
    assert body["lowest_competitor_amount"] is None
    assert body["is_l1"] is None
    assert body["rank"] is None


def test_l1_view_reports_l1_when_our_price_is_lowest(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, quotation = _tender_quotation(client, headers)

    client.post(
        f"/projects/{project_id}/tender-details/competitor-bids",
        json={"bidder_name": "Rival Co", "amount": quotation["quotation_total"] + 50000},
        headers=headers,
    )

    res = client.get(f"/quotations/{quotation['id']}/l1-view", headers=headers)
    body = res.json()
    assert body["is_l1"] is True
    assert body["rank"] == 1
    assert body["lowest_competitor_amount"] == quotation["quotation_total"] + 50000
    assert body["margin_percent"] == quotation["margin_percent"]


def test_l1_view_reports_not_l1_and_correct_rank_when_beaten(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, quotation = _tender_quotation(client, headers)
    our_price = quotation["quotation_total"]

    client.post(
        f"/projects/{project_id}/tender-details/competitor-bids",
        json={"bidder_name": "Cheaper Co", "amount": our_price - 10000},
        headers=headers,
    )
    client.post(
        f"/projects/{project_id}/tender-details/competitor-bids",
        json={"bidder_name": "Pricier Co", "amount": our_price + 10000},
        headers=headers,
    )

    res = client.get(f"/quotations/{quotation['id']}/l1-view", headers=headers)
    body = res.json()
    assert body["is_l1"] is False
    assert body["rank"] == 2  # one competitor bid below ours
    assert body["lowest_competitor_amount"] == our_price - 10000
    assert len(body["competitor_bids"]) == 2


def test_l1_view_is_live_and_reflects_a_revised_price(client, director_user):
    """A revision that lowers quotation_total below a previously-losing
    competitor bid should flip is_l1 to True on the very next read --
    'live' means recomputed each call, not a stored snapshot."""
    headers = _director_headers(client, director_user)
    project_id, estimate_id, option_id = _quotation_setup(client, headers)
    client.post(
        f"/projects/{project_id}/tender-details",
        json={"retention_percent": 7.5, "performance_bg_percent": 4.0, "dlp_months": 12},
        headers=headers,
    )
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    client.post(
        f"/projects/{project_id}/tender-details/competitor-bids",
        json={"bidder_name": "Rival Co", "amount": quotation["quotation_total"] - 1000},
        headers=headers,
    )
    before = client.get(f"/quotations/{quotation['id']}/l1-view", headers=headers).json()
    assert before["is_l1"] is False

    client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    client.post(
        f"/quotations/{quotation['id']}/revise",
        json={
            "included_option_ids": [option_id],
            "discount_type": "amount", "discount_value": 5000, "refresh_pricing": True,
        },
        headers=headers,
    )
    after = client.get(f"/quotations/{quotation['id']}/l1-view", headers=headers).json()
    assert after["is_l1"] is True
    assert after["our_price"] < before["our_price"]


def test_sales_sees_masked_margin_in_l1_view(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    _, quotation = _tender_quotation(client, headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.get(f"/quotations/{quotation['id']}/l1-view", headers=sales_headers)
    assert res.status_code == 200, res.text
    assert res.json()["margin_percent"] is None
    assert res.json()["our_price"] == quotation["quotation_total"]  # price itself is not cost-side


def test_add_list_and_delete_competitor_bids(client, director_user):
    headers = _director_headers(client, director_user)
    project_id, quotation = _tender_quotation(client, headers)

    create_res = client.post(
        f"/projects/{project_id}/tender-details/competitor-bids",
        json={"bidder_name": "Rival Co", "amount": 999000},
        headers=headers,
    )
    assert create_res.status_code == 201, create_res.text
    bid_id = create_res.json()["id"]

    listed = client.get(f"/projects/{project_id}/tender-details/competitor-bids", headers=headers).json()
    assert len(listed) == 1
    assert listed[0]["bidder_name"] == "Rival Co"

    delete_res = client.delete(f"/projects/{project_id}/tender-details/competitor-bids/{bid_id}", headers=headers)
    assert delete_res.status_code == 204

    assert client.get(f"/projects/{project_id}/tender-details/competitor-bids", headers=headers).json() == []


def test_competitor_bids_require_tender_details_to_exist(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)

    res = client.post(
        f"/projects/{project_id}/tender-details/competitor-bids",
        json={"bidder_name": "Rival Co", "amount": 100000},
        headers=headers,
    )
    assert res.status_code == 404


def test_sales_cannot_manage_competitor_bids(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    project_id, _quotation = _tender_quotation(client, headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/projects/{project_id}/tender-details/competitor-bids",
        json={"bidder_name": "Rival Co", "amount": 100000},
        headers=sales_headers,
    )
    assert res.status_code == 403
