from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _sales_headers(client, db_session):
    user = User(name="Test Sales", email="sales@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.SALES)
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales@test.local")


def _create_client_record(client, headers, name="Revision Client"):
    res = client.post("/clients", json={"name": name, "type": "school"}, headers=headers)
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


def _verified_cost_sheet(client, headers, project_id, cost_total=850000):
    cost_sheet_id = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_total}, headers=headers
    ).json()["id"]
    res = client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    assert res.status_code == 200, res.text
    return cost_sheet_id


def _sent_estimate(client, headers, project_id, project_sport_id, cost_for_option=850000):
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost_for_option}]},
        headers=headers,
    ).json()
    res = client.post(f"/estimates/{estimate['id']}/send", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _approve_option(client, headers, estimate_id, option_id):
    res = client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert res.status_code == 200, res.text


def _released_quotation(client, headers, project_id, estimate_id, option_id):
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    res = client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _sent_quotation(client, headers, project_id, estimate_id, option_id):
    quotation = _released_quotation(client, headers, project_id, estimate_id, option_id)
    res = client.post(f"/quotations/{quotation['id']}/send", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


# ---------------------------------------------------------------------------
# Estimate revision
# ---------------------------------------------------------------------------


def test_cannot_revise_a_draft_estimate(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 850000}]},
        headers=headers,
    ).json()

    res = client.post(
        f"/estimates/{estimate['id']}/revise",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 900000}]},
        headers=headers,
    )
    assert res.status_code == 400
    assert "sent" in res.json()["detail"].lower()


def test_revising_a_sent_estimate_creates_a_new_revision_and_supersedes_the_old(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)

    res = client.post(
        f"/estimates/{estimate['id']}/revise",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 900000}]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    revised = res.json()
    assert revised["id"] != estimate["id"]
    assert revised["revision_major"] == 2
    assert revised["document_no"].endswith("-R2")
    assert revised["status"] == "draft"
    assert revised["options"][0]["cost_for_option"] == 900000

    old = client.get(f"/estimates/{estimate['id']}", headers=headers).json()
    assert old["status"] == "superseded"


def test_unchanged_option_keeps_its_frozen_price_by_default(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)
    original_price_low = estimate["options"][0]["price_low"]
    original_price_high = estimate["options"][0]["price_high"]

    # Widen the price range setting -- if pricing were recomputed, the
    # unchanged option's price band would change.
    client.post("/settings", json={"key": "estimate_price_range_percent", "value": "20.0"}, headers=headers)

    res = client.post(
        f"/estimates/{estimate['id']}/revise",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 850000}]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    option = res.json()["options"][0]
    assert option["price_low"] == original_price_low
    assert option["price_high"] == original_price_high


def test_changed_option_cost_is_repriced(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)
    original_price_low = estimate["options"][0]["price_low"]

    res = client.post(
        f"/estimates/{estimate['id']}/revise",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 1000000}]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    option = res.json()["options"][0]
    assert option["cost_for_option"] == 1000000
    assert option["price_low"] > original_price_low


def test_refresh_pricing_recomputes_even_an_unchanged_option(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)
    original_price_low = estimate["options"][0]["price_low"]

    client.post("/settings", json={"key": "estimate_price_range_percent", "value": "20.0"}, headers=headers)

    res = client.post(
        f"/estimates/{estimate['id']}/revise",
        json={
            "options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 850000}],
            "refresh_pricing": True,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["options"][0]["price_low"] != original_price_low


def test_new_revision_options_start_back_at_pending(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)
    _approve_option(client, headers, estimate["id"], estimate["options"][0]["id"])

    res = client.post(
        f"/estimates/{estimate['id']}/revise",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 900000}]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["options"][0]["client_status"] == "pending"


def test_revising_an_estimate_writes_an_audit_log_entry(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)

    client.post(
        f"/estimates/{estimate['id']}/revise",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 900000}]},
        headers=headers,
    )

    entries = client.get(
        "/audit-log", params={"document_type": "estimate", "document_id": estimate["id"]}, headers=headers
    ).json()
    entry = next(e for e in entries if e["field"] == "status" and e["new_value"] == "superseded")
    assert "Major revision created" in entry["reason"]


