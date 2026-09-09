"""End-to-end integration tests for Tender Mode (Part L), chaining every
piece built across the whole Tender Mode effort into single, realistic
scenarios: auto-triggered tender_mode (B.2), TenderDetails, the technical
bid checklist, K.1 step 4A cost overheads (DLP reserve, BOCW cess, tender
fee, performance-BG cost) driven by REAL CostSheetLine rows (not a flat
cost_total, unlike most other test files), margin floor by sport type
(K.2) composing with Tender Mode's own cost engine, the BOQ-format
Quotation PDF, the M.3 Formal-evidence-for-Government gate, and Work
Order + payment reconciliation post-award. Each isolated piece already
has its own unit tests elsewhere (test_tender.py, test_tender_overheads.py,
test_work_orders.py, test_margin_floor_by_sport.py) -- this file exists
to catch bugs that only show up when they all run together on one
project, which none of those files individually can."""

import io

from pypdf import PdfReader


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _create_client_record(client, headers, client_type="government", name="Integration Municipal Corp"):
    res = client.post("/clients", json={"name": name, "type": client_type}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id, **overrides):
    fields = {
        # Bengaluru is seeded at neutral 1.0/1.0/1.0 regional multipliers --
        # this file's end-to-end total isn't about regional pricing, so a
        # non-neutral city (e.g. Mumbai) would silently distort it.
        "client_id": client_id, "city": "Bengaluru", "site_condition": "level", "soil_type": "normal",
        "building_status": "open_air", "site_access": "good", "power_available": "yes",
        "water_available": True, "package": "standard",
        **overrides,
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _sport_id(client, headers, sport_key):
    return next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)


def _add_project_sport(client, headers, project_id, sport_key="badminton"):
    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": _sport_id(client, headers, sport_key), "building_status": "open_air"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _empty_draft_cost_sheet(client, headers, project_id):
    res = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers)
    assert res.status_code == 201, res.text
    cost_sheet_id = res.json()["id"]
    # E.5: every project in this file is a Government client (tender_mode
    # auto-on), which always auto-adds a "Structural engineer design &
    # sign-off" line -- removed so these formula-precision tests see only
    # the lines they add themselves.
    for line in client.get(f"/cost-sheets/{cost_sheet_id}/lines", headers=headers).json():
        client.delete(f"/cost-sheets/{cost_sheet_id}/lines/{line['id']}", headers=headers)
    return cost_sheet_id


