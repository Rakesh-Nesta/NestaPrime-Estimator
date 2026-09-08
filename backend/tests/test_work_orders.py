import io

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


def _create_client_record(client, headers, client_type="school", name="Work Order Client"):
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
        f"/projects/{project_id}/sports", json={"sport_id": sport_id, "building_status": "open_air"}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _won_quotation(client, headers, client_type="school", cost_for_option=850000):
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
    quotation_id = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id]},
        headers=headers,
    ).json()["id"]
    client.post(f"/quotations/{quotation_id}/release", headers=headers)
    client.post(f"/quotations/{quotation_id}/send", headers=headers)
    client.post(
        f"/quotations/{quotation_id}/mark-won",
        json={"reason": "Best offer", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    return project_id, quotation_id


def _released_quotation_not_yet_won(client, headers, client_type="school", cost_for_option=850000):
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
    quotation_id = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id]},
        headers=headers,
    ).json()["id"]
    return quotation_id


# ---------------------------------------------------------------------------
# Work Order creation (gated on Quotation Won)
# ---------------------------------------------------------------------------


def test_work_order_cannot_be_created_before_quotation_is_won(client, director_user):
    headers = _director_headers(client, director_user)
    quotation_id = _released_quotation_not_yet_won(client, headers)

    res = client.post(f"/quotations/{quotation_id}/work-order", headers=headers)
    assert res.status_code == 400


def test_work_order_created_once_quotation_is_won(client, director_user):
    """M.1: 'QUOTATION -> WORK ORDER / ACTUALS', status starts at Awarded."""
    headers = _director_headers(client, director_user)
    project_id, quotation_id = _won_quotation(client, headers)

    res = client.post(f"/quotations/{quotation_id}/work-order", headers=headers)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["project_id"] == project_id
    assert body["quotation_id"] == quotation_id
    assert body["status"] == "awarded"
    assert body["awarded_at"] is not None


def test_work_order_cannot_be_created_twice_for_same_quotation(client, director_user):
    headers = _director_headers(client, director_user)
    _, quotation_id = _won_quotation(client, headers)
    client.post(f"/quotations/{quotation_id}/work-order", headers=headers)

    res = client.post(f"/quotations/{quotation_id}/work-order", headers=headers)
    assert res.status_code == 400


def test_get_work_order_for_quotation(client, director_user):
    headers = _director_headers(client, director_user)
    _, quotation_id = _won_quotation(client, headers)
    created = client.post(f"/quotations/{quotation_id}/work-order", headers=headers).json()

    res = client.get(f"/quotations/{quotation_id}/work-order", headers=headers)
    assert res.status_code == 200
    assert res.json()["id"] == created["id"]


def test_get_work_order_404_when_none_exists(client, director_user):
    headers = _director_headers(client, director_user)
    _, quotation_id = _won_quotation(client, headers)

    res = client.get(f"/quotations/{quotation_id}/work-order", headers=headers)
    assert res.status_code == 404