def test_sales_cannot_revise_an_estimate(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    project_id = _create_project(client, director_headers, _create_client_record(client, director_headers))
    project_sport_id = _add_project_sport(client, director_headers, project_id)
    _verified_cost_sheet(client, director_headers, project_id)
    estimate = _sent_estimate(client, director_headers, project_id, project_sport_id)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/estimates/{estimate['id']}/revise",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 900000}]},
        headers=sales_headers,
    )
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Quotation revision
# ---------------------------------------------------------------------------


def test_cannot_revise_a_draft_quotation(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)
    option_id = estimate["options"][0]["id"]
    _approve_option(client, headers, estimate["id"], option_id)
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id]},
        headers=headers,
    ).json()

    res = client.post(
        f"/quotations/{quotation['id']}/revise",
        json={"included_option_ids": [option_id], "discount_value": 5000},
        headers=headers,
    )
    assert res.status_code == 400


def test_revising_a_released_quotation_returns_it_to_draft_in_place(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)
    option_id = estimate["options"][0]["id"]
    _approve_option(client, headers, estimate["id"], option_id)
    quotation = _released_quotation(client, headers, project_id, estimate["id"], option_id)

    res = client.post(
        f"/quotations/{quotation['id']}/revise",
        json={"included_option_ids": [option_id], "discount_type": "percent", "discount_value": 5},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["id"] == quotation["id"]
    assert body["status"] == "draft"
    assert body["discount_value"] == 5


def test_revising_a_sent_quotation_creates_a_new_revision(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)
    option_id = estimate["options"][0]["id"]
    _approve_option(client, headers, estimate["id"], option_id)
    quotation = _sent_quotation(client, headers, project_id, estimate["id"], option_id)

    res = client.post(
        f"/quotations/{quotation['id']}/revise",
        json={"included_option_ids": [option_id], "discount_type": "percent", "discount_value": 5},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    revised = res.json()
    assert revised["id"] != quotation["id"]
    assert revised["revision_major"] == 2
    assert revised["document_no"].endswith("-R2")
    assert revised["status"] == "draft"
    assert revised["discount_value"] == 5

    old = client.get(f"/quotations/{quotation['id']}", headers=headers).json()
    assert old["status"] == "superseded"


def test_unchanged_quotation_content_keeps_frozen_pricing(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)
    option_id = estimate["options"][0]["id"]
    _approve_option(client, headers, estimate["id"], option_id)
    quotation = _sent_quotation(client, headers, project_id, estimate["id"], option_id)
    original_total = quotation["quotation_total"]

    # Change the GST rate -- if pricing were recomputed, the total would move.
    client.post("/settings", json={"key": "gst_rate_percent", "value": "12.0"}, headers=headers)

    res = client.post(
        f"/quotations/{quotation['id']}/revise",
        json={"included_option_ids": [option_id], "discount_type": quotation["discount_type"], "discount_value": quotation["discount_value"]},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["quotation_total"] == original_total


def test_refresh_pricing_recomputes_an_unchanged_quotation(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)
    option_id = estimate["options"][0]["id"]
    _approve_option(client, headers, estimate["id"], option_id)
    quotation = _sent_quotation(client, headers, project_id, estimate["id"], option_id)
    original_total = quotation["quotation_total"]

    client.post("/settings", json={"key": "gst_rate_percent", "value": "12.0"}, headers=headers)

    res = client.post(
        f"/quotations/{quotation['id']}/revise",
        json={
            "included_option_ids": [option_id],
            "discount_type": quotation["discount_type"],
            "discount_value": quotation["discount_value"],
            "refresh_pricing": True,
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["quotation_total"] != original_total


def test_revising_a_sent_quotation_writes_an_audit_log_entry(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)
    option_id = estimate["options"][0]["id"]
    _approve_option(client, headers, estimate["id"], option_id)
    quotation = _sent_quotation(client, headers, project_id, estimate["id"], option_id)

    client.post(
        f"/quotations/{quotation['id']}/revise",
        json={"included_option_ids": [option_id], "discount_value": 1000},
        headers=headers,
    )

    entries = client.get(
        "/audit-log", params={"document_type": "quotation", "document_id": quotation["id"]}, headers=headers
    ).json()
    entry = next(e for e in entries if e["field"] == "status" and e["new_value"] == "superseded")
    assert "Major revision created" in entry["reason"]
