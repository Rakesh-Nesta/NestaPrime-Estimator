from datetime import UTC, datetime

from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _pm_headers(client, db_session):
    user = User(name="Test PM", email="pm@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.PM)
    db_session.add(user)
    db_session.commit()
    return _login(client, "pm@test.local")


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


def _create_project(client, headers, client_id):
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
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _add_project_sport(client, headers, project_id, sport_key="badminton"):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports",
        json={"sport_id": sport_id, "building_status": "open_air"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _released_quotation(client, headers, cost_for_option=850000, client_type="government"):
    """Full CS -> EST -> approved option -> NPQ -> released chain, reused
    from test_documents.py's pattern, reproducing K.2's worked example
    (government: cost 850000 -> selling 1,000,000, margin 15%)."""
    client_id = _create_client_record(client, headers, client_type=client_type)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)

    cs_res = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_for_option}, headers=headers)
    client.post(f"/cost-sheets/{cs_res.json()['id']}/verify", headers=headers)

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
    release_res = client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    assert release_res.status_code == 200, release_res.text
    return release_res.json()


TODAY = datetime.now(UTC).date().isoformat()  # must track the real run date -- quotations are released "now"


# ---------------------------------------------------------------------------
# Role gates (T.2 rule 3: matches the underlying data's own visibility)
# ---------------------------------------------------------------------------


