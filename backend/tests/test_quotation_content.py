"""Amendment 54 (Section 58): what the client-facing Quotation says about the work.

A "Scope of work" section (package content + Part I inclusions, no prices), a
letter block around the cover note, a richer fact-only AI draft, and a `pdf_gaps`
note for what the PDF leaves out. All of it appears only on a quotation not yet
sent and never in tender mode -- what a client already received does not change."""

import io
import re
from datetime import date, timedelta

from pypdf import PdfReader

from app.api import documents as documents_api
from app.api import pdf_documents
from app.services import quotation_content
from tests.test_quotations_admin import (
    _add_project_sport,
    _approve_option,
    _create_project,
    _login,
    _released_quotation,
    _sent_estimate,
    _verified_cost_sheet,
)

PACKAGE = {
    "flooring_description": "22mm interlocking PVC sports tiles",
    "structure_description": "Type C PEB structure, hot-dip galvanised",
    "lighting_description": "6 x 150 lm/W LED floodlights, 300 lux",
    "scope_description": "Full-size court markings\nNet post set",
    "warranty_years": 5,
}
BANK = {
    "company_bank_name": "Test Bank",
    "company_bank_account_name": "NestaPrime Test Pvt Ltd",
    "company_bank_account_number": "1234567890",
    "company_bank_ifsc": "TEST0001234",
}


def _director(client, director_user):
    return _login(client, "director@test.local")


def _pdf_text(response) -> str:
    assert response.status_code == 200, response.text
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(response.content)).pages)


def _flat(text: str) -> str:
    return re.sub(r"\s+", " ", text)


def _set(client, headers, key, value):
    res = client.post("/settings", json={"key": key, "value": value}, headers=headers)
    assert res.status_code in (200, 201), res.text


def _set_package_content(client, headers, sport_key="badminton", tier="standard"):
    sport_id = next(s["id"] for s in client.get("/sports", headers=headers).json() if s["key"] == sport_key)
    res = client.put(f"/package-contents/{sport_id}/{tier}", json=PACKAGE, headers=headers)
    assert res.status_code in (200, 201), res.text


def _quotation(client, headers, name="Content Test School", client_type="school", contact_name=None, send=False):
    """A released (or sent) private-client quotation for badminton, standard."""
    res = client.post(
        "/clients",
        json={"name": name, "type": client_type, **({"contact_name": contact_name} if contact_name else {})},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    client_id = res.json()["id"]
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)
    _verified_cost_sheet(client, headers, project_id)
    estimate = _sent_estimate(client, headers, project_id, project_sport_id)
    option_id = estimate["options"][0]["id"]
    _approve_option(client, headers, estimate["id"], option_id)
    quotation = _released_quotation(client, headers, project_id, estimate["id"], option_id)
    if send:
        assert client.post(f"/quotations/{quotation['id']}/send", headers=headers).status_code == 200
    return client_id, project_id, quotation


def _set_cover_note(client, headers, quotation_id, text="We are pleased to submit our quotation."):
    res = client.patch(f"/quotations/{quotation_id}/cover-note", json={"cover_note": text}, headers=headers)
    assert res.status_code == 200, res.text


def _pdf(client, headers, quotation_id):
    return _pdf_text(client.get(f"/quotations/{quotation_id}/pdf", headers=headers))


# --- Scope of work ------------------------------------------------------------


def test_scope_of_work_lists_package_content_and_inclusions_without_a_price(client, director_user):
    headers = _director(client, director_user)
    _set_package_content(client, headers)
    _, project_id, quotation = _quotation(client, headers)
    scope_item_id = next(s["id"] for s in client.get("/scope-items", headers=headers).json() if s["key"] == "changing_rooms")
    assert client.post(f"/projects/{project_id}/scope-items", json={"scope_item_id": scope_item_id, "note": "two rooms"}, headers=headers).status_code == 201

    text = _pdf(client, headers, quotation["id"])
    assert "Scope of work" in text
    section = text[text.index("Scope of work"):text.index("Delivery timeline")]
    for expected in ("22mm interlocking PVC sports tiles", "Type C PEB structure", "300 lux", "Full-size court markings", "5 year(s)"):
        assert expected in section
    assert "Included in the scope of work" in section and "two rooms" in section
    assert "Rs" not in section and "₹" not in section  # no price on any descriptive line
    assert "Total Project Cost" in text  # the total is still one lump-sum figure


