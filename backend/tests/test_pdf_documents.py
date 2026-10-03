import io
import json
import uuid

import pytest

from pypdf import PdfReader

from app.core.security import hash_password
from app.models.user import User, UserRole
from tests.valid_files import valid_jpeg, valid_pdf, valid_png  # noqa: E402


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


def test_estimate_pdf_shows_configured_package_content(client, director_user):
    """Part O PACKAGES / M.6: once the Director has set the badminton
    Standard tier's content, the Estimate PDF's 'Package content' section
    shows it -- not the generic fallback."""
    headers = _director_headers(client, director_user)
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == "badminton")
    client.put(
        f"/package-contents/{sport_id}/standard",
        json={
            "flooring_description": "22mm interlocking PVC sports tiles",
            "structure_description": "Type C PEB structure, hot-dip galvanised",
            "lighting_description": "6 x 150 lm/W LED floodlights, 300 lux",
            "scope_description": "Full-size court markings\nNet post set",
            "warranty_years": 5,
        },
        headers=headers,
    )
    _, estimate = _draft_estimate(client, headers)  # options default to package="standard"

    res = client.get(f"/estimates/{estimate['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    assert "Package content" in text
    assert "22mm interlocking PVC sports tiles" in text
    assert "Type C PEB structure, hot-dip galvanised" in text
    assert "Full-size court markings" in text
    assert "5 year(s)" in text


def test_estimate_pdf_shows_fallback_when_package_content_not_configured(client, director_user):
    headers = _director_headers(client, director_user)
    _, estimate = _draft_estimate(client, headers)

    res = client.get(f"/estimates/{estimate['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    assert "Package content not yet configured" in text


def test_estimate_pdf_renders_with_a_png_company_logo_configured(client, director_user):
    """R.0: 'Logo (SVG/PNG) ... for PDF.' A configured PNG logo must
    actually embed without breaking PDF generation."""
    import base64

    png_1x1 = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    headers = _director_headers(client, director_user)
    upload_res = client.post("/company/logo", files={"file": ("logo.png", png_1x1, "image/png")}, headers=headers)
    assert upload_res.status_code == 201, upload_res.text

    _, estimate = _draft_estimate(client, headers)
    res = client.get(f"/estimates/{estimate['id']}/pdf", headers=headers)
    assert res.status_code == 200
    assert res.content[:4] == b"%PDF"


def test_estimate_pdf_falls_back_to_text_header_with_an_svg_logo_configured(client, director_user):
    """reportlab/Pillow can't rasterise SVG (_company_logo_flowable's own
    docstring) -- an SVG-configured logo must not break PDF generation,
    it just doesn't get embedded."""
    headers = _director_headers(client, director_user)
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'
    upload_res = client.post("/company/logo", files={"file": ("logo.svg", svg, "image/svg+xml")}, headers=headers)
    assert upload_res.status_code == 201, upload_res.text

    _, estimate = _draft_estimate(client, headers)
    res = client.get(f"/estimates/{estimate['id']}/pdf", headers=headers)
    assert res.status_code == 200
    assert res.content[:4] == b"%PDF"
    text = _pdf_text(res)
    assert "NESTAPRIME SPORTS INFRASTRUCTURE" in text


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
    assert "GST @ 18.0%" in text  # Amendment 24: derived from the document's own gst_amount/selling_ex_gst
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


# ---------------------------------------------------------------------------
# Amendment 13 (Section 12): cover_note on the Quotation PDF
# ---------------------------------------------------------------------------


def test_quotation_pdf_shows_cover_note_when_set(client, director_user):
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers)
    client.patch(
        f"/quotations/{quotation['id']}/cover-note",
        json={"cover_note": "We're excited to help build your new badminton facility."},
        headers=headers,
    )

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    assert "We're excited to help build your new badminton facility." in text


def test_quotation_pdf_omits_cover_note_section_when_unset(client, director_user):
    """Additive only -- an unused cover_note changes nothing about
    today's PDF."""
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers)

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert res.status_code == 200
    assert res.content[:4] == b"%PDF"


