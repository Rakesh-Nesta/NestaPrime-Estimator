"""Amendment 50 (Section 54): expected-payment milestones, receipts linked to
them, derived status/overdue/outstanding, audit of every money write, the
org-wide Payments list and the Overview's payment figures.

Reconciliation only: nothing here computes GST, TDS or invoices, and nothing
is inferred from the client's free-text payment terms."""
from datetime import date, timedelta

from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _role_headers(client, db_session, role, email):
    user = User(name=f"Test {role.value}", email=email, hashed_password=hash_password("TestPass!1"), role=role)
    db_session.add(user)
    db_session.commit()
    return _login(client, email)


def _won_work_order(client, headers, name="Payments Client", cost_for_option=850000):
    """A Work Order on a Won Quotation; returns (work_order_id, project_id, order_value)."""
    client_id = client.post("/clients", json={"name": name, "type": "school"}, headers=headers).json()["id"]
    fields = {
        "client_id": client_id, "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
        "building_status": "open_air", "site_access": "good", "power_available": "yes",
        "water_available": True, "package": "standard",
    }
    project_id = client.post("/projects", json=fields, headers=headers).json()["id"]
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == "badminton")
    project_sport_id = client.post(
        f"/projects/{project_id}/sports", json={"sport_id": sport_id, "building_status": "open_air"}, headers=headers
    ).json()["id"]
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
    order_value = client.get(f"/projects/{project_id}/quotations", headers=headers).json()[0]["quotation_total"]
    work_order_id = client.post(f"/quotations/{quotation_id}/work-order", headers=headers).json()["id"]
    return work_order_id, project_id, order_value


