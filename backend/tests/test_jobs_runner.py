from datetime import UTC, date, datetime, timedelta

from app.models.document import Estimate, Quotation


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _create_client_record(client, headers, name="Jobs Runner Client", client_type="school"):
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


def _sent_estimate(client, headers, project_id, project_sport_id, cost_for_option=850000):
    cs_id = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_for_option}, headers=headers).json()["id"]
    client.post(f"/cost-sheets/{cs_id}/verify", headers=headers)
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost_for_option}]},
        headers=headers,
    ).json()
    res = client.post(f"/estimates/{estimate['id']}/send", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _sent_quotation(client, headers, project_id, estimate_id, option_id):
    client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate_id, "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    res = client.post(f"/quotations/{quotation['id']}/send", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


# ---------------------------------------------------------------------------
# Estimate / Quotation auto-expiry (M.1)
# ---------------------------------------------------------------------------


def test_freshly_sent_estimate_is_not_expired(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_project_sport(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)
    assert estimate["status"] == "sent"


def test_estimate_past_its_validity_shows_expired(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_project_sport(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)

    row = db_session.query(Estimate).filter(Estimate.id == estimate["id"]).first()
    row.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    db_session.commit()

    fresh = client.get(f"/estimates/{estimate['id']}", headers=headers).json()
    assert fresh["status"] == "expired"


def test_cannot_record_a_client_decision_on_an_expired_estimate(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_project_sport(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)
    option_id = estimate["options"][0]["id"]

    row = db_session.query(Estimate).filter(Estimate.id == estimate["id"]).first()
    row.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    db_session.commit()

    res = client.patch(
        f"/estimates/{estimate['id']}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


def test_expired_estimate_can_still_be_revised(client, director_user, db_session):
    """The stored status stays 'sent' -- a late client can still get a
    fresh revision without the row first needing special handling."""
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_project_sport(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)

    row = db_session.query(Estimate).filter(Estimate.id == estimate["id"]).first()
    row.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    db_session.commit()

    res = client.post(
        f"/estimates/{estimate['id']}/revise",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": 900000}]},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["status"] == "draft"


def test_quotation_past_its_validity_shows_expired(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_project_sport(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)
    quotation = _sent_quotation(client, headers, project_id, estimate["id"], estimate["options"][0]["id"])

    row = db_session.query(Quotation).filter(Quotation.id == quotation["id"]).first()
    row.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    db_session.commit()

    fresh = client.get(f"/quotations/{quotation['id']}", headers=headers).json()
    assert fresh["status"] == "expired"


def test_expired_quotation_can_still_be_marked_won(client, director_user, db_session):
    """Stored status stays SENT -- a late-signed deal isn't blocked."""
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_project_sport(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)
    quotation = _sent_quotation(client, headers, project_id, estimate["id"], estimate["options"][0]["id"])

    row = db_session.query(Quotation).filter(Quotation.id == quotation["id"]).first()
    row.expires_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1)
    db_session.commit()

    res = client.post(
        f"/quotations/{quotation['id']}/mark-won",
        json={"reason": "Client accepted", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "won"


# ---------------------------------------------------------------------------
# SLA breach flag (M.3)
# ---------------------------------------------------------------------------


def test_fresh_draft_cost_sheet_is_not_sla_breached(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    cs = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": 850000}, headers=headers).json()
    assert cs["sla_breached"] is False


def test_zero_day_sla_setting_breaches_immediately(client, director_user):
    headers = _director_headers(client, director_user)
    client.post("/settings", json={"key": "approval_sla_working_days", "value": "0"}, headers=headers)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    cs = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": 850000}, headers=headers).json()
    assert cs["sla_breached"] is True


def test_verified_cost_sheet_is_never_sla_breached(client, director_user):
    headers = _director_headers(client, director_user)
    client.post("/settings", json={"key": "approval_sla_working_days", "value": "0"}, headers=headers)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    cs = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": 850000}, headers=headers).json()
    verified = client.post(f"/cost-sheets/{cs['id']}/verify", headers=headers).json()
    assert verified["sla_breached"] is False


def test_draft_quotation_sla_breach(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_project_sport(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)
    option_id = estimate["options"][0]["id"]
    client.patch(
        f"/estimates/{estimate['id']}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=headers,
    )

    client.post("/settings", json={"key": "approval_sla_working_days", "value": "0"}, headers=headers)
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    assert quotation["sla_breached"] is True

    released = client.post(f"/quotations/{quotation['id']}/release", headers=headers).json()
    assert released["sla_breached"] is False


# ---------------------------------------------------------------------------
# Tender reminders (Part L)
# ---------------------------------------------------------------------------


def _government_project_with_tender_details(client, headers, **tender_overrides):
    client_id = _create_client_record(client, headers, client_type="government")
    project_id = _create_project(client, headers, client_id)
    fields = {"retention_percent": 7.5, "performance_bg_percent": 4.0, "dlp_months": 12, **tender_overrides}
    res = client.post(f"/projects/{project_id}/tender-details", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def test_pre_bid_meeting_reminder_due_within_lookahead(client, director_user):
    headers = _director_headers(client, director_user)
    soon = (date.today() + timedelta(days=1)).isoformat()
    row = _government_project_with_tender_details(client, headers, pre_bid_meeting_date=soon)
    assert row["pre_bid_meeting_reminder_due"] is True


def test_pre_bid_meeting_reminder_not_due_far_out(client, director_user):
    headers = _director_headers(client, director_user)
    far = (date.today() + timedelta(days=10)).isoformat()
    row = _government_project_with_tender_details(client, headers, pre_bid_meeting_date=far)
    assert row["pre_bid_meeting_reminder_due"] is False


def test_bid_due_reminder_due_within_lookahead(client, director_user):
    headers = _director_headers(client, director_user)
    soon = date.today().isoformat()
    row = _government_project_with_tender_details(client, headers, bid_due_date=soon)
    assert row["bid_due_reminder_due"] is True


def test_emd_refund_reminder_due_after_validity_lapses(client, director_user):
    headers = _director_headers(client, director_user)
    past = (date.today() - timedelta(days=1)).isoformat()
    row = _government_project_with_tender_details(client, headers, emd_amount=50000, emd_validity_date=past)
    assert row["emd_refund_reminder_due"] is True


def test_emd_refund_reminder_not_due_before_validity_lapses(client, director_user):
    headers = _director_headers(client, director_user)
    future = (date.today() + timedelta(days=30)).isoformat()
    row = _government_project_with_tender_details(client, headers, emd_amount=50000, emd_validity_date=future)
    assert row["emd_refund_reminder_due"] is False


def test_reminders_survive_a_get_after_create(client, director_user):
    headers = _director_headers(client, director_user)
    soon = (date.today() + timedelta(days=1)).isoformat()
    row = _government_project_with_tender_details(client, headers, pre_bid_meeting_date=soon)
    fresh = client.get(f"/projects/{row['project_id']}/tender-details", headers=headers).json()
    assert fresh["pre_bid_meeting_reminder_due"] is True
