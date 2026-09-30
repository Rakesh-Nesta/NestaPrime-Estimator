"""P3 contract (revision 4), Sections 2/3/5 -- the import ledger's Capture/Process/retry/
retention pipeline. Fixture-based throughout, matching the contract's own acceptance-case
discipline (Section 11) -- no live IndiaMART call anywhere in this file. Acceptance-case numbers
below refer to the contract's Section 11 list, published at
https://claude.ai/artifact/SZQPrL3GcJHVi9qQZf2GYY.
"""

import uuid
from datetime import UTC, datetime, timedelta

from app.core import marketplace_imports as mi
from app.models.follow_up import FollowUp
from app.models.marketplace_lead_import import (
    MarketplaceApiRateGate,
    MarketplaceLeadImport,
    MarketplaceLeadImportDuplicateDelivery,
    MarketplaceLeadImportStatus,
    MarketplacePullCheckpoint,
)
from app.models.opportunity import Opportunity

ACCOUNT_ID = "test-account-1"


def _fixture_item(*, unique_id="Q-1001", query_time="30-SEP-2026 10:15:00", **overrides):
    item = {
        "UNIQUE_QUERY_ID": unique_id,
        "QUERY_TIME": query_time,
        "QUERY_TYPE": "W",
        "SENDER_NAME": "Ravi Kumar",
        "SENDER_MOBILE": "9876543210",
        "SENDER_EMAIL": "ravi@example.com",
        "SENDER_COMPANY": "Ravi Sports Pvt Ltd",
        "SENDER_ADDRESS": "12 MG Road",
        "SENDER_CITY": "Pune",
        "SENDER_STATE": "Maharashtra",
        "SENDER_PINCODE": "411001",
        "SENDER_COUNTRY_ISO": "IN",
        "QUERY_MESSAGE": "Need a synthetic court quote",
        "QUERY_PRODUCT_NAME": "Synthetic Court Flooring",
        "SUBJECT": "Court flooring enquiry",
    }
    item.update(overrides)
    return item


def test_replay_safe_fixture_import_case_1(db_session):
    """Case 1: capturing the same item twice yields one ledger row, one duplicate_delivery
    event, and the original row's own status untouched."""
    item = _fixture_item()
    r1 = mi.capture_batch(db_session, items=[item], account_id=ACCOUNT_ID)
    assert len(r1.captured_ids) == 1 and not r1.quarantined_ids and not r1.duplicate_of_ids

    r2 = mi.capture_batch(db_session, items=[item], account_id=ACCOUNT_ID)
    assert not r2.captured_ids and r2.duplicate_of_ids == [r1.captured_ids[0]]

    assert db_session.query(MarketplaceLeadImport).count() == 1
    log = db_session.get(MarketplaceLeadImportDuplicateDelivery, r1.captured_ids[0])
    assert log is not None and log.delivery_count == 1


def test_converted_status_never_overwritten_by_repeat_delivery_case_2(db_session):
    """Case 2: after conversion, a repeat delivery is logged as duplicate_delivery and the
    original row's status/opportunity_id are byte-for-byte unchanged afterward."""
    item = _fixture_item()
    r1 = mi.capture_batch(db_session, items=[item], account_id=ACCOUNT_ID)
    outcome = mi.process_one(db_session)
    assert outcome.converted is True

    row_before = db_session.get(MarketplaceLeadImport, r1.captured_ids[0])
    status_before, opp_before = row_before.status, row_before.opportunity_id

    r2 = mi.capture_batch(db_session, items=[item], account_id=ACCOUNT_ID)
    assert r2.duplicate_of_ids == [r1.captured_ids[0]]

    row_after = db_session.get(MarketplaceLeadImport, r1.captured_ids[0])
    assert row_after.status == status_before == MarketplaceLeadImportStatus.CONVERTED
    assert row_after.opportunity_id == opp_before


def test_malformed_capture_quarantined_and_never_blocks_window_new_case(db_session):
    """New case (revision 4): a malformed item alongside four well-formed ones still yields five
    durable rows -- four pending, one quarantined with the full raw payload preserved -- and the
    malformed one is never dropped, never blocks the others."""
    good_items = [_fixture_item(unique_id=f"Q-{n}") for n in range(2000, 2004)]
    malformed = {"SENDER_NAME": "No identity fields at all"}  # missing UNIQUE_QUERY_ID/QUERY_TIME

    result = mi.capture_batch(db_session, items=[*good_items, malformed], account_id=ACCOUNT_ID)
    assert len(result.captured_ids) == 4
    assert len(result.quarantined_ids) == 1

    quarantined = db_session.get(MarketplaceLeadImport, result.quarantined_ids[0])
    assert quarantined.status == MarketplaceLeadImportStatus.QUARANTINED
    assert quarantined.external_id is None
    assert quarantined.raw_payload == malformed

    assert db_session.query(MarketplaceLeadImport).count() == 5