def test_a_sport_without_package_content_is_omitted_and_never_called_not_configured(client, director_user):
    headers = _director(client, director_user)
    _, project_id, quotation = _quotation(client, headers)
    text = _pdf(client, headers, quotation["id"])
    assert "not yet configured" not in text.lower() and "not configured" not in text.lower()
    assert "Package content" not in text
    # nothing at all to show (no package content, no included scope items) -> no heading either
    assert "Scope of work" not in text
    # ...but the included scope items alone still make a section
    scope_item_id = next(s["id"] for s in client.get("/scope-items", headers=headers).json() if s["key"] == "changing_rooms")
    client.post(f"/projects/{project_id}/scope-items", json={"scope_item_id": scope_item_id}, headers=headers)
    text = _pdf(client, headers, quotation["id"])
    assert "Scope of work" in text and "Included in the scope of work" in text
    assert "not yet configured" not in text.lower()


def test_a_sent_quotation_and_a_tender_quotation_have_none_of_the_new_sections(client, director_user):
    headers = _director(client, director_user)
    _set_package_content(client, headers)
    _set(client, headers, "company_signatory_name", "A. Signatory")
    _, _, sent = _quotation(client, headers, name="Sent Content School", send=True)
    _set_cover_note(client, headers, sent["id"])  # allowed on a sent quotation too
    text = _pdf(client, headers, sent["id"])
    assert "Scope of work" not in text and "Yours faithfully" not in text and "Subject:" not in text
    assert "We are pleased to submit our quotation." in text  # the note still prints, as a plain paragraph

    _, project_id, tender = _quotation(client, headers, name="Tender Content Dept", client_type="government")
    assert client.get(f"/projects/{project_id}", headers=headers).json()["tender_mode"] is True
    _set_cover_note(client, headers, tender["id"])
    text = _pdf(client, headers, tender["id"])
    assert "Bill of Quantities" in text
    assert "Scope of work" not in text and "Yours faithfully" not in text


# --- the letter block -----------------------------------------------------------


def test_the_letter_block_prints_only_with_a_cover_note_and_uses_the_signatory_settings(client, director_user):
    headers = _director(client, director_user)
    _, _, quotation = _quotation(client, headers, contact_name="Mr. Contact Person")
    text = _flat(_pdf(client, headers, quotation["id"]))
    for absent in ("Subject:", "Yours faithfully", "Kind attention"):
        assert absent not in text  # no cover note -> the top of the PDF is what it was

    _set_cover_note(client, headers, quotation["id"], "Line one.\nLine two.")
    text = _flat(_pdf(client, headers, quotation["id"]))
    assert "Kind attention: Mr. Contact Person" in text
    assert f"Subject: Quotation {quotation['document_no']} -- Badminton at Mumbai" in text
    assert "Line one. Line two." in text
    assert "Yours faithfully," in text and "For NestaPrime Sports Infrastructure" in text

    _set(client, headers, "company_legal_name", "NestaPrime Test Pvt Ltd")
    _set(client, headers, "company_signatory_name", "R. Patni")
    _set(client, headers, "company_signatory_designation", "Director")
    text = _flat(_pdf(client, headers, quotation["id"]))
    assert "For NestaPrime Test Pvt Ltd" in text and "R. Patni" in text and "Director" in text


