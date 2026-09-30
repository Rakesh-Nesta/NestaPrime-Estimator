"""P4 contract v7, Section 3: stage evidence capture."""

from app.core.project_stages import CONSTRUCTION_PHASES
from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _pm_headers(client, db_session):
    user = User(name="Test PM", email="pm-p4@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.PM)
    db_session.add(user)
    db_session.commit()
    return _login(client, "pm-p4@test.local")


def _site_engineer_headers(client, db_session):
    user = User(
        name="Test Site Engineer", email="se-p4@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.SITE_ENGINEER,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "se-p4@test.local")


def _sales_headers(client, db_session):
    user = User(
        name="Test Sales", email="sales-p4-stage@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.SALES,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales-p4-stage@test.local")


def _create_project(client, headers):
    res = client.post("/clients", json={"name": "P4 Stage Client", "type": "school"}, headers=headers)
    assert res.status_code == 201, res.text
    client_id = res.json()["id"]
    fields = {
        "client_id": client_id, "city": "Mumbai", "site_condition": "level", "soil_type": "normal",
        "building_status": "open_air", "site_access": "good", "power_available": "yes",
        "water_available": True, "package": "standard",
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _upload_stage_evidence(client, headers, stage_id, filename="site.jpg"):
    return client.post(
        "/attachments",
        data={"doc_type": "project_stage", "doc_id": stage_id, "tag": "photo"},
        files={"file": (filename, b"photo bytes", "image/jpeg")},
        headers=headers,
    )


def _get_stage(client, headers, project_id, phase):
    res = client.get(f"/projects/{project_id}/stages", headers=headers)
    assert res.status_code == 200, res.text
    return next(s for s in res.json() if s["phase"] == phase)


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


def test_stage_rows_seeded_for_new_project(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers)
    res = client.get(f"/projects/{project_id}/stages", headers=headers)
    assert res.status_code == 200, res.text
    stages = res.json()
    assert {s["phase"] for s in stages} == set(CONSTRUCTION_PHASES)
    assert all(s["status"] == "not_started" for s in stages)

    # a read-only call again creates zero additional rows
    res2 = client.get(f"/projects/{project_id}/stages", headers=headers)
    assert len(res2.json()) == len(stages)


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


def test_zero_evidence_submission_refused_leaves_status_unchanged(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers)
    stage = _get_stage(client, headers, project_id, CONSTRUCTION_PHASES[0])
    assert stage["status"] == "not_started"

    res = client.post(f"/stages/{stage['id']}/submit", headers=headers)
    assert res.status_code == 400, res.text

    stage_after = _get_stage(client, headers, project_id, CONSTRUCTION_PHASES[0])
    assert stage_after["status"] == "not_started"  # unchanged, whatever it was -- not forced to in_progress


def test_upload_advances_not_started_to_in_progress_and_pm_director_can_submit(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers)
    phase = CONSTRUCTION_PHASES[0]
    stage = _get_stage(client, headers, project_id, phase)

    res = _upload_stage_evidence(client, headers, stage["id"])
    assert res.status_code == 201, res.text
    stage = _get_stage(client, headers, project_id, phase)
    assert stage["status"] == "in_progress"
    assert stage["started_at"] is not None

    # PM/Director can submit, not only Site Engineer (revision 4 fix)
    res = client.post(f"/stages/{stage['id']}/submit", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "evidence_submitted"


def test_rejection_and_resubmission_cycle(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers)
    phase = CONSTRUCTION_PHASES[0]
    stage = _get_stage(client, headers, project_id, phase)
    _upload_stage_evidence(client, headers, stage["id"])
    stage = _get_stage(client, headers, project_id, phase)
    client.post(f"/stages/{stage['id']}/submit", headers=headers)

    res = client.post(
        f"/stages/{stage['id']}/review", json={"action": "reject", "rejection_reason": "blurry photo"}, headers=headers
    )
    assert res.status_code == 200, res.text
    rejected = res.json()
    assert rejected["status"] == "rejected"  # not in_progress yet -- the transition happens on next upload
    assert rejected["rejection_reason"] == "blurry photo"

    res = _upload_stage_evidence(client, headers, stage["id"], filename="retake.jpg")
    assert res.status_code == 201, res.text
    stage = _get_stage(client, headers, project_id, phase)
    assert stage["status"] == "in_progress"  # now it moves, matching Section 3's stated rule

    res = client.post(f"/stages/{stage['id']}/submit", headers=headers)
    assert res.status_code == 200, res.text
    res = client.post(f"/stages/{stage['id']}/review", json={"action": "approve"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "reviewed"


def test_new_evidence_invalidates_a_prior_review(client, director_user):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers)
    phase = CONSTRUCTION_PHASES[0]
    stage = _get_stage(client, headers, project_id, phase)
    _upload_stage_evidence(client, headers, stage["id"])
    stage = _get_stage(client, headers, project_id, phase)
    client.post(f"/stages/{stage['id']}/submit", headers=headers)
    client.post(f"/stages/{stage['id']}/review", json={"action": "approve"}, headers=headers)
    stage = _get_stage(client, headers, project_id, phase)
    assert stage["status"] == "reviewed"

    res = _upload_stage_evidence(client, headers, stage["id"], filename="new-evidence.jpg")
    assert res.status_code == 201, res.text
    stage = _get_stage(client, headers, project_id, phase)
    assert stage["status"] == "evidence_submitted"  # a stale sign-off is never left in place


# ---------------------------------------------------------------------------
# Role/access
# ---------------------------------------------------------------------------


def test_sales_cannot_touch_stage_evidence(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers)
    stage = _get_stage(client, headers, project_id, CONSTRUCTION_PHASES[0])

    sales_headers = _sales_headers(client, db_session)
    res = client.get(f"/projects/{project_id}/stages", headers=sales_headers)
    assert res.status_code == 403, res.text
    res = client.post(f"/stages/{stage['id']}/submit", headers=sales_headers)
    assert res.status_code == 403, res.text


def test_site_engineer_can_upload_and_submit_but_not_review(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    project_id = _create_project(client, headers)
    phase = CONSTRUCTION_PHASES[0]
    stage = _get_stage(client, headers, project_id, phase)

    se_headers = _site_engineer_headers(client, db_session)
    res = _upload_stage_evidence(client, se_headers, stage["id"])
    assert res.status_code == 201, res.text
    res = client.post(f"/stages/{stage['id']}/submit", headers=se_headers)
    assert res.status_code == 200, res.text

    res = client.post(f"/stages/{stage['id']}/review", json={"action": "approve"}, headers=se_headers)
    assert res.status_code == 403, res.text  # review is PM/Director only
