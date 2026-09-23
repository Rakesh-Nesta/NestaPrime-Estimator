"""Amendment 45 (Section 51): a general free-text notes/remarks catch-all
on Client and Opportunity, distinct from either entity's own follow-up
note."""
from app.core.security import hash_password
from app.models.user import User, UserRole


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _procurement_headers(client, db_session):
    user = User(
        name="Test Procurement", email="procurement@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.PROCUREMENT,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "procurement@test.local")


def _create_client_record(client, headers, **overrides):
    payload = {"name": "Notes Test Client", "type": "school", **overrides}
    res = client.post("/clients", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def _create_opportunity(client, headers, **overrides):
    payload = {"lead_name": "Notes Test Lead", "next_follow_up_date": "2026-10-01", **overrides}
    res = client.post("/opportunities", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


# --- Client.notes ---------------------------------------------------------


def test_client_notes_default_to_null(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client_record(client, headers)
    assert row["notes"] is None


def test_client_can_be_created_with_notes(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client_record(client, headers, notes="Prefers site visits on weekdays.")
    assert row["notes"] == "Prefers site visits on weekdays."


def test_update_client_notes(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client_record(client, headers)

    res = client.patch(f"/clients/{row['id']}/notes", json={"notes": "Called twice, no answer."}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["notes"] == "Called twice, no answer."

    # Explicitly clearing back to null.
    res = client.patch(f"/clients/{row['id']}/notes", json={"notes": None}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["notes"] is None


def test_client_notes_are_independent_of_follow_up_note(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client_record(client, headers)
    client.patch(
        f"/clients/{row['id']}/follow-up",
        json={"next_follow_up_date": "2026-10-05", "follow_up_note": "Call about pricing"},
        headers=headers,
    )
    res = client.patch(f"/clients/{row['id']}/notes", json={"notes": "General remark"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["follow_up_note"] == "Call about pricing"
    assert res.json()["notes"] == "General remark"


def test_procurement_cannot_update_client_notes(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    row = _create_client_record(client, director_headers)

    procurement_headers = _procurement_headers(client, db_session)
    res = client.patch(f"/clients/{row['id']}/notes", json={"notes": "Blocked"}, headers=procurement_headers)
    assert res.status_code == 403


def test_client_notes_update_does_not_write_an_audit_log_entry(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client_record(client, headers)
    client.patch(f"/clients/{row['id']}/notes", json={"notes": "A remark"}, headers=headers)

    entries = client.get(
        "/audit-log", params={"document_type": "client", "document_id": row["id"]}, headers=headers
    ).json()
    assert not any(e["field"] == "notes" for e in entries)


def test_client_notes_update_on_nonexistent_client_is_404(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.patch(
        "/clients/00000000-0000-0000-0000-000000000000/notes", json={"notes": "x"}, headers=headers
    )
    assert res.status_code == 404


# --- Opportunity.notes -----------------------------------------------------


def test_opportunity_notes_default_to_null(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_opportunity(client, headers)
    assert row["notes"] is None


def test_opportunity_can_be_created_with_notes(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_opportunity(client, headers, notes="Referred by an existing client.")
    assert row["notes"] == "Referred by an existing client."


def test_update_opportunity_notes(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_opportunity(client, headers)

    res = client.patch(f"/opportunities/{row['id']}/notes", json={"notes": "Wants a badminton court."}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["notes"] == "Wants a badminton court."

    res = client.patch(f"/opportunities/{row['id']}/notes", json={"notes": None}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["notes"] is None


def test_opportunity_notes_are_independent_of_follow_up_note(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_opportunity(client, headers)
    client.patch(
        f"/opportunities/{row['id']}/follow-up",
        json={"next_follow_up_date": "2026-10-15", "follow_up_note": "Call back after Diwali"},
        headers=headers,
    )
    res = client.patch(f"/opportunities/{row['id']}/notes", json={"notes": "General remark"}, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["follow_up_note"] == "Call back after Diwali"
    assert res.json()["notes"] == "General remark"


def test_procurement_cannot_update_opportunity_notes(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    row = _create_opportunity(client, director_headers)

    procurement_headers = _procurement_headers(client, db_session)
    res = client.patch(f"/opportunities/{row['id']}/notes", json={"notes": "Blocked"}, headers=procurement_headers)
    assert res.status_code == 403


def test_opportunity_notes_update_does_not_write_an_audit_log_entry(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_opportunity(client, headers)
    client.patch(f"/opportunities/{row['id']}/notes", json={"notes": "A remark"}, headers=headers)

    entries = client.get(
        "/audit-log", params={"document_type": "opportunity", "document_id": row["id"]}, headers=headers
    ).json()
    assert entries == []


def test_opportunity_notes_update_on_nonexistent_opportunity_is_404(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.patch(
        "/opportunities/00000000-0000-0000-0000-000000000000/notes", json={"notes": "x"}, headers=headers
    )
    assert res.status_code == 404
