"""Marketing M4: conformance of the Phase A dashboard to P3 contract (revision 4), Section 9.

Governing text: "Aggregate volume dashboard (counts by source, QUERY_TYPE, and date bucket) and a current-stage
distribution by import cohort ... a current-stage snapshot, grouped by import cohort (leads whose enquiry_time or
received_at -- stated explicitly, not left implicit -- falls in the selected period), showing the count currently
sitting at each Opportunity stage as of now, with an explicit denominator (total Opportunities imported in that
period)... counts and rates only -- never individual buyer fields, never raw payload, never full Opportunity rows."

INTERPRETATIONS the contract does not settle (each is stated in the API response and documented in the PR, not silent):
  * cohort basis: selectable (`basis` = enquiry_time | received_at); default enquiry_time = the behaviour already shipped.
  * date bucket granularity: selectable (`bucket` = day | week | month); default day. Weeks start Monday (ISO).
  * calendar/timezone: period dates and buckets are Asia/Kolkata (IST) calendar days. `enquiry_time` is stored as the provider's
    own wall-clock value (unconverted) and is compared as written; `received_at` is stored UTC and is converted to IST.
  * period is [period_start 00:00, period_end + 1 day 00:00) in that calendar (end date inclusive).
  * denominator = Opportunities imported (ledger rows that produced an Opportunity), not all ledger rows.
Every expected figure below is computed by hand from the fixture data."""

from datetime import datetime

import pytest
from sqlalchemy import text

from app.core import marketplace_imports as mi
from app.models.marketplace_lead_import import MarketplaceLeadImport, MarketplaceLeadImportStatus
from app.models.opportunity import Opportunity, OpportunityStage
from app.models.user import UserRole
from tests.test_p3_marketplace_imports_api import _fixture_item, _marketing_headers
from tests.test_quotations_admin import _director_headers, _role_headers

URL = "/marketplace-imports/marketing/dashboard"
SEPT = {"period_start": "2026-09-01", "period_end": "2026-09-30"}

EXPECTED_KEYS = {
    "period_start", "period_end", "cohort_basis", "bucket", "timezone", "received_total", "imported_total",
    "excluded_missing_enquiry_time", "by_source", "by_query_type", "by_date_bucket", "current_stage_distribution",
}
FORBIDDEN_KEYS = {"lead_name", "lead_phone", "lead_email", "notes", "raw_payload", "sender_company", "sender_city",
                  "sender_address", "sender_state", "sender_pincode", "opportunity_id", "external_id", "id"}


def _ingest(db, uid, enquiry="15-SEP-2026 12:00:00", qtype="W", platform="indiamart", process=True, received_at=None):
    """A lead through the real Capture (and Process) steps. `received_at` (naive UTC) is set afterwards when given."""
    mi.capture_batch(db, items=[_fixture_item(unique_id=uid, query_time=enquiry, QUERY_TYPE=qtype)],
                     account_id="default", platform=platform)
    if process:
        while mi.process_one(db, platform=platform) is not None:
            pass
    row = db.query(MarketplaceLeadImport).filter(MarketplaceLeadImport.external_id == uid).one()
    if received_at is not None:
        db.execute(text("UPDATE marketplace_lead_imports SET received_at = :r WHERE id = :i"), {"r": received_at, "i": row.id})
        db.commit()
    return row.id


def _set_stage(db, ledger_id, stage):
    row = db.get(MarketplaceLeadImport, ledger_id)
    opportunity = db.get(Opportunity, row.opportunity_id)
    opportunity.stage = stage
    db.commit()


def _get(client, headers, **params):
    return client.get(URL, params=params, headers=headers)


