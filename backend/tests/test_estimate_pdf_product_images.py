import base64
import io

from pypdf import PdfReader

from app.core.security import hash_password
from app.models.user import User, UserRole

# A minimal valid 4x4 solid-colour PNG -- small, real, decodable image bytes
# (round-trips cleanly through Pillow, which reportlab uses internally).
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAIAAAAmkwkpAAAAE0lEQVR4nGM8YWTEAANMcBZeDgA8MgE0GRiVCQAAAABJRU5ErkJggg=="
)


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


def _create_client_record(client, headers):
    res = client.post("/clients", json={"name": "Product Image Client", "type": "school"}, headers=headers)
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


def _add_project_sport(client, headers, project_id, sport_key="badminton"):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.post(
        f"/projects/{project_id}/sports", json={"sport_id": sport_id, "building_status": "open_air"}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _draft_estimate(client, headers, cost_for_option=850000):
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    cost_sheet_id = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_for_option}, headers=headers
    ).json()["id"]
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost_for_option}]},
        headers=headers,
    ).json()
    return estimate


def _upload_product_image(client, headers, option_id, filename="court.png"):
    res = client.post(
        "/attachments",
        data={"doc_type": "estimate_option", "doc_id": option_id, "tag": "product_image"},
        files={"file": (filename, io.BytesIO(_TINY_PNG), "image/png")},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()


def _embedded_image_count(response) -> int:
    reader = PdfReader(io.BytesIO(response.content))
    return sum(len(page.images) for page in reader.pages)


def test_estimate_pdf_has_no_images_when_none_uploaded(client, director_user):
    headers = _director_headers(client, director_user)
    estimate = _draft_estimate(client, headers)

    res = client.get(f"/estimates/{estimate['id']}/pdf", headers=headers)
    assert res.status_code == 200
    assert _embedded_image_count(res) == 0


def test_estimate_pdf_embeds_the_uploaded_product_image(client, director_user):
    headers = _director_headers(client, director_user)
    estimate = _draft_estimate(client, headers)
    option_id = estimate["options"][0]["id"]
    _upload_product_image(client, headers, option_id)

    res = client.get(f"/estimates/{estimate['id']}/pdf", headers=headers)
    assert res.status_code == 200
    assert _embedded_image_count(res) == 1


def test_only_the_latest_non_superseded_image_is_embedded(client, director_user):
    headers = _director_headers(client, director_user)
    estimate = _draft_estimate(client, headers)
    option_id = estimate["options"][0]["id"]
    first = _upload_product_image(client, headers, option_id, filename="old.png")

    res = client.post(
        f"/attachments/{first['id']}/supersede",
        data={"tag": "product_image"},
        files={"file": ("new.png", io.BytesIO(_TINY_PNG), "image/png")},
        headers=headers,
    )
    assert res.status_code == 201, res.text

    pdf_res = client.get(f"/estimates/{estimate['id']}/pdf", headers=headers)
    assert _embedded_image_count(pdf_res) == 1


def test_corrupt_image_file_does_not_break_pdf_generation(client, director_user):
    """The upload endpoint doesn't validate image content, only extension
    and size (M.3) -- a malformed file must degrade to 'no image', never
    crash the whole PDF."""
    headers = _director_headers(client, director_user)
    estimate = _draft_estimate(client, headers)
    option_id = estimate["options"][0]["id"]
    res = client.post(
        "/attachments",
        data={"doc_type": "estimate_option", "doc_id": option_id, "tag": "product_image"},
        files={"file": ("not_really_a.png", io.BytesIO(b"this is not a valid PNG file at all"), "image/png")},
        headers=headers,
    )
    assert res.status_code == 201, res.text

    pdf_res = client.get(f"/estimates/{estimate['id']}/pdf", headers=headers)
    assert pdf_res.status_code == 200
    assert _embedded_image_count(pdf_res) == 0


def test_sales_can_upload_a_product_image(client, director_user, db_session):
    """M.6: the Estimate is a Sales-sent document (DOCUMENT_ROLES), so
    Sales can attach the product photo it shows the client."""
    director_headers = _director_headers(client, director_user)
    estimate = _draft_estimate(client, director_headers)
    option_id = estimate["options"][0]["id"]

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        "/attachments",
        data={"doc_type": "estimate_option", "doc_id": option_id, "tag": "product_image"},
        files={"file": ("court.png", io.BytesIO(_TINY_PNG), "image/png")},
        headers=sales_headers,
    )
    assert res.status_code == 201, res.text