def _png_bytes() -> bytes:
    from PIL import Image as PILImage

    buf = io.BytesIO()
    PILImage.new("RGB", (4, 4), color=(200, 50, 50)).save(buf, format="PNG")
    return buf.getvalue()


def test_quotation_pdf_includes_a_photo_attachment(client, director_user):
    """A photo-tagged attachment uploaded via the Quotation's existing
    Attachments panel now actually appears in the client-facing PDF --
    previously it could be attached but never made it into the PDF at
    all."""
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers)

    res = client.post(
        "/attachments",
        data={"doc_type": "quotation", "doc_id": quotation["id"], "tag": "photo"},
        files={"file": ("site-layout.png", _png_bytes(), "image/png")},
        headers=headers,
    )
    assert res.status_code == 201, res.text

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert res.status_code == 200
    text = _pdf_text(res)
    assert "Reference Images" in text


def test_quotation_pdf_omits_reference_images_section_when_no_photos(client, director_user):
    """Additive only -- a Quotation with no photo attachments renders
    exactly as before."""
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers)

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert res.status_code == 200
    text = _pdf_text(res)
    assert "Reference Images" not in text


def test_quotation_pdf_never_crashes_on_a_corrupt_stored_photo_and_never_silently_drops_it(client, director_user, db_session):
    """Purpose preserved: a stored photo that is not a readable image must not crash PDF generation (no 500). New contract:
    it is not silently left out either -- generation refuses with a structured 409 naming the image, and works once the user
    explicitly removes that image from THIS document (the attachment itself is untouched)."""
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers)
    res = client.post(
        "/attachments", data={"doc_type": "quotation", "doc_id": quotation["id"], "tag": "photo"},
        files={"file": ("not-really-a-photo.png", valid_png(), "image/png")},  # valid at upload; damaged on disk below
        headers=headers,
    )
    assert res.status_code == 201, res.text
    attachment_id = res.json()["id"]
    from pathlib import Path

    from app.models.attachment import Attachment

    path = Path(db_session.get(Attachment, uuid.UUID(attachment_id)).storage_path)
    path.write_bytes(b"this is not a real png file")

    refused = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert refused.status_code == 409, refused.status_code  # a controlled refusal, not a 500
    detail = refused.json()["detail"]
    assert detail["code"] == "pdf_images_excluded"
    assert [(e["attachment_id"], e["reason"]) for e in detail["excluded"]] == [(attachment_id, "unreadable")]

    removed = client.post(
        "/pdf-image-exclusions", json={"doc_type": "quotation", "doc_id": quotation["id"], "attachment_id": attachment_id},
        headers=headers,
    )
    assert removed.status_code == 201, removed.text
    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert res.status_code == 200 and res.content[:4] == b"%PDF"
    assert "Reference Images" not in _pdf_text(res)
    assert path.read_bytes() == b"this is not a real png file"  # the stored file is exactly as it was


# ---------------------------------------------------------------------------
# Section 14: customizable Quotation T&C / warranty table
# ---------------------------------------------------------------------------


def test_quotation_pdf_shows_default_terms_when_unset(client, director_user):
    """Baseline -- nothing about today's PDF changes until a Director
    actually edits the setting."""
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers)

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    assert "Validity: 30 days from the date of this quotation." in text
    assert "Flooring / turf" in text


def test_quotation_pdf_uses_custom_terms_when_set(client, director_user):
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers)

    res = client.post(
        "/settings",
        json={"key": "quotation_terms_and_conditions", "value": json.dumps(["A brand-new custom term."])},
        headers=headers,
    )
    assert res.status_code == 201, res.text

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    assert "A brand-new custom term." in text
    assert "Validity: 30 days from the date of this quotation." not in text