@pytest.fixture
def seeded(client, db_session):
    """September fixture (enquiry_time basis). Hand-computed:
      A Q-A  indiamart W  enq 2026-09-01 00:00:00 (start boundary)      converted  stage new
      B Q-B  indiamart B  enq 2026-09-30 23:59:59 (end boundary)        converted  stage qualified
      C Q-C  indiamart W  enq 2026-10-01 00:00:00 (first instant after) converted  (outside)
      D Q-D  indiamart W  enq 2026-08-31 23:59:59 (last instant before) converted  (outside)
      E Q-E  indiamart P  enq 2026-09-15 09:00:00                       rejected   (no Opportunity)
      F Q-F  indiamart W  enq 2026-09-15 13:00:00                       converted  stage contacted
      H Q-H  tradeindia P enq 2026-09-20 10:00:00                       converted  stage new
      G Q-G  indiamart -  malformed QUERY_TIME -> quarantined, enquiry_time NULL, received 2026-09-10
      I Q-I  indiamart W  enq 2026-09-12 10:00:00                       pending (never processed)
    In-period (enquiry basis): A B E F H I -> received_total 6; Opportunities: A B F H -> imported_total 4."""
    h = _marketing_headers(client, db_session)
    ids = {
        "A": _ingest(db_session, "Q-A", "01-SEP-2026 00:00:00", "W"),
        "B": _ingest(db_session, "Q-B", "30-SEP-2026 23:59:59", "B"),
        "C": _ingest(db_session, "Q-C", "01-OCT-2026 00:00:00", "W"),
        "D": _ingest(db_session, "Q-D", "31-AUG-2026 23:59:59", "W"),
        "F": _ingest(db_session, "Q-F", "15-SEP-2026 13:00:00", "W"),
        "H": _ingest(db_session, "Q-H", "20-SEP-2026 10:00:00", "P", platform="tradeindia"),
    }
    # Created last and never processed, so the Process loop above cannot convert them.
    ids["E"] = _ingest(db_session, "Q-E", "15-SEP-2026 09:00:00", "P", process=False)
    ids["G"] = _ingest(db_session, "Q-G", "not a date", "W", process=False, received_at=datetime(2026, 9, 10, 8, 0, 0))
    ids["I"] = _ingest(db_session, "Q-I", "12-SEP-2026 10:00:00", "W", process=False)
    db_session.execute(text("UPDATE marketplace_lead_imports SET status = 'rejected' WHERE id = :i"), {"i": ids["E"]})
    db_session.commit()
    _set_stage(db_session, ids["B"], OpportunityStage.QUALIFIED)
    _set_stage(db_session, ids["F"], OpportunityStage.CONTACTED)
    return h, ids


# --- 1. contract shape: counts and rates only --------------------------------------------------------------


def test_response_has_exactly_the_contract_fields_and_no_individual_data(client, db_session, seeded):
    h, _ = seeded
    res = _get(client, h, **SEPT)
    assert res.status_code == 200, res.text
    body = res.json()
    assert set(body) == EXPECTED_KEYS, sorted(set(body) ^ EXPECTED_KEYS)
    flat = repr(body)
    for key in FORBIDDEN_KEYS:
        assert f"'{key}'" not in flat, key
    for forbidden_value in ("Meera", "9123456780", "meera@example.com", "Shah Sports", "Ahmedabad", "badminton court"):
        assert forbidden_value not in flat


def test_defaults_preserve_existing_behaviour_and_state_the_interpretation(client, db_session, seeded):
    h, _ = seeded
    body = _get(client, h, **SEPT).json()
    assert body["cohort_basis"] == "enquiry_time" and body["bucket"] == "day"
    assert "Asia/Kolkata" in body["timezone"]


# --- 2. counts by source, QUERY_TYPE and date bucket -------------------------------------------------------


def test_counts_by_source_query_type_and_day_bucket_are_hand_computed(client, db_session, seeded):
    h, _ = seeded
    body = _get(client, h, **SEPT).json()
    assert body["received_total"] == 6                                    # A B E F H I
    assert body["by_source"] == {"indiamart": 5, "tradeindia": 1}         # A B E F I | H
    assert body["by_query_type"] == {"W": 3, "B": 1, "P": 2}              # A F I | B | E H
    buckets = {b["bucket_start"]: b["count"] for b in body["by_date_bucket"]}
    assert len(body["by_date_bucket"]) == 30                              # every day of September, zero-filled
    assert buckets["2026-09-01"] == 1 and buckets["2026-09-12"] == 1 and buckets["2026-09-15"] == 2
    assert buckets["2026-09-20"] == 1 and buckets["2026-09-30"] == 1
    assert sum(buckets.values()) == 6
    assert [b["bucket_start"] for b in body["by_date_bucket"]] == sorted(buckets)


def test_week_buckets_start_on_monday_and_month_buckets_are_calendar_months(client, db_session, seeded):
    h, _ = seeded
    weeks = _get(client, h, bucket="week", **SEPT).json()
    got = {b["bucket_start"]: b["count"] for b in weeks["by_date_bucket"]}
    # Mondays 2026-08-31, 09-07, 09-14, 09-21, 09-28. A(09-01 Tue) -> 08-31; I(09-12 Sat) -> 09-07; E,F(09-15) and H(09-20 Sun) -> 09-14;
    # B(09-30 Wed) -> 09-28.
    assert got == {"2026-08-31": 1, "2026-09-07": 1, "2026-09-14": 3, "2026-09-21": 0, "2026-09-28": 1}
    months = _get(client, h, bucket="month", **SEPT).json()
    assert [(b["bucket_start"], b["count"]) for b in months["by_date_bucket"]] == [("2026-09-01", 6)]


# --- 3. denominator and stage distribution -----------------------------------------------------------------


