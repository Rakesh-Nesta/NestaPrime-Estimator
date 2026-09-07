from datetime import date, timedelta

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


def _procurement_headers(client, db_session):
    user = User(
        name="Test Procurement", email="procurement@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.PROCUREMENT,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "procurement@test.local")


def _site_engineer_headers(client, db_session):
    user = User(
        name="Test Site Engineer", email="site@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.SITE_ENGINEER,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "site@test.local")


def _create_client_record(client, headers, name="Signatories Client"):
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


def _draft_cost_sheet(client, headers, client_id):
    project_id = _create_project(client, headers, client_id)
    res = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": 100000}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _signatory_payload(**overrides):
    payload = {
        "name": "Priya Sharma",
        "designation": "Principal",
        "email": "priya@school.example",
        "authorization_date": str(date.today() - timedelta(days=1)),
    }
    payload.update(overrides)
    return payload


def _upload(client, headers, doc_type, doc_id, tag, **extra):
    data = {"doc_type": doc_type, "doc_id": doc_id, "tag": tag, **extra}
    return client.post(
        "/attachments", data=data, files={"file": ("evidence.txt", b"approval evidence", "text/plain")}, headers=headers
    )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


def test_create_and_list_signatory(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)

    res = client.post(f"/clients/{client_id}/signatories", json=_signatory_payload(), headers=headers)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["name"] == "Priya Sharma"
    assert body["designation"] == "Principal"
    assert body["is_active"] is True

    listed = client.get(f"/clients/{client_id}/signatories", headers=headers).json()
    assert len(listed) == 1
    assert listed[0]["id"] == body["id"]


def test_create_signatory_requires_the_client_to_exist(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/clients/00000000-0000-0000-0000-000000000000/signatories", json=_signatory_payload(), headers=headers
    )
    assert res.status_code == 404


def test_procurement_cannot_create_but_can_list(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, director_headers)

    procurement_headers = _procurement_headers(client, db_session)
    create_res = client.post(f"/clients/{client_id}/signatories", json=_signatory_payload(), headers=procurement_headers)
    assert create_res.status_code == 403

    client.post(f"/clients/{client_id}/signatories", json=_signatory_payload(), headers=director_headers)
    list_res = client.get(f"/clients/{client_id}/signatories", headers=procurement_headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1


def test_site_engineer_cannot_read_or_write(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, director_headers)

    site_headers = _site_engineer_headers(client, db_session)
    assert client.get(f"/clients/{client_id}/signatories", headers=site_headers).status_code == 403
    assert client.post(f"/clients/{client_id}/signatories", json=_signatory_payload(), headers=site_headers).status_code == 403


def test_deactivate_hides_from_default_listing(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    signatory_id = client.post(f"/clients/{client_id}/signatories", json=_signatory_payload(), headers=headers).json()["id"]

    patch_res = client.patch(
        f"/clients/{client_id}/signatories/{signatory_id}", json={"is_active": False}, headers=headers
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["is_active"] is False

    default_listing = client.get(f"/clients/{client_id}/signatories", headers=headers).json()
    assert default_listing == []

    full_listing = client.get(f"/clients/{client_id}/signatories", params={"include_inactive": True}, headers=headers).json()
    assert len(full_listing) == 1


def test_update_missing_signatory_404s(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    res = client.patch(
        f"/clients/{client_id}/signatories/00000000-0000-0000-0000-000000000000",
        json={"is_active": False}, headers=headers,
    )
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# M.3 approval-evidence signatory matching (Part O)
# ---------------------------------------------------------------------------


def test_approval_evidence_with_no_signatory_named_still_works(client, director_user):
    """Backward compatible: naming a signatory is optional, not mandatory."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    cost_sheet_id = _draft_cost_sheet(client, headers, client_id)

    res = _upload(client, headers, "cost_sheet", cost_sheet_id, "approval_evidence")
    assert res.status_code == 201, res.text
    assert res.json()["signatory_name"] is None


def test_approval_evidence_matching_active_signatory_succeeds(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    client.post(f"/clients/{client_id}/signatories", json=_signatory_payload(), headers=headers)
    cost_sheet_id = _draft_cost_sheet(client, headers, client_id)

    res = _upload(
        client, headers, "cost_sheet", cost_sheet_id, "approval_evidence",
        signatory_name="Priya Sharma", signatory_designation="Principal",
    )
    assert res.status_code == 201, res.text
    assert res.json()["signatory_name"] == "Priya Sharma"
    assert res.json()["signatory_designation"] == "Principal"


def test_approval_evidence_matching_is_case_insensitive(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    client.post(f"/clients/{client_id}/signatories", json=_signatory_payload(), headers=headers)
    cost_sheet_id = _draft_cost_sheet(client, headers, client_id)

    res = _upload(
        client, headers, "cost_sheet", cost_sheet_id, "approval_evidence",
        signatory_name="priya sharma", signatory_designation="PRINCIPAL",
    )
    assert res.status_code == 201, res.text


def test_approval_evidence_rejects_a_non_matching_name(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    client.post(f"/clients/{client_id}/signatories", json=_signatory_payload(), headers=headers)
    cost_sheet_id = _draft_cost_sheet(client, headers, client_id)

    res = _upload(
        client, headers, "cost_sheet", cost_sheet_id, "approval_evidence",
        signatory_name="Someone Else", signatory_designation="Principal",
    )
    assert res.status_code == 422


def test_approval_evidence_rejects_an_inactive_signatory(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    signatory_id = client.post(f"/clients/{client_id}/signatories", json=_signatory_payload(), headers=headers).json()["id"]
    client.patch(f"/clients/{client_id}/signatories/{signatory_id}", json={"is_active": False}, headers=headers)
    cost_sheet_id = _draft_cost_sheet(client, headers, client_id)

    res = _upload(
        client, headers, "cost_sheet", cost_sheet_id, "approval_evidence",
        signatory_name="Priya Sharma", signatory_designation="Principal",
    )
    assert res.status_code == 422


def test_approval_evidence_rejects_an_expired_signatory(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    client.post(
        f"/clients/{client_id}/signatories",
        json=_signatory_payload(expiry_date=str(date.today() - timedelta(days=1))),
        headers=headers,
    )
    cost_sheet_id = _draft_cost_sheet(client, headers, client_id)

    res = _upload(
        client, headers, "cost_sheet", cost_sheet_id, "approval_evidence",
        signatory_name="Priya Sharma", signatory_designation="Principal",
    )
    assert res.status_code == 422


def test_approval_evidence_rejects_a_not_yet_authorized_signatory(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    client.post(
        f"/clients/{client_id}/signatories",
        json=_signatory_payload(authorization_date=str(date.today() + timedelta(days=5))),
        headers=headers,
    )
    cost_sheet_id = _draft_cost_sheet(client, headers, client_id)

    res = _upload(
        client, headers, "cost_sheet", cost_sheet_id, "approval_evidence",
        signatory_name="Priya Sharma", signatory_designation="Principal",
    )
    assert res.status_code == 422


def test_approval_evidence_accepts_a_signatory_with_no_expiry(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    client.post(f"/clients/{client_id}/signatories", json=_signatory_payload(expiry_date=None), headers=headers)
    cost_sheet_id = _draft_cost_sheet(client, headers, client_id)

    res = _upload(
        client, headers, "cost_sheet", cost_sheet_id, "approval_evidence",
        signatory_name="Priya Sharma", signatory_designation="Principal",
    )
    assert res.status_code == 201, res.text


def test_signatory_fields_rejected_on_a_non_approval_evidence_tag(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    client.post(f"/clients/{client_id}/signatories", json=_signatory_payload(), headers=headers)
    cost_sheet_id = _draft_cost_sheet(client, headers, client_id)

    res = _upload(
        client, headers, "cost_sheet", cost_sheet_id, "photo",
        signatory_name="Priya Sharma", signatory_designation="Principal",
    )
    assert res.status_code == 422


def test_naming_only_one_of_name_or_designation_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    client.post(f"/clients/{client_id}/signatories", json=_signatory_payload(), headers=headers)
    cost_sheet_id = _draft_cost_sheet(client, headers, client_id)

    res = _upload(client, headers, "cost_sheet", cost_sheet_id, "approval_evidence", signatory_name="Priya Sharma")
    assert res.status_code == 422
