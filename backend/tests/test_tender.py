def _login(client, director_user):
    res = client.post(
        "/auth/login",
        data={"username": "director@test.local", "password": "TestPass!1"},
    )
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _create_client(client, headers, client_type="school", name="Test School"):
    res = client.post("/clients", json={"name": name, "type": client_type}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id, **overrides):
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
        **overrides,
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


TENDER_DETAILS_FIELDS = {
    "retention_percent": 7.5,
    "performance_bg_percent": 4.0,
    "dlp_months": 12,
}


def test_tender_details_can_only_be_added_to_government_projects(client, director_user):
    """Part L is scoped to Tender Mode (Government clients)."""
    headers = _login(client, director_user)
    school_client_id = _create_client(client, headers, client_type="school")
    project_id = _create_project(client, headers, school_client_id)

    res = client.post(
        f"/projects/{project_id}/tender-details", json=TENDER_DETAILS_FIELDS, headers=headers
    )
    assert res.status_code == 400


def test_create_and_fetch_tender_details_for_government_project(client, director_user):
    headers = _login(client, director_user)
    gov_client_id = _create_client(client, headers, client_type="government", name="Municipal Corp")
    project_id = _create_project(client, headers, gov_client_id)

    res = client.post(
        f"/projects/{project_id}/tender-details",
        json={
            **TENDER_DETAILS_FIELDS,
            "emd_amount": 50000,
            "emd_validity_date": "2026-12-31",
            "bid_due_date": "2026-10-15",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["retention_percent"] == 7.5
    assert body["emd_amount"] == 50000
    assert body["dlp_months"] == 12

    get_res = client.get(f"/projects/{project_id}/tender-details", headers=headers)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == body["id"]


def test_tender_details_cannot_be_created_twice_for_same_project(client, director_user):
    headers = _login(client, director_user)
    gov_client_id = _create_client(client, headers, client_type="government", name="Municipal Corp")
    project_id = _create_project(client, headers, gov_client_id)

    client.post(f"/projects/{project_id}/tender-details", json=TENDER_DETAILS_FIELDS, headers=headers)
    res = client.post(f"/projects/{project_id}/tender-details", json=TENDER_DETAILS_FIELDS, headers=headers)
    assert res.status_code == 400


def test_tender_details_for_unknown_project_is_rejected(client, director_user):
    headers = _login(client, director_user)
    res = client.post(
        "/projects/00000000-0000-0000-0000-000000000000/tender-details",
        json=TENDER_DETAILS_FIELDS,
        headers=headers,
    )
    assert res.status_code == 404


def test_performance_bg_cost_matches_hand_computed_example(client, director_user):
    """L: 'BG cost = BG amount x bank charge x (contract months + DLP
    months) / 12, contract months = ceil(schedule weeks / 4.33).'
    500000 * 1.5% * (7 + 12) / 12 = 11875.0 (contract_months = ceil(26/4.33) = 7)."""
    headers = _login(client, director_user)
    res = client.post(
        "/tender/performance-bg-cost",
        json={
            "bg_amount": 500000,
            "bank_charge_percent_pa": 1.5,
            "contract_weeks": 26,
            "dlp_months": 12,
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["contract_months"] == 7
    assert round(body["bg_cost"], 2) == 11875.0


def test_net_receivable_deducts_retention_from_quotation_total(client, director_user):
    headers = _login(client, director_user)
    res = client.post(
        "/tender/net-receivable",
        json={"quotation_total": 1180000, "retention_percent": 5},
        headers=headers,
    )
    body = res.json()
    assert body["retention_amount"] == 59000.0
    assert body["gst_tds_amount"] == 0.0
    assert body["net_receivable"] == 1121000.0


def test_net_receivable_also_deducts_gst_tds_when_given(client, director_user):
    """Part L 'Statutory': 'GST-TDS 2% by government/PSU payer' -- built
    as a receipt-side deduction despite the blueprint's own K.1b section
    (v5.1.9) having explicitly retired GST-TDS logic, per an explicit,
    informed decision to override that retirement note. Computed on the
    ex-GST value: 1,180,000 / 1.18 = 1,000,000 ex-GST; 2% of that = 20,000."""
    headers = _login(client, director_user)
    res = client.post(
        "/tender/net-receivable",
        json={"quotation_total": 1180000, "retention_percent": 5, "gst_tds_percent": 2},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["retention_amount"] == 59000.0
    assert body["gst_tds_amount"] == 20000.0
    assert body["net_receivable"] == 1101000.0


def test_net_receivable_gst_tds_uses_the_live_gst_rate_setting(client, director_user):
    headers = _login(client, director_user)
    client.post("/settings", json={"key": "gst_rate_percent", "value": "12", "reason": "test setup"}, headers=headers)

    res = client.post(
        "/tender/net-receivable",
        json={"quotation_total": 1120000, "retention_percent": 5, "gst_tds_percent": 2},
        headers=headers,
    )
    # 1,120,000 / 1.12 = 1,000,000 ex-GST; 2% = 20,000.
    assert round(res.json()["gst_tds_amount"], 2) == 20000.0


def test_tender_endpoints_require_auth(client):
    assert client.get("/projects/00000000-0000-0000-0000-000000000000/tender-details").status_code == 401
    assert client.post("/tender/performance-bg-cost", json={
        "bg_amount": 1, "bank_charge_percent_pa": 1, "contract_weeks": 1, "dlp_months": 1
    }).status_code == 401


# ---------------------------------------------------------------------------
# Technical bid checklist (Part L "Documents" row: GST, PAN, turnover,
# past work certificates, ISO -- the complete, verbatim item list)
# ---------------------------------------------------------------------------


def test_technical_bid_checklist_rejected_for_non_tender_project(client, director_user):
    headers = _login(client, director_user)
    school_client_id = _create_client(client, headers, client_type="school")
    project_id = _create_project(client, headers, school_client_id)

    res = client.get(f"/projects/{project_id}/technical-bid-checklist", headers=headers)
    assert res.status_code == 400


def test_technical_bid_checklist_lazily_seeds_the_five_named_items(client, director_user):
    headers = _login(client, director_user)
    gov_client_id = _create_client(client, headers, client_type="government", name="Municipal Corp")
    project_id = _create_project(client, headers, gov_client_id)

    res = client.get(f"/projects/{project_id}/technical-bid-checklist", headers=headers)
    assert res.status_code == 200, res.text
    items = res.json()
    keys = {i["key"] for i in items}
    assert keys == {"gst", "pan", "turnover", "past_work_certificates", "iso"}
    assert all(i["confirmed"] is False for i in items)
    assert all(i["confirmed_at"] is None for i in items)


def test_technical_bid_checklist_get_does_not_duplicate_rows_on_repeat_calls(client, director_user):
    headers = _login(client, director_user)
    gov_client_id = _create_client(client, headers, client_type="government", name="Municipal Corp")
    project_id = _create_project(client, headers, gov_client_id)

    client.get(f"/projects/{project_id}/technical-bid-checklist", headers=headers)
    res = client.get(f"/projects/{project_id}/technical-bid-checklist", headers=headers)
    assert len(res.json()) == 5


def test_can_confirm_and_unconfirm_a_checklist_item(client, director_user):
    headers = _login(client, director_user)
    gov_client_id = _create_client(client, headers, client_type="government", name="Municipal Corp")
    project_id = _create_project(client, headers, gov_client_id)

    confirm_res = client.patch(
        f"/projects/{project_id}/technical-bid-checklist/gst", json={"confirmed": True}, headers=headers
    )
    assert confirm_res.status_code == 200, confirm_res.text
    body = confirm_res.json()
    assert body["confirmed"] is True
    assert body["confirmed_at"] is not None
    assert body["confirmed_by_id"] is not None

    unconfirm_res = client.patch(
        f"/projects/{project_id}/technical-bid-checklist/gst", json={"confirmed": False}, headers=headers
    )
    assert unconfirm_res.status_code == 200
    assert unconfirm_res.json()["confirmed"] is False
    assert unconfirm_res.json()["confirmed_at"] is None
    assert unconfirm_res.json()["confirmed_by_id"] is None


def test_confirming_one_checklist_item_does_not_affect_others(client, director_user):
    headers = _login(client, director_user)
    gov_client_id = _create_client(client, headers, client_type="government", name="Municipal Corp")
    project_id = _create_project(client, headers, gov_client_id)

    client.patch(f"/projects/{project_id}/technical-bid-checklist/pan", json={"confirmed": True}, headers=headers)

    items = client.get(f"/projects/{project_id}/technical-bid-checklist", headers=headers).json()
    by_key = {i["key"]: i for i in items}
    assert by_key["pan"]["confirmed"] is True
    assert by_key["gst"]["confirmed"] is False
    assert by_key["iso"]["confirmed"] is False


def test_technical_bid_checklist_update_rejected_for_non_tender_project(client, director_user):
    headers = _login(client, director_user)
    school_client_id = _create_client(client, headers, client_type="school")
    project_id = _create_project(client, headers, school_client_id)

    res = client.patch(
        f"/projects/{project_id}/technical-bid-checklist/gst", json={"confirmed": True}, headers=headers
    )
    assert res.status_code == 400


def test_sales_cannot_access_technical_bid_checklist(client, db_session):
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    director_user = User(
        name="Test Director2", email="director2@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.DIRECTOR,
    )
    db_session.add(director_user)
    db_session.commit()
    director_headers = {
        "Authorization": f"Bearer {client.post('/auth/login', data={'username': 'director2@test.local', 'password': 'TestPass!1'}).json()['access_token']}"
    }
    gov_client_id = _create_client(client, director_headers, client_type="government", name="Municipal Corp")
    project_id = _create_project(client, director_headers, gov_client_id)

    sales_user = User(
        name="Test Sales", email="sales_checklist@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.SALES,
    )
    db_session.add(sales_user)
    db_session.commit()
    sales_headers = {
        "Authorization": f"Bearer {client.post('/auth/login', data={'username': 'sales_checklist@test.local', 'password': 'TestPass!1'}).json()['access_token']}"
    }

    assert client.get(f"/projects/{project_id}/technical-bid-checklist", headers=sales_headers).status_code == 403
    assert client.patch(
        f"/projects/{project_id}/technical-bid-checklist/gst", json={"confirmed": True}, headers=sales_headers
    ).status_code == 403


def test_technical_bid_checklist_item_document_can_be_attached(client, director_user):
    import io

    headers = _login(client, director_user)
    gov_client_id = _create_client(client, headers, client_type="government", name="Municipal Corp")
    project_id = _create_project(client, headers, gov_client_id)
    items = client.get(f"/projects/{project_id}/technical-bid-checklist", headers=headers).json()
    gst_item_id = next(i["id"] for i in items if i["key"] == "gst")

    res = client.post(
        "/attachments",
        data={"doc_type": "technical_bid_checklist_item", "doc_id": gst_item_id, "tag": "reference"},
        files={"file": ("gst_certificate.pdf", io.BytesIO(b"%PDF-1.4 fake gst certificate"), "application/pdf")},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["doc_type"] == "technical_bid_checklist_item"

    listed = client.get(
        "/attachments", params={"doc_type": "technical_bid_checklist_item", "doc_id": gst_item_id}, headers=headers
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_sales_cannot_access_tender_endpoints(client, db_session):
    """Tender Mode is money-adjacent (EMD, retention, BG %) -- PM/Director
    only, same restriction as Part K's commercial layer."""
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    sales_user = User(
        name="Test Sales",
        email="sales@test.local",
        hashed_password=hash_password("TestPass!1"),
        role=UserRole.SALES,
    )
    db_session.add(sales_user)
    db_session.commit()

    login_res = client.post(
        "/auth/login", data={"username": "sales@test.local", "password": "TestPass!1"}
    )
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    assert client.post(
        "/tender/net-receivable",
        json={"quotation_total": 100, "retention_percent": 5},
        headers=headers,
    ).status_code == 403