def test_denominator_is_opportunities_imported_not_ledger_rows_and_rates_use_it(client, db_session, seeded):
    h, _ = seeded
    body = _get(client, h, **SEPT).json()
    assert body["received_total"] == 6 and body["imported_total"] == 4     # E rejected, I pending, have no Opportunity
    stages = {s["stage"]: s for s in body["current_stage_distribution"]}
    assert {k: v["count"] for k, v in stages.items()} == {"new": 2, "contacted": 1, "qualified": 1}
    assert sum(v["count"] for v in stages.values()) == body["imported_total"]
    assert stages["new"]["rate"] == 0.5 and stages["contacted"]["rate"] == 0.25 and stages["qualified"]["rate"] == 0.25


def test_stage_distribution_is_the_stage_as_of_now(client, db_session, seeded):
    h, ids = seeded
    _set_stage(db_session, ids["A"], OpportunityStage.WON)
    _set_stage(db_session, ids["H"], OpportunityStage.LOST)
    body = _get(client, h, **SEPT).json()
    stages = {s["stage"]: s["count"] for s in body["current_stage_distribution"]}
    assert stages == {"won": 1, "lost": 1, "contacted": 1, "qualified": 1}
    assert body["imported_total"] == 4


# --- 4. date boundaries -------------------------------------------------------------------------------------


def test_enquiry_time_boundaries_start_inclusive_end_inclusive_next_instant_excluded(client, db_session, seeded):
    h, _ = seeded
    # A (09-01 00:00:00) and B (09-30 23:59:59) are in; D (08-31 23:59:59) and C (10-01 00:00:00) are out.
    body = _get(client, h, **SEPT).json()
    buckets = {b["bucket_start"]: b["count"] for b in body["by_date_bucket"]}
    assert buckets["2026-09-01"] == 1 and buckets["2026-09-30"] == 1
    assert "2026-08-31" not in buckets and "2026-10-01" not in buckets
    oct_only = _get(client, h, period_start="2026-10-01", period_end="2026-10-01").json()
    assert oct_only["received_total"] == 1 and oct_only["imported_total"] == 1
    aug_only = _get(client, h, period_start="2026-08-31", period_end="2026-08-31").json()
    assert aug_only["received_total"] == 1


def test_received_at_basis_uses_ist_calendar_days_converted_from_utc(client, db_session):
    """received_at is stored UTC; period membership and buckets are IST days. 2026-09-30 18:30:00 UTC is 2026-10-01 00:00:00 IST."""
    h = _marketing_headers(client, db_session)
    _ingest(db_session, "R-1", received_at=datetime(2026, 8, 31, 18, 30, 0))    # IST 2026-09-01 00:00:00 -> September (start boundary)
    _ingest(db_session, "R-2", received_at=datetime(2026, 9, 30, 18, 29, 59))   # IST 2026-09-30 23:59:59 -> September (end boundary)
    _ingest(db_session, "R-3", received_at=datetime(2026, 9, 30, 18, 30, 0))    # IST 2026-10-01 00:00:00 -> October
    _ingest(db_session, "R-4", received_at=datetime(2026, 8, 31, 18, 29, 59))   # IST 2026-08-31 23:59:59 -> August
    sept = _get(client, h, basis="received_at", **SEPT).json()
    assert sept["cohort_basis"] == "received_at"
    assert sept["received_total"] == 2 and sept["imported_total"] == 2
    buckets = {b["bucket_start"]: b["count"] for b in sept["by_date_bucket"]}
    assert buckets["2026-09-01"] == 1 and buckets["2026-09-30"] == 1
    octo = _get(client, h, basis="received_at", period_start="2026-10-01", period_end="2026-10-01").json()
    assert octo["received_total"] == 1


def test_rows_without_enquiry_time_are_reported_not_silently_dropped(client, db_session, seeded):
    h, _ = seeded
    body = _get(client, h, **SEPT).json()
    # G is quarantined with no enquiry_time: not in an enquiry_time cohort, but its existence in the period is disclosed.
    assert body["received_total"] == 6 and body["excluded_missing_enquiry_time"] == 1
    by_received = _get(client, h, basis="received_at", **SEPT).json()
    assert by_received["excluded_missing_enquiry_time"] == 0
    assert by_received["by_query_type"].get("W", 0) >= 1


# --- 5. empty periods and validation -----------------------------------------------------------------------


def test_empty_period_returns_zeros_without_error(client, db_session):
    h = _marketing_headers(client, db_session)
    body = _get(client, h, period_start="2026-01-01", period_end="2026-01-31").json()
    assert body["received_total"] == 0 and body["imported_total"] == 0 and body["excluded_missing_enquiry_time"] == 0
    assert body["by_source"] == {} and body["by_query_type"] == {} and body["current_stage_distribution"] == []
    assert len(body["by_date_bucket"]) == 31 and all(b["count"] == 0 for b in body["by_date_bucket"])


