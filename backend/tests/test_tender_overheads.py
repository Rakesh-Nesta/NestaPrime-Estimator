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


def _create_client_record(client, headers, client_type="government", name="Municipal Corp"):
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


def _draft_cost_sheet(client, headers, project_id=None, client_type="government"):
    if project_id is None:
        client_id = _create_client_record(client, headers, client_type=client_type)
        project_id = _create_project(client, headers, client_id)
    res = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers)
    assert res.status_code == 201, res.text
    return project_id, res.json()["id"]


def _add_structure_line(client, headers, cost_sheet_id, quantity=100, rate=68):
    return client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={
            "work_package": "structure", "category": "MS structure", "item_name": "SHS 3x3",
            "unit": "kg", "quantity": quantity, "rate": rate,
        },
        headers=headers,
    )


def _set_setting(client, headers, key, value):
    res = client.post("/settings", json={"key": key, "value": value, "reason": "test setup"}, headers=headers)
    assert res.status_code == 201, res.text


# ---------------------------------------------------------------------------
# K.1 step 4A: DLP reserve % and BOCW cess % in the real recompute engine
# ---------------------------------------------------------------------------


def test_dlp_reserve_percent_is_a_live_master_setting(client, director_user):
    """Distinguishes the DLP reserve actually applying from the coincidence
    that its 1% default matches the private-client warranty reserve's own
    1% default (see test_k1_overheads.py's
    test_warranty_reserve_is_replaced_by_dlp_reserve_for_tender_mode_projects)."""
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)
    _add_structure_line(client, headers, cost_sheet_id)
    _set_setting(client, headers, "dlp_reserve_percent", "3.0")

    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    # 8296 material+labour * 1.06 site estab * 1.03 DLP * 1.10 overhead * 1.05 contingency
    expected = 8296 * 1.06 * 1.03 * 1.10 * 1.05
    assert round(res.json()["cost_total"], 2) == round(expected, 2)


def test_bocw_cess_does_not_apply_below_the_rs_10l_threshold(client, director_user):
    """Part L: 'BOCW cess 1% on works > Rs 10 L.' A small tender-mode job
    stays under the threshold and pays no cess at all."""
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)
    _add_structure_line(client, headers, cost_sheet_id)  # ~8296 material+labour, well under 10L

    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    expected = 8296 * 1.06 * 1.01 * 1.10 * 1.05  # no cess factor
    assert round(res.json()["cost_total"], 2) == round(expected, 2)


def test_bocw_cess_applies_once_the_rs_10l_threshold_is_exceeded(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)
    # 15000 kg x 68 = 1,020,000 material -- comfortably past Rs 10 L after
    # the running site-establishment/DLP/overhead multipliers too.
    _add_structure_line(client, headers, cost_sheet_id, quantity=15000, rate=68)

    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    material = 15000 * 68 * 1.22  # blended 22% labour fallback
    pre_cess = material * 1.06 * 1.01 * 1.10
    assert pre_cess > 1_000_000  # sanity: the threshold really is exceeded
    expected = pre_cess * 1.01 * 1.05  # BOCW cess 1% then structure contingency 5%
    assert round(res.json()["cost_total"], 2) == round(expected, 2)


def test_bocw_cess_never_applies_to_private_clients(client, director_user):
    """BOCW cess is a Tender Mode (Part L) statutory addition only -- a
    private client above the same Rs 10 L subtotal must not pick it up."""
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers, client_type="school")
    _add_structure_line(client, headers, cost_sheet_id, quantity=15000, rate=68)

    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    material = 15000 * 68 * 1.22
    expected = material * 1.06 * 1.01 * 1.10 * 1.05  # warranty reserve 1%, no cess
    assert round(res.json()["cost_total"], 2) == round(expected, 2)


def test_bocw_cess_threshold_is_a_live_master_setting(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)
    _add_structure_line(client, headers, cost_sheet_id)  # ~8296, would not exceed Rs 10 L
    _set_setting(client, headers, "bocw_cess_threshold_rs", "5000")  # lower than this job's subtotal

    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    expected = 8296 * 1.06 * 1.01 * 1.10 * 1.01 * 1.05  # cess now applies
    assert round(res.json()["cost_total"], 2) == round(expected, 2)


def test_k1_constants_offers_dlp_reserve_and_bocw_cess_for_tender_mode(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)

    res = client.get(f"/cost-sheets/{cost_sheet_id}/k1-constants", headers=headers)
    by_key = {c["key"]: c for c in res.json()}
    assert by_key["dlp_reserve_percent"]["master_value"] == 1.0
    assert by_key["bocw_cess_percent"]["master_value"] == 1.0
    assert "warranty_reserve_percent" not in by_key


def test_k1_constants_omits_dlp_reserve_and_bocw_cess_for_private_clients(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers, client_type="school")

    res = client.get(f"/cost-sheets/{cost_sheet_id}/k1-constants", headers=headers)
    keys = {c["key"] for c in res.json()}
    assert "dlp_reserve_percent" not in keys
    assert "bocw_cess_percent" not in keys
    assert "warranty_reserve_percent" in keys


# ---------------------------------------------------------------------------
# POST /cost-sheets/{id}/tender-overheads: tender fee + performance-BG cost
# ---------------------------------------------------------------------------


def test_tender_overheads_rejected_for_a_non_tender_project(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers, client_type="school")

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/tender-overheads", json={"tender_fee": 5000}, headers=headers
    )
    assert res.status_code == 400


def test_sales_cannot_add_tender_overheads(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/tender-overheads", json={"tender_fee": 5000}, headers=sales_headers
    )
    assert res.status_code == 403


