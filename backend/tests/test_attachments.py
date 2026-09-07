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


def _create_client_record(client, headers):
    res = client.post("/clients", json={"name": "Attachments Client", "type": "school"}, headers=headers)
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


def _draft_cost_sheet(client, headers):
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    res = client.post(f"/projects/{project_id}/cost-sheets", json={"cost_total": 100000}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _upload(client, headers, doc_type, doc_id, tag, approval_strength=None, filename="test.txt", content=b"hello world"):
    data = {"doc_type": doc_type, "doc_id": doc_id, "tag": tag}
    if approval_strength:
        data["approval_strength"] = approval_strength
    return client.post(
        "/attachments", data=data, files={"file": (filename, content, "text/plain")}, headers=headers
    )


# ---------------------------------------------------------------------------
# Upload, list, download
# ---------------------------------------------------------------------------


def test_upload_and_list_attachment(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)

    res = _upload(client, headers, "cost_sheet", cost_sheet_id, "soil_report", content=b"soil report contents")
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["original_filename"] == "test.txt"
    assert body["original_size"] == len(b"soil report contents")
    assert body["version"] == 1
    assert body["superseded_by_id"] is None
    import hashlib
    assert body["original_sha256"] == hashlib.sha256(b"soil report contents").hexdigest()

    listed = client.get("/attachments", params={"doc_type": "cost_sheet", "doc_id": cost_sheet_id}, headers=headers).json()
    assert len(listed) == 1
    assert listed[0]["id"] == body["id"]


def test_download_returns_the_original_bytes(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    upload_res = _upload(client, headers, "cost_sheet", cost_sheet_id, "photo", content=b"a real site photo")
    attachment_id = upload_res.json()["id"]

    download_res = client.get(f"/attachments/{attachment_id}/download", headers=headers)
    assert download_res.status_code == 200
    assert download_res.content == b"a real site photo"


def test_upload_rejects_empty_file(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    res = _upload(client, headers, "cost_sheet", cost_sheet_id, "photo", content=b"")
    assert res.status_code == 422


def test_upload_requires_the_document_to_exist(client, director_user):
    headers = _director_headers(client, director_user)
    res = _upload(client, headers, "cost_sheet", "00000000-0000-0000-0000-000000000000", "photo")
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Role gates -- cost_sheet stays behind the same gate as every other
# cost-sheet endpoint; procurement has no valid attachment target at all.
# ---------------------------------------------------------------------------


def test_sales_cannot_attach_to_a_cost_sheet(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = _upload(client, sales_headers, "cost_sheet", cost_sheet_id, "photo")
    assert res.status_code == 403


def test_procurement_cannot_attach_to_anything(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)

    procurement_headers = _procurement_headers(client, db_session)
    res = _upload(client, procurement_headers, "cost_sheet", cost_sheet_id, "vendor_quote")
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Write-once / supersede (evidence integrity)
# ---------------------------------------------------------------------------


def test_supersede_creates_a_new_row_and_never_mutates_the_old_one(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    original = _upload(client, headers, "cost_sheet", cost_sheet_id, "soil_report", content=b"v1 report").json()

    res = client.post(
        f"/attachments/{original['id']}/supersede",
        data={},
        files={"file": ("v2.txt", b"v2 report", "text/plain")},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    new = res.json()
    assert new["version"] == 2
    assert new["id"] != original["id"]

    # The old row is untouched -- still fetchable, unchanged content, now
    # pointing at its successor.
    listed_all = client.get(
        "/attachments", params={"doc_type": "cost_sheet", "doc_id": cost_sheet_id, "include_superseded": True},
        headers=headers,
    ).json()
    assert len(listed_all) == 2
    old_row = next(a for a in listed_all if a["id"] == original["id"])
    assert old_row["superseded_by_id"] == new["id"]
    assert old_row["original_sha256"] == original["original_sha256"]  # never mutated

    old_download = client.get(f"/attachments/{original['id']}/download", headers=headers)
    assert old_download.content == b"v1 report"  # original bytes still intact


def test_default_listing_excludes_superseded_attachments(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    original = _upload(client, headers, "cost_sheet", cost_sheet_id, "soil_report").json()
    client.post(
        f"/attachments/{original['id']}/supersede",
        data={},
        files={"file": ("v2.txt", b"v2", "text/plain")},
        headers=headers,
    )

    current = client.get("/attachments", params={"doc_type": "cost_sheet", "doc_id": cost_sheet_id}, headers=headers).json()
    assert len(current) == 1
    assert current[0]["version"] == 2


def test_cannot_supersede_an_already_superseded_attachment(client, director_user):
    headers = _director_headers(client, director_user)
    cost_sheet_id = _draft_cost_sheet(client, headers)
    original = _upload(client, headers, "cost_sheet", cost_sheet_id, "soil_report").json()
    client.post(
        f"/attachments/{original['id']}/supersede",
        data={}, files={"file": ("v2.txt", b"v2", "text/plain")}, headers=headers,
    )

    third_attempt = client.post(
        f"/attachments/{original['id']}/supersede",
        data={}, files={"file": ("v3.txt", b"v3", "text/plain")}, headers=headers,
    )
    assert third_attempt.status_code == 400