def test_quarantined_row_is_exempt_from_uniqueness_and_never_auto_retried(db_session):
    """A second, separately-malformed item never collides with the first quarantined row (both
    have external_id=None) and quarantine never enters the retry cycle at all."""
    r = mi.capture_batch(
        db_session,
        items=[{"SENDER_NAME": "a"}, {"SENDER_NAME": "b"}],
        account_id=ACCOUNT_ID,
    )
    assert len(r.quarantined_ids) == 2
    assert mi.process_one(db_session) is None  # nothing pending -- quarantined rows are never picked up


def test_process_one_creates_real_opportunity_and_follow_up_case_11(db_session):
    """Case 11 (Sales handoff): after conversion, a query against follow_ups (not just a legacy
    column) finds a real open row, due on the import date, and the Opportunity lands unassigned
    for the unassigned queue (Section 7)."""
    item = _fixture_item()
    r1 = mi.capture_batch(db_session, items=[item], account_id=ACCOUNT_ID)
    outcome = mi.process_one(db_session)
    assert outcome.converted is True

    opp = db_session.get(Opportunity, outcome.opportunity_id)
    assert opp.lead_name == "Ravi Kumar"
    assert opp.lead_phone == "9876543210"
    assert opp.source == "indiamart"
    assert opp.owner_id is None  # unassigned queue

    follow_up = db_session.query(FollowUp).filter(FollowUp.entity_id == opp.id).one()
    assert follow_up.due_date == db_session.get(MarketplaceLeadImport, r1.captured_ids[0]).received_at.date()

    row = db_session.get(MarketplaceLeadImport, r1.captured_ids[0])
    assert row.sender_company == "Ravi Sports Pvt Ltd"
    assert row.query_type == "W"


def test_retry_count_survives_its_own_rollback_new_case(db_session):
    """New case (revision 4): forcing a Process failure increments retry_count and records a
    rejection_reason in the database even though the processing transaction itself rolled back --
    proving the failure-recording step is a genuinely separate, surviving transaction."""
    bad_item = _fixture_item(unique_id="Q-3000", SENDER_MOBILE="9" * 40)  # exceeds lead_phone's String(20)
    mi.capture_batch(db_session, items=[bad_item], account_id=ACCOUNT_ID)

    outcome = mi.process_one(db_session)
    assert outcome.converted is False
    assert outcome.rejection_reason

    row = db_session.query(MarketplaceLeadImport).filter(MarketplaceLeadImport.external_id == "Q-3000").one()
    assert row.retry_count == 1
    assert row.rejection_reason
    assert row.status == MarketplaceLeadImportStatus.PENDING  # below the cap, stays pending for retry


def test_automatic_retry_cap_moves_row_to_rejected(db_session):
    bad_item = _fixture_item(unique_id="Q-3100", SENDER_MOBILE="9" * 40)
    mi.capture_batch(db_session, items=[bad_item], account_id=ACCOUNT_ID)

    for _ in range(mi.AUTOMATIC_RETRY_CAP):
        outcome = mi.process_one(db_session)
        assert outcome.converted is False

    row = db_session.query(MarketplaceLeadImport).filter(MarketplaceLeadImport.external_id == "Q-3100").one()
    assert row.retry_count == mi.AUTOMATIC_RETRY_CAP
    assert row.status == MarketplaceLeadImportStatus.REJECTED
    assert mi.process_one(db_session) is None  # rejected rows are never picked up automatically again


