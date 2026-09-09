import io

from pypdf import PdfReader

from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _site_engineer_headers(client, db_session):
    user = User(
        name="Test Site Engineer", email="siteeng@test.local",
        hashed_password=hash_password("TestPass!1"), role=UserRole.SITE_ENGINEER,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "siteeng@test.local")


def _sales_headers(client, db_session):
    user = User(name="Test Sales", email="sales@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.SALES)
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales@test.local")


def _create_client_record(client, headers, name="Deviation Client"):
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


def _add_badminton(client, headers, project_id):
    """Badminton is seeded with playing_l_ft=44, playing_w_ft=20 (BWF)."""
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == "badminton")
    res = client.post(
        f"/projects/{project_id}/sports", json={"sport_id": sport_id, "building_status": "open_air"}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_no_deviation_before_any_actual_is_recorded(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    selection_id = _add_badminton(client, headers, project_id)

    selections = client.get(f"/projects/{project_id}/sports", headers=headers).json()
    sel = next(s for s in selections if s["id"] == selection_id)
    assert sel["actual_l_ft"] is None
    assert sel["dimension_deviations"] == []
    assert sel["dimension_deviation_status"] is None


def test_matching_actual_dimensions_are_green(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    selection_id = _add_badminton(client, headers, project_id)

    res = client.patch(
        f"/projects/{project_id}/sports/{selection_id}/actual-dimensions",
        json={"actual_l_ft": 44, "actual_w_ft": 20},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["dimension_deviation_status"] == "green"
    assert all(d["status"] == "green" for d in body["dimension_deviations"])


def test_small_deviation_is_amber(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    selection_id = _add_badminton(client, headers, project_id)

    # 45 vs standard 44 = 2.27% deviation on length -> amber (>= 2%, <= 10%)
    res = client.patch(
        f"/projects/{project_id}/sports/{selection_id}/actual-dimensions",
        json={"actual_l_ft": 45, "actual_w_ft": 20},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["dimension_deviation_status"] == "amber"
    length_dev = next(d for d in body["dimension_deviations"] if d["axis"] == "length")
    assert length_dev["status"] == "amber"
    width_dev = next(d for d in body["dimension_deviations"] if d["axis"] == "width")
    assert width_dev["status"] == "green"


def test_large_deviation_is_red(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    selection_id = _add_badminton(client, headers, project_id)

    # 50 vs standard 44 = 13.6% deviation -> red (> 10%)
    res = client.patch(
        f"/projects/{project_id}/sports/{selection_id}/actual-dimensions",
        json={"actual_l_ft": 50, "actual_w_ft": 20},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["dimension_deviation_status"] == "red"


def test_clearing_actual_dimensions_removes_the_deviation(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    selection_id = _add_badminton(client, headers, project_id)
    client.patch(
        f"/projects/{project_id}/sports/{selection_id}/actual-dimensions",
        json={"actual_l_ft": 50, "actual_w_ft": 20},
        headers=headers,
    )

    res = client.patch(
        f"/projects/{project_id}/sports/{selection_id}/actual-dimensions",
        json={"actual_l_ft": None, "actual_w_ft": None},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["actual_l_ft"] is None
    assert body["dimension_deviation_status"] is None


def test_site_engineer_can_record_actuals(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    project_id = _create_project(client, director_headers, _create_client_record(client, director_headers))
    selection_id = _add_badminton(client, director_headers, project_id)

    site_engineer_headers = _site_engineer_headers(client, db_session)
    res = client.patch(
        f"/projects/{project_id}/sports/{selection_id}/actual-dimensions",
        json={"actual_l_ft": 44, "actual_w_ft": 20},
        headers=site_engineer_headers,
    )
    assert res.status_code == 200, res.text


def test_sales_cannot_record_actuals(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    project_id = _create_project(client, director_headers, _create_client_record(client, director_headers))
    selection_id = _add_badminton(client, director_headers, project_id)

    sales_headers = _sales_headers(client, db_session)
    res = client.patch(
        f"/projects/{project_id}/sports/{selection_id}/actual-dimensions",
        json={"actual_l_ft": 44, "actual_w_ft": 20},
        headers=sales_headers,
    )
    assert res.status_code == 403


def test_recording_actuals_writes_an_audit_log_entry(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    selection_id = _add_badminton(client, headers, project_id)

    client.patch(
        f"/projects/{project_id}/sports/{selection_id}/actual-dimensions",
        json={"actual_l_ft": 44, "actual_w_ft": 20},
        headers=headers,
    )

    entries = client.get(
        "/audit-log", params={"document_type": "project_sport", "document_id": selection_id}, headers=headers
    ).json()
    entry = next(e for e in entries if e["field"] == "actual_dimensions")
    assert "44" in entry["new_value"] and "20" in entry["new_value"]


# ---------------------------------------------------------------------------
# PDF wiring (M.6): the Estimate and Quotation PDFs both print the
# "Standard vs. actual dimensions" table.
# ---------------------------------------------------------------------------


def _pdf_text(response) -> str:
    reader = PdfReader(io.BytesIO(response.content))
    return "\n".join(page.extract_text() for page in reader.pages)


def _verified_cost_sheet_and_estimate(client, headers, project_id, project_sport_id, cost_for_option=850000):
    cs_id = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_for_option}, headers=headers).json()["id"]
    client.post(f"/cost-sheets/{cs_id}/verify", headers=headers)
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost_for_option}]},
        headers=headers,
    ).json()
    return estimate


def test_estimate_pdf_shows_not_yet_recorded_before_any_actual(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_badminton(client, headers, project_id)
    estimate = _verified_cost_sheet_and_estimate(client, headers, project_id, project_sport_id)

    res = client.get(f"/estimates/{estimate['id']}/pdf", headers=headers)
    assert res.status_code == 200
    text = _pdf_text(res)
    assert "Standard vs. actual dimensions" in text
    assert "Not yet recorded" in text


def test_estimate_pdf_shows_the_deviation_status_once_recorded(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_badminton(client, headers, project_id)
    client.patch(
        f"/projects/{project_id}/sports/{project_sport_id}/actual-dimensions",
        json={"actual_l_ft": 50, "actual_w_ft": 20},
        headers=headers,
    )
    estimate = _verified_cost_sheet_and_estimate(client, headers, project_id, project_sport_id)

    res = client.get(f"/estimates/{estimate['id']}/pdf", headers=headers)
    assert res.status_code == 200
    text = _pdf_text(res)
    assert "RED" in text
    assert "deviation" in text


def test_quotation_pdf_shows_the_deviation_status(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers, _create_client_record(client, headers))
    project_sport_id = _add_badminton(client, headers, project_id)
    client.patch(
        f"/projects/{project_id}/sports/{project_sport_id}/actual-dimensions",
        json={"actual_l_ft": 45, "actual_w_ft": 20},
        headers=headers,
    )
    estimate = _verified_cost_sheet_and_estimate(client, headers, project_id, project_sport_id)
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
    client.post(f"/quotations/{quotation['id']}/release", headers=headers)

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert res.status_code == 200
    text = _pdf_text(res)
    assert "Standard vs. actual dimensions" in text
    assert "AMBER" in text