def test_quotation_pdf_uses_custom_warranty_table_when_set(client, director_user):
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers)

    res = client.post(
        "/settings",
        json={
            "key": "quotation_warranty_table",
            "value": json.dumps([["Court surface", "Manufacturer-backed, 7 years"]]),
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    assert "Court surface" in text
    assert "Flooring / turf" not in text


def test_quotation_pdf_ignores_malformed_terms_setting(client, director_user):
    """A Director-typo'd (non-JSON) value degrades to the default rather
    than crashing PDF generation for every Quotation."""
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers)

    res = client.post(
        "/settings",
        json={"key": "quotation_terms_and_conditions", "value": "not valid json at all"},
        headers=headers,
    )
    assert res.status_code == 201, res.text

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert res.status_code == 200
    assert "Validity: 30 days from the date of this quotation." in _pdf_text(res)


def test_preview_pdf_shows_draft_terms_without_saving(client, director_user):
    """The Section 14 live-preview step -- draft text renders in the
    preview PDF, but the real Quotation PDF (and the underlying Setting)
    are completely untouched."""
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers)

    res = client.post(
        f"/quotations/{quotation['id']}/preview-pdf",
        json={"terms": ["Draft-only term, never saved."]},
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert res.content[:4] == b"%PDF"
    assert "Draft-only term, never saved." in _pdf_text(res)

    real_pdf = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    real_text = _pdf_text(real_pdf)
    assert "Draft-only term, never saved." not in real_text
    assert "Validity: 30 days from the date of this quotation." in real_text

    settings_res = client.get("/settings", headers=headers)
    assert all(s["key"] != "quotation_terms_and_conditions" for s in settings_res.json())


def test_preview_pdf_requires_director_role(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers)

    sales_headers = _sales_headers(client, db_session)
    res = client.post(
        f"/quotations/{quotation['id']}/preview-pdf", json={"terms": ["x"]}, headers=sales_headers
    )
    assert res.status_code == 403


def test_template_defaults_returns_hardcoded_defaults_when_unset(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.get("/quotation-template-defaults", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert "Validity: 30 days from the date of this quotation." in body["terms"]
    assert ["Flooring / turf", "Manufacturer-backed"] in body["warranty_table"]


def test_template_defaults_reflects_a_saved_override(client, director_user):
    headers = _director_headers(client, director_user)
    client.post(
        "/settings",
        json={"key": "quotation_terms_and_conditions", "value": json.dumps(["Only term."])},
        headers=headers,
    )

    res = client.get("/quotation-template-defaults", headers=headers)
    assert res.json()["terms"] == ["Only term."]


def test_template_defaults_requires_pm_or_director(client, director_user, db_session):
    sales_headers = _sales_headers(client, db_session)
    res = client.get("/quotation-template-defaults", headers=sales_headers)
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Amendment 5: Custom Notes on the Quotation PDF's "Special Remarks" section
# ---------------------------------------------------------------------------


def test_quotation_pdf_includes_custom_notes_as_special_remarks(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    client.patch(
        f"/projects/{project_id}/notes",
        json={"custom_notes": "Client wants matte finish, confirmed by phone."},
        headers=headers,
    )
    quotation = _sent_quotation_from_project(client, headers, project_id)

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert res.status_code == 200
    text = _pdf_text(res)
    assert "Special Remarks" in text
    assert "Client wants matte finish, confirmed by phone." in text


def test_quotation_pdf_omits_special_remarks_when_no_notes(client, director_user):
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers)

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert "Special Remarks" not in _pdf_text(res)


def test_quotation_pdf_escapes_special_characters_in_custom_notes(client, director_user):
    """custom_notes is genuinely free-typed text, unlike every other string
    interpolated into this PDF -- a stray '<' or '&' must not crash
    ReportLab's mini-XML parser."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project(client, headers, client_id)
    client.patch(
        f"/projects/{project_id}/notes",
        json={"custom_notes": "Tolerance < 5% & confirm with site engineer.\nSecond line."},
        headers=headers,
    )
    quotation = _sent_quotation_from_project(client, headers, project_id)

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert res.status_code == 200, res.text
    text = _pdf_text(res)
    assert "Tolerance < 5% & confirm with site engineer." in text
    assert "Second line." in text


# ---------------------------------------------------------------------------
# Amendment 2: Quick setup's blind-quoting assumptions on the Quotation PDF
# ---------------------------------------------------------------------------


def _create_project_quick(client, headers, client_id):
    """Same shape as _create_project, but flagged quick_setup=True --
    mirrors what the frontend's Quick setup form actually sends."""
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
        "quick_setup": True,
    }
    res = client.post("/projects", json=fields, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _sent_quotation_from_project(client, headers, project_id, cost_for_option=850000):
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


def test_quick_setup_quotation_pdf_prints_the_blind_quoting_assumptions(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers)
    project_id = _create_project_quick(client, headers, client_id)
    quotation = _sent_quotation_from_project(client, headers, project_id)

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    text = _pdf_text(res)

    assert "simplified (Quick) setup" in text
    assert "Site address to be confirmed before survey" in text
    assert "Site assumed level pending physical survey" in text
    assert "Power and water assumed available on site" in text


def test_detailed_setup_quotation_pdf_omits_the_blind_quoting_assumptions(client, director_user):
    """Control: a normal (non-Quick) project must not print assumption
    clauses it never actually made."""
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers)

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    text = _pdf_text(res)

    assert "simplified (Quick) setup" not in text
    assert "Site address to be confirmed before survey" not in text


def test_an_over_budget_stored_image_is_refused_with_its_reason_instead_of_being_decoded_or_silently_dropped(client, director_user, monkeypatch):
    """Downstream processing, not validation: generated PDFs decode every embedded image in full. Images stored before the
    upload pixel ceiling existed can exceed it: generation refuses (409, reason over_image_budget) rather than decoding it or
    omitting it silently."""
    import app.api.pdf_documents as pdf_module

    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers)
    res = client.post(
        "/attachments", data={"doc_type": "quotation", "doc_id": quotation["id"], "tag": "photo"},
        files={"file": ("site-layout.png", _png_bytes(), "image/png")}, headers=headers,
    )
    assert res.status_code == 201, res.text
    ok = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert "Reference Images" in _pdf_text(ok)  # within budget: embedded as before

    monkeypatch.setattr(pdf_module, "MAX_EMBED_PIXELS", 1)  # the same image is now over budget
    refused = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert refused.status_code == 409
    assert [e["reason"] for e in refused.json()["detail"]["excluded"]] == ["over_image_budget"]


def test_a_documents_total_image_pixels_are_bounded_across_all_its_images(client, director_user, monkeypatch):
    """Per-document budget: three 4x4 photos (16 px each) against a 40-pixel document budget: the third is refused (409,
    over_document_budget); once it is explicitly removed from this document the other two are embedded."""
    import app.api.pdf_documents as pdf_module

    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers)
    ids = []
    for i in range(3):  # distinct images (the PDF library shares identical ones, which would hide the count)
        res = client.post(
            "/attachments", data={"doc_type": "quotation", "doc_id": quotation["id"], "tag": "photo"},
            files={"file": (f"photo{i}.png", valid_png(color=(40 * i + 10, 90, 200 - 30 * i), size=(4, 4)), "image/png")}, headers=headers,
        )
        assert res.status_code == 201, res.text
        ids.append(res.json()["id"])

    def embedded(res):
        return res.content.count(b"/Subtype /Image")

    unbounded = embedded(client.get(f"/quotations/{quotation['id']}/pdf", headers=headers))
    monkeypatch.setattr(pdf_module, "MAX_PDF_IMAGE_PIXELS", 40)
    refused = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert unbounded >= 3 and refused.status_code == 409
    excluded = refused.json()["detail"]["excluded"]
    assert [e["reason"] for e in excluded] == ["over_document_budget"] and len(excluded) == 1
    client.post("/pdf-image-exclusions", json={"doc_type": "quotation", "doc_id": quotation["id"], "attachment_id": excluded[0]["attachment_id"]}, headers=headers)
    bounded = embedded(client.get(f"/quotations/{quotation['id']}/pdf", headers=headers))
    assert bounded == unbounded - 1, (unbounded, bounded)


