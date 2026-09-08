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


def _site_engineer_headers(client, db_session):
    user = User(
        name="Test Site Engineer", email="site@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.SITE_ENGINEER,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "site@test.local")


def _create_project(client, headers):
    client_id = client.post("/clients", json={"name": "Survey Client", "type": "school"}, headers=headers).json()["id"]
    fields = {
        "client_id": client_id, "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
        "building_status": "open_air", "site_access": "good", "power_available": "yes",
        "water_available": True, "package": "standard",
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_survey(client, headers, project_id, **overrides):
    payload = {"client_name": "Green Valley School", "site_address": "123 Main St", **overrides}
    res = client.post(f"/projects/{project_id}/site-surveys", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _upload_photo(client, headers, survey_id, filename="photo1.jpg"):
    res = client.post(
        "/attachments",
        data={"doc_type": "site_survey", "doc_id": survey_id, "tag": "photo"},
        files={"file": (filename, io.BytesIO(b"fake jpg bytes"), "image/jpeg")},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def _audit_entries(client, headers, **params):
    res = client.get("/audit-log", params=params, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


# ---------------------------------------------------------------------------
# Create / list / update
# ---------------------------------------------------------------------------


def test_create_site_survey_starts_blank_in_draft(client, director_user, db_session):
    headers = _site_engineer_headers(client, db_session)
    director_headers = _director_headers(client, director_user)
    project_id = _create_project(client, director_headers)

    survey = _create_survey(client, headers, project_id)
    assert survey["status"] == "draft"
    assert survey["client_name"] == "Green Valley School"
    assert survey["photo_count"] == 0
    assert survey["surveyed_at"] is None


def test_update_site_survey_fills_in_appendix_c_fields(client, director_user, db_session):
    headers = _site_engineer_headers(client, db_session)
    director_headers = _director_headers(client, director_user)
    project_id = _create_project(client, director_headers)
    survey = _create_survey(client, headers, project_id)

    res = client.patch(
        f"/site-surveys/{survey['id']}",
        json={
            "sports_and_count": "2x Badminton, 1x Basketball",
            "available_area_length": 100, "available_area_width": 60, "area_unit": "feet",
            "slope_or_level": "sloped", "soil_observed": "rocky", "water_logging_observed": False,
            "access_road_width_m": 4.5, "crane_access": True,
            "power_phase": "three", "power_load_kw": 25,
            "water_source": "municipal + borewell",
            "existing_structures_trees": "3 mango trees near boundary",
            "neighbour_constraints": "shared wall with adjacent plot",
            "orientation": "N-S",
        },
        headers=headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["sports_and_count"] == "2x Badminton, 1x Basketball"
    assert body["slope_or_level"] == "sloped"
    assert body["soil_observed"] == "rocky"
    assert body["crane_access"] is True
    assert body["power_phase"] == "three"
    assert body["orientation"] == "N-S"


def test_list_site_surveys_for_a_project(client, director_user, db_session):
    headers = _site_engineer_headers(client, db_session)
    director_headers = _director_headers(client, director_user)
    project_id = _create_project(client, director_headers)
    _create_survey(client, headers, project_id)

    rows = client.get(f"/projects/{project_id}/site-surveys", headers=headers).json()
    assert len(rows) == 1


def test_sales_cannot_create_a_site_survey(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    project_id = _create_project(client, director_headers)
    sales_headers = _sales_headers(client, db_session)

    res = client.post(f"/projects/{project_id}/site-surveys", json={}, headers=sales_headers)
    assert res.status_code == 403


def test_create_site_survey_for_unknown_project_404s(client, director_user, db_session):
    headers = _site_engineer_headers(client, db_session)
    res = client.post(
        "/projects/00000000-0000-0000-0000-000000000000/site-surveys", json={}, headers=headers
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Complete
# ---------------------------------------------------------------------------


def test_complete_requires_at_least_four_photos(client, director_user, db_session):
    headers = _site_engineer_headers(client, db_session)
    director_headers = _director_headers(client, director_user)
    project_id = _create_project(client, director_headers)
    survey = _create_survey(client, headers, project_id)

    res = client.post(f"/site-surveys/{survey['id']}/complete", headers=headers)
    assert res.status_code == 400
    assert "4 photos" in res.json()["detail"]

    for i in range(3):
        _upload_photo(client, headers, survey["id"], filename=f"photo{i}.jpg")
    res = client.post(f"/site-surveys/{survey['id']}/complete", headers=headers)
    assert res.status_code == 400

    _upload_photo(client, headers, survey["id"], filename="photo4.jpg")
    res = client.post(f"/site-surveys/{survey['id']}/complete", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "completed"
    assert body["photo_count"] == 4
    assert body["surveyed_by_id"] is not None
    assert body["surveyed_at"] is not None
    assert body["completed_at"] is not None


def test_completing_a_survey_writes_an_audit_log_entry(client, director_user, db_session):
    headers = _site_engineer_headers(client, db_session)
    director_headers = _director_headers(client, director_user)
    project_id = _create_project(client, director_headers)
    survey = _create_survey(client, headers, project_id)
    for i in range(4):
        _upload_photo(client, headers, survey["id"], filename=f"photo{i}.jpg")

    client.post(f"/site-surveys/{survey['id']}/complete", headers=headers)

    entries = _audit_entries(client, director_headers, document_type="site_survey", document_id=survey["id"])
    entry = next(e for e in entries if e["new_value"] == "completed")
    assert entry["old_value"] == "draft"


def test_cannot_edit_a_completed_survey(client, director_user, db_session):
    headers = _site_engineer_headers(client, db_session)
    director_headers = _director_headers(client, director_user)
    project_id = _create_project(client, director_headers)
    survey = _create_survey(client, headers, project_id)
    for i in range(4):
        _upload_photo(client, headers, survey["id"], filename=f"photo{i}.jpg")
    client.post(f"/site-surveys/{survey['id']}/complete", headers=headers)

    res = client.patch(f"/site-surveys/{survey['id']}", json={"orientation": "E-W"}, headers=headers)
    assert res.status_code == 400


def test_cannot_complete_an_already_completed_survey(client, director_user, db_session):
    headers = _site_engineer_headers(client, db_session)
    director_headers = _director_headers(client, director_user)
    project_id = _create_project(client, director_headers)
    survey = _create_survey(client, headers, project_id)
    for i in range(4):
        _upload_photo(client, headers, survey["id"], filename=f"photo{i}.jpg")
    client.post(f"/site-surveys/{survey['id']}/complete", headers=headers)

    res = client.post(f"/site-surveys/{survey['id']}/complete", headers=headers)
    assert res.status_code == 400


def test_pm_and_director_can_also_manage_site_surveys(client, director_user):
    """A.3: PM/Director oversee the Site Engineer's survey work."""
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers)
    survey = _create_survey(client, headers, project_id)
    res = client.get(f"/site-surveys/{survey['id']}", headers=headers)
    assert res.status_code == 200
