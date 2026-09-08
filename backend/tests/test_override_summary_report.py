from datetime import UTC, datetime

from app.core.security import hash_password
from app.models.user import User, UserRole

TODAY = datetime.now(UTC).date().isoformat()


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


def _create_client_record(client, headers, name="Override Report Client"):
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


def _draft_cost_sheet(client, headers, project_id):
    res = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": 500000}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_override(client, headers, cost_sheet_id, setting_key, master_value, override_value, reason="test"):
    res = client.post(
        "/overrides",
        json={
            "document_type": "cost_sheet", "document_id": cost_sheet_id, "setting_key": setting_key,
            "master_value": master_value, "override_value": override_value, "reason": reason,
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def _generate(client, headers, **overrides):
    payload = {"report_type": "override_summary", "period_from": TODAY, "period_to": TODAY, **overrides}
    return client.post("/reports/generate", json=payload, headers=headers)


def test_override_summary_ranks_by_frequency_and_finds_the_candidate_value(client, director_user):
    """Q.2 rule 2: 'which settings are overridden most often -> candidates
    for a master update.'"""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _draft_cost_sheet(client, headers, project_id)

    # site_establishment_percent overridden 3x (candidate value "8", used twice)
    _create_override(client, headers, cost_sheet_id, "site_establishment_percent", "6", "8")
    _create_override(client, headers, cost_sheet_id, "site_establishment_percent", "6", "8")
    _create_override(client, headers, cost_sheet_id, "site_establishment_percent", "6", "7")
    # contingency_civil_percent overridden once
    _create_override(client, headers, cost_sheet_id, "contingency_civil_percent", "5", "10")

    report = _generate(client, headers).json()
    assert report["status"] == "draft"
    content = report["content"]
    assert content["total_overrides"] == 4

    rows = content["rows"]
    assert rows[0]["setting_key"] == "site_establishment_percent"
    assert rows[0]["override_count"] == 3
    assert rows[0]["most_common_override_value"] == "8"
    assert rows[0]["value_breakdown"] == {"8": 2, "7": 1}
    assert rows[0]["document_types"] == ["cost_sheet"]

    assert rows[1]["setting_key"] == "contingency_civil_percent"
    assert rows[1]["override_count"] == 1


def test_overrides_outside_the_period_are_excluded(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    cost_sheet_id = _draft_cost_sheet(client, headers, project_id)
    _create_override(client, headers, cost_sheet_id, "site_establishment_percent", "6", "8")

    report = _generate(client, headers, period_from="2020-01-01", period_to="2020-01-31").json()
    assert report["content"]["total_overrides"] == 0
    assert report["content"]["rows"] == []


def test_only_director_can_generate_or_view_override_summary(client, director_user, db_session):
    """Q.2 rule 2 names only the Director -- narrower than Margin's PM/Director."""
    director_headers = _director_headers(client, director_user)
    pm_headers = _pm_headers(client, db_session)

    res = _generate(client, pm_headers)
    assert res.status_code == 403

    report = _generate(client, director_headers).json()
    get_res = client.get(f"/reports/{report['id']}", headers=pm_headers)
    assert get_res.status_code == 403

    list_res = client.get("/reports", headers=pm_headers)
    assert all(r["report_type"] != "override_summary" for r in list_res.json())

    director_list = client.get("/reports", headers=director_headers)
    assert any(r["id"] == report["id"] for r in director_list.json())


def test_override_summary_is_draft_until_director_releases_it(client, director_user):
    headers = _director_headers(client, director_user)
    report = _generate(client, headers).json()
    assert report["status"] == "draft"

    release = client.post(f"/reports/{report['id']}/release", headers=headers)
    assert release.status_code == 200
    assert release.json()["status"] == "released"


def test_override_summary_has_a_sha256_integrity_hash(client, director_user):
    headers = _director_headers(client, director_user)
    report = _generate(client, headers).json()
    assert len(report["file_hash"]) == 64
    assert report["source_tables"] == "OVERRIDES"
