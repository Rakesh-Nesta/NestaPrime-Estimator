"""Shared P5 test helpers: drive the real HTTP API through the full Won -> Agreement -> staffed team ->
authorized path, so a Work Order can be created exactly as production would allow it."""

import uuid
from datetime import date, timedelta

PASSWORD = "StrongPass!234"


def login(client, email, password=PASSWORD):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def make_user(db_session, role, name=None, active=True):
    """A directly-inserted user who can log in (no forced password change), unlike create_user_via_api."""
    from app.core.security import hash_password
    from app.models.user import User, UserRole

    user = User(
        name=name or f"P5 {role}", email=f"{role}-{uuid.uuid4().hex[:8]}@p5.test",
        hashed_password=hash_password(PASSWORD), role=UserRole(role), is_active=active,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def user_headers(client, user):
    return login(client, user.email)


def create_user_via_api(client, director_headers, role, name=None):
    email = f"{role}-{uuid.uuid4().hex[:8]}@p5.test"
    res = client.post(
        "/users",
        json={"name": name or f"P5 {role}", "email": email, "role": role, "password": PASSWORD},
        headers=director_headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def quotation_project(client, headers, quotation_id):
    quotation = client.get(f"/quotations/{quotation_id}", headers=headers).json()
    project = client.get(f"/projects/{quotation['project_id']}", headers=headers).json()
    return project["id"], project["client_id"]


def draft_agreement(client, headers, quotation_id):
    res = client.post(f"/quotations/{quotation_id}/agreement", headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def add_signatory(client, headers, client_id, authorized_on=None, expiry=None, name="A. Signatory"):
    res = client.post(
        f"/clients/{client_id}/signatories",
        json={
            "name": name, "designation": "Principal",
            "authorization_date": str(authorized_on or date.today() - timedelta(days=30)),
            **({"expiry_date": str(expiry)} if expiry else {}),
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def upload_agreement_document(client, headers, agreement_id, content=b"signed agreement"):
    res = client.post(
        "/attachments",
        data={"doc_type": "agreement", "doc_id": agreement_id, "tag": "signed_document"},
        files={"file": ("agreement.pdf", content, "application/pdf")},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def client_sign(client, headers, agreement_id, signatory_id, attachment_id, signed_on=None):
    return client.post(
        f"/agreements/{agreement_id}/client-sign",
        json={
            "client_signatory_id": signatory_id,
            "signed_on": str(signed_on or date.today()),
            "attachment_id": attachment_id,
        },
        headers=headers,
    )


def execute_agreement(client, headers, quotation_id, client_id, *, signatory=None):
    """Drafts, uploads, client-signs and (Director) executes. Returns the executed Agreement JSON."""
    agreement = draft_agreement(client, headers, quotation_id)
    attachment = upload_agreement_document(client, headers, agreement["id"])
    signatory = signatory or add_signatory(client, headers, client_id)
    res = client_sign(client, headers, agreement["id"], signatory["id"], attachment["id"])
    assert res.status_code == 200, res.text
    res = client.post(f"/agreements/{agreement['id']}/execute", headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def staff_site_engineer(client, headers, project_id, user=None):
    user = user or create_user_via_api(client, headers, "site_engineer")
    res = client.post(
        f"/projects/{project_id}/team", json={"user_id": user["id"], "project_role": "site_engineer"}, headers=headers
    )
    assert res.status_code == 200, res.text
    return user, res.json()


def authorize(client, headers, quotation_id):
    return client.post(f"/quotations/{quotation_id}/execution-authorization", headers=headers)


def make_execution_ready(client, headers, quotation_id, engineer=None):
    """The whole prerequisite chain for creating a Work Order. Returns a dict of the created records.
    `engineer` (a dict with an "id") lets a test supply a user who can actually log in."""
    project_id, client_id = quotation_project(client, headers, quotation_id)
    agreement = execute_agreement(client, headers, quotation_id, client_id)
    engineer, member = staff_site_engineer(client, headers, project_id, user=engineer)
    res = authorize(client, headers, quotation_id)
    assert res.status_code == 200, res.text
    return {
        "project_id": project_id, "client_id": client_id, "agreement": agreement,
        "engineer": engineer, "member": member, "authorization": res.json(),
    }


def create_work_order(client, headers, quotation_id):
    """Prerequisites first, then the real Work Order endpoint. Returns the Response."""
    make_execution_ready(client, headers, quotation_id)
    return client.post(f"/quotations/{quotation_id}/work-order", headers=headers)