def test_sales_cannot_create_or_read_work_orders(client, director_user, db_session):
    """M.1 stage 4's role column lists only PM/Director -- no Sales row,
    unlike the Estimate/Quotation stages."""
    director_headers = _director_headers(client, director_user)
    _, quotation_id = _won_quotation(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    assert client.post(f"/quotations/{quotation_id}/work-order", headers=sales_headers).status_code == 403

    client.post(f"/quotations/{quotation_id}/work-order", headers=director_headers)
    assert client.get(f"/quotations/{quotation_id}/work-order", headers=sales_headers).status_code == 403


# ---------------------------------------------------------------------------
# Status lifecycle: Awarded -> In progress -> Completed (forward-only)
# ---------------------------------------------------------------------------


def test_work_order_status_moves_forward_awarded_to_in_progress_to_completed(client, director_user):
    headers = _director_headers(client, director_user)
    _, quotation_id = _won_quotation(client, headers)
    work_order = client.post(f"/quotations/{quotation_id}/work-order", headers=headers).json()

    res = client.patch(f"/work-orders/{work_order['id']}", json={"status": "in_progress"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "in_progress"

    res = client.patch(f"/work-orders/{work_order['id']}", json={"status": "completed"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["status"] == "completed"


def test_work_order_status_cannot_skip_in_progress(client, director_user):
    headers = _director_headers(client, director_user)
    _, quotation_id = _won_quotation(client, headers)
    work_order = client.post(f"/quotations/{quotation_id}/work-order", headers=headers).json()

    res = client.patch(f"/work-orders/{work_order['id']}", json={"status": "completed"}, headers=headers)
    assert res.status_code == 400


def test_work_order_status_cannot_move_backward(client, director_user):
    headers = _director_headers(client, director_user)
    _, quotation_id = _won_quotation(client, headers)
    work_order = client.post(f"/quotations/{quotation_id}/work-order", headers=headers).json()
    client.patch(f"/work-orders/{work_order['id']}", json={"status": "in_progress"}, headers=headers)

    res = client.patch(f"/work-orders/{work_order['id']}", json={"status": "awarded"}, headers=headers)
    assert res.status_code == 400


def test_work_order_status_cannot_change_once_completed(client, director_user):
    headers = _director_headers(client, director_user)
    _, quotation_id = _won_quotation(client, headers)
    work_order = client.post(f"/quotations/{quotation_id}/work-order", headers=headers).json()
    client.patch(f"/work-orders/{work_order['id']}", json={"status": "in_progress"}, headers=headers)
    client.patch(f"/work-orders/{work_order['id']}", json={"status": "completed"}, headers=headers)

    res = client.patch(f"/work-orders/{work_order['id']}", json={"status": "in_progress"}, headers=headers)
    assert res.status_code == 400


def test_work_order_not_found_404s(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.patch(
        "/work-orders/00000000-0000-0000-0000-000000000000", json={"status": "in_progress"}, headers=headers
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Payment reconciliation entries (not a blueprint-named RA bill -- the
# "simple reconciliation entry" Part O's own BILLING note allows)
# ---------------------------------------------------------------------------


def test_add_and_list_payment_entries(client, director_user):
    headers = _director_headers(client, director_user)
    _, quotation_id = _won_quotation(client, headers)
    work_order = client.post(f"/quotations/{quotation_id}/work-order", headers=headers).json()

    res1 = client.post(
        f"/work-orders/{work_order['id']}/payment-entries",
        json={"milestone_name": "Advance", "amount_received": 340000, "received_date": "2026-09-10"},
        headers=headers,
    )
    assert res1.status_code == 201, res1.text
    body = res1.json()
    assert body["milestone_name"] == "Advance"
    assert body["amount_received"] == 340000
    assert body["work_order_id"] == work_order["id"]

    client.post(
        f"/work-orders/{work_order['id']}/payment-entries",
        json={
            "milestone_name": "Flooring completion", "amount_received": 340000,
            "received_date": "2026-09-20", "notes": "cheque #4521",
        },
        headers=headers,
    )

    listed = client.get(f"/work-orders/{work_order['id']}/payment-entries", headers=headers)
    assert listed.status_code == 200
    entries = listed.json()
    assert len(entries) == 2
    assert [e["milestone_name"] for e in entries] == ["Advance", "Flooring completion"]
    assert entries[1]["notes"] == "cheque #4521"
    assert entries[0]["gst_tds_amount"] is None


def test_payment_entry_can_record_gst_tds_withheld(client, director_user):
    """Part L 'Statutory': 'GST-TDS 2% by government/PSU payer' -- the
    actual amount THIS payment's TDS certificate showed withheld,
    recorded alongside the amount actually received."""
    headers = _director_headers(client, director_user)
    _, quotation_id = _won_quotation(client, headers)
    work_order = client.post(f"/quotations/{quotation_id}/work-order", headers=headers).json()

    res = client.post(
        f"/work-orders/{work_order['id']}/payment-entries",
        json={
            "milestone_name": "Advance", "amount_received": 340000,
            "received_date": "2026-09-10", "gst_tds_amount": 5762.71,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["gst_tds_amount"] == 5762.71


def test_payment_entry_amount_must_be_positive(client, director_user):
    headers = _director_headers(client, director_user)
    _, quotation_id = _won_quotation(client, headers)
    work_order = client.post(f"/quotations/{quotation_id}/work-order", headers=headers).json()

    res = client.post(
        f"/work-orders/{work_order['id']}/payment-entries",
        json={"milestone_name": "Advance", "amount_received": 0, "received_date": "2026-09-10"},
        headers=headers,
    )
    assert res.status_code == 422


def test_payment_entries_for_unknown_work_order_404(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/work-orders/00000000-0000-0000-0000-000000000000/payment-entries",
        json={"milestone_name": "Advance", "amount_received": 1000, "received_date": "2026-09-10"},
        headers=headers,
    )
    assert res.status_code == 404


def test_sales_cannot_add_payment_entries(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, quotation_id = _won_quotation(client, director_headers)
    work_order = client.post(f"/quotations/{quotation_id}/work-order", headers=director_headers).json()

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/work-orders/{work_order['id']}/payment-entries",
        json={"milestone_name": "Advance", "amount_received": 1000, "received_date": "2026-09-10"},
        headers=sales_headers,
    )
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Attachment integration (the "client work order attachment" field)
# ---------------------------------------------------------------------------


def test_client_work_order_can_be_attached_via_the_generic_attachment_system(client, director_user):
    headers = _director_headers(client, director_user)
    _, quotation_id = _won_quotation(client, headers)
    work_order = client.post(f"/quotations/{quotation_id}/work-order", headers=headers).json()

    res = client.post(
        "/attachments",
        data={"doc_type": "work_order", "doc_id": work_order["id"], "tag": "signed_document"},
        files={"file": ("work_order.pdf", io.BytesIO(b"%PDF-1.4 fake work order"), "application/pdf")},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["doc_type"] == "work_order"

    listed = client.get("/attachments", params={"doc_type": "work_order", "doc_id": work_order["id"]}, headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_sales_cannot_attach_to_a_work_order(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, quotation_id = _won_quotation(client, director_headers)
    work_order = client.post(f"/quotations/{quotation_id}/work-order", headers=director_headers).json()

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        "/attachments",
        data={"doc_type": "work_order", "doc_id": work_order["id"], "tag": "signed_document"},
        files={"file": ("work_order.pdf", io.BytesIO(b"%PDF-1.4 fake work order"), "application/pdf")},
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_work_order_endpoints_require_auth(client):
    assert client.post("/quotations/00000000-0000-0000-0000-000000000000/work-order").status_code == 401
    assert client.get("/quotations/00000000-0000-0000-0000-000000000000/work-order").status_code == 401