def _milestone(client, headers, work_order_id, amount, due, name="Advance", **extra):
    res = client.post(
        f"/work-orders/{work_order_id}/payment-milestones",
        json={"name": name, "amount_due": amount, "due_date": due.isoformat(), **extra},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def _receipt(client, headers, work_order_id, amount, milestone_id=None, tds=None, name="Receipt", when=None):
    body = {
        "milestone_name": name, "amount_received": amount,
        "received_date": (when or date.today()).isoformat(),
    }
    if milestone_id:
        body["milestone_id"] = milestone_id
    if tds is not None:
        body["gst_tds_amount"] = tds
    res = client.post(f"/work-orders/{work_order_id}/payment-entries", json=body, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _milestones(client, headers, work_order_id):
    res = client.get(f"/work-orders/{work_order_id}/payment-milestones", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _audit(client, headers, document_type, document_id):
    res = client.get("/audit-log", params={"document_type": document_type, "document_id": document_id}, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


# --- creating milestones ---------------------------------------------------


def test_a_milestone_starts_pending_and_not_overdue(client, director_user):
    headers = _director_headers(client, director_user)
    wo, _p, value = _won_work_order(client, headers)
    m = _milestone(client, headers, wo, 100000, date.today() + timedelta(days=10), notes="On site start")

    assert m["status"] == "pending"
    assert m["overdue"] is False
    assert m["received_amount"] == 0 and m["settled_amount"] == 0
    assert m["outstanding_amount"] == 100000
    assert m["notes"] == "On site start"


def test_milestone_validation(client, director_user):
    headers = _director_headers(client, director_user)
    wo, _p, _v = _won_work_order(client, headers)
    due = (date.today() + timedelta(days=5)).isoformat()

    for bad in ({"name": "", "amount_due": 10, "due_date": due},
                {"name": "X", "amount_due": 0, "due_date": due},
                {"name": "X", "amount_due": -5, "due_date": due},
                {"name": "X", "amount_due": 10}):
        res = client.post(f"/work-orders/{wo}/payment-milestones", json=bad, headers=headers)
        assert res.status_code == 422, (bad, res.text)


def test_milestones_cannot_total_more_than_the_order_value(client, director_user):
    headers = _director_headers(client, director_user)
    wo, _p, value = _won_work_order(client, headers)
    due = date.today() + timedelta(days=5)

    first = _milestone(client, headers, wo, value - 1000, due, name="Bulk")
    res = client.post(
        f"/work-orders/{wo}/payment-milestones",
        json={"name": "Too much", "amount_due": 1000.01, "due_date": due.isoformat()},
        headers=headers,
    )
    assert res.status_code == 400
    assert "more than this Work Order's value" in res.json()["detail"]

    # Exactly the remaining balance is allowed...
    _milestone(client, headers, wo, 1000, due, name="Balance")
    # ...and so is shrinking a milestone, but growing one past the cap is not.
    assert client.patch(f"/payment-milestones/{first['id']}", json={"amount_due": value - 2000}, headers=headers).status_code == 200
    res = client.patch(f"/payment-milestones/{first['id']}", json={"amount_due": value}, headers=headers)
    assert res.status_code == 400


def test_a_milestone_for_an_unknown_work_order_is_404(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/work-orders/00000000-0000-0000-0000-000000000000/payment-milestones",
        json={"name": "X", "amount_due": 10, "due_date": date.today().isoformat()},
        headers=headers,
    )
    assert res.status_code == 404


# --- receipts, statuses, overdue ------------------------------------------


def test_status_moves_pending_to_part_paid_to_paid(client, director_user):
    headers = _director_headers(client, director_user)
    wo, _p, _v = _won_work_order(client, headers)
    m = _milestone(client, headers, wo, 100000, date.today() + timedelta(days=3))

    _receipt(client, headers, wo, 40000, milestone_id=m["id"])
    [part] = _milestones(client, headers, wo)
    assert part["status"] == "part_paid"
    assert part["received_amount"] == 40000 and part["outstanding_amount"] == 60000

    _receipt(client, headers, wo, 60000, milestone_id=m["id"])
    [paid] = _milestones(client, headers, wo)
    assert paid["status"] == "paid"
    assert paid["outstanding_amount"] == 0


def test_overdue_is_strictly_past_the_due_date_and_never_when_paid(client, director_user):
    headers = _director_headers(client, director_user)
    wo, _p, _v = _won_work_order(client, headers)
    today = date.today()
    yesterday = _milestone(client, headers, wo, 10000, today - timedelta(days=1), name="Yesterday")
    due_today = _milestone(client, headers, wo, 10000, today, name="Today")
    tomorrow = _milestone(client, headers, wo, 10000, today + timedelta(days=1), name="Tomorrow")

    by_name = {m["name"]: m for m in _milestones(client, headers, wo)}
    assert by_name["Yesterday"]["overdue"] is True
    assert by_name["Today"]["overdue"] is False  # due today is not yet overdue
    assert by_name["Tomorrow"]["overdue"] is False

    # Paying the overdue milestone in full clears the flag.
    _receipt(client, headers, wo, 10000, milestone_id=yesterday["id"])
    by_name = {m["name"]: m for m in _milestones(client, headers, wo)}
    assert by_name["Yesterday"]["status"] == "paid" and by_name["Yesterday"]["overdue"] is False
    assert due_today["id"] and tomorrow["id"]


def test_tds_withheld_counts_as_settled_and_is_shown_separately(client, director_user):
    headers = _director_headers(client, director_user)
    wo, _p, value = _won_work_order(client, headers)
    m = _milestone(client, headers, wo, 100000, date.today() + timedelta(days=3))

    _receipt(client, headers, wo, 98000, milestone_id=m["id"], tds=2000)
    [row] = _milestones(client, headers, wo)
    assert row["received_amount"] == 98000
    assert row["tds_amount"] == 2000
    assert row["settled_amount"] == 100000
    assert row["status"] == "paid"

    summary = client.get(f"/work-orders/{wo}/payment-summary", headers=headers).json()
    assert summary["total_received"] == 98000
    assert summary["total_tds"] == 2000
    assert summary["outstanding"] == round(value - 100000, 2)


def test_an_unlinked_receipt_counts_toward_totals_but_no_milestone(client, director_user):
    headers = _director_headers(client, director_user)
    wo, _p, value = _won_work_order(client, headers)
    m = _milestone(client, headers, wo, 50000, date.today() + timedelta(days=3))
    _receipt(client, headers, wo, 25000)  # not against any milestone

    [row] = _milestones(client, headers, wo)
    assert row["received_amount"] == 0 and row["status"] == "pending"
    summary = client.get(f"/work-orders/{wo}/payment-summary", headers=headers).json()
    assert summary["total_received"] == 25000
    assert summary["outstanding"] == round(value - 25000, 2)
    assert m["id"]


def test_receipts_beyond_order_value_are_flagged_not_refused(client, director_user):
    headers = _director_headers(client, director_user)
    wo, _p, value = _won_work_order(client, headers)
    _receipt(client, headers, wo, value + 5000)

    summary = client.get(f"/work-orders/{wo}/payment-summary", headers=headers).json()
    assert summary["over_received"] is True
    assert summary["outstanding"] == 0  # never negative


def test_a_receipt_cannot_link_to_another_work_orders_milestone(client, director_user):
    headers = _director_headers(client, director_user)
    wo_a, _pa, _va = _won_work_order(client, headers, name="Link Client A")
    wo_b, _pb, _vb = _won_work_order(client, headers, name="Link Client B")
    milestone_b = _milestone(client, headers, wo_b, 10000, date.today() + timedelta(days=3))

    res = client.post(
        f"/work-orders/{wo_a}/payment-entries",
        json={"milestone_name": "X", "amount_received": 5000, "received_date": date.today().isoformat(),
              "milestone_id": milestone_b["id"]},
        headers=headers,
    )
    assert res.status_code == 400
    assert "does not belong to this Work Order" in res.json()["detail"]

    own = _receipt(client, headers, wo_a, 5000)
    res = client.patch(f"/payment-entries/{own['id']}", json={"milestone_id": milestone_b["id"]}, headers=headers)
    assert res.status_code == 400


# --- editing, deleting, audit ---------------------------------------------


def test_a_receipt_can_be_edited_and_the_edit_is_audit_logged(client, director_user):
    headers = _director_headers(client, director_user)
    wo, _p, _v = _won_work_order(client, headers)
    entry = _receipt(client, headers, wo, 12345, name="Typo")

    res = client.patch(
        f"/payment-entries/{entry['id']}", json={"amount_received": 12000, "notes": "Corrected"}, headers=headers
    )
    assert res.status_code == 200, res.text
    assert res.json()["amount_received"] == 12000

    entries = _audit(client, headers, "work_order_payment_entry", entry["id"])
    by_field = {e["field"]: e for e in entries}
    assert set(by_field) == {"created", "amount_received", "notes"}
    assert by_field["amount_received"]["old_value"] == "12345.00"
    assert by_field["amount_received"]["new_value"] == "12000.00"


def test_editing_a_receipt_with_unchanged_values_writes_no_audit_row(client, director_user):
    headers = _director_headers(client, director_user)
    wo, _p, _v = _won_work_order(client, headers)
    entry = _receipt(client, headers, wo, 5000, name="Same")
    client.patch(f"/payment-entries/{entry['id']}", json={"amount_received": 5000}, headers=headers)

    fields = [e["field"] for e in _audit(client, headers, "work_order_payment_entry", entry["id"])]
    assert fields == ["created"]


def test_a_receipt_can_be_relinked_and_unlinked(client, director_user):
    headers = _director_headers(client, director_user)
    wo, _p, _v = _won_work_order(client, headers)
    m = _milestone(client, headers, wo, 20000, date.today() + timedelta(days=3))
    entry = _receipt(client, headers, wo, 20000)

    assert client.patch(f"/payment-entries/{entry['id']}", json={"milestone_id": m["id"]}, headers=headers).status_code == 200
    assert _milestones(client, headers, wo)[0]["status"] == "paid"

    res = client.patch(f"/payment-entries/{entry['id']}", json={"milestone_id": None}, headers=headers)
    assert res.status_code == 200 and res.json()["milestone_id"] is None
    assert _milestones(client, headers, wo)[0]["status"] == "pending"


def test_required_receipt_fields_cannot_be_cleared(client, director_user):
    headers = _director_headers(client, director_user)
    wo, _p, _v = _won_work_order(client, headers)
    entry = _receipt(client, headers, wo, 5000)
    for field in ("amount_received", "received_date", "milestone_name"):
        res = client.patch(f"/payment-entries/{entry['id']}", json={field: None}, headers=headers)
        assert res.status_code == 400, (field, res.text)
    res = client.patch(f"/payment-entries/{entry['id']}", json={"amount_received": 0}, headers=headers)
    assert res.status_code == 422


def test_receipts_cannot_be_deleted(client, director_user):
    headers = _director_headers(client, director_user)
    wo, _p, _v = _won_work_order(client, headers)
    entry = _receipt(client, headers, wo, 5000)
    assert client.delete(f"/payment-entries/{entry['id']}", headers=headers).status_code == 405


def test_editing_a_receipt_that_does_not_exist_is_404(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.patch(
        "/payment-entries/00000000-0000-0000-0000-000000000000", json={"amount_received": 5}, headers=headers
    )
    assert res.status_code == 404


def test_milestone_edits_and_creation_are_audit_logged(client, director_user):
    headers = _director_headers(client, director_user)
    wo, _p, _v = _won_work_order(client, headers)
    m = _milestone(client, headers, wo, 10000, date.today() + timedelta(days=3), name="Original")

    res = client.patch(f"/payment-milestones/{m['id']}", json={"name": "Renamed", "amount_due": 12000}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["name"] == "Renamed" and res.json()["amount_due"] == 12000

    by_field = {e["field"]: e for e in _audit(client, headers, "work_order_payment_milestone", m["id"])}
    assert set(by_field) == {"created", "name", "amount_due"}
    assert by_field["name"]["old_value"] == "Original" and by_field["name"]["new_value"] == "Renamed"

    for field in ("name", "amount_due", "due_date"):
        assert client.patch(f"/payment-milestones/{m['id']}", json={field: None}, headers=headers).status_code == 400


def test_a_milestone_can_be_deleted_and_is_audited_unless_receipts_are_linked(client, director_user):
    headers = _director_headers(client, director_user)
    wo, _p, _v = _won_work_order(client, headers)
    keep = _milestone(client, headers, wo, 10000, date.today() + timedelta(days=3), name="Keep")
    drop = _milestone(client, headers, wo, 10000, date.today() + timedelta(days=4), name="Drop")
    entry = _receipt(client, headers, wo, 4000, milestone_id=keep["id"])

    res = client.delete(f"/payment-milestones/{keep['id']}", headers=headers)
    assert res.status_code == 400
    assert "unlink them before deleting" in res.json()["detail"]

    assert client.delete(f"/payment-milestones/{drop['id']}", headers=headers).status_code == 204
    assert [m["name"] for m in _milestones(client, headers, wo)] == ["Keep"]
    assert "deleted" in [e["field"] for e in _audit(client, headers, "work_order_payment_milestone", drop["id"])]

    # Once the receipt is unlinked, the milestone can go.
    client.patch(f"/payment-entries/{entry['id']}", json={"milestone_id": None}, headers=headers)
    assert client.delete(f"/payment-milestones/{keep['id']}", headers=headers).status_code == 204
    assert client.delete(f"/payment-milestones/{keep['id']}", headers=headers).status_code == 404


# --- roles -----------------------------------------------------------------


def test_only_pm_and_director_can_write_and_ca_tax_can_read(client, director_user, db_session):
    director = _director_headers(client, director_user)
    wo, _p, _v = _won_work_order(client, director)
    m = _milestone(client, director, wo, 10000, date.today() + timedelta(days=3))
    entry = _receipt(client, director, wo, 3000, milestone_id=m["id"])
    body = {"name": "X", "amount_due": 10, "due_date": date.today().isoformat()}

    pm = _role_headers(client, db_session, UserRole.PM, "pm-pay@test.local")
    assert client.post(f"/work-orders/{wo}/payment-milestones", json=body, headers=pm).status_code == 201

    ca = _role_headers(client, db_session, UserRole.CA_TAX, "ca-pay@test.local")
    # ca_tax can read everything...
    assert client.get(f"/work-orders/{wo}/payment-milestones", headers=ca).status_code == 200
    assert client.get(f"/work-orders/{wo}/payment-entries", headers=ca).status_code == 200
    assert client.get(f"/work-orders/{wo}/payment-summary", headers=ca).status_code == 200
    assert client.get("/payments", headers=ca).status_code == 200
    # ...and change nothing.
    assert client.post(f"/work-orders/{wo}/payment-milestones", json=body, headers=ca).status_code == 403
    assert client.patch(f"/payment-milestones/{m['id']}", json={"name": "Y"}, headers=ca).status_code == 403
    assert client.delete(f"/payment-milestones/{m['id']}", headers=ca).status_code == 403
    assert client.patch(f"/payment-entries/{entry['id']}", json={"notes": "Y"}, headers=ca).status_code == 403
    receipt = {"milestone_name": "X", "amount_received": 1, "received_date": date.today().isoformat()}
    assert client.post(f"/work-orders/{wo}/payment-entries", json=receipt, headers=ca).status_code == 403


def test_sales_procurement_and_site_engineer_are_refused_everywhere(client, director_user, db_session):
    director = _director_headers(client, director_user)
    wo, _p, _v = _won_work_order(client, director)
    m = _milestone(client, director, wo, 10000, date.today() + timedelta(days=3))
    body = {"name": "X", "amount_due": 10, "due_date": date.today().isoformat()}

    for role, email in (
        (UserRole.SALES, "sales-pay@test.local"),
        (UserRole.PROCUREMENT, "proc-pay@test.local"),
        (UserRole.SITE_ENGINEER, "eng-pay@test.local"),
    ):
        headers = _role_headers(client, db_session, role, email)
        assert client.get("/payments", headers=headers).status_code == 403, role
        assert client.get(f"/work-orders/{wo}/payment-milestones", headers=headers).status_code == 403, role
        assert client.get(f"/work-orders/{wo}/payment-summary", headers=headers).status_code == 403, role
        assert client.post(f"/work-orders/{wo}/payment-milestones", json=body, headers=headers).status_code == 403, role
        assert client.patch(f"/payment-milestones/{m['id']}", json={"name": "Y"}, headers=headers).status_code == 403, role


def test_payments_endpoints_require_auth(client):
    assert client.get("/payments").status_code == 401
    assert client.get("/work-orders/00000000-0000-0000-0000-000000000000/payment-milestones").status_code == 401


# --- the org-wide list -----------------------------------------------------


def test_payments_lists_one_row_per_work_order_with_real_figures(client, director_user):
    headers = _director_headers(client, director_user)
    wo, project_id, value = _won_work_order(client, headers, name="List Client")
    m = _milestone(client, headers, wo, 50000, date.today() + timedelta(days=4))
    _receipt(client, headers, wo, 20000, milestone_id=m["id"], tds=500)

    rows = client.get("/payments", headers=headers).json()
    row = next(r for r in rows if r["work_order_id"] == wo)
    assert row["project_id"] == project_id
    assert row["client_name"] == "List Client"
    assert row["order_value"] == value
    assert row["total_received"] == 20000 and row["total_tds"] == 500
    assert row["outstanding"] == round(value - 20500, 2)
    assert row["milestone_count"] == 1 and row["milestones_total"] == 50000
    assert row["next_due_date"] == (date.today() + timedelta(days=4)).isoformat()
    assert row["overdue"] is False and row["overdue_amount"] == 0


def test_the_overdue_filter_search_and_ordering(client, director_user):
    headers = _director_headers(client, director_user)
    wo_late, project_late, _v1 = _won_work_order(client, headers, name="Zulu Late Client")
    wo_ok, _project_ok, _v2 = _won_work_order(client, headers, name="Alpha Fine Client")
    _milestone(client, headers, wo_late, 30000, date.today() - timedelta(days=2))
    _milestone(client, headers, wo_ok, 30000, date.today() + timedelta(days=9))

    rows = client.get("/payments", headers=headers).json()
    ids = [r["work_order_id"] for r in rows]
    assert ids.index(wo_late) < ids.index(wo_ok)  # overdue first

    overdue = client.get("/payments", params={"overdue": "true"}, headers=headers).json()
    assert [r["work_order_id"] for r in overdue] == [wo_late]
    assert overdue[0]["overdue_amount"] == 30000
    assert overdue[0]["overdue_milestones_count"] == 1

    not_overdue = client.get("/payments", params={"overdue": "false"}, headers=headers).json()
    assert wo_late not in [r["work_order_id"] for r in not_overdue]

    by_client = client.get("/payments", params={"search": "alpha fine"}, headers=headers).json()
    assert [r["work_order_id"] for r in by_client] == [wo_ok]
    late_no = next(r["project_no"] for r in rows if r["work_order_id"] == wo_late)
    by_project = client.get("/payments", params={"search": late_no.lower()}, headers=headers).json()
    assert [r["work_order_id"] for r in by_project] == [wo_late]
    assert project_late


def test_the_summary_endpoint_matches_the_list_row(client, director_user):
    headers = _director_headers(client, director_user)
    wo, _p, _v = _won_work_order(client, headers)
    _milestone(client, headers, wo, 10000, date.today() - timedelta(days=1))

    summary = client.get(f"/work-orders/{wo}/payment-summary", headers=headers).json()
    row = next(r for r in client.get("/payments", headers=headers).json() if r["work_order_id"] == wo)
    assert summary == row


# --- the Overview's figures -----------------------------------------------


def test_the_overview_shows_no_tracked_milestones_until_one_exists(client, director_user):
    headers = _director_headers(client, director_user)
    _won_work_order(client, headers)

    payments = client.get("/dashboard", headers=headers).json()["payments"]
    assert payments["tracked_milestones_count"] == 0
    assert payments["overdue_count"] == 0 and payments["overdue_amount"] == 0
    assert payments["work_orders_count"] == 1  # the Work Order exists; nothing is scheduled yet


def test_the_overview_figures_agree_with_the_payments_list(client, director_user):
    headers = _director_headers(client, director_user)
    wo_late, _p1, v1 = _won_work_order(client, headers, name="Overview Late")
    wo_ok, _p2, v2 = _won_work_order(client, headers, name="Overview Fine")
    late = _milestone(client, headers, wo_late, 40000, date.today() - timedelta(days=3))
    _milestone(client, headers, wo_ok, 25000, date.today() + timedelta(days=6))
    _receipt(client, headers, wo_late, 10000, milestone_id=late["id"])
    _receipt(client, headers, wo_ok, 5000, tds=100)

    overview = client.get("/dashboard", headers=headers).json()["payments"]
    rows = client.get("/payments", headers=headers).json()
    overdue_rows = client.get("/payments", params={"overdue": "true"}, headers=headers).json()

    assert overview["tracked_milestones_count"] == 2
    assert overview["overdue_count"] == len(overdue_rows) == 1
    assert overview["overdue_milestones_count"] == 1
    assert overview["overdue_amount"] == sum(r["overdue_amount"] for r in overdue_rows) == 30000
    assert overview["work_orders_count"] == len(rows)
    assert overview["awarded_value_total"] == round(sum(r["order_value"] for r in rows), 2)
    assert overview["cash_received_total"] == 15000
    assert overview["tds_total"] == 100
    assert overview["outstanding_total"] == round(sum(r["outstanding"] for r in rows), 2)
    assert v1 and v2


def test_the_overview_month_series_uses_award_date_and_received_date(client, director_user):
    headers = _director_headers(client, director_user)
    wo, _p, value = _won_work_order(client, headers)
    _receipt(client, headers, wo, 7000)
    long_ago = date.today().replace(day=1) - timedelta(days=400)
    _receipt(client, headers, wo, 999, when=long_ago)  # outside the six-month window

    months = client.get("/dashboard", headers=headers).json()["payments"]["months"]
    assert len(months) == 6
    this_month = months[-1]
    assert this_month["month"] == date.today().strftime("%Y-%m")
    assert this_month["awarded_value"] == value  # the Work Order was awarded now
    assert this_month["cash_received"] == 7000
    assert sum(m["cash_received"] for m in months) == 7000  # the 400-day-old receipt is not in the window
    assert [m["month"] for m in months] == sorted(m["month"] for m in months)


def test_the_overview_payments_block_is_role_gated(client, director_user, db_session):
    _director_headers(client, director_user)
    for role, email, expected in (
        (UserRole.PM, "pm-dash@test.local", True),
        (UserRole.CA_TAX, "ca-dash@test.local", True),
        (UserRole.SALES, "sales-dash@test.local", False),
        (UserRole.PROCUREMENT, "proc-dash@test.local", False),
        (UserRole.SITE_ENGINEER, "eng-dash@test.local", False),
    ):
        headers = _role_headers(client, db_session, role, email)
        res = client.get("/dashboard", headers=headers)
        assert res.status_code == 200, (role, res.text)
        assert (res.json()["payments"] is not None) is expected, role