def test_the_addressee_is_the_active_signatory_then_the_contact_then_nobody(client, director_user):
    headers = _director(client, director_user)
    client_id, _, quotation = _quotation(client, headers, contact_name="Mr. Contact Person")
    _set_cover_note(client, headers, quotation["id"])
    payload = {
        "name": "Priya Sharma", "designation": "Principal", "email": "p@x.example",
        "authorization_date": str(date.today() - timedelta(days=1)),
    }
    assert client.post(f"/clients/{client_id}/signatories", json=payload, headers=headers).status_code == 201
    assert "Kind attention: Priya Sharma, Principal" in _flat(_pdf(client, headers, quotation["id"]))

    # a deactivated signatory is not addressed; the contact name is
    signatories = client.get(f"/clients/{client_id}/signatories", headers=headers).json()
    res = client.patch(f"/clients/{client_id}/signatories/{signatories[0]['id']}", json={"is_active": False}, headers=headers)
    assert res.status_code == 200, res.text
    assert "Kind attention: Mr. Contact Person" in _flat(_pdf(client, headers, quotation["id"]))

    _, _, no_contact = _quotation(client, headers, name="No Contact School")
    _set_cover_note(client, headers, no_contact["id"])
    assert "Kind attention" not in _pdf(client, headers, no_contact["id"])


def test_free_typed_letter_values_are_escaped(client, director_user):
    headers = _director(client, director_user)
    _, _, quotation = _quotation(client, headers)
    _set_cover_note(client, headers, quotation["id"], "Rates < 5 & fixed > 3")
    _set(client, headers, "company_signatory_name", "A <b>& Co")
    text = _flat(_pdf(client, headers, quotation["id"]))
    assert "Rates < 5 & fixed > 3" in text and "A <b>& Co" in text


# --- warranty without an invented duration ------------------------------------------


def test_an_unsent_quotation_without_a_configured_duration_has_no_duration_column(client, director_user):
    headers = _director(client, director_user)
    _, _, corporate = _quotation(client, headers, name="Corporate Content Ltd", client_type="corporate")
    text = _pdf(client, headers, corporate["id"])
    assert "Not yet configured" not in text and "Duration" not in text
    _, _, school = _quotation(client, headers, name="School Content Ltd", client_type="school")
    text = _pdf(client, headers, school["id"])
    assert "Duration" in text and "5 year(s)" in text  # school has a documented duration

    _, _, corporate_sent = _quotation(client, headers, name="Corporate Sent Ltd", client_type="corporate", send=True)
    assert "Not yet configured (Q.1)" in _pdf(client, headers, corporate_sent["id"])  # unchanged once sent


# --- pdf_gaps ---------------------------------------------------------------------------


def test_pdf_gaps_names_what_the_pdf_leaves_out_and_empties_when_complete(client, director_user):
    headers = _director(client, director_user)
    _, _, quotation = _quotation(client, headers)
    gaps = client.get(f"/quotations/{quotation['id']}", headers=headers).json()["pdf_gaps"]
    joined = " | ".join(gaps)
    assert "No package content is set for Badminton (Standard)" in joined
    assert "no cover note" in joined.lower()
    assert "Bank details are not set" in joined

    _set_package_content(client, headers)
    _set_cover_note(client, headers, quotation["id"])
    gaps = client.get(f"/quotations/{quotation['id']}", headers=headers).json()["pdf_gaps"]
    assert any("No authorised signatory is set" in g for g in gaps)
    _set(client, headers, "company_signatory_name", "R. Patni")
    gaps = client.get(f"/quotations/{quotation['id']}", headers=headers).json()["pdf_gaps"]
    assert any("no designation" in g for g in gaps)
    _set(client, headers, "company_signatory_designation", "Director")
    _set(client, headers, "company_bank_name", "Test Bank")
    gaps = client.get(f"/quotations/{quotation['id']}", headers=headers).json()["pdf_gaps"]
    assert gaps == ["Bank details are incomplete (not set: Account name, Account no., IFSC)."]
    for key, value in BANK.items():
        _set(client, headers, key, value)
    assert client.get(f"/quotations/{quotation['id']}", headers=headers).json()["pdf_gaps"] == []


