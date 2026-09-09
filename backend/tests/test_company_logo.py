import base64

from app.core.security import hash_password
from app.models.company_logo import CompanyLogo
from app.models.user import User, UserRole

# A real, minimally valid 1x1 transparent PNG -- needed because
# _company_logo_flowable() actually decodes the file with Pillow when
# embedding it in a PDF, not just trusting the declared content-type.
_PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
_SVG_MINIMAL = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'


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


def _pm_headers(client, db_session):
    user = User(name="Test PM", email="pm@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.PM)
    db_session.add(user)
    db_session.commit()
    return _login(client, "pm@test.local")


def test_director_can_upload_a_png_logo(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post("/company/logo", files={"file": ("logo.png", _PNG_1X1, "image/png")}, headers=headers)
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["original_filename"] == "logo.png"
    assert body["content_type"] == "image/png"
    assert body["uploaded_by_id"]


def test_director_can_upload_an_svg_logo(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/company/logo", files={"file": ("logo.svg", _SVG_MINIMAL, "image/svg+xml")}, headers=headers
    )
    assert res.status_code == 201, res.text
    assert res.json()["content_type"] == "image/svg+xml"


def test_pm_cannot_upload_a_logo(client, director_user, db_session):
    pm_headers = _pm_headers(client, db_session)
    res = client.post("/company/logo", files={"file": ("logo.png", _PNG_1X1, "image/png")}, headers=pm_headers)
    assert res.status_code == 403


def test_non_image_content_type_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/company/logo", files={"file": ("logo.pdf", b"%PDF-1.4 fake", "application/pdf")}, headers=headers
    )
    assert res.status_code == 422
    assert "PNG or SVG" in res.json()["detail"]


def test_empty_file_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post("/company/logo", files={"file": ("logo.png", b"", "image/png")}, headers=headers)
    assert res.status_code == 422


def test_oversized_logo_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    oversized = b"\x00" * (5 * 1024 * 1024 + 1)
    res = client.post("/company/logo", files={"file": ("logo.png", oversized, "image/png")}, headers=headers)
    assert res.status_code == 413


def test_logo_meta_404s_when_none_uploaded(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.get("/company/logo/meta", headers=headers)
    assert res.status_code == 404


def test_logo_binary_404s_when_none_uploaded(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.get("/company/logo", headers=headers)
    assert res.status_code == 404


def test_get_logo_returns_the_uploaded_bytes(client, director_user):
    headers = _director_headers(client, director_user)
    client.post("/company/logo", files={"file": ("logo.png", _PNG_1X1, "image/png")}, headers=headers)

    res = client.get("/company/logo", headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "image/png"
    assert res.content == _PNG_1X1


def test_any_authenticated_role_can_read_the_logo(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    client.post("/company/logo", files={"file": ("logo.png", _PNG_1X1, "image/png")}, headers=director_headers)

    sales_headers = _sales_headers(client, db_session)
    meta_res = client.get("/company/logo/meta", headers=sales_headers)
    assert meta_res.status_code == 200, meta_res.text
    binary_res = client.get("/company/logo", headers=sales_headers)
    assert binary_res.status_code == 200


def test_uploading_a_new_logo_supersedes_without_deleting_history(client, director_user, db_session):
    """M.3's 'no overwrite, no delete' discipline: the second upload
    becomes current, but the first row is never removed."""
    headers = _director_headers(client, director_user)
    client.post("/company/logo", files={"file": ("old.png", _PNG_1X1, "image/png")}, headers=headers)
    client.post(
        "/company/logo", files={"file": ("new.svg", _SVG_MINIMAL, "image/svg+xml")}, headers=headers
    )

    meta = client.get("/company/logo/meta", headers=headers).json()
    assert meta["original_filename"] == "new.svg"

    assert db_session.query(CompanyLogo).count() == 2


def test_logo_upload_requires_auth(client):
    res = client.post("/company/logo", files={"file": ("logo.png", _PNG_1X1, "image/png")})
    assert res.status_code == 401