def test_single_day_period_and_reversed_or_oversized_periods(client, db_session, seeded):
    h, _ = seeded
    one = _get(client, h, period_start="2026-09-15", period_end="2026-09-15").json()
    assert one["received_total"] == 2 and len(one["by_date_bucket"]) == 1       # E and F
    reversed_ = _get(client, h, period_start="2026-09-30", period_end="2026-09-01")
    assert reversed_.status_code == 400 and "period_end" in reversed_.json()["detail"]
    huge = _get(client, h, period_start="2000-01-01", period_end="2026-09-30")
    assert huge.status_code == 400 and "bucket" in huge.json()["detail"].lower()
    assert _get(client, h, bucket="week", period_start="2000-01-01", period_end="2026-09-30").status_code == 200


@pytest.mark.parametrize("params", [{"basis": "created_at"}, {"bucket": "year"}])
def test_unknown_basis_or_bucket_is_refused(client, db_session, params):
    h = _marketing_headers(client, db_session)
    assert _get(client, h, **SEPT, **params).status_code == 422


# --- 6. duplicate / retried ledger entries ------------------------------------------------------------------


def test_a_lead_delivered_twice_is_counted_once(client, db_session):
    h = _marketing_headers(client, db_session)
    _ingest(db_session, "DUP-1", "10-SEP-2026 10:00:00", "W")
    mi.capture_batch(db_session, items=[_fixture_item(unique_id="DUP-1", query_time="10-SEP-2026 10:00:00")], account_id="default")
    mi.capture_batch(db_session, items=[_fixture_item(unique_id="DUP-1", query_time="10-SEP-2026 10:00:00")], account_id="default")
    body = _get(client, h, **SEPT).json()
    assert body["received_total"] == 1 and body["imported_total"] == 1
    assert body["by_query_type"] == {"W": 1} and sum(s["count"] for s in body["current_stage_distribution"]) == 1


def test_a_manually_retried_rejected_lead_is_counted_exactly_once(client, db_session, director_user):
    h = _marketing_headers(client, db_session)
    ledger_id = _ingest(db_session, "RETRY-1", "10-SEP-2026 10:00:00", "W", process=False)
    db_session.execute(text("UPDATE marketplace_lead_imports SET status = 'rejected', rejection_reason = 'boom' WHERE id = :i"), {"i": ledger_id})
    db_session.commit()
    before = _get(client, h, **SEPT).json()
    assert before["received_total"] == 1 and before["imported_total"] == 0 and before["current_stage_distribution"] == []
    from app.models.user import User
    director = db_session.query(User).filter(User.role == UserRole.DIRECTOR).first()
    outcome = mi.manual_retry(db_session, ledger_row_id=ledger_id, current_user=director)
    assert outcome.converted is True
    again = _get(client, h, **SEPT).json()
    assert again["received_total"] == 1 and again["imported_total"] == 1
    assert db_session.query(Opportunity).count() == 1


def test_query_type_grouping_survives_the_retention_purge(client, db_session):
    h = _marketing_headers(client, db_session)
    _ingest(db_session, "PURGE-1", "10-SEP-2026 10:00:00", "B", received_at=datetime(2026, 1, 1, 0, 0, 0))
    purged = mi.run_retention_purge(db_session, now=datetime(2026, 9, 30, 0, 0, 0))
    assert purged.purged_ids
    body = _get(client, h, **SEPT).json()
    assert body["by_query_type"] == {"B": 1} and body["by_source"] == {"indiamart": 1}


# --- 7. permitted and denied roles (existing permissions preserved) -----------------------------------------


@pytest.mark.parametrize("role", [UserRole.MARKETING, UserRole.PM])
def test_permitted_roles_can_read_the_dashboard(client, db_session, seeded, role):
    h = _role_headers(client, db_session, role, f"{role.value}-m4@test.local")
    assert _get(client, h, **SEPT).status_code == 200


def test_director_can_read_the_dashboard(client, db_session, director_user, seeded):
    assert _get(client, _director_headers(client, director_user), **SEPT).status_code == 200


@pytest.mark.parametrize("role", [UserRole.SALES, UserRole.PROCUREMENT, UserRole.SITE_ENGINEER, UserRole.CA_TAX, UserRole.ADMIN])
def test_every_other_role_is_denied(client, db_session, seeded, role):
    h = _role_headers(client, db_session, role, f"{role.value}-m4@test.local")
    assert _get(client, h, **SEPT).status_code == 403


def test_unauthenticated_request_is_refused(client, db_session, seeded):
    assert client.get(URL, params=SEPT).status_code in (401, 403)


def test_marketing_still_cannot_reach_individual_records(client, db_session, seeded):
    h = _marketing_headers(client, db_session, email="marketing-m4b@test.local")
    for path in ("/opportunities", "/clients", "/marketplace-imports", "/marketplace-imports/summary"):
        assert client.get(path, headers=h).status_code == 403, path
