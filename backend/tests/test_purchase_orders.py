from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _procurement_headers(client, db_session):
    user = User(
        name="Test Procurement", email="procurement@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.PROCUREMENT,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "procurement@test.local")


def _sales_headers(client, db_session):
    user = User(
        name="Test Sales", email="sales@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.SALES
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales@test.local")


def _create_client_record(client, headers):
    res = client.post("/clients", json={"name": "PO Test Client", "type": "school"}, headers=headers)
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


def _cost_sheet_with_two_lines(client, headers):
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = client.post(f"/projects/{project_id}/cost-sheets", json={}, headers=headers).json()["id"]
    line_a = client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={"work_package": "structure", "category": "MS structure", "item_name": "SHS 3x3", "unit": "kg", "quantity": 500, "rate": 68},
        headers=headers,
    ).json()
    line_b = client.post(
        f"/cost-sheets/{cost_sheet_id}/lines",
        json={"work_package": "flooring", "category": "Turf", "item_name": "Turf roll", "unit": "sqm", "quantity": 200, "rate": 900},
        headers=headers,
    ).json()
    return cost_sheet_id, line_a, line_b


def _vendor(client, headers, name="Steel Co"):
    res = client.post("/vendors", json={"name": name, "city": "Mumbai"}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


# ---------------------------------------------------------------------------
# Vendors
# ---------------------------------------------------------------------------


def test_sales_cannot_manage_vendors(client, director_user, db_session):
    sales_headers = _sales_headers(client, db_session)
    res = client.post("/vendors", json={"name": "Steel Co"}, headers=sales_headers)
    assert res.status_code == 403
    assert client.get("/vendors", headers=sales_headers).status_code == 403


def test_procurement_can_create_and_update_a_vendor(client, director_user, db_session):
    procurement_headers = _procurement_headers(client, db_session)
    vendor = client.post(
        "/vendors",
        json={"name": "Steel Co", "city": "Mumbai", "phone": "9999999999", "gstin": "27AAAAA0000A1Z5"},
        headers=procurement_headers,
    )
    assert vendor.status_code == 201, vendor.text
    vendor_id = vendor.json()["id"]

    updated = client.patch(
        f"/vendors/{vendor_id}", json={"reliability_score": 4.5, "rcm_applicable": True}, headers=procurement_headers
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["reliability_score"] == 4.5
    assert updated.json()["rcm_applicable"] is True
    assert updated.json()["name"] == "Steel Co"  # untouched fields survive a partial update


def test_vendor_not_found(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.get("/vendors/00000000-0000-0000-0000-000000000000", headers=headers)
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Purchase orders
# ---------------------------------------------------------------------------


def test_sales_cannot_raise_a_purchase_order(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    cost_sheet_id, line_a, _ = _cost_sheet_with_two_lines(client, headers)
    vendor = _vendor(client, headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/purchase-orders",
        json={"vendor_id": vendor["id"], "lines": [{"cost_sheet_line_id": line_a["id"], "quantity": 500, "rate": 68}]},
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_procurement_can_raise_a_po_with_frozen_item_details(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    cost_sheet_id, line_a, line_b = _cost_sheet_with_two_lines(client, headers)
    vendor = _vendor(client, headers)

    procurement_headers = _procurement_headers(client, db_session)
    res = client.post(
        f"/cost-sheets/{cost_sheet_id}/purchase-orders",
        json={
            "vendor_id": vendor["id"],
            "lines": [
                {"cost_sheet_line_id": line_a["id"], "quantity": 500, "rate": 65},  # vendor's own quote, not 68
                {"cost_sheet_line_id": line_b["id"], "quantity": 200, "rate": 900},
            ],
            "delivery_date": "2026-11-01",
        },
        headers=procurement_headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["po_no"].startswith("PO-")
    assert body["status"] == "draft"
    assert body["vendor_name"] == "Steel Co"
    assert len(body["lines"]) == 2
    steel_line = next(line for line in body["lines"] if line["item_name"] == "SHS 3x3")
    assert steel_line["rate"] == 65  # frozen at the vendor's quoted rate, not the cost sheet's
    assert steel_line["amount"] == 500 * 65
    assert steel_line["received_qty"] == 0
    assert steel_line["balance_qty"] == 500


def test_a_cost_sheet_line_cannot_be_raised_on_two_open_pos(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id, line_a, _ = _cost_sheet_with_two_lines(client, headers)
    vendor = _vendor(client, headers)

    client.post(
        f"/cost-sheets/{cost_sheet_id}/purchase-orders",
        json={"vendor_id": vendor["id"], "lines": [{"cost_sheet_line_id": line_a["id"], "quantity": 500, "rate": 68}]},
        headers=headers,
    )
    second_attempt = client.post(
        f"/cost-sheets/{cost_sheet_id}/purchase-orders",
        json={"vendor_id": vendor["id"], "lines": [{"cost_sheet_line_id": line_a["id"], "quantity": 500, "rate": 68}]},
        headers=headers,
    )
    assert second_attempt.status_code == 400
    assert "already on an open PO" in second_attempt.json()["detail"]


def test_po_number_increments_per_project(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id, line_a, line_b = _cost_sheet_with_two_lines(client, headers)
    vendor = _vendor(client, headers)

    first = client.post(
        f"/cost-sheets/{cost_sheet_id}/purchase-orders",
        json={"vendor_id": vendor["id"], "lines": [{"cost_sheet_line_id": line_a["id"], "quantity": 500, "rate": 68}]},
        headers=headers,
    ).json()
    second = client.post(
        f"/cost-sheets/{cost_sheet_id}/purchase-orders",
        json={"vendor_id": vendor["id"], "lines": [{"cost_sheet_line_id": line_b["id"], "quantity": 200, "rate": 900}]},
        headers=headers,
    ).json()
    assert first["po_no"] != second["po_no"]
    assert first["po_no"].endswith("-01")
    assert second["po_no"].endswith("-02")


def test_full_lifecycle_draft_issue_receive(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id, line_a, _ = _cost_sheet_with_two_lines(client, headers)
    vendor = _vendor(client, headers)

    po = client.post(
        f"/cost-sheets/{cost_sheet_id}/purchase-orders",
        json={"vendor_id": vendor["id"], "lines": [{"cost_sheet_line_id": line_a["id"], "quantity": 500, "rate": 68}]},
        headers=headers,
    ).json()

    # Can't receive a draft PO.
    premature = client.post(
        f"/purchase-orders/{po['id']}/receive",
        json={"lines": [{"line_id": po["lines"][0]["id"], "received_qty": 200}]},
        headers=headers,
    )
    assert premature.status_code == 400

    issued = client.post(f"/purchase-orders/{po['id']}/issue", headers=headers)
    assert issued.status_code == 200, issued.text
    assert issued.json()["status"] == "issued"

    partial = client.post(
        f"/purchase-orders/{po['id']}/receive",
        json={"lines": [{"line_id": po["lines"][0]["id"], "received_qty": 200}]},
        headers=headers,
    )
    assert partial.status_code == 200, partial.text
    assert partial.json()["status"] == "partially_received"
    assert partial.json()["lines"][0]["balance_qty"] == 300

    full = client.post(
        f"/purchase-orders/{po['id']}/receive",
        json={"lines": [{"line_id": po["lines"][0]["id"], "received_qty": 500}]},
        headers=headers,
    )
    assert full.status_code == 200, full.text
    assert full.json()["status"] == "received"
    assert full.json()["lines"][0]["balance_qty"] == 0


def test_received_qty_cannot_exceed_ordered_qty(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id, line_a, _ = _cost_sheet_with_two_lines(client, headers)
    vendor = _vendor(client, headers)
    po = client.post(
        f"/cost-sheets/{cost_sheet_id}/purchase-orders",
        json={"vendor_id": vendor["id"], "lines": [{"cost_sheet_line_id": line_a["id"], "quantity": 500, "rate": 68}]},
        headers=headers,
    ).json()
    client.post(f"/purchase-orders/{po['id']}/issue", headers=headers)

    res = client.post(
        f"/purchase-orders/{po['id']}/receive",
        json={"lines": [{"line_id": po["lines"][0]["id"], "received_qty": 999}]},
        headers=headers,
    )
    assert res.status_code == 422


def test_cancelling_a_po_frees_its_lines_for_a_new_po(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id, line_a, _ = _cost_sheet_with_two_lines(client, headers)
    vendor = _vendor(client, headers)
    po = client.post(
        f"/cost-sheets/{cost_sheet_id}/purchase-orders",
        json={"vendor_id": vendor["id"], "lines": [{"cost_sheet_line_id": line_a["id"], "quantity": 500, "rate": 68}]},
        headers=headers,
    ).json()

    cancelled = client.post(f"/purchase-orders/{po['id']}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    retried = client.post(
        f"/cost-sheets/{cost_sheet_id}/purchase-orders",
        json={"vendor_id": vendor["id"], "lines": [{"cost_sheet_line_id": line_a["id"], "quantity": 500, "rate": 70}]},
        headers=headers,
    )
    assert retried.status_code == 201, retried.text


def test_received_purchase_order_cannot_be_cancelled(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id, line_a, _ = _cost_sheet_with_two_lines(client, headers)
    vendor = _vendor(client, headers)
    po = client.post(
        f"/cost-sheets/{cost_sheet_id}/purchase-orders",
        json={"vendor_id": vendor["id"], "lines": [{"cost_sheet_line_id": line_a["id"], "quantity": 500, "rate": 68}]},
        headers=headers,
    ).json()
    client.post(f"/purchase-orders/{po['id']}/issue", headers=headers)
    client.post(
        f"/purchase-orders/{po['id']}/receive",
        json={"lines": [{"line_id": po["lines"][0]["id"], "received_qty": 500}]},
        headers=headers,
    )

    res = client.post(f"/purchase-orders/{po['id']}/cancel", headers=headers)
    assert res.status_code == 400


def test_consumption_sheet_reflects_the_po_once_raised(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id, line_a, line_b = _cost_sheet_with_two_lines(client, headers)
    vendor = _vendor(client, headers, name="Turf Supplier")

    client.post(
        f"/cost-sheets/{cost_sheet_id}/purchase-orders",
        json={
            "vendor_id": vendor["id"],
            "lines": [{"cost_sheet_line_id": line_b["id"], "quantity": 200, "rate": 900}],
            "delivery_date": "2026-11-15",
            "eway_bill_no": "EWB123",
        },
        headers=headers,
    )

    rows = client.get(f"/cost-sheets/{cost_sheet_id}/consumption-sheet", headers=headers).json()
    turf_row = next(r for r in rows if r["id"] == line_b["id"])
    steel_row = next(r for r in rows if r["id"] == line_a["id"])

    assert turf_row["vendor"] == "Turf Supplier"
    assert turf_row["po_no"].startswith("PO-")
    assert turf_row["delivery_date"] == "2026-11-15"
    assert turf_row["received_qty"] == 0
    assert turf_row["balance_qty"] == 200

    # The line with no PO yet stays genuinely null, not a fabricated zero.
    assert steel_row["vendor"] is None
    assert steel_row["po_no"] is None
    assert steel_row["delivery_date"] is None
    assert steel_row["received_qty"] is None
    assert steel_row["balance_qty"] is None
