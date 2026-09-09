from datetime import UTC, datetime

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


def _create_client_record(client, headers, name="Rejection Reason Client"):
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


def _sent_estimate(client, headers, cost_for_option=850000):
    """CS -> Verified, EST -> Sent. Rejection only makes sense once the
    client has actually seen the Estimate."""
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cs_id = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_for_option}, headers=headers).json()["id"]
    client.post(f"/cost-sheets/{cs_id}/verify", headers=headers)
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost_for_option}]},
        headers=headers,
    ).json()
    res = client.post(f"/estimates/{estimate['id']}/send", headers=headers)
    assert res.status_code == 200, res.text
    return project_id, estimate["id"], estimate["options"][0]["id"]


def test_rejecting_without_a_reason_is_rejected_with_422(client, director_user):
    headers = _director_headers(client, director_user)
    _, estimate_id, option_id = _sent_estimate(client, headers)

    res = client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "rejected"},
        headers=headers,
    )
    assert res.status_code == 422
    assert "rejection_reason" in res.json()["detail"]


def test_rejecting_with_a_reason_succeeds_and_is_stored(client, director_user):
    headers = _director_headers(client, director_user)
    _, estimate_id, option_id = _sent_estimate(client, headers)

    res = client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "rejected", "rejection_reason": "competitor"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["client_status"] == "rejected"
    assert body["rejection_reason"] == "competitor"


def test_sales_can_reject_with_a_reason(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, estimate_id, option_id = _sent_estimate(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "rejected", "rejection_reason": "price"},
        headers=sales_headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["rejection_reason"] == "price"


def test_re_approving_clears_the_rejection_reason(client, director_user):
    headers = _director_headers(client, director_user)
    _, estimate_id, option_id = _sent_estimate(client, headers)
    client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "rejected", "rejection_reason": "timing"},
        headers=headers,
    )

    res = client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "reconsidered"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["rejection_reason"] is None


def test_rejection_writes_an_audit_log_entry_with_the_reason(client, director_user):
    headers = _director_headers(client, director_user)
    _, estimate_id, option_id = _sent_estimate(client, headers)
    client.patch(
        f"/estimates/{estimate_id}/options/{option_id}/client-status",
        json={"client_status": "rejected", "rejection_reason": "scope"},
        headers=headers,
    )

    entries = client.get(
        "/audit-log", params={"document_type": "estimate_option", "document_id": option_id}, headers=headers
    ).json()
    entry = next(e for e in entries if e["field"] == "client_status" and e["new_value"] == "rejected")
    assert entry["reason"] == "scope"


TODAY = datetime.now(UTC).date().isoformat()


def test_pipeline_report_counts_rejected_options_by_reason(client, director_user):
    headers = _director_headers(client, director_user)
    _, estimate_id_1, option_id_1 = _sent_estimate(client, headers)
    _, estimate_id_2, option_id_2 = _sent_estimate(client, headers)
    client.patch(
        f"/estimates/{estimate_id_1}/options/{option_id_1}/client-status",
        json={"client_status": "rejected", "rejection_reason": "price"},
        headers=headers,
    )
    client.patch(
        f"/estimates/{estimate_id_2}/options/{option_id_2}/client-status",
        json={"client_status": "rejected", "rejection_reason": "price"},
        headers=headers,
    )

    res = client.post(
        "/reports/generate",
        json={"report_type": "pipeline", "period_from": TODAY, "period_to": TODAY},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    rejected_by_reason = res.json()["content"]["estimates"]["rejected_by_reason"]
    assert rejected_by_reason == {"price": 2}


def test_pipeline_report_has_no_rejected_bucket_when_nothing_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    _sent_estimate(client, headers)

    res = client.post(
        "/reports/generate",
        json={"report_type": "pipeline", "period_from": TODAY, "period_to": TODAY},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    assert res.json()["content"]["estimates"]["rejected_by_reason"] == {}
