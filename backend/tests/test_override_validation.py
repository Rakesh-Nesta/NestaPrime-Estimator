"""Amendment 22 (Section 28): Master Settings/Override values are never
validated. Covers all three parts of the fix: write-time rejection of a
non-numeric override_value against a numeric master_value, the read-side
parse_setting_number() helper raising a clear error instead of a bare
crash, and the GST-rate divisor guard in pricing.py."""

from app.core.security import hash_password
from app.core.settings_parse import parse_setting_number
from app.models.user import User, UserRole
from fastapi import HTTPException
import pytest


def _login(client, email, password="TestPass!1"):
    res = client.post("/auth/login", data={"username": email, "password": password})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _director_headers(client, director_user):
    return _login(client, "director@test.local")


# ---------------------------------------------------------------------------
# parse_setting_number (read-side fix)
# ---------------------------------------------------------------------------


def test_parse_setting_number_parses_valid_numbers():
    assert parse_setting_number("gst_rate_percent", "18.0", float) == 18.0
    assert parse_setting_number("number_of_courts", "3", int) == 3


def test_parse_setting_number_raises_a_clear_error_naming_the_key():
    with pytest.raises(HTTPException) as exc_info:
        parse_setting_number("gst_rate_percent", "not-a-number", float)
    assert exc_info.value.status_code == 500
    assert "gst_rate_percent" in exc_info.value.detail
    assert "not-a-number" in exc_info.value.detail


# ---------------------------------------------------------------------------
# Write-time validation on /overrides (Part 3 of the fix)
# ---------------------------------------------------------------------------


def test_numeric_override_with_non_numeric_value_is_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/overrides",
        json={
            "document_type": "cost_sheet",
            "document_id": "00000000-0000-0000-0000-0000000000dd",
            "setting_key": "site_establishment_percent",
            "master_value": "6.0",  # numeric
            "override_value": "not-a-number",
            "reason": "test",
        },
        headers=headers,
    )
    assert res.status_code == 422, res.text
    assert "site_establishment_percent" in res.json()["detail"]


def test_non_numeric_setting_override_is_unaffected(client, director_user):
    """A genuinely text-valued Setting (company details, T&C clauses,
    etc.) must still accept a text override -- this fix only kicks in
    when master_value itself is numeric."""
    headers = _director_headers(client, director_user)
    res = client.post(
        "/overrides",
        json={
            "document_type": "quotation",
            "document_id": "00000000-0000-0000-0000-0000000000ee",
            "setting_key": "company_tagline",
            "master_value": "Building champions since 2015",  # not numeric
            "override_value": "Custom tagline for this client",  # not numeric either
            "reason": "test",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text


def test_numeric_override_with_numeric_value_still_succeeds(client, director_user):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/overrides",
        json={
            "document_type": "cost_sheet",
            "document_id": "00000000-0000-0000-0000-0000000000ff",
            "setting_key": "contingency_percent",
            "master_value": "5.0",
            "override_value": "7.5",
            "reason": "test",
        },
        headers=headers,
    )
    assert res.status_code == 201, res.text


# ---------------------------------------------------------------------------
# GST-rate divisor guard (Part 2 of the fix)
# ---------------------------------------------------------------------------


def test_absurd_gst_rate_setting_is_rejected_not_a_crash(client, director_user):
    headers = _director_headers(client, director_user)
    set_res = client.post(
        "/settings", json={"key": "gst_rate_percent", "value": "-150", "reason": "test"}, headers=headers
    )
    assert set_res.status_code == 201, set_res.text

    quote = client.post(
        "/pricing/quote",
        json={"cost_incl_contingency": 850000, "client_type": "government"},
        headers=headers,
    )
    assert quote.status_code == 400, quote.text
    assert "GST rate" in quote.json()["detail"]