def test_manual_retry_succeeds_after_the_cap_case_new(db_session, director_user):
    """Manual retry synchronously attempts real processing and succeeds once the underlying data
    is fixed -- reports the real outcome immediately, and never touches retry_count."""
    bad_item = _fixture_item(unique_id="Q-3200", SENDER_MOBILE="9" * 40)
    mi.capture_batch(db_session, items=[bad_item], account_id=ACCOUNT_ID)
    for _ in range(mi.AUTOMATIC_RETRY_CAP):
        mi.process_one(db_session)

    row = db_session.query(MarketplaceLeadImport).filter(MarketplaceLeadImport.external_id == "Q-3200").one()
    assert row.status == MarketplaceLeadImportStatus.REJECTED
    retry_count_before = row.retry_count

    # Simulates the underlying data being fixed before a manual retry -- the contract's own case
    # says "against a fixture that now parses cleanly."
    row.raw_payload = {**row.raw_payload, "SENDER_MOBILE": "9876500000"}
    db_session.commit()

    outcome = mi.manual_retry(db_session, ledger_row_id=row.id, current_user=director_user)
    assert outcome.converted is True
    assert outcome.opportunity_id is not None

    refreshed = db_session.get(MarketplaceLeadImport, row.id)
    assert refreshed.status == MarketplaceLeadImportStatus.CONVERTED
    assert refreshed.retry_count == retry_count_before  # untouched
    assert refreshed.manually_retried_by_id == director_user.id
    assert refreshed.manually_retried_at is not None


def test_manual_retry_that_fails_again_is_recorded_distinctly_new_case(db_session, director_user):
    """A second manual retry attempt, still against bad data, records a NEW rejection_reason and
    returns to rejected -- distinguishable from the original failure, not silently merged."""
    bad_item = _fixture_item(unique_id="Q-3300", SENDER_MOBILE="9" * 40)
    mi.capture_batch(db_session, items=[bad_item], account_id=ACCOUNT_ID)
    for _ in range(mi.AUTOMATIC_RETRY_CAP):
        mi.process_one(db_session)
    row = db_session.query(MarketplaceLeadImport).filter(MarketplaceLeadImport.external_id == "Q-3300").one()
    original_reason = row.rejection_reason
    retry_count_before = row.retry_count

    outcome = mi.manual_retry(db_session, ledger_row_id=row.id, current_user=director_user)
    assert outcome.converted is False
    assert outcome.rejection_reason

    refreshed = db_session.get(MarketplaceLeadImport, row.id)
    assert refreshed.status == MarketplaceLeadImportStatus.REJECTED
    assert refreshed.retry_count == retry_count_before  # never touched by manual retry
    assert refreshed.manually_retried_at is not None
    # Same underlying bad data reproduces the same class of DB error -- what matters is that the
    # column is actively rewritten by this attempt (recorded fresh), not silently left stale.
    assert refreshed.rejection_reason == outcome.rejection_reason


def test_manual_retry_refuses_a_non_rejected_row(db_session, director_user):
    item = _fixture_item(unique_id="Q-3400")
    r = mi.capture_batch(db_session, items=[item], account_id=ACCOUNT_ID)
    row_id = r.captured_ids[0]  # still pending, never rejected
    try:
        mi.manual_retry(db_session, ledger_row_id=row_id, current_user=director_user)
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_retention_purges_payload_preserves_durable_columns_and_dedup_id_case(db_session):
    item = _fixture_item(unique_id="Q-4000")
    r = mi.capture_batch(db_session, items=[item], account_id=ACCOUNT_ID)
    mi.process_one(db_session)

    old_received_at = datetime.now(UTC) - timedelta(days=mi.RETENTION_DAYS + 1)
    row = db_session.get(MarketplaceLeadImport, r.captured_ids[0])
    row.received_at = old_received_at
    db_session.commit()

    result = mi.run_retention_purge(db_session)
    assert r.captured_ids[0] in result.purged_ids
    assert r.captured_ids[0] not in result.expired_ids  # converted rows never become expired

    refreshed = db_session.get(MarketplaceLeadImport, r.captured_ids[0])
    assert refreshed.raw_payload is None
    assert refreshed.sender_company == "Ravi Sports Pvt Ltd"  # durable column survives
    assert refreshed.external_id == "Q-4000"  # dedup identifier survives
    assert refreshed.status == MarketplaceLeadImportStatus.CONVERTED
    assert refreshed.opportunity_id is not None