def test_concurrent_pdf_builds_in_one_worker_are_serialised_so_image_memory_cannot_stack():
    import threading
    import time

    import app.api.pdf_documents as pdf_module

    state = {"now": 0, "max": 0}
    lock = threading.Lock()

    @pdf_module._one_pdf_build_at_a_time
    def fake_build():
        with lock:
            state["now"] += 1
            state["max"] = max(state["max"], state["now"])
        time.sleep(0.05)
        with lock:
            state["now"] -= 1
        return "done"

    results = []
    # one build running + MAX_PDF_BUILD_WAITERS waiting: every request is served, one at a time
    count = 1 + pdf_module.MAX_PDF_BUILD_WAITERS
    threads = [threading.Thread(target=lambda: results.append(fake_build())) for _ in range(count)]
    [t.start() for t in threads]
    [t.join(30) for t in threads]
    assert results == ["done"] * count and state["max"] == 1  # concurrent requests, never two builds at once


def test_a_pdf_request_that_cannot_get_the_build_slot_is_told_to_retry_with_503(client, director_user, monkeypatch):
    import threading

    import app.api.pdf_documents as pdf_module

    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers)
    slot = threading.BoundedSemaphore(1)
    slot.acquire()  # another build holds the worker's only slot
    monkeypatch.setattr(pdf_module, "_PDF_BUILD_SLOT", slot)
    monkeypatch.setattr(pdf_module, "PDF_BUILD_WAIT_SECONDS", 0.2)
    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert res.status_code == 503 and res.json()["detail"] == {"code": "pdf_busy", "message": "PDF generation is busy. Please retry shortly."}
    assert res.headers["retry-after"] == "5"
    slot.release()
    assert client.get(f"/quotations/{quotation['id']}/pdf", headers=headers).status_code == 200  # and the slot works again