def test_sales_can_generate_and_view_pipeline_report(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _released_quotation(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        "/reports/generate",
        json={"report_type": "pipeline", "period_from": TODAY, "period_to": TODAY},
        headers=sales_headers,
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["status"] == "released"  # nothing to gate for Pipeline
    assert body["content"]["quotations_released_in_period"]["count"] == 1


def test_sales_cannot_generate_or_view_margin_report(client, director_user, db_session):
    """K.3 / T.2 rule 3: Margin carries cost and margin, PM/Director only."""
    director_headers = _director_headers(client, director_user)
    quotation = _released_quotation(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    generate_res = client.post(
        "/reports/generate",
        json={"report_type": "margin", "period_from": TODAY, "period_to": TODAY},
        headers=sales_headers,
    )
    assert generate_res.status_code == 403

    # Even a margin report generated by the Director must stay hidden from Sales.
    director_margin = client.post(
        "/reports/generate",
        json={"report_type": "margin", "period_from": TODAY, "period_to": TODAY},
        headers=director_headers,
    ).json()
    view_attempt = client.get(f"/reports/{director_margin['id']}", headers=sales_headers)
    assert view_attempt.status_code == 403

    list_res = client.get("/reports", headers=sales_headers)
    assert all(r["report_type"] != "margin" for r in list_res.json())
    del quotation


def test_pm_can_generate_and_view_both_report_types(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _released_quotation(client, director_headers)

    pm_headers = _pm_headers(client, db_session)
    pipeline_res = client.post(
        "/reports/generate",
        json={"report_type": "pipeline", "period_from": TODAY, "period_to": TODAY},
        headers=pm_headers,
    )
    margin_res = client.post(
        "/reports/generate",
        json={"report_type": "margin", "period_from": TODAY, "period_to": TODAY},
        headers=pm_headers,
    )
    assert pipeline_res.status_code == 201
    assert margin_res.status_code == 201
    assert margin_res.json()["status"] == "draft"  # T.2 rule 4


def test_reports_require_auth(client):
    assert client.get("/reports").status_code == 401
    assert client.post("/reports/generate", json={}).status_code == 401


# ---------------------------------------------------------------------------
# Snapshot / release semantics (T.2 rules 2 and 4)
# ---------------------------------------------------------------------------


def test_regenerating_the_same_period_creates_a_new_row_not_an_edit(client, director_user):
    """T.2 rule 2: re-running the same period produces a new REPORTS row;
    the earlier one is never edited or deleted."""
    headers = _director_headers(client, director_user)
    _released_quotation(client, headers)

    first = client.post(
        "/reports/generate",
        json={"report_type": "pipeline", "period_from": TODAY, "period_to": TODAY},
        headers=headers,
    ).json()
    second = client.post(
        "/reports/generate",
        json={"report_type": "pipeline", "period_from": TODAY, "period_to": TODAY},
        headers=headers,
    ).json()

    assert first["id"] != second["id"]
    still_there = client.get(f"/reports/{first['id']}", headers=headers)
    assert still_there.status_code == 200
    assert still_there.json()["id"] == first["id"]


def test_margin_report_is_draft_until_director_releases_it(client, director_user, db_session):
    """T.2 rule 4: mirrors the Cost Sheet verification gate; PM cannot release."""
    director_headers = _director_headers(client, director_user)
    _released_quotation(client, director_headers)

    pm_headers = _pm_headers(client, db_session)
    report = client.post(
        "/reports/generate",
        json={"report_type": "margin", "period_from": TODAY, "period_to": TODAY},
        headers=pm_headers,
    ).json()
    assert report["status"] == "draft"

    pm_release_attempt = client.post(f"/reports/{report['id']}/release", headers=pm_headers)
    assert pm_release_attempt.status_code == 403

    director_release = client.post(f"/reports/{report['id']}/release", headers=director_headers)
    assert director_release.status_code == 200
    assert director_release.json()["status"] == "released"
    assert director_release.json()["released_by_id"] is not None

    second_release_attempt = client.post(f"/reports/{report['id']}/release", headers=director_headers)
    assert second_release_attempt.status_code == 400


def test_report_has_a_sha256_integrity_hash(client, director_user):
    """T.2 rule 2: 'a SHA-256 hash of its output, same integrity pattern as
    ATTACHMENTS.'"""
    headers = _director_headers(client, director_user)
    _released_quotation(client, headers)

    report = client.post(
        "/reports/generate",
        json={"report_type": "pipeline", "period_from": TODAY, "period_to": TODAY},
        headers=headers,
    ).json()
    assert len(report["file_hash"]) == 64
    int(report["file_hash"], 16)  # valid hex


def test_period_from_after_period_to_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/reports/generate",
        json={"report_type": "pipeline", "period_from": "2026-09-06", "period_to": "2026-09-01"},
        headers=headers,
    )
    assert res.status_code == 422


# ---------------------------------------------------------------------------
# Content correctness (T.1)
# ---------------------------------------------------------------------------


def test_pipeline_content_matches_the_released_quotation(client, director_user):
    headers = _director_headers(client, director_user)
    quotation = _released_quotation(client, headers, cost_for_option=850000)

    report = client.post(
        "/reports/generate",
        json={"report_type": "pipeline", "period_from": TODAY, "period_to": TODAY},
        headers=headers,
    ).json()
    pipeline = report["content"]["quotations_released_in_period"]
    assert pipeline["count"] == 1
    assert round(pipeline["total_amount"], 2) == round(quotation["quotation_total"], 2)
    assert pipeline["by_status"] == {"released": 1}
    assert "badminton" in {name.lower() for name in pipeline["by_sport"]}
    assert report["content"]["estimates"]["created"] == 1


def test_margin_content_carries_cost_and_floor_comparison_hidden_from_pipeline(client, director_user):
    """T.1: Margin carries cost_price/selling/margin% against the floor --
    exactly the figures K.3 keeps off the Pipeline report and off Sales."""
    headers = _director_headers(client, director_user)
    quotation = _released_quotation(client, headers, cost_for_option=850000)

    margin_report = client.post(
        "/reports/generate",
        json={"report_type": "margin", "period_from": TODAY, "period_to": TODAY},
        headers=headers,
    ).json()
    line = margin_report["content"]["quotations"][0]
    assert line["document_no"] == quotation["document_no"]
    assert round(line["cost_total"], 2) == 850000.00
    assert round(line["margin_percent"], 1) == 15.0
    assert line["below_floor"] is False
    assert margin_report["content"]["summary"]["count"] == 1
    assert round(margin_report["content"]["summary"]["average_margin_percent"], 1) == 15.0

    pipeline_report = client.post(
        "/reports/generate",
        json={"report_type": "pipeline", "period_from": TODAY, "period_to": TODAY},
        headers=headers,
    ).json()
    assert "cost_total" not in pipeline_report["content"]["quotations_released_in_period"]


def test_a_period_with_no_activity_produces_an_empty_but_valid_report(client, director_user):
    headers = _director_headers(client, director_user)
    report = client.post(
        "/reports/generate",
        json={"report_type": "pipeline", "period_from": "2020-01-01", "period_to": "2020-01-31"},
        headers=headers,
    ).json()
    assert report["content"]["quotations_released_in_period"]["count"] == 0
    assert report["content"]["quotations_released_in_period"]["total_amount"] == 0