def test_pdf_gaps_on_a_sent_quotation_only_names_the_bank_details_and_carries_no_amount(client, director_user):
    headers = _director(client, director_user)
    _, _, sent = _quotation(client, headers, send=True)
    gaps = client.get(f"/quotations/{sent['id']}", headers=headers).json()["pdf_gaps"]
    assert gaps == ["Bank details are not set, so the PDF has no 'Payment to' block."]
    listed = client.get(f"/projects/{sent['project_id']}/quotations", headers=headers).json()
    assert listed[0]["pdf_gaps"] == gaps
    assert "Rs" not in " ".join(gaps)


def test_the_bank_keys_here_match_the_ones_the_pdf_prints():
    assert set(quotation_content.BANK_SETTING_LABELS) == pdf_documents._COMPANY_BANK_KEYS


# --- the richer AI draft -------------------------------------------------------------------


def _capture_draft(client, headers, quotation_id, monkeypatch):
    captured = {}

    def fake(prompt, max_tokens=400):
        captured["prompt"], captured["max_tokens"] = prompt, max_tokens
        return "A draft."

    monkeypatch.setattr(documents_api.ai_content, "generate_text", fake)
    res = client.post(f"/quotations/{quotation_id}/draft-cover-note", headers=headers)
    assert res.status_code == 200 and res.json() == {"draft": "A draft."}
    return captured


def test_the_draft_prompt_carries_the_set_facts_and_the_no_invention_rules(client, director_user, monkeypatch):
    headers = _director(client, director_user)
    _set_package_content(client, headers)
    client_id, _, quotation = _quotation(client, headers, name="Prompt Facts School", contact_name="Ms. Contact")
    captured = _capture_draft(client, headers, quotation["id"], monkeypatch)
    prompt = captured["prompt"]
    assert captured["max_tokens"] == 600
    for fact in (
        "Client: Prompt Facts School", "Addressed to: Ms. Contact", "Site: Mumbai", "Sport: Badminton",
        "Standard package", "Flooring: 22mm interlocking PVC sports tiles", "Structure: Type C PEB",
        "Lighting: 6 x 150 lm/W", "Full-size court markings; Net post set", "Warranty: 5 year(s)",
        "valid for 30 days", "Quotation total (single lump sum, incl. GST): Rs",
    ):
        assert fact in prompt, fact
    for rule in ("ONLY the facts", "past projects", "do not invent", "greeting", "placeholder"):
        assert rule.lower() in prompt.lower(), rule


def test_the_draft_prompt_leaves_out_facts_that_are_not_set(client, director_user, monkeypatch):
    headers = _director(client, director_user)
    _, _, quotation = _quotation(client, headers, name="Sparse Facts School")
    prompt = _capture_draft(client, headers, quotation["id"], monkeypatch)["prompt"]
    for absent in ("Addressed to", "Flooring:", "Structure:", "Lighting:", "Scope:", "Warranty:"):
        assert absent not in prompt, absent
    assert "Client: Sparse Facts School" in prompt


def test_a_failed_draft_still_returns_503_and_saves_nothing(client, director_user, monkeypatch):
    headers = _director(client, director_user)
    _, _, quotation = _quotation(client, headers)

    def boom(prompt, max_tokens=400):
        raise documents_api.ai_content.AiContentError("AI drafting returned 500")

    monkeypatch.setattr(documents_api.ai_content, "generate_text", boom)
    res = client.post(f"/quotations/{quotation['id']}/draft-cover-note", headers=headers)
    assert res.status_code == 503 and "AI drafting returned 500" in res.json()["detail"]
    assert client.get(f"/quotations/{quotation['id']}", headers=headers).json()["cover_note"] is None