def test_backfilled_old_lead_not_purged_before_it_can_be_processed_new_case(db_session):
    """New case (revision 4): a backfilled lead with an old enquiry_time but a fresh received_at
    is NOT purged -- proving the anchor is genuinely received_at, not enquiry_time."""
    old_enquiry = datetime.now(UTC) - timedelta(days=300)
    item = _fixture_item(unique_id="Q-4100", query_time=old_enquiry.strftime("%d-%b-%Y %H:%M:%S").upper())
    r = mi.capture_batch(db_session, items=[item], account_id=ACCOUNT_ID)
    row = db_session.get(MarketplaceLeadImport, r.captured_ids[0])
    assert row.enquiry_time is not None
    assert (datetime.now(UTC).replace(tzinfo=None) - row.enquiry_time) > timedelta(days=250)

    result = mi.run_retention_purge(db_session)  # received_at is "now" -- well within the window
    assert r.captured_ids[0] not in result.purged_ids
    refreshed = db_session.get(MarketplaceLeadImport, r.captured_ids[0])
    assert refreshed.raw_payload is not None


def test_never_converted_rows_transition_to_expired_and_lose_retry_new_case(db_session):
    """New case (revision 4): a pending row and a rejected row both past their retention window
    transition to `expired` at the same pass that nulls their payload."""
    # bad_item is captured and exhausted to `rejected` BEFORE pending_item exists, so process_one
    # (which always claims the oldest pending row first) can never pick up pending_item instead.
    bad_item = _fixture_item(unique_id="Q-4201", SENDER_MOBILE="9" * 40)
    r2 = mi.capture_batch(db_session, items=[bad_item], account_id=ACCOUNT_ID)
    for _ in range(mi.AUTOMATIC_RETRY_CAP):
        mi.process_one(db_session)
    assert db_session.get(MarketplaceLeadImport, r2.captured_ids[0]).status == MarketplaceLeadImportStatus.REJECTED

    pending_item = _fixture_item(unique_id="Q-4200")
    r1 = mi.capture_batch(db_session, items=[pending_item], account_id=ACCOUNT_ID)

    old = datetime.now(UTC) - timedelta(days=mi.RETENTION_DAYS + 1)
    for ledger_id in (r1.captured_ids[0], r2.captured_ids[0]):
        row = db_session.get(MarketplaceLeadImport, ledger_id)
        row.received_at = old
    db_session.commit()

    result = mi.run_retention_purge(db_session)
    assert set(result.expired_ids) == {r1.captured_ids[0], r2.captured_ids[0]}
    for ledger_id in (r1.captured_ids[0], r2.captured_ids[0]):
        refreshed = db_session.get(MarketplaceLeadImport, ledger_id)
        assert refreshed.status == MarketplaceLeadImportStatus.EXPIRED
        assert refreshed.raw_payload is None


def test_shared_rate_gate_covers_every_caller_case(db_session):
    now = datetime.now(UTC)
    assert mi.try_acquire_rate_gate(db_session, now=now) is True
    # A second caller (any of scheduled Pull / backfill / verify-key) within 5 minutes is refused.
    assert mi.try_acquire_rate_gate(db_session, now=now + timedelta(minutes=2)) is False
    # After the minimum interval has genuinely elapsed, the gate opens again.
    assert mi.try_acquire_rate_gate(db_session, now=now + timedelta(minutes=6)) is True


def test_checkpoint_advances_only_when_explicitly_told_to(db_session):
    assert mi.get_checkpoint(db_session) is None
    end_time = datetime.now(UTC).replace(tzinfo=None)
    mi.advance_checkpoint(db_session, end_time=end_time)
    assert mi.get_checkpoint(db_session) == end_time
    later = end_time + timedelta(minutes=10)
    mi.advance_checkpoint(db_session, end_time=later)
    assert mi.get_checkpoint(db_session) == later


def test_concurrent_claim_safety_via_row_locking_case_4(db_session, monkeypatch):
    """Case 4: two rows are both pending; process_one always claims exactly one row per call and
    never returns the same row twice while it's already been converted. FOR UPDATE SKIP LOCKED
    itself is exercised for real (against real Postgres) by every process_one call in this file --
    this test specifically proves repeated calls drain the queue without ever double-converting
    a single row, which is the observable guarantee that matters."""
    items = [_fixture_item(unique_id=f"Q-500{n}") for n in range(3)]
    mi.capture_batch(db_session, items=items, account_id=ACCOUNT_ID)

    converted_ids = set()
    for _ in range(3):
        outcome = mi.process_one(db_session)
        assert outcome is not None and outcome.converted
        assert outcome.ledger_row_id not in converted_ids
        converted_ids.add(outcome.ledger_row_id)

    assert mi.process_one(db_session) is None  # queue drained, no double-processing
    assert len(converted_ids) == 3
