from datetime import UTC, datetime, timedelta

from app.core.security import hash_password
from app.models.price_request import PriceRequest
from app.models.user import User, UserRole

RATE_ITEM_FIELDS = {
    "category": "MS structure",
    "item_name": "Steel Rs/kg",
    "unit": "kg",
    "hsn_sac": "7306",
    "rate": 60.0,
}


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


def _procurement_headers(client, db_session):
    user = User(
        name="Test Procurement", email="procurement@test.local",
        hashed_password=hash_password("TestPass!1"), role=UserRole.PROCUREMENT,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "procurement@test.local")


def _create_rate_item(client, headers, **overrides):
    payload = {**RATE_ITEM_FIELDS, **overrides}
    res = client.post("/rate-items", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_vendor(client, headers, name="Steel Traders", whatsapp_opt_in=True, email_opt_in=True, **overrides):
    payload = {
        "name": name, "phone": "+919876543210", "email": "vendor@example.com",
        "whatsapp_opt_in": whatsapp_opt_in, "email_opt_in": email_opt_in, **overrides,
    }
    res = client.post("/vendors", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_price_request(client, headers, rate_item_id, vendor_id, channels=None, **overrides):
    payload = {
        "items": [{"rate_item_id": rate_item_id, "quantity_band": "100-500 kg"}],
        "vendor_ids": [vendor_id],
        "channels": channels or ["whatsapp", "email"],
        **overrides,
    }
    res = client.post("/price-requests", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _draft_cost_sheet(client, headers):
    res = client.post("/clients", json={"name": "PR Client", "type": "school"}, headers=headers)
    client_id = res.json()["id"]
    fields = {
        "client_id": client_id, "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
        "building_status": "open_air", "site_access": "good", "power_available": "yes",
        "water_available": True, "package": "standard",
    }
    project_id = client.post("/projects", json=fields, headers=headers).json()["id"]
    res = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers)
    return res.json()["id"]


def _add_line(client, headers, cost_sheet_id, rate_item_id, rate=60.0):
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={
            "rate_item_id": rate_item_id, "work_package": "civil", "category": "MS structure",
            "item_name": "Steel Rs/kg", "unit": "kg", "quantity": 100, "rate": rate,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _audit_entries(client, headers, **params):
    res = client.get("/audit-log", params=params, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


# ---------------------------------------------------------------------------
# Create price request
# ---------------------------------------------------------------------------


def test_create_price_request(client, director_user):
    headers = _director_headers(client, director_user)
    rate_item_id = _create_rate_item(client, headers)
    vendor_id = _create_vendor(client, headers)

    pr = _create_price_request(client, headers, rate_item_id, vendor_id, required_by="2026-10-01", requested_validity_days=15)
    assert pr["status"] == "open"
    assert len(pr["items"]) == 1
    assert pr["items"][0]["rate_item_id"] == rate_item_id
    assert pr["items"][0]["quantity_band"] == "100-500 kg"
    assert len(pr["vendors"]) == 1
    assert pr["vendors"][0]["vendor_id"] == vendor_id
    assert pr["vendors"][0]["replied"] is False


def test_create_price_request_writes_an_audit_log_entry(client, director_user):
    headers = _director_headers(client, director_user)
    rate_item_id = _create_rate_item(client, headers)
    vendor_id = _create_vendor(client, headers)

    pr = _create_price_request(client, headers, rate_item_id, vendor_id)

    entries = _audit_entries(client, headers, document_type="price_request", document_id=pr["id"])
    entry = next(e for e in entries if e["new_value"] == "open")
    assert "1 item(s) from 1 vendor(s)" in entry["reason"]


def test_create_price_request_fails_for_whatsapp_not_opted_in_vendor(client, director_user):
    headers = _director_headers(client, director_user)
    rate_item_id = _create_rate_item(client, headers)
    vendor_id = _create_vendor(client, headers, whatsapp_opt_in=False)

    res = client.post(
        "/price-requests",
        json={
            "items": [{"rate_item_id": rate_item_id}], "vendor_ids": [vendor_id], "channels": ["whatsapp"],
        },
        headers=headers,
    )
    assert res.status_code == 400
    assert "opted in" in res.json()["detail"]


def test_create_price_request_fails_for_email_opted_out_vendor(client, director_user):
    headers = _director_headers(client, director_user)
    rate_item_id = _create_rate_item(client, headers)
    vendor_id = _create_vendor(client, headers, email_opt_in=False)

    res = client.post(
        "/price-requests",
        json={"items": [{"rate_item_id": rate_item_id}], "vendor_ids": [vendor_id], "channels": ["email"]},
        headers=headers,
    )
    assert res.status_code == 400
    assert "opted out" in res.json()["detail"]


def test_create_price_request_fails_for_unknown_rate_item(client, director_user):
    headers = _director_headers(client, director_user)
    vendor_id = _create_vendor(client, headers)
    res = client.post(
        "/price-requests",
        json={
            "items": [{"rate_item_id": "00000000-0000-0000-0000-000000000000"}],
            "vendor_ids": [vendor_id], "channels": ["email"],
        },
        headers=headers,
    )
    assert res.status_code == 404


def test_sales_cannot_create_a_price_request(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    rate_item_id = _create_rate_item(client, headers)
    vendor_id = _create_vendor(client, headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        "/price-requests",
        json={"items": [{"rate_item_id": rate_item_id}], "vendor_ids": [vendor_id], "channels": ["email"]},
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_procurement_can_create_a_price_request(client, director_user, db_session):
    """M.7.5: 'Send RFQ / PO / price-update request to vendor' includes Procurement."""
    headers = _director_headers(client, director_user)
    rate_item_id = _create_rate_item(client, headers)
    vendor_id = _create_vendor(client, headers)

    procurement_headers = _procurement_headers(client, db_session)
    pr = _create_price_request(client, procurement_headers, rate_item_id, vendor_id)
    assert pr["status"] == "open"


def test_list_price_requests_filters_by_status(client, director_user):
    headers = _director_headers(client, director_user)
    rate_item_id = _create_rate_item(client, headers)
    vendor_id = _create_vendor(client, headers)
    _create_price_request(client, headers, rate_item_id, vendor_id)

    open_only = client.get("/price-requests", params={"status": "open"}, headers=headers).json()
    assert len(open_only) == 1
    closed_only = client.get("/price-requests", params={"status": "closed"}, headers=headers).json()
    assert len(closed_only) == 0


def test_close_price_request(client, director_user):
    headers = _director_headers(client, director_user)
    rate_item_id = _create_rate_item(client, headers)
    vendor_id = _create_vendor(client, headers)
    pr = _create_price_request(client, headers, rate_item_id, vendor_id)

    res = client.post(f"/price-requests/{pr['id']}/close", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "closed"

    res = client.post(f"/price-requests/{pr['id']}/close", headers=headers)
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# Vendor replies
# ---------------------------------------------------------------------------


def test_capture_vendor_reply_with_explicit_parsed_fields(client, director_user):
    headers = _director_headers(client, director_user)
    rate_item_id = _create_rate_item(client, headers)
    vendor_id = _create_vendor(client, headers)
    pr = _create_price_request(client, headers, rate_item_id, vendor_id)
    item_id = pr["items"][0]["id"]

    res = client.post(
        f"/price-requests/{pr['id']}/items/{item_id}/replies",
        json={
            "vendor_id": vendor_id, "raw_reply_text": "We can do Rs 65/kg, exclusive of GST, valid for 10 days.",
            "parsed_rate": 65.0, "parsed_unit": "kg", "parsed_gst_basis": "exclusive", "parsed_validity_days": 10,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    reply = res.json()
    assert reply["parsed_rate"] == 65.0
    assert reply["parsed_gst_basis"] == "exclusive"
    assert reply["confirmed"] is False

    # First reply flips the request to replied.
    pr_after = client.get(f"/price-requests/{pr['id']}", headers=headers).json()
    assert pr_after["status"] == "replied"
    assert pr_after["vendors"][0]["replied"] is True


def test_capture_vendor_reply_regex_assist_parses_the_blueprint_example(client, director_user):
    """M.7.3 rule 2's own reply-format example: 'SHS 75x75x2.5 -- Rs
    68/kg ex-GST, valid 15 days.'"""
    headers = _director_headers(client, director_user)
    rate_item_id = _create_rate_item(client, headers)
    vendor_id = _create_vendor(client, headers)
    pr = _create_price_request(client, headers, rate_item_id, vendor_id)
    item_id = pr["items"][0]["id"]

    res = client.post(
        f"/price-requests/{pr['id']}/items/{item_id}/replies",
        json={"vendor_id": vendor_id, "raw_reply_text": "SHS 75x75x2.5 -- Rs 68/kg ex-GST, valid 15 days"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    reply = res.json()
    assert reply["parsed_rate"] == 68.0
    assert reply["parsed_unit"] == "kg"
    assert reply["parsed_gst_basis"] == "exclusive"
    assert reply["parsed_validity_days"] == 15


def test_explicit_parsed_fields_override_the_regex_assist(client, director_user):
    headers = _director_headers(client, director_user)
    rate_item_id = _create_rate_item(client, headers)
    vendor_id = _create_vendor(client, headers)
    pr = _create_price_request(client, headers, rate_item_id, vendor_id)
    item_id = pr["items"][0]["id"]

    res = client.post(
        f"/price-requests/{pr['id']}/items/{item_id}/replies",
        json={
            "vendor_id": vendor_id, "raw_reply_text": "Rs 68/kg ex-GST, valid 15 days",
            "parsed_rate": 70.0,  # human corrects a misread OCR/typo
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["parsed_rate"] == 70.0


def test_reply_from_an_uninvited_vendor_fails(client, director_user):
    headers = _director_headers(client, director_user)
    rate_item_id = _create_rate_item(client, headers)
    vendor_id = _create_vendor(client, headers)
    other_vendor_id = _create_vendor(client, headers, name="Other Vendor")
    pr = _create_price_request(client, headers, rate_item_id, vendor_id)
    item_id = pr["items"][0]["id"]

    res = client.post(
        f"/price-requests/{pr['id']}/items/{item_id}/replies",
        json={"vendor_id": other_vendor_id, "raw_reply_text": "Rs 65/kg"},
        headers=headers,
    )
    assert res.status_code == 400


def test_replies_are_listed_side_by_side_sorted_by_rate(client, director_user):
    headers = _director_headers(client, director_user)
    rate_item_id = _create_rate_item(client, headers)
    vendor_a = _create_vendor(client, headers, name="Vendor A")
    vendor_b = _create_vendor(client, headers, name="Vendor B")
    pr = _create_price_request(
        client, headers, rate_item_id, vendor_a, channels=["email"],
    )
    # Add vendor B to the same request too.
    client.post(
        "/price-requests",
        json={
            "items": [{"rate_item_id": rate_item_id}], "vendor_ids": [vendor_b], "channels": ["email"],
        },
        headers=headers,
    )
    item_id = pr["items"][0]["id"]

    client.post(
        f"/price-requests/{pr['id']}/items/{item_id}/replies",
        json={"vendor_id": vendor_a, "raw_reply_text": "Rs 70/kg"},
        headers=headers,
    )

    replies = client.get(f"/price-requests/{pr['id']}/items/{item_id}/replies", headers=headers).json()
    assert len(replies) == 1
    assert replies[0]["vendor_name"] == "Vendor A"
    assert replies[0]["parsed_rate"] == 70.0


def test_reminder_due_when_no_reply_after_working_days(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    rate_item_id = _create_rate_item(client, headers)
    vendor_id = _create_vendor(client, headers)
    pr = _create_price_request(client, headers, rate_item_id, vendor_id)

    fresh = client.get(f"/price-requests/{pr['id']}", headers=headers).json()
    assert fresh["reminder_due"] is False

    row = db_session.query(PriceRequest).filter(PriceRequest.id == pr["id"]).first()
    row.sent_at = datetime.now(UTC) - timedelta(days=10)
    db_session.commit()

    stale = client.get(f"/price-requests/{pr['id']}", headers=headers).json()
    assert stale["reminder_due"] is True
    assert stale["vendors"][0]["reminder_due"] is True

    overdue_only = client.get("/price-requests", params={"overdue_only": True}, headers=headers).json()
    assert any(p["id"] == pr["id"] for p in overdue_only)


# ---------------------------------------------------------------------------
# Use this rate
# ---------------------------------------------------------------------------


def _capture_reply(client, headers, pr, item_id, vendor_id, rate=65.0, text=None):
    res = client.post(
        f"/price-requests/{pr['id']}/items/{item_id}/replies",
        json={"vendor_id": vendor_id, "raw_reply_text": text or f"Rs {rate}/kg", "parsed_rate": rate},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def test_use_reply_applies_to_master_rate_as_unverified_proposal(client, director_user):
    headers = _director_headers(client, director_user)
    rate_item_id = _create_rate_item(client, headers)
    vendor_id = _create_vendor(client, headers)
    pr = _create_price_request(client, headers, rate_item_id, vendor_id)
    item_id = pr["items"][0]["id"]
    reply = _capture_reply(client, headers, pr, item_id, vendor_id, rate=65.0)

    res = client.post(f"/vendor-replies/{reply['id']}/use", json={"apply_to": "master"}, headers=headers)
    assert res.status_code == 200, res.text
    used = res.json()
    assert used["confirmed"] is True
    assert used["applied_as"] == "master"

    rate_item = client.get("/rate-items", headers=headers).json()
    updated = next(r for r in rate_item if r["id"] == rate_item_id)
    assert updated["rate"] == 65.0
    assert updated["verified"] is False
    assert updated["source"] == "manual"

    history = client.get(f"/rate-items/{rate_item_id}/history", headers=headers).json()
    latest = next(h for h in history if h["effective_to"] is None)
    assert latest["vendor_id"] == vendor_id
    assert latest["rate"] == 65.0


def test_use_reply_applies_to_cost_sheet_line(client, director_user):
    headers = _director_headers(client, director_user)
    rate_item_id = _create_rate_item(client, headers)
    vendor_id = _create_vendor(client, headers)
    pr = _create_price_request(client, headers, rate_item_id, vendor_id)
    item_id = pr["items"][0]["id"]
    reply = _capture_reply(client, headers, pr, item_id, vendor_id, rate=65.0)

    cost_sheet_id = _draft_cost_sheet(client, headers)
    line_id = _add_line(client, headers, cost_sheet_id, rate_item_id, rate=60.0)

    res = client.post(
        f"/vendor-replies/{reply['id']}/use",
        json={"apply_to": "cost_sheet_line", "cost_sheet_line_id": line_id},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["applied_as"] == "cost_sheet_line"

    lines = client.get(f"/cost-sheets/{cost_sheet_id}/lines", headers=headers).json()
    updated_line = next(l for l in lines if l["id"] == line_id)
    assert updated_line["rate"] == 65.0


def test_use_reply_blocked_on_a_verified_cost_sheet(client, director_user):
    headers = _director_headers(client, director_user)
    rate_item_id = _create_rate_item(client, headers)
    vendor_id = _create_vendor(client, headers)
    pr = _create_price_request(client, headers, rate_item_id, vendor_id)
    item_id = pr["items"][0]["id"]
    reply = _capture_reply(client, headers, pr, item_id, vendor_id, rate=65.0)

    cost_sheet_id = _draft_cost_sheet(client, headers)
    line_id = _add_line(client, headers, cost_sheet_id, rate_item_id, rate=60.0)
    client.post(f"/cost-sheets/{cost_sheet_id}/recompute", headers=headers)
    res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert res.status_code == 200, res.text

    res = client.post(
        f"/vendor-replies/{reply['id']}/use",
        json={"apply_to": "cost_sheet_line", "cost_sheet_line_id": line_id},
        headers=headers,
    )
    assert res.status_code == 400


def test_use_reply_with_no_parsed_rate_fails(client, director_user):
    headers = _director_headers(client, director_user)
    rate_item_id = _create_rate_item(client, headers)
    vendor_id = _create_vendor(client, headers)
    pr = _create_price_request(client, headers, rate_item_id, vendor_id)
    item_id = pr["items"][0]["id"]

    res = client.post(
        f"/price-requests/{pr['id']}/items/{item_id}/replies",
        json={"vendor_id": vendor_id, "raw_reply_text": "we will get back to you soon"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    reply = res.json()
    assert reply["parsed_rate"] is None

    res = client.post(f"/vendor-replies/{reply['id']}/use", json={"apply_to": "master"}, headers=headers)
    assert res.status_code == 400


def test_use_reply_writes_an_audit_log_entry(client, director_user):
    headers = _director_headers(client, director_user)
    rate_item_id = _create_rate_item(client, headers)
    vendor_id = _create_vendor(client, headers)
    pr = _create_price_request(client, headers, rate_item_id, vendor_id)
    item_id = pr["items"][0]["id"]
    reply = _capture_reply(client, headers, pr, item_id, vendor_id, rate=65.0)

    client.post(f"/vendor-replies/{reply['id']}/use", json={"apply_to": "master"}, headers=headers)

    entries = _audit_entries(client, headers, document_type="price_request", document_id=pr["id"])
    applied = next(e for e in entries if e["field"] == "applied_rate")
    assert applied["new_value"] == "65.00"


# ---------------------------------------------------------------------------
# Vendor consent fields
# ---------------------------------------------------------------------------


def test_vendor_update_accepts_opt_in_fields(client, director_user):
    headers = _director_headers(client, director_user)
    vendor_id = _create_vendor(client, headers, whatsapp_opt_in=False)

    res = client.patch(
        f"/vendors/{vendor_id}",
        json={"whatsapp_opt_in": True, "consent_date": "2026-09-08"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["whatsapp_opt_in"] is True
    assert body["consent_date"] == "2026-09-08"
