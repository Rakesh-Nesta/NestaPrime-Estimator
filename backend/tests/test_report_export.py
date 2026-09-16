"""GET /reports/{report_id}/export (Excel) and GET /reports/{report_id}/pdf --
the report's real, shareable form. Same T.2 rule 3 gate as GET
/reports/{report_id} and POST .../summary: role must be in
VISIBLE_ROLES[report.report_type]."""

from datetime import UTC, datetime

from app.core.security import hash_password
from app.models.user import User, UserRole

TODAY = datetime.now(UTC).date().isoformat()


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


def _sales_headers(client, db_session):
    user = User(
        name="Test Sales", email="sales-export@test.local", hashed_password=hash_password("TestPass!1"),
        role=UserRole.SALES,
    )
    db_session.add(user)
    db_session.commit()
    return _login(client, "sales-export@test.local")


def _pipeline_report(client, headers):
    res = client.post(
        "/reports/generate", json={"report_type": "pipeline", "period_from": TODAY, "period_to": TODAY}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _margin_report(client, headers):
    res = client.post(
        "/reports/generate", json={"report_type": "margin", "period_from": TODAY, "period_to": TODAY}, headers=headers
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _override_summary_report(client, headers):
    res = client.post(
        "/reports/generate",
        json={"report_type": "override_summary", "period_from": TODAY, "period_to": TODAY},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


# ---------------------------------------------------------------------------
# Excel export
# ---------------------------------------------------------------------------


def test_export_requires_auth(client):
    assert client.get("/reports/00000000-0000-0000-0000-000000000000/export").status_code == 401


def test_export_not_found(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.get("/reports/00000000-0000-0000-0000-000000000000/export", headers=headers)
    assert res.status_code == 404


def test_sales_cannot_export_a_margin_report(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    report_id = _margin_report(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.get(f"/reports/{report_id}/export", headers=sales_headers)
    assert res.status_code == 403


def test_pipeline_export_returns_a_real_xlsx(client, director_user):
    headers = _director_headers(client, director_user)
    report_id = _pipeline_report(client, headers)

    res = client.get(f"/reports/{report_id}/export", headers=headers)
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert res.content[:2] == b"PK"  # xlsx is a zip container
    assert len(res.content) > 0


def test_margin_export_returns_a_real_xlsx(client, director_user):
    headers = _director_headers(client, director_user)
    report_id = _margin_report(client, headers)

    res = client.get(f"/reports/{report_id}/export", headers=headers)
    assert res.status_code == 200, res.text
    assert res.content[:2] == b"PK"


def test_override_summary_export_returns_a_real_xlsx(client, director_user):
    headers = _director_headers(client, director_user)
    report_id = _override_summary_report(client, headers)

    res = client.get(f"/reports/{report_id}/export", headers=headers)
    assert res.status_code == 200, res.text
    assert res.content[:2] == b"PK"


# ---------------------------------------------------------------------------
# PDF export
# ---------------------------------------------------------------------------


def test_export_pdf_requires_auth(client):
    assert client.get("/reports/00000000-0000-0000-0000-000000000000/pdf").status_code == 401


def test_export_pdf_not_found(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.get("/reports/00000000-0000-0000-0000-000000000000/pdf", headers=headers)
    assert res.status_code == 404


def test_sales_cannot_export_a_margin_report_pdf(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    report_id = _margin_report(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.get(f"/reports/{report_id}/pdf", headers=sales_headers)
    assert res.status_code == 403


def test_pipeline_export_returns_a_real_pdf(client, director_user):
    headers = _director_headers(client, director_user)
    report_id = _pipeline_report(client, headers)

    res = client.get(f"/reports/{report_id}/pdf", headers=headers)
    assert res.status_code == 200, res.text
    assert res.headers["content-type"] == "application/pdf"
    assert res.content[:4] == b"%PDF"


def test_margin_export_returns_a_real_pdf(client, director_user):
    headers = _director_headers(client, director_user)
    report_id = _margin_report(client, headers)

    res = client.get(f"/reports/{report_id}/pdf", headers=headers)
    assert res.status_code == 200, res.text
    assert res.content[:4] == b"%PDF"


def test_override_summary_export_returns_a_real_pdf(client, director_user):
    headers = _director_headers(client, director_user)
    report_id = _override_summary_report(client, headers)

    res = client.get(f"/reports/{report_id}/pdf", headers=headers)
    assert res.status_code == 200, res.text
    assert res.content[:4] == b"%PDF"