def test_an_oversized_logo_is_refused_before_any_pixel_data_is_decoded(client, director_user, monkeypatch):
    """Logos are budgeted like every other image and the refusal happens from the header: load() is never called."""
    import app.api.pdf_documents as pdf_module
    from PIL import Image as PILImage

    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers)
    assert client.post("/company/logo", files={"file": ("logo.png", _png_bytes(), "image/png")}, headers=headers).status_code in (200, 201)
    loaded = []
    real_load = PILImage.Image.load
    monkeypatch.setattr(PILImage.Image, "load", lambda self, *a, **k: (loaded.append(self.size), real_load(self, *a, **k))[1])
    monkeypatch.setattr(pdf_module, "MAX_EMBED_PIXELS", 1)  # the 4x4 logo is now over budget
    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert res.status_code == 200 and res.content[:4] == b"%PDF"
    assert loaded == [], f"an over-budget image was decoded: {loaded}"


def test_a_stored_png_with_valid_checksums_but_corrupt_pixel_data_is_refused_by_the_pdf_without_crashing(client, director_user, db_session):
    """Rendering-side handling for data stored BEFORE the stream check existed (the upload path now refuses it): a 409
    naming the image, never a 500 and never a silent omission."""
    from pathlib import Path

    from app.models.attachment import Attachment

    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers)
    res = client.post(
        "/attachments", data={"doc_type": "quotation", "doc_id": quotation["id"], "tag": "photo"},
        files={"file": ("layout.png", _png_bytes(), "image/png")}, headers=headers,
    )
    assert res.status_code == 201, res.text
    path = Path(db_session.get(Attachment, uuid.UUID(res.json()["id"])).storage_path)
    path.write_bytes(_png_with_garbage_pixel_data())
    pdf = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert pdf.status_code == 409 and pdf.json()["detail"]["excluded"][0]["reason"] == "unreadable"


def _png_with_garbage_pixel_data() -> bytes:
    import struct
    import zlib

    def chunk(kind, data):
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 8, 8, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", b"this is not a zlib stream at all") + chunk(b"IEND", b""))
