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


def _set_setting(client, headers, key, value):
    res = client.post("/settings", json={"key": key, "value": value, "reason": "test setup"}, headers=headers)
    assert res.status_code == 201, res.text


def _create_client_record(client, headers, client_type="school", name="Quick Win Client"):
    res = client.post(
        "/clients",
        json={"name": name, "type": client_type, "contact_name": "Jane PM", "phone": "9999999999"},
        headers=headers,
    )
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


def _draft_estimate(client, headers, client_type="school", cost_for_option=850000):
    client_id = _create_client_record(client, headers, client_type=client_type)
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
    return project_id, project_sport_id, estimate


def _sent_quotation(client, headers, client_type="school", cost_for_option=850000):
    project_id, project_sport_id, estimate = _draft_estimate(client, headers, client_type, cost_for_option)
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
    return project_sport_id, quotation


def _pdf_text(response) -> str:
    reader = PdfReader(io.BytesIO(response.content))
    return "\n".join(page.extract_text() for page in reader.pages)


# ---------------------------------------------------------------------------
# Warranty years (K.1 Appendix B / Q.1 "Commercial terms")
# ---------------------------------------------------------------------------


def test_warranty_years_defaults_to_five_for_school(client, director_user):
    """B.2: 'Client = School -> ... Warranty 5 yr' -- the only concrete
    duration the blueprint gives for any client type."""
    headers = _director_headers(client, director_user)
    _, quotation = _sent_quotation(client, headers, client_type="school")

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    assert "5 year(s)" in text


def test_warranty_years_unconfigured_for_other_client_types(client, director_user):
    """No other client type has a duration figure anywhere in the
    blueprint -- nothing is fabricated for them."""
    headers = _director_headers(client, director_user)
    _, quotation = _sent_quotation(client, headers, client_type="corporate")

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    assert "Not yet configured (Q.1)" in text
    assert "year(s)" not in text


def test_warranty_years_configurable_per_client_type(client, director_user):
    headers = _director_headers(client, director_user)
    _set_setting(client, headers, "warranty_years_corporate", "2")
    _, quotation = _sent_quotation(client, headers, client_type="corporate")

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    assert "2 year(s)" in text


def test_warranty_years_override_for_school_takes_precedence_over_default(client, director_user):
    headers = _director_headers(client, director_user)
    _set_setting(client, headers, "warranty_years_school", "7")
    _, quotation = _sent_quotation(client, headers, client_type="school")

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    assert "7 year(s)" in text
    assert "5 year(s)" not in text


# ---------------------------------------------------------------------------
# Payment schedule per client type (Part N / Q.1)
# ---------------------------------------------------------------------------


def test_payment_schedule_defaults_to_forty_forty_twenty_for_any_client_type(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, client_type="club")
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)

    res = client.get(f"/schedule/project-sports/{project_sport_id}", headers=headers)
    assert res.status_code == 200, res.text
    by_name = {m["name"]: m["percent"] for m in res.json()["payment_schedule"]}
    assert by_name == {"Advance": 40.0, "Flooring completion": 40.0, "Handover": 20.0}


def test_payment_schedule_configurable_per_client_type(client, director_user):
    """Q.1: 'Payment templates ... Per client type ... Director.'"""
    headers = _director_headers(client, director_user)
    _set_setting(client, headers, "payment_schedule_advance_percent_club", "50")
    _set_setting(client, headers, "payment_schedule_milestone_percent_club", "30")
    _set_setting(client, headers, "payment_schedule_handover_percent_club", "20")

    client_id = _create_client_record(client, headers, client_type="club")
    project_id = _create_project(client, headers, client_id)
    project_sport_id = _add_project_sport(client, headers, project_id)

    res = client.get(f"/schedule/project-sports/{project_sport_id}", headers=headers)
    by_name = {m["name"]: m["percent"] for m in res.json()["payment_schedule"]}
    assert by_name == {"Advance": 50.0, "Flooring completion": 30.0, "Handover": 20.0}


def test_payment_schedule_override_for_one_client_type_does_not_affect_another(client, director_user):
    headers = _director_headers(client, director_user)
    _set_setting(client, headers, "payment_schedule_advance_percent_club", "50")

    club_client_id = _create_client_record(client, headers, client_type="club", name="Club Client")
    club_project_id = _create_project(client, headers, club_client_id)
    club_project_sport_id = _add_project_sport(client, headers, club_project_id)

    school_client_id = _create_client_record(client, headers, client_type="school", name="School Client")
    school_project_id = _create_project(client, headers, school_client_id)
    school_project_sport_id = _add_project_sport(client, headers, school_project_id)

    club_schedule = client.get(f"/schedule/project-sports/{club_project_sport_id}", headers=headers).json()
    school_schedule = client.get(f"/schedule/project-sports/{school_project_sport_id}", headers=headers).json()

    club_advance = next(m["percent"] for m in club_schedule["payment_schedule"] if m["name"] == "Advance")
    school_advance = next(m["percent"] for m in school_schedule["payment_schedule"] if m["name"] == "Advance")
    assert club_advance == 50.0
    assert school_advance == 40.0


# ---------------------------------------------------------------------------
# Company master data (Part O COMPANY / R.0 checklist)
# ---------------------------------------------------------------------------


def test_company_details_absent_by_default(client, director_user):
    headers = _director_headers(client, director_user)
    _, quotation = _sent_quotation(client, headers)

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    assert "PAN:" not in text
    assert "GSTIN:" not in text
    assert "Payment to" not in text


def test_company_identity_details_appear_once_configured(client, director_user):
    headers = _director_headers(client, director_user)
    _set_setting(client, headers, "company_pan", "AAAAA1234A")
    _set_setting(client, headers, "company_gstin", "27AAAAA1234A1Z5")

    _, quotation = _sent_quotation(client, headers)
    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    assert "AAAAA1234A" in text
    assert "27AAAAA1234A1Z5" in text


def test_company_identity_details_also_appear_on_estimate_pdf(client, director_user):
    headers = _director_headers(client, director_user)
    _set_setting(client, headers, "company_pan", "AAAAA1234A")

    _, _, estimate = _draft_estimate(client, headers)
    res = client.get(f"/estimates/{estimate['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    assert "AAAAA1234A" in text


def test_company_bank_details_appear_only_once_configured(client, director_user):
    headers = _director_headers(client, director_user)
    _set_setting(client, headers, "company_bank_name", "HDFC Bank")
    _set_setting(client, headers, "company_bank_account_number", "123456789012")
    _set_setting(client, headers, "company_bank_ifsc", "HDFC0000123")

    _, quotation = _sent_quotation(client, headers)
    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    assert "Payment to" in text
    assert "HDFC Bank" in text
    assert "123456789012" in text
    assert "HDFC0000123" in text


def test_jurisdiction_clause_defaults_to_generic_wording(client, director_user):
    headers = _director_headers(client, director_user)
    _, quotation = _sent_quotation(client, headers)

    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    assert "NestaPrime's registered office city" in text


def test_jurisdiction_clause_uses_configured_registered_office_city(client, director_user):
    headers = _director_headers(client, director_user)
    _set_setting(client, headers, "company_registered_office_city", "Mumbai")

    _, quotation = _sent_quotation(client, headers)
    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    text = _pdf_text(res)
    assert "courts at Mumbai" in text
    assert "NestaPrime's registered office city" not in text
