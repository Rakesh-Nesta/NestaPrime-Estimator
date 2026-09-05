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
    assert body["net_receivable"] == 1121000.0


def test_tender_endpoints_require_auth(client):
    assert client.get("/projects/00000000-0000-0000-0000-000000000000/tender-details").status_code == 401
    assert client.post("/tender/performance-bg-cost", json={
        "bg_amount": 1, "bank_charge_percent_pa": 1, "contract_weeks": 1, "dlp_months": 1
    }).status_code == 401


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