def test_tender_fee_line_is_a_flat_pm_entered_amount(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/tender-overheads", json={"tender_fee": 7500}, headers=headers
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["bg_contract_months"] is None
    assert len(body["lines"]) == 1
    line = body["lines"][0]
    assert line["work_package"] == "services"
    assert line["item_name"] == "Tender fee"
    assert line["quantity"] == 1
    assert line["rate"] == 7500
    assert line["amount"] == 7500


def test_performance_bg_cost_line_matches_the_standalone_calculator(client, director_user):
    """Same hand-computed example as test_performance_bg_cost_matches_hand_
    computed_example in test_tender.py (500000 * 1.5% * (7+12)/12 = 11875.0),
    now landing as a real CostSheetLine via the shared compute_bg_cost()."""
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/tender-overheads",
        json={"bg_amount": 500000, "bank_charge_percent_pa": 1.5, "contract_weeks": 26, "dlp_months": 12},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["bg_contract_months"] == 7
    assert len(body["lines"]) == 1
    line = body["lines"][0]
    assert line["item_name"] == "Performance BG cost"
    assert round(line["rate"], 2) == 11875.0


def test_tender_fee_and_bg_cost_can_be_added_together(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/tender-overheads",
        json={
            "tender_fee": 5000,
            "bg_amount": 500000, "bank_charge_percent_pa": 1.5, "contract_weeks": 26, "dlp_months": 12,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert len(res.json()["lines"]) == 2


def test_bg_cost_inputs_must_all_be_given_together(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)

    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/tender-overheads",
        json={"bg_amount": 500000, "bank_charge_percent_pa": 1.5},  # missing contract_weeks/dlp_months
        headers=headers,
    )
    assert res.status_code == 422


def test_tender_overheads_requires_at_least_one_field(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)

    res = client.post(f"/cost-sheets/{cost_sheet_id}/tender-overheads", json={}, headers=headers)
    assert res.status_code == 422


def test_tender_fee_and_bg_cost_lines_flow_into_the_real_recompute(client, director_user):
    headers = _director_headers(client, director_user)
    _, cost_sheet_id = _draft_cost_sheet(client, headers)
    _add_structure_line(client, headers, cost_sheet_id)  # 8296 material+labour, work_package structure
    client.post(
        f"/cost-sheets/{cost_sheet_id}/tender-overheads",
        json={"tender_fee": 5000},  # lands in work_package "services"
        headers=headers,
    )

    res = client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    structure_total = 8296 * 1.06 * 1.01 * 1.10 * 1.05  # structure contingency 5%
    # Tender fee is a "services" work_package line (blended 22% labour
    # fallback applies to it too, same as every other line) with services
    # contingency default 0%.
    services_material = 5000
    services_total = services_material * 1.22 * 1.06 * 1.01 * 1.10 * 1.0
    assert round(res.json()["cost_total"], 2) == round(structure_total + services_total, 2)


# ---------------------------------------------------------------------------
# BOQ-style Quotation PDF export for Tender Mode
# ---------------------------------------------------------------------------


def _pdf_text(response):
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(response.content))
    return "\n".join(page.extract_text() for page in reader.pages)


def _add_project_sport(client, headers, project_id, sport_key="badminton"):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports", json={"sport_id": sport_id, "building_status": "open_air"}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _sent_quotation(client, headers, client_type, cost_for_option=850000):
    client_id = _create_client_record(client, headers, client_type=client_type)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_for_option}, headers=headers
    ).json()["id"]
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost_for_option}]},
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
    client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    client.post(f"/quotations/{quotation['id']}/send", headers=headers)
    return quotation


def test_tender_mode_quotation_pdf_renders_as_a_boq(client, director_user):
    """Part L: 'BOQ-style itemised schedule (item no., description, unit,
    qty, rate, amount) instead of packages; DSR/SOR reference column.'"""
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers, client_type="government")

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert res.status_code == 200
    text = _pdf_text(res)
    assert "FINANCIAL BID (Tender Mode)" in text
    assert "Bill of Quantities (BOQ)" in text
    assert "DSR/SOR ref." in text
    assert "FORMAL QUOTATION" not in text
    assert "Particulars" not in text


def test_private_client_quotation_pdf_is_unaffected_by_boq_changes(client, director_user):
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers, client_type="school")

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    assert "FORMAL QUOTATION" in text
    assert "Particulars" in text
    assert "Bill of Quantities" not in text
    assert "FINANCIAL BID" not in text


def test_tender_mode_pdf_names_the_dlp_reserve_not_the_warranty_reserve(client, director_user):
    """K.1 4A/4B are mutually exclusive -- a Tender Mode document actually
    holds a DLP reserve internally, not the private-client warranty
    reserve, so the fixed T&C wording must say so."""
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers, client_type="government")

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    assert "DLP (defect-liability period) reserve of 1%" in text
    assert "A warranty reserve of 1%" not in text


def test_private_client_pdf_still_names_the_warranty_reserve(client, director_user):
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers, client_type="school")

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    assert "A warranty reserve of 1%" in text
    assert "DLP" not in text


def test_tender_boq_pdf_never_leaks_cost_or_margin(client, director_user):
    """K.3 still applies to the BOQ export -- same guard as the private-
    client Quotation PDF."""
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers, client_type="government", cost_for_option=850000)

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    from app.pdf_utils import format_inr

    assert format_inr(quotation["cost_total"]) not in text
    assert f"{quotation['margin_percent']:.2f}" not in text
