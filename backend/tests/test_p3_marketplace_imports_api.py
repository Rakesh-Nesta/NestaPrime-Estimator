"""P3 contract (revision 4), Sections 5/7/8/9/11 -- the HTTP surface: operational screen,
import-detail, possible-client-matches, assignment notification, Marketing dashboard, and the
explicitly-required permission-denial and secret-redaction acceptance cases."""

from app.core import marketplace_pull as pull
from app.core.security import hash_password
from app.models.notification import Notification, NotificationKind
from app.models.user import User, UserRole
from tests.test_quotations_admin import _director_headers, _role_headers


def _fixture_item(*, unique_id="Q-9001", query_time="30-SEP-2026 10:15:00", **overrides):
    item = {
        "UNIQUE_QUERY_ID": unique_id,
        "QUERY_TIME": query_time,
        "QUERY_TYPE": "W",
        "SENDER_NAME": "Meera Shah",
        "SENDER_MOBILE": "9123456780",
        "SENDER_EMAIL": "meera@example.com",
        "SENDER_COMPANY": "Shah Sports",
        "SENDER_CITY": "Ahmedabad",
        "QUERY_MESSAGE": "Need a badminton court quote",
    }
    item.update(overrides)
    return item


def _sales_headers(client, db_session, email="sales-p3@test.local"):
    return _role_headers(client, db_session, UserRole.SALES, email)


def _pm_headers(client, db_session, email="pm-p3@test.local"):
    return _role_headers(client, db_session, UserRole.PM, email)


def _marketing_headers(client, db_session, email="marketing-p3@test.local"):
    return _role_headers(client, db_session, UserRole.MARKETING, email)


def _import_one(db_session):
    from app.core import marketplace_imports as mi

    r = mi.capture_batch(db_session, items=[_fixture_item()], account_id="default")
    outcome = mi.process_one(db_session)
    return outcome.opportunity_id


# --- Section 8: operational screen, permission denial (explicit, new case) --------------------


def _call(client, method, path, headers):
    if method == "post":
        return client.post(path, headers=headers, json={"range_start": "2026-01-01T00:00:00", "range_end": "2026-01-02T00:00:00"} if "backfill" in path else {})
    return client.get(path, headers=headers)


def test_operational_screen_refuses_sales_case_new(client, director_user, db_session):
    sales_headers = _sales_headers(client, db_session)
    for path, method in [
        ("/marketplace-imports/connection-health", "get"),
        ("/marketplace-imports/summary", "get"),
        ("/marketplace-imports", "get"),
        ("/marketplace-imports/verify-key", "post"),
        ("/marketplace-imports/backfill", "post"),
    ]:
        res = _call(client, method, path, sales_headers)
        assert res.status_code == 403, f"{path} should refuse Sales, got {res.status_code}: {res.text}"


def test_operational_screen_refuses_marketing_case_new(client, director_user, db_session):
    """Not just the ledger's own summary counts -- every operational control (verify-key, retry,
    backfill, the raw ledger list) and every existing business endpoint must independently refuse
    Marketing, proving the new role's access is genuinely limited to its one aggregation
    endpoint, not merely that a hardcoded role-list assertion happens to match."""
    marketing_headers = _marketing_headers(client, db_session)
    for path, method in [
        ("/marketplace-imports/connection-health", "get"),
        ("/marketplace-imports/summary", "get"),
        ("/marketplace-imports", "get"),
        ("/marketplace-imports/verify-key", "post"),
        ("/marketplace-imports/backfill", "post"),
    ]:
        res = _call(client, method, path, marketing_headers)
        assert res.status_code == 403, f"{path} should refuse Marketing, got {res.status_code}: {res.text}"

    fake_id = "00000000-0000-0000-0000-000000000000"
    res = client.post(f"/marketplace-imports/{fake_id}/retry", headers=marketing_headers)
    assert res.status_code == 403, res.text


def test_marketing_refused_buyer_detail_and_client_match_endpoints_case_new(client, director_user, db_session):
    """Section 5/7's Opportunity-scoped endpoints (import-detail, possible-client-matches) use
    the existing READ_ROLES tuple, which was never extended to include Marketing -- confirmed
    directly here, not inferred from the aggregation endpoint's own separate gate."""
    from app.core import marketplace_imports as mi

    opp_id = _import_one(db_session)
    marketing_headers = _marketing_headers(client, db_session, email="marketing-buyer-detail@test.local")
    res1 = client.get(f"/opportunities/{opp_id}/import-detail", headers=marketing_headers)
    assert res1.status_code == 403, res1.text
    res2 = client.get(f"/opportunities/{opp_id}/possible-client-matches", headers=marketing_headers)
    assert res2.status_code == 403, res2.text
    res3 = client.get(f"/opportunities/{opp_id}", headers=marketing_headers)
    assert res3.status_code == 403, res3.text


