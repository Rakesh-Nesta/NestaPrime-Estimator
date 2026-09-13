"""Amendment 5's Custom Notes component: one field on Project (not per
screen) -- "+ Add Note" on Project Setup, Cost Sheet, and Estimate all
read/write the same custom_notes field."""

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


def _create_client_record(client, headers, client_type="school", name="Test School"):
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


def test_project_custom_notes_defaults_to_none(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)

    res = client.get(f"/projects/{project_id}", headers=headers)
    assert res.json()["custom_notes"] is None


def test_project_notes_can_be_set_and_read_back(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)

    update_res = client.patch(
        f"/projects/{project_id}/notes", json={"custom_notes": "Client wants matte finish, confirmed by phone."},
        headers=headers,
    )
    assert update_res.status_code == 200, update_res.text
    assert update_res.json()["custom_notes"] == "Client wants matte finish, confirmed by phone."

    get_res = client.get(f"/projects/{project_id}", headers=headers)
    assert get_res.json()["custom_notes"] == "Client wants matte finish, confirmed by phone."


def test_project_notes_can_be_cleared(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    client.patch(f"/projects/{project_id}/notes", json={"custom_notes": "Draft note"}, headers=headers)

    clear_res = client.patch(f"/projects/{project_id}/notes", json={"custom_notes": None}, headers=headers)
    assert clear_res.status_code == 200, clear_res.text
    assert clear_res.json()["custom_notes"] is None


def test_updating_notes_on_nonexistent_project_is_404(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.patch(
        "/projects/00000000-0000-0000-0000-000000000000/notes", json={"custom_notes": "X"}, headers=headers
    )
    assert res.status_code == 404


def test_site_engineer_cannot_update_project_notes(client, db_session, director_user):
    """The + Add Note button lives on Project Setup/Cost Sheet/Estimate --
    the same sales/pm/director roles that reach those screens, matching
    create_project's own role gate."""
    director_headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, director_headers)
    project_id = _create_project(client, director_headers, client_id)

    site_engineer_headers = _site_engineer_headers(client, db_session)
    res = client.patch(
        f"/projects/{project_id}/notes", json={"custom_notes": "X"}, headers=site_engineer_headers
    )
    assert res.status_code == 403