def _upload_evidence(client, headers, doc_type, doc_id, strength="informal"):
    res = client.post(
        "/attachments",
        data={"doc_type": doc_type, "doc_id": doc_id, "tag": "approval_evidence", "approval_strength": strength},
        files={"file": ("evidence.png", b"screenshot bytes", "image/png")},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def _pdf_text(response) -> str:
    reader = PdfReader(io.BytesIO(response.content))
    return "\n".join(page.extract_text() for page in reader.pages)


# ---------------------------------------------------------------------------
# Scenario 1: single-sport project through the FULL Tender Mode chain --
# real CostSheetLine rows -> K.1 4A overheads -> Formal evidence -> Won ->
# Work Order -> payment reconciliation -> checklist, all on one project.
# ---------------------------------------------------------------------------


def test_full_tender_mode_lifecycle_end_to_end(client, director_user):
    headers = _director_headers(client, director_user)

    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project = client.get(f"/projects/{project_id}", headers=headers).json()
    assert project["tender_mode"] is True  # B.2 auto-trigger

    # Part L tracking fields.
    tender_details = client.post(
        f"/projects/{project_id}/tender-details",
        json={
            "emd_amount": 50000, "emd_validity_date": "2026-12-31",
            "retention_percent": 7.5, "performance_bg_percent": 4.0, "dlp_months": 12,
            "bid_due_date": "2026-10-15",
        },
        headers=headers,
    )
    assert tender_details.status_code == 201, tender_details.text

    # Technical bid checklist: seed + confirm all five items.
    checklist = client.get(f"/projects/{project_id}/technical-bid-checklist", headers=headers).json()
    assert {i["key"] for i in checklist} == {"gst", "pan", "turnover", "past_work_certificates", "iso"}
    for item in checklist:
        res = client.patch(
            f"/projects/{project_id}/technical-bid-checklist/{item['key']}", json={"confirmed": True}, headers=headers
        )
        assert res.status_code == 200

    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = _empty_draft_cost_sheet(client, headers, project_id)

    # A real structure line (K.1 steps 1-2): 200 kg x Rs 70 = 14000 material.
    client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={"work_package": "structure", "category": "MS structure", "item_name": "SHS 3x3", "unit": "kg", "quantity": 200, "rate": 70},
        headers=headers,
    )
    # K.1 step 4A: tender fee + performance-BG cost, both PM-entered lines.
    overheads_res = client.post(
        f"/cost-sheets/{cost_sheet_id}/tender-overheads",
        json={
            "tender_fee": 5000,
            "bg_amount": 500000, "bank_charge_percent_pa": 1.5, "contract_weeks": 26, "dlp_months": 12,
        },
        headers=headers,
    )
    assert overheads_res.status_code == 201, overheads_res.text
    assert overheads_res.json()["bg_contract_months"] == 7
    assert len(overheads_res.json()["lines"]) == 2

    recomputed = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers).json()
    # Structure line: 14000 * 1.22 (blended labour) * 1.06 (site estab) *
    # 1.01 (DLP reserve) * 1.10 (overhead) = 20009.85..., no cess (well
    # under Rs 10 L), * 1.05 (structure contingency) = 21010.34.
    structure_total = 200 * 70 * 1.22 * 1.06 * 1.01 * 1.10 * 1.05
    # Tender-overheads lines land in "services" (blended 22% labour,
    # services contingency default 0%): (5000 + 11875) * 1.22 * 1.06 * 1.01 * 1.10
    overheads_total = (5000 + 11875) * 1.22 * 1.06 * 1.01 * 1.10
    expected_total = structure_total + overheads_total
    assert round(recomputed["cost_total"], 2) == round(expected_total, 2)

    k1_constants = {c["key"]: c for c in client.get(f"/cost-sheets/{cost_sheet_id}/k1-constants", headers=headers).json()}
    assert k1_constants["dlp_reserve_percent"]["master_value"] == 1.0
    assert k1_constants["bocw_cess_percent"]["master_value"] == 1.0
    assert "warranty_reserve_percent" not in k1_constants

    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)

    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": recomputed["cost_total"]}]},
        headers=headers,
    ).json()
    option_id = estimate["options"][0]["id"]
    # M.3 only requires FORMAL specifically at Won (below); approving an
    # Estimate option just needs any approval_evidence attachment -- using
    # a real one here (rather than always waiving) for a more realistic
    # end-to-end chain.
    _upload_evidence(client, headers, "estimate", estimate["id"], strength="formal")
    approve_res = client.patch(
        f"/estimates/{estimate['id']}/options/{option_id}/client-status",
        json={"client_status": "approved"},
        headers=headers,
    )
    assert approve_res.status_code == 200, approve_res.text

    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    # K.2 worked example: government floor 12%, competitive -> target 15%.
    assert quotation["floor_margin_percent"] == 12.0
    assert quotation["target_margin_percent"] == 15.0

    client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    client.post(f"/quotations/{quotation['id']}/send", headers=headers)

    # Informal evidence alone must NOT be enough for a Tender Mode Won.
    _upload_evidence(client, headers, "quotation", quotation["id"], strength="informal")
    informal_attempt = client.post(f"/quotations/{quotation['id']}/mark-won", json={}, headers=headers)
    assert informal_attempt.status_code == 422

    _upload_evidence(client, headers, "quotation", quotation["id"], strength="formal")
    won_res = client.post(
        f"/quotations/{quotation['id']}/mark-won", json={"reason": "L1 bidder"}, headers=headers
    )
    assert won_res.status_code == 200, won_res.text
    quotation = won_res.json()
    assert quotation["status"] == "won"

    # Financial bid PDF = the same Quotation record, BOQ-format for Tender Mode.
    pdf_res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert pdf_res.status_code == 200
    text = _pdf_text(pdf_res)
    assert "FINANCIAL BID (Tender Mode)" in text
    assert "Bill of Quantities (BOQ)" in text
    assert "DLP (defect-liability period) reserve of 1%" in text
    from app.pdf_utils import format_inr

    assert format_inr(quotation["cost_total"]) not in text  # K.3: cost never leaks

    # Post-award: Work Order & Actuals.
    work_order = client.post(f"/quotations/{quotation['id']}/work-order", headers=headers).json()
    assert work_order["status"] == "awarded"

    advance = client.post(
        f"/work-orders/{work_order['id']}/payment-entries",
        json={"milestone_name": "Advance", "amount_received": quotation["quotation_total"] * 0.4, "received_date": "2026-09-15"},
        headers=headers,
    )
    assert advance.status_code == 201, advance.text
    client.post(
        f"/work-orders/{work_order['id']}/payment-entries",
        json={"milestone_name": "Handover", "amount_received": quotation["quotation_total"] * 0.6, "received_date": "2026-10-15"},
        headers=headers,
    )
    entries = client.get(f"/work-orders/{work_order['id']}/payment-entries", headers=headers).json()
    total_received = sum(e["amount_received"] for e in entries)
    assert round(total_received, 2) == round(quotation["quotation_total"], 2)

    client.patch(f"/work-orders/{work_order['id']}", json={"status": "in_progress"}, headers=headers)
    completed = client.patch(f"/work-orders/{work_order['id']}", json={"status": "completed"}, headers=headers)
    assert completed.json()["status"] == "completed"

    # The checklist confirmed earlier must be untouched by everything since.
    final_checklist = client.get(f"/projects/{project_id}/technical-bid-checklist", headers=headers).json()
    assert all(i["confirmed"] for i in final_checklist)