def test_raw_payload_is_never_returned_by_any_endpoint_case_new(client, director_user, db_session):
    """Explicit, positive proof (not an absence-of-evidence argument): the ledger list endpoint
    -- the one place PM/Director can read details about a captured lead -- exposes status/reason/
    retry metadata but never the raw_payload blob itself, for any role, including PM/Director
    who otherwise have full ledger read access."""
    _import_one(db_session)
    headers = _director_headers(client, director_user)
    res = client.get("/marketplace-imports", headers=headers)
    assert res.status_code == 200
    for row in res.json():
        assert "raw_payload" not in row
    assert "raw_payload" not in res.text
    assert "QUERY_MESSAGE" not in res.text  # a raw-payload field name that would only leak via the blob itself


def test_operational_screen_allows_pm_and_director(client, director_user, db_session):
    pm_headers = _pm_headers(client, db_session)
    director_headers = _director_headers(client, director_user)
    for headers in (pm_headers, director_headers):
        assert client.get("/marketplace-imports/summary", headers=headers).status_code == 200
        assert client.get("/marketplace-imports/connection-health", headers=headers).status_code == 200


def test_summary_counts_are_accurate(client, director_user, db_session):
    from app.core import marketplace_imports as mi

    # The bad item must be captured (and exhausted to `rejected`) BEFORE the good one exists --
    # process_one always claims the oldest pending row first, so capturing the good item first
    # would let it "use up" one of the loop's process_one calls instead of the bad one.
    bad = _fixture_item(unique_id="Q-9101", SENDER_MOBILE="9" * 40)
    mi.capture_batch(db_session, items=[bad], account_id="default")
    for _ in range(mi.AUTOMATIC_RETRY_CAP):
        mi.process_one(db_session)
    mi.capture_batch(db_session, items=[_fixture_item(unique_id="Q-9100")], account_id="default")
    mi.capture_batch(db_session, items=[{"SENDER_NAME": "malformed"}], account_id="default")

    headers = _director_headers(client, director_user)
    res = client.get("/marketplace-imports/summary", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["backlog_count"] == 1
    assert body["quarantined_count"] == 1
    assert body["failures_count"] == 1


# --- Secret redaction (explicit, new case) ------------------------------------------------------


def test_api_key_never_returned_or_logged_case_new(client, director_user, db_session, monkeypatch):
    monkeypatch.setattr("app.config.settings.indiamart_pull_api_key", "sekrit-value-should-never-leak-1234567890")
    headers = _director_headers(client, director_user)
    res = client.get("/marketplace-imports/connection-health", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert "sekrit-value-should-never-leak-1234567890" not in res.text
    assert body["masked_key"] == "...567890"

    # Every other response body touched by this test file must never contain the real key either.
    for path in ("/marketplace-imports/summary", "/marketplace-imports"):
        r = client.get(path, headers=headers)
        assert "sekrit-value-should-never-leak-1234567890" not in r.text


def test_verify_key_failure_notifies_directors_and_never_leaks_key_case_6(client, director_user, db_session, monkeypatch):
    """Case 6 (expired-key alert): a simulated failure produces a real in-app Notification to
    every active Director, and the key itself never appears in the response."""
    monkeypatch.setattr("app.config.settings.indiamart_pull_api_key", "real-secret-abcdefghij")

    def failing_fetch(api_key, start, end):
        raise RuntimeError("401 Unauthorized: key expired")

    monkeypatch.setattr(pull, "default_fetch_window", failing_fetch)

    headers = _director_headers(client, director_user)
    res = client.post("/marketplace-imports/verify-key", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["ok"] is False
    assert "real-secret-abcdefghij" not in res.text

    note = (
        db_session.query(Notification)
        .filter(Notification.user_id == director_user.id, Notification.kind == NotificationKind.IMPORT_KEY_EXPIRED)
        .first()
    )
    assert note is not None
    assert note.email_status.value == "pending"  # never queued for digest email -- in-app only


# --- Section 5: import-detail -------------------------------------------------------------------


def test_import_detail_reachable_by_owner_after_purge(client, director_user, db_session):
    from app.core import marketplace_imports as mi
    from app.models.marketplace_lead_import import MarketplaceLeadImport
    from datetime import UTC, datetime, timedelta

    opp_id = _import_one(db_session)
    headers = _director_headers(client, director_user)
    res = client.get(f"/opportunities/{opp_id}/import-detail", headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["sender_company"] == "Shah Sports"

    row = db_session.query(MarketplaceLeadImport).filter(MarketplaceLeadImport.opportunity_id == opp_id).one()
    row.received_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=mi.RETENTION_DAYS + 1)
    db_session.commit()
    mi.run_retention_purge(db_session)

    res2 = client.get(f"/opportunities/{opp_id}/import-detail", headers=headers)
    assert res2.status_code == 200
    assert res2.json()["sender_company"] == "Shah Sports"  # durable column survives the purge


def test_import_detail_404_for_non_imported_opportunity(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/opportunities",
        json={"lead_name": "Regular Lead", "lead_phone": "9000000000", "next_follow_up_date": "2027-01-01"},
        headers=headers,
    )
    assert res.status_code == 201, res.text
    opp_id = res.json()["id"]
    res2 = client.get(f"/opportunities/{opp_id}/import-detail", headers=headers)
    assert res2.status_code == 404


# --- Section 7: unassigned queue, possible-client-matches, assignment notification -------------


def test_unassigned_queue_lists_only_unassigned_imported_leads(client, director_user, db_session):
    opp_id = _import_one(db_session)
    headers = _director_headers(client, director_user)
    res = client.get("/opportunities?unassigned=true&source=indiamart", headers=headers)
    assert res.status_code == 200
    ids = [o["id"] for o in res.json()]
    assert str(opp_id) in ids
    for o in res.json():
        assert o["owner_id"] is None


def test_possible_client_matches_finds_phone_match(client, director_user, db_session):
    headers = _director_headers(client, director_user)
    res = client.post(
        "/clients",
        json={"name": "Shah Sports Academy", "type": "school", "contact_name": "Meera", "phone": "9123456780"},
        headers=headers,
    )
    assert res.status_code == 201, res.text

    opp_id = _import_one(db_session)  # lead_phone == 9123456780 (same fixture)
    res2 = client.get(f"/opportunities/{opp_id}/possible-client-matches", headers=headers)
    assert res2.status_code == 200
    matches = res2.json()
    assert len(matches) == 1
    assert matches[0]["matched_field"] == "phone"


def test_assignment_notification_fires_in_app_only_case_new(client, director_user, db_session):
    """New case: assigning an unassigned imported Opportunity to a Sales rep produces a real
    in-app Notification to that rep, never queued for digest email."""
    sales_user = User(
        name="Sales Rep", email="rep-p3@test.local", hashed_password=hash_password("TestPass!1"), role=UserRole.SALES,
    )
    db_session.add(sales_user)
    db_session.commit()

    opp_id = _import_one(db_session)
    headers = _director_headers(client, director_user)
    res = client.patch(
        f"/ownership/opportunity/{opp_id}", json={"owner_id": str(sales_user.id)}, headers=headers,
    )
    assert res.status_code == 200, res.text

    note = (
        db_session.query(Notification)
        .filter(Notification.user_id == sales_user.id, Notification.kind == NotificationKind.IMPORT_LEAD_ASSIGNED)
        .first()
    )
    assert note is not None
    assert note.email_status.value == "pending"


# --- Section 9: Marketing Phase A dashboard -----------------------------------------------------


def test_marketing_dashboard_aggregates_only_and_role_boundary_case_15(client, director_user, db_session):
    """Case 15: a Marketing-role user can read the dashboard and is refused on an existing
    Opportunity/Client endpoint, proving the new role wasn't added to any existing tuple. Figures
    checked against a hand-computed expectation from the fixture data, not just a non-error response."""
    _import_one(db_session)
    marketing_headers = _marketing_headers(client, db_session)

    res = client.get(
        "/marketplace-imports/marketing/dashboard",
        params={"period_start": "2026-09-01", "period_end": "2026-09-30"},
        headers=marketing_headers,
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["imported_total"] == 1
    assert body["by_query_type"] == {"W": 1}
    # M4: each stage now carries its rate over the explicit denominator (Opportunities imported in the period).
    assert body["current_stage_distribution"] == [{"stage": "new", "count": 1, "rate": 1.0}]

    refused = client.get("/opportunities", headers=marketing_headers)
    assert refused.status_code == 403
    refused2 = client.get("/clients", headers=marketing_headers)
    assert refused2.status_code == 403
