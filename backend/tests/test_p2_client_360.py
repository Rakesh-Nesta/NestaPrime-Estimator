"""P2 Client 360 Implementation Contract (revision 4): Contacts, Sites, source tracking,
duplicate suggestions, and the 3-check Communication tab. Acceptance cases reference the
contract's own Section 9 numbering in comments where they map directly."""

from datetime import date

from app.models.client import Client
from app.models.client_contact import ClientContact
from app.models.client_site import ClientSite
from app.models.duplicate_client_pair import DismissedDuplicatePair
from tests.test_own_records import _give, _switch, two_sales  # noqa: F401 (fixture)
from tests.test_quotations_admin import (
    _approve_option,
    _create_client_record,
    _create_project,
    _add_project_sport,
    _director_headers,
    _released_quotation,
    _role_headers,
    _satisfy_project_readiness,
    _sent_estimate,
    _verified_cost_sheet,
)
from app.models.user import UserRole


# --- Contacts ----------------------------------------------------------------------------------


def test_contact_create_list_edit(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Contact Test Client")

    created = client.post(
        f"/clients/{client_id}/contacts",
        json={"name": "A. Contact", "designation": "Facilities Head", "phone": "9000000001"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    contact_id = created.json()["id"]
    assert created.json()["is_active"] is True

    listed = client.get(f"/clients/{client_id}/contacts", headers=headers)
    assert listed.status_code == 200 and len(listed.json()) == 1

    edited = client.patch(
        f"/clients/{client_id}/contacts/{contact_id}", json={"phone": "9000000002"}, headers=headers
    )
    assert edited.status_code == 200 and edited.json()["phone"] == "9000000002"

    deactivated = client.patch(
        f"/clients/{client_id}/contacts/{contact_id}", json={"is_active": False}, headers=headers
    )
    assert deactivated.status_code == 200 and deactivated.json()["is_active"] is False


def test_contact_nested_record_mismatch_rejected_without_partial_write(client, director_user, db_session):
    """Contract Section 9: mismatched parent/child id rejected; Client B's Contact confirmed
    unchanged in the DB, not just a non-200 status code."""
    headers = _director_headers(client, director_user)
    client_a = _create_client_record(client, headers, "Nested A")
    client_b = _create_client_record(client, headers, "Nested B")
    contact_b = client.post(f"/clients/{client_b}/contacts", json={"name": "B. Contact"}, headers=headers).json()

    res = client.patch(
        f"/clients/{client_a}/contacts/{contact_b['id']}", json={"name": "HIJACKED"}, headers=headers
    )
    assert res.status_code == 404, res.text

    db_session.expire_all()
    row = db_session.query(ClientContact).filter(ClientContact.id == contact_b["id"]).first()
    assert row.name == "B. Contact"  # unchanged


def test_contact_signatory_kept_structurally_separate(client, director_user):
    """Contract Section 3: creating/editing a Contact never touches a Signatory row."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Separation Client")
    signatory = client.post(
        f"/clients/{client_id}/signatories",
        json={"name": "Same Name", "designation": "Principal", "authorization_date": str(date.today())},
        headers=headers,
    ).json()
    contact = client.post(
        f"/clients/{client_id}/contacts", json={"name": "Same Name", "designation": "Principal"}, headers=headers
    ).json()
    client.patch(f"/clients/{client_id}/contacts/{contact['id']}", json={"designation": "Changed"}, headers=headers)

    still = client.get(f"/clients/{client_id}/signatories", headers=headers).json()
    match = next(s for s in still if s["id"] == signatory["id"])
    assert match["designation"] == "Principal"  # untouched by the Contact edit


def test_contact_write_switch_off_succeeds_on_unowned_client(client, two_sales):
    """Contract Section 1 (fixed): matches existing Client-write behaviour -- with the switch
    off, a Sales write is unrestricted, not own-only in both switch states."""
    a, wb = two_sales["a"], two_sales["wb"]
    res = client.post(f"/clients/{wb['client_id']}/contacts", json={"name": "Cross-owner contact"}, headers=a)
    assert res.status_code == 201, res.text


def test_contact_write_switch_on_refused_and_unchanged(client, two_sales, db_session):
    _switch(client, two_sales["director"])
    a, wb = two_sales["a"], two_sales["wb"]
    existing = client.post(
        f"/clients/{wb['client_id']}/contacts", json={"name": "B-owned contact"}, headers=two_sales["b"]
    ).json()
    res = client.patch(
        f"/clients/{wb['client_id']}/contacts/{existing['id']}", json={"name": "HIJACKED"}, headers=a
    )
    assert res.status_code == 404, res.text
    db_session.expire_all()
    row = db_session.query(ClientContact).filter(ClientContact.id == existing["id"]).first()
    assert row.name == "B-owned contact"


# --- Sites -------------------------------------------------------------------------------------


def test_site_create_list_edit(client, director_user):
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Site Test Client")
    created = client.post(
        f"/clients/{client_id}/sites",
        json={"label": "Main Campus", "city": "Pune", "site_address": "123 MG Road"},
        headers=headers,
    )
    assert created.status_code == 201, created.text
    site_id = created.json()["id"]

    listed = client.get(f"/clients/{client_id}/sites", headers=headers)
    assert listed.status_code == 200 and len(listed.json()) == 1

    edited = client.patch(f"/clients/{client_id}/sites/{site_id}", json={"city": "Mumbai"}, headers=headers)
    assert edited.status_code == 200 and edited.json()["city"] == "Mumbai"


def test_site_nested_record_mismatch_rejected(client, director_user):
    headers = _director_headers(client, director_user)
    client_a = _create_client_record(client, headers, "Site Nested A")
    client_b = _create_client_record(client, headers, "Site Nested B")
    site_b = client.post(f"/clients/{client_b}/sites", json={"label": "B site", "city": "Delhi"}, headers=headers).json()
    res = client.patch(f"/clients/{client_a}/sites/{site_b['id']}", json={"city": "HIJACKED"}, headers=headers)
    assert res.status_code == 404, res.text


def test_project_site_cross_client_mismatch_rejected_400(client, director_user):
    """Contract Section 9: Site/Client mismatch rejected, 400, no partial write."""
    headers = _director_headers(client, director_user)
    client_a = _create_client_record(client, headers, "Project Client A")
    client_b = _create_client_record(client, headers, "Project Client B")
    site_b = client.post(f"/clients/{client_b}/sites", json={"label": "B site", "city": "Delhi"}, headers=headers).json()

    res = client.post(
        "/projects",
        json={
            "client_id": client_a, "city": "Placeholder", "site_condition": "level", "soil_type": "normal",
            "building_status": "open_air", "site_access": "good", "power_available": "yes",
            "water_available": True, "package": "standard", "site_id": site_b["id"],
        },
        headers=headers,
    )
    assert res.status_code == 400, res.text


def test_project_site_copy_on_select_not_live(client, director_user, db_session):
    """Contract Section 9: address copy-on-select, not live -- editing the Site afterward
    leaves the already-created Project's address untouched; re-selecting re-copies."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Copy Client")
    site = client.post(
        f"/clients/{client_id}/sites",
        json={"label": "Site A", "city": "Nashik", "site_address": "Old Address", "site_state_code": "MH"},
        headers=headers,
    ).json()
    project = _create_project(client, headers, client_id, site_id=site["id"], city="ignored")
    got = client.get(f"/projects/{project}", headers=headers).json()
    assert got["city"] == "Nashik" and got["site_address"] == "Old Address" and got["site_id"] == site["id"]

    # Site's own address edited afterward -- Project must NOT change.
    client.patch(f"/clients/{client_id}/sites/{site['id']}", json={"city": "Changed City"}, headers=headers)
    still = client.get(f"/projects/{project}", headers=headers).json()
    assert still["city"] == "Nashik"

    # Re-selecting the same Site (explicit action) re-copies the NEW address.
    res = client.patch(f"/projects/{project}/site", json={"site_id": site["id"]}, headers=headers)
    assert res.status_code == 200 and res.json()["city"] == "Changed City"


def test_legacy_project_no_site_shows_own_fields(client, director_user):
    """Contract Section 9: a pre-P2-style Project with site_id null shows its own inline fields."""
    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Legacy Client")
    project_id = _create_project(client, headers, client_id, city="Legacy City", site_address="Legacy Addr")
    got = client.get(f"/projects/{project_id}", headers=headers).json()
    assert got["site_id"] is None and got["city"] == "Legacy City" and got["site_address"] == "Legacy Addr"


# --- Client.source / Opportunity.source ---------------------------------------------------------


def test_client_source_pm_director_only_after_creation(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    sales = _role_headers(client, db_session, UserRole.SALES, "source-sales@test.local")
    client_id = _create_client_record(client, headers, "Source Client")

    refused = client.patch(f"/clients/{client_id}/source", json={"source": "referral"}, headers=sales)
    assert refused.status_code == 403, refused.text

    ok = client.patch(f"/clients/{client_id}/source", json={"source": "referral"}, headers=headers)
    assert ok.status_code == 200 and ok.json()["source"] == "referral"


def test_client_source_edit_is_audited(client, director_user, db_session):
    from app.models.audit_log import AuditLogEntry

    headers = _director_headers(client, director_user)
    client_id = _create_client_record(client, headers, "Audited Source Client")
    client.patch(f"/clients/{client_id}/source", json={"source": "indiamart"}, headers=headers)
    entries = db_session.query(AuditLogEntry).filter(
        AuditLogEntry.document_type == "client", AuditLogEntry.field == "source"
    ).all()
    assert entries and entries[-1].new_value == "indiamart"


def test_opportunity_source_follows_existing_write_roles_not_client_rule(client, two_sales):
    """Contract Section 1: deliberately NOT Director/PM-only -- follows this Opportunity's own
    existing WRITE_ROLES (sales/pm/director), scoped like any other opportunity_id route."""
    _switch(client, two_sales["director"])
    a, wa, wb = two_sales["a"], two_sales["wa"], two_sales["wb"]

    own = client.patch(f"/opportunities/{wa['opportunity_id']}/source", json={"source": "website"}, headers=a)
    assert own.status_code == 200, own.text

    not_owned = client.patch(f"/opportunities/{wb['opportunity_id']}/source", json={"source": "website"}, headers=a)
    assert not_owned.status_code == 404

    _switch(client, two_sales["director"], on=False)
    now_ok = client.patch(f"/opportunities/{wb['opportunity_id']}/source", json={"source": "website"}, headers=a)
    assert now_ok.status_code == 200, now_ok.text


# --- Duplicate suggestions -----------------------------------------------------------------------


def test_duplicate_suggestion_matches_phone_and_respects_scoping(client, two_sales):
    """Contract Section 9: two Clients share a phone; a scoped Sales viewer owning neither sees
    no suggestion, regardless of match strength."""
    _switch(client, two_sales["director"])
    director, a, b = two_sales["director"], two_sales["a"], two_sales["b"]
    c1 = client.post("/clients", json={"name": "Dup One", "type": "school", "phone": "9111111111"}, headers=director).json()
    c2 = client.post("/clients", json={"name": "Dup Two", "type": "school", "phone": "9111111111"}, headers=director).json()

    director_view = client.get(f"/clients/{c1['id']}/duplicates", headers=director).json()
    assert any(d["client_id"] == c2["id"] and d["matched_field"] == "phone" for d in director_view)

    b_view = client.get(f"/clients/{c1['id']}/duplicates", headers=b)
    assert b_view.status_code == 404  # b doesn't own c1 either, under scoping


def test_duplicate_dismiss_requires_both_clients_accessible_and_is_concealed(client, two_sales):
    """Contract Section 9 (corrected from 403 to 404): concealed, not merely refused."""
    _switch(client, two_sales["director"])
    a, wa, wb = two_sales["a"], two_sales["wa"], two_sales["wb"]
    res = client.post(
        f"/clients/{wa['client_id']}/duplicates/dismiss", json={"other_client_id": wb["client_id"]}, headers=a
    )
    assert res.status_code == 404
    assert res.json()["detail"] == "Not found"  # same as a genuinely missing client, not a distinguishable 403


def test_duplicate_dismiss_switch_off_succeeds_any_pair(client, two_sales):
    a, wa, wb = two_sales["a"], two_sales["wa"], two_sales["wb"]
    res = client.post(
        f"/clients/{wa['client_id']}/duplicates/dismiss", json={"other_client_id": wb["client_id"]}, headers=a
    )
    assert res.status_code == 201, res.text


def test_duplicate_dismiss_is_global_and_restore_is_pm_director_only(client, two_sales, db_session):
    director, a, b = two_sales["director"], two_sales["a"], two_sales["b"]
    wa, wb = two_sales["wa"], two_sales["wb"]

    res = client.post(
        f"/clients/{wa['client_id']}/duplicates/dismiss", json={"other_client_id": wb["client_id"]}, headers=director
    )
    assert res.status_code == 201, res.text
    row = db_session.query(DismissedDuplicatePair).first()
    assert row is not None  # global: one shared row, not per-viewer

    refused = client.post(
        f"/clients/{wa['client_id']}/duplicates/restore", json={"other_client_id": wb["client_id"]}, headers=a
    )
    assert refused.status_code == 403

    restored = client.post(
        f"/clients/{wa['client_id']}/duplicates/restore", json={"other_client_id": wb["client_id"]}, headers=director
    )
    assert restored.status_code == 204


def test_duplicate_self_pair_and_reversed_pair_rejected(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    c1 = _create_client_record(client, headers, "Self Pair A")
    c2 = _create_client_record(client, headers, "Self Pair B")

    self_pair = client.post(f"/clients/{c1}/duplicates/dismiss", json={"other_client_id": c1}, headers=headers)
    assert self_pair.status_code == 400

    first = client.post(f"/clients/{c1}/duplicates/dismiss", json={"other_client_id": c2}, headers=headers)
    assert first.status_code == 201
    row_count_before = db_session.query(DismissedDuplicatePair).count()
    reversed_pair = client.post(f"/clients/{c2}/duplicates/dismiss", json={"other_client_id": c1}, headers=headers)
    assert reversed_pair.status_code == 201  # idempotent return of the same row, not a second one
    assert db_session.query(DismissedDuplicatePair).count() == row_count_before


# --- Communication tab (3-check message authorisation) -------------------------------------------


def _quotation_world(client, director_headers, name):
    client_id = _create_client_record(client, director_headers, name)
    project_id = _create_project(client, director_headers, client_id)
    sport_id = _add_project_sport(client, director_headers, project_id)
    _verified_cost_sheet(client, director_headers, project_id)
    _satisfy_project_readiness(client, director_headers, project_id)
    estimate = _sent_estimate(client, director_headers, project_id, sport_id)
    option_id = estimate["options"][0]["id"]
    _approve_option(client, director_headers, estimate["id"], option_id)
    quotation = _released_quotation(client, director_headers, project_id, estimate["id"], option_id)
    return client_id, quotation


def test_communication_tab_role_gate_procurement_sees_nothing(client, director_user, db_session):
    """Contract Section 9 acceptance case 1: Procurement can open Client 360 (READ_ROLES) but
    has no document role at all -- check 1 fails for every message, list is empty."""
    director_headers = _director_headers(client, director_user)
    procurement = _role_headers(client, db_session, UserRole.PROCUREMENT, "procurement-comms@test.local")
    client_id, quotation = _quotation_world(client, director_headers, "Comms Client")
    client.post("/messages", json={
        "doc_type": "quotation", "doc_id": quotation["id"], "channel": "email", "recipient": "client@example.com",
    }, headers=director_headers)

    as_procurement = client.get(f"/clients/{client_id}/messages", headers=procurement)
    assert as_procurement.status_code == 200 and as_procurement.json() == []


def test_communication_tab_ownership_scope_excludes_non_owned_document(client, two_sales):
    """Contract Section 9 acceptance case 3: check 1 (role) passes, check 2 (ownership) fails."""
    _switch(client, two_sales["director"])
    director, a, wb = two_sales["director"], two_sales["a"], two_sales["wb"]
    client.post("/messages", json={
        "doc_type": "quotation", "doc_id": wb["quotation_id"], "channel": "email", "recipient": "client@example.com",
    }, headers=director)

    as_a = client.get(f"/clients/{wb['client_id']}/messages", headers=a)
    # a doesn't own wb's client at all under scoping -- entry itself is refused (404)
    assert as_a.status_code == 404


def test_communication_tab_below_floor_quotation_hidden_from_sales(client, director_user, db_session):
    """Contract Section 7 check 3 (K.3): a message tied to a below-floor Quotation is omitted
    for a rate-blind Sales viewer, matching the redaction already applied to QuotationOut."""
    director_headers = _director_headers(client, director_user)
    sales_headers = _role_headers(client, db_session, UserRole.SALES, "comms-sales@test.local")
    client_id = _create_client_record(client, director_headers, "Below Floor Comms Client")
    project_id = _create_project(client, director_headers, client_id)
    sport_id = _add_project_sport(client, director_headers, project_id)
    _verified_cost_sheet(client, director_headers, project_id, cost_total=850000)
    _satisfy_project_readiness(client, director_headers, project_id)
    estimate = _sent_estimate(client, director_headers, project_id, sport_id)
    option_id = estimate["options"][0]["id"]
    _approve_option(client, director_headers, estimate["id"], option_id)
    quotation = client.post(
        f"/projects/{project_id}/quotations",
        json={"estimate_id": estimate["id"], "included_option_ids": [option_id], "discount_type": "percent", "discount_value": 90},
        headers=director_headers,
    ).json()
    assert quotation["below_floor"] is True
    client.post("/messages", json={
        "doc_type": "quotation", "doc_id": quotation["id"], "channel": "email", "recipient": "client@example.com",
    }, headers=director_headers)

    as_director = client.get(f"/clients/{client_id}/messages", headers=director_headers)
    assert len(as_director.json()) == 1  # Director sees it

    as_sales = client.get(f"/clients/{client_id}/messages", headers=sales_headers)
    assert as_sales.status_code == 200 and as_sales.json() == []  # omitted, not flagged
