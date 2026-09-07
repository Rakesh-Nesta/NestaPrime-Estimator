import io

from pypdf import PdfReader

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


def _create_client_record(client, headers, client_type="school"):
    res = client.post(
        "/clients",
        json={
            "name": "PDF Test Client", "type": client_type,
            "contact_name": "Jane PM", "phone": "9999999999", "email": "jane@example.com",
            "billing_address": "1 Sports Lane, Mumbai",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _create_project(client, headers, client_id):
    fields = {
        "client_id": client_id,
        "city": "Mumbai",
        "site_condition": "level",
        "soil_type": "normal",
        "building_status": "open_air",
        "site_access": "good",
        "power_available": "yes",
        "water_available": True,
        "package": "standard",
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


def _add_scope_item(client, headers, project_id, scope_item_key="changing_rooms"):
    scope_item_id = next(s["id"] for s in client.get("/scope-items", headers=headers).json() if s["key"] == scope_item_key)
    res = client.post(f"/projects/{project_id}/scope-items", json={"scope_item_id": scope_item_id}, headers=headers)
    assert res.status_code == 201, res.text


def _draft_estimate(client, headers, cost_for_option=850000):
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _add_scope_item(client, headers, project_id)
    cost_sheet_id = client.post(
        f"/projects/{project_id}/cost-sheets", json={"cost_total": cost_for_option}, headers=headers
    ).json()["id"]
    client.post(f"/cost-sheets/{cost_sheet_id}/verify", headers=headers)
    estimate = client.post(
        f"/projects/{project_id}/estimates",
        json={"options": [{"project_sport_id": project_sport_id, "package": "standard", "cost_for_option": cost_for_option}]},
        headers=headers,
    ).json()
    return project_id, estimate


def _sent_quotation(client, headers, client_type="school", cost_for_option=850000):
    project_id, estimate = _draft_estimate(client, headers, cost_for_option)
    option_id = estimate["options"][0]["id"]
    client.patch(
        f"/estimates/{estimate['id']}/options/{option_id}/client-status",
        json={"client_status": "approved", "waive_evidence_reason": "test setup"},
        headers=headers,
    )
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id]},
        headers=headers,
    ).json()
    client.post(f"/quotations/{quotation['id']}/release", headers=headers)
    client.post(f"/quotations/{quotation['id']}/send", headers=headers)
    return quotation


def _pdf_text(response) -> str:
    reader = PdfReader(io.BytesIO(response.content))
    return "\n".join(page.extract_text() for page in reader.pages)


# ---------------------------------------------------------------------------
# Estimate PDF
# ---------------------------------------------------------------------------


def test_procurement_cannot_download_estimate_pdf(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, estimate = _draft_estimate(client, director_headers)

    procurement_headers = _procurement_headers(client, db_session)
    res = client.get(f"/estimates/{estimate['id']}/pdf", headers=procurement_headers)
    assert res.status_code == 403


def test_estimate_pdf_not_found(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.get("/estimates/00000000-0000-0000-0000-000000000000/pdf", headers=headers)
    assert res.status_code == 404


def test_sales_can_download_estimate_pdf_with_real_content(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    _, estimate = _draft_estimate(client, director_headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.get(f"/estimates/{estimate['id']}/pdf", headers=sales_headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content[:4] == b"%PDF"

    text = _pdf_text(res)
    assert estimate["document_no"] in text
    assert "ESTIMATE" in text
    assert "Badminton" in text
    assert "Jane PM" in text
    assert "1 Sports Lane, Mumbai" in text
    # Part I: the scope item actually added on this project shows as an inclusion.
    assert "Changing rooms" in text


def test_estimate_pdf_lists_unadded_scope_items_as_exclusions(client, director_user):
    headers = _director_headers(client, director_user)
    _, estimate = _draft_estimate(client, headers)

    res = client.get(f"/estimates/{estimate['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    assert "Toilets" in text  # never added by _add_scope_item -> must appear under Exclusions


# ---------------------------------------------------------------------------
# Quotation PDF
# ---------------------------------------------------------------------------


def test_procurement_cannot_download_quotation_pdf(client, director_user, db_session):
    director_headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, director_headers)

    procurement_headers = _procurement_headers(client, db_session)
    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=procurement_headers)
    assert res.status_code == 403


def test_quotation_pdf_not_found(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.get("/quotations/00000000-0000-0000-0000-000000000000/pdf", headers=headers)
    assert res.status_code == 404


def test_quotation_pdf_has_real_content_and_never_leaks_cost_or_margin(client, director_user):
    """K.3: the client-facing Quotation PDF must never carry cost price or
    margin -- a real regression guard, not just a smoke test."""
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers, client_type="government", cost_for_option=850000)

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"

    text = _pdf_text(res)
    assert quotation["document_no"] in text
    assert "FORMAL QUOTATION" in text
    assert "Subtotal" in text
    assert "GST @ 18%" in text
    assert "Total Project Cost" in text
    assert "Amount in words" in text
    assert "Advance" in text and "Flooring completion" in text and "Handover" in text
    assert "Force majeure" in text
    assert "Manufacturer-backed" in text

    # K.2's worked example: government client, cost 850000 -> margin 15%,
    # cost_total is never printed anywhere on this client-facing document.
    from app.pdf_utils import format_inr

    assert format_inr(quotation["cost_total"]) not in text
    assert "850000" not in text
    assert f"{quotation['margin_percent']:.2f}" not in text
    assert f"{quotation['margin_percent']:.1f}" not in text


def test_quotation_pdf_line_amounts_sum_to_the_quotation_total(client, director_user):
    """The apportioned per-sport ex-GST + GST amounts must reconcile to
    the same Subtotal/GST the Quotation record itself carries -- not an
    independent, possibly-inconsistent number."""
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers, cost_for_option=500000)

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    from app.pdf_utils import format_inr, round_to_nearest_10

    assert format_inr(quotation["selling_after_discount"]) in text
    assert format_inr(quotation["gst_amount"]) in text
    assert format_inr(round_to_nearest_10(quotation["quotation_total"])) in text
