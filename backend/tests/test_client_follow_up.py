"""Amendment 42 (Section 48): Client.next_follow_up_date / follow_up_note."""
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


def _procurement_headers(client, db_session):
    user = User(
        name="Test Procurement", email="procurement@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.PROCUREMENT,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "procurement@test.local")


def _create_client_record(client, headers, name="Follow-Up Client", **overrides):
    payload = {"name": name, "type": "school", **overrides}
    res = client.post("/clients", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def test_client_follow_up_fields_default_to_null(client, director_user):
    headers = _director_headers(client, director_user)
    row = _create_client_record(client, headers)
    assert row["next_follow_up_date"] is None
    assert row["follow_up_note"] is None


def test_setting_and_clearing_a_follow_up(client, director_user):
    headers = _director_headers(client, director_user)
    client_row = _create_client_record(client, headers)

    res = client.patch(
        f"/clients/{client_row['id']}/follow-up",
        json={"next_follow_up_date": "2026-10-01", "follow_up_note": "Discuss pricing"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["next_follow_up_date"] == "2026-10-01"
    assert res.json()["follow_up_note"] == "Discuss pricing"

    # Explicitly clearing (null) both fields -- distinct from omitting them.
    res = client.patch(
        f"/clients/{client_row['id']}/follow-up",
        json={"next_follow_up_date": None, "follow_up_note": None},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["next_follow_up_date"] is None
    assert res.json()["follow_up_note"] is None


def test_omitted_field_is_left_unchanged(client, director_user):
    headers = _director_headers(client, director_user)
    client_row = _create_client_record(client, headers)
    client.patch(
        f"/clients/{client_row['id']}/follow-up",
        json={"next_follow_up_date": "2026-10-01", "follow_up_note": "Discuss pricing"},
        headers=headers,
    )

    # Only follow_up_note sent -- next_follow_up_date must survive untouched.
    res = client.patch(
        f"/clients/{client_row['id']}/follow-up",
        json={"follow_up_note": "Send updated quote"},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.json()["next_follow_up_date"] == "2026-10-01"
    assert res.json()["follow_up_note"] == "Send updated quote"


def test_sales_can_set_a_follow_up(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    client_row = _create_client_record(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.patch(
        f"/clients/{client_row['id']}/follow-up",
        json={"next_follow_up_date": "2026-10-05"},
        headers=sales_headers,
    )
    assert res.status_code == 200, res.text


def test_procurement_cannot_set_a_follow_up(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    client_row = _create_client_record(client, director_headers)

    procurement_headers = _procurement_headers(client, db_session)
    res = client.patch(
        f"/clients/{client_row['id']}/follow-up",
        json={"next_follow_up_date": "2026-10-05"},
        headers=procurement_headers,
    )
    assert res.status_code == 403


def test_follow_up_update_does_not_write_an_audit_log_entry(client, director_user):
    """Deliberate, per the approved spec: a routine personal reminder, not
    a governance-relevant fact like a blacklist flag or consent change."""
    headers = _director_headers(client, director_user)
    client_row = _create_client_record(client, headers)

    client.patch(
        f"/clients/{client_row['id']}/follow-up",
        json={"next_follow_up_date": "2026-10-01"},
        headers=headers,
    )

    entries = client.get(
        "/audit-log", params={"document_type": "client", "document_id": client_row["id"]}, headers=headers
    ).json()
    assert not any(e["field"] in ("next_follow_up_date", "follow_up_note") for e in entries)


def test_follow_up_update_on_nonexistent_client_is_404(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.patch(
        "/clients/00000000-0000-0000-0000-000000000000/follow-up",
        json={"next_follow_up_date": "2026-10-01"},
        headers=headers,
    )
    assert res.status_code == 404