# ---------------------------------------------------------------------------
# Scenario 2: multi-sport Tender Mode quotation composing K.2's margin
# floor by sport (a Director-set sport override) with Tender Mode's own
# BOQ export -- two features built independently, never exercised together.
# ---------------------------------------------------------------------------


def test_multi_sport_tender_mode_quotation_with_sport_margin_override(client, director_user):
    headers = _director_headers(client, director_user)
    badminton_id = _sport_id(client, headers, "badminton")
    # K.2: Director-defined sport floor override replaces the client
    # floor for badminton only; table_tennis keeps the government default.
    override_res = client.put(f"/sport-margin-policies/{badminton_id}", json={"floor_margin_percent": 8.0}, headers=headers)
    assert override_res.status_code == 200, override_res.text

    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    badminton_ps_id = _add_project_sport(client, headers, project_id, "badminton")
    tt_ps_id = _add_project_sport(client, headers, project_id, "table_tennis")

    cost_sheet_id = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": 850000 + 500000}, headers=headers
    ).json()["id"]
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)

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
    by_sport_id = {o["project_sport_id"]: o for o in estimate["options"]}

    # Badminton: override floor 8% -> target 11% (government's +3 gap).
    # Table tennis: client default floor 12% -> target 15%.
    gst = 1.18
    badminton_selling = (850000 / (1 - 0.11)) * gst
    assert round(float(by_sport_id[badminton_ps_id]["price_low"]), 2) == round(badminton_selling * 0.95, 2)
    tt_selling = (500000 / (1 - 0.15)) * gst
    assert round(float(by_sport_id[tt_ps_id]["price_low"]), 2) == round(tt_selling * 0.95, 2)

    option_ids = [o["id"] for o in estimate["options"]]
    for option_id in option_ids:
        client.patch(
            f"/estimates/{estimate['id']}/options/{option_id}/client-status",
            json={"client_status": "approved", "waive_evidence_reason": "integration test setup"},
            headers=headers,
        )

    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": option_ids},
        headers=headers,
    ).json()

    # K.2 multi-sport rule: floor = cost-weighted average of each sport's
    # own effective floor.
    expected_floor = (850000 * 8.0 + 500000 * 12.0) / (850000 + 500000)
    expected_target = expected_floor + 3.0
    assert round(quotation["floor_margin_percent"], 2) == round(expected_floor, 2)
    assert round(quotation["target_margin_percent"], 2) == round(expected_target, 2)

    client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    client.post(f"/quotations/{quotation['id']}/send", headers=headers)
    pdf_res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert pdf_res.status_code == 200
    text = _pdf_text(pdf_res)
    assert "Bill of Quantities (BOQ)" in text
    assert "Badminton (Standard)" in text
    assert "Table Tennis (Standard)" in text


def test_work_order_cannot_be_created_before_release_and_send_even_if_evidence_exists(client, director_user):
    """Regression guard for the full chain: Work Order creation must stay
    gated on the Quotation actually reaching Won, not merely having
    approval evidence attached (evidence and status are separate gates)."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": 850000}, headers=headers
    ).json()["id"]
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 850000}]},
        headers=headers,
    ).json()
    option_id = estimate["options"][0]["id"]
    client.patch(
        f"/estimates/{estimate['id']}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "integration test setup"},
        headers=headers,
    )
    quotation_id = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id]},
        headers=headers,
    ).json()["id"]
    _upload_evidence(client, headers, "quotation", quotation_id, strength="formal")

    # Evidence exists, but the quotation is still Draft -- no Work Order yet.
    res = client.post(f"/quotations/{quotation_id}/work-order", headers=headers)
    assert res.status_code == 400

    client.post(f"/quotations/{quotation_id}/release", headers=headers)
    res = client.post(f"/quotations/{quotation_id}/work-order", headers=headers)
    assert res.status_code == 400  # released, not sent+won yet

    client.post(f"/quotations/{quotation_id}/send", headers=headers)
    res = client.post(f"/quotations/{quotation_id}/work-order", headers=headers)
    assert res.status_code == 400  # sent, not won yet

    client.post(f"/quotations/{quotation_id}/mark-won", json={}, headers=headers)
    res = client.post(f"/quotations/{quotation_id}/work-order", headers=headers)
    assert res.status_code == 201, res.text
