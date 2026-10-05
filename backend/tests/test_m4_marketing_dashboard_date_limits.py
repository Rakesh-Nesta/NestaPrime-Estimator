"""Marketing M4: calendar limits of the dashboard period (review finding P2).

`datetime.date` spans 0001-01-01 .. 9999-12-31. The bucket loop used to advance past the FINAL bucket and the period end was an
exclusive "end + 1 day", so 9999-12-31 overflowed; converting 0001-01-01 00:00 IST to UTC underflowed. Both raised unhandled
exceptions (HTTP 500). The contract imposes no business-date cutoff, so the boundary dates are SUPPORTED, not refused:
  * buckets are generated without stepping beyond the last one required;
  * the period end is an inclusive last instant (23:59:59.999999) rather than "next midnight";
  * a lower bound earlier than the smallest representable timestamp is exactly "no lower bound" (no stored value is earlier).
What genuinely cannot be answered gets a clear 4xx, never a 500: dates outside the calendar (422, FastAPI date validation),
a reversed period (400), and a period needing more buckets than the response limit (400, including 0001-01-01..9999-12-31)."""

from datetime import date, datetime, timedelta

import pytest

from tests.test_m4_marketing_dashboard_conformance import _get, _ingest
from tests.test_p3_marketplace_imports_api import _marketing_headers

LOWEST = date(1, 1, 1)
HIGHEST = date(9999, 12, 31)


def _expected_starts(first: date, last: date, bucket: str) -> list[date]:
    """Independent of the implementation: the bucket start dates that cover [first, last], never stepping past `last`."""
    def start_of(d):
        return d - timedelta(days=d.weekday()) if bucket == "week" else d.replace(day=1) if bucket == "month" else d

    out, cur, final = [], start_of(first), start_of(last)
    while True:
        out.append(cur)
        if cur >= final:
            return out
        if bucket == "day":
            cur = cur + timedelta(days=1)
        elif bucket == "week":
            cur = cur + timedelta(days=7)
        else:
            cur = date(cur.year + (cur.month == 12), cur.month % 12 + 1, 1)


@pytest.fixture
def edge_rows(client, db_session):
    """Leads at the two ends of the calendar (UTC naive received_at; enquiry_time as the provider wrote it)."""
    h = _marketing_headers(client, db_session)
    _ingest(db_session, "E-MIN", "01-JAN-0001 00:00:00", "W", received_at=datetime(1, 1, 1, 0, 0, 0))              # IST 0001-01-01 05:30
    _ingest(db_session, "E-MAX", "31-DEC-9999 23:59:59", "B", received_at=datetime(9999, 12, 31, 18, 29, 59))     # IST 9999-12-31 23:59:59
    _ingest(db_session, "R-OVER", "15-SEP-2026 12:00:00", "P", received_at=datetime(9999, 12, 31, 18, 30, 0))     # IST day 10000-01-01: unrepresentable
    return h


BASES = ["enquiry_time", "received_at"]
BUCKETS = ["day", "week", "month"]


@pytest.mark.parametrize("basis", BASES)
@pytest.mark.parametrize("bucket", BUCKETS)
def test_upper_boundary_single_day_is_supported(client, db_session, edge_rows, basis, bucket):
    res = _get(client, edge_rows, period_start="9999-12-31", period_end="9999-12-31", basis=basis, bucket=bucket)
    assert res.status_code == 200, res.text
    body = res.json()
    assert [b["bucket_start"] for b in body["by_date_bucket"]] == [d.isoformat() for d in _expected_starts(HIGHEST, HIGHEST, bucket)]
    # E-MAX is in 9999-12-31 under both bases; R-OVER (received 18:30:00 UTC) is on an IST day that does not exist -> never counted
    assert body["received_total"] == 1 and body["by_query_type"] == {"B": 1}
    assert sum(b["count"] for b in body["by_date_bucket"]) == 1


@pytest.mark.parametrize("basis", BASES)
@pytest.mark.parametrize("bucket", BUCKETS)
def test_lower_boundary_single_day_is_supported(client, db_session, edge_rows, basis, bucket):
    res = _get(client, edge_rows, period_start="0001-01-01", period_end="0001-01-01", basis=basis, bucket=bucket)
    assert res.status_code == 200, res.text
    body = res.json()
    assert [b["bucket_start"] for b in body["by_date_bucket"]] == [d.isoformat() for d in _expected_starts(LOWEST, LOWEST, bucket)]
    assert body["received_total"] == 1 and body["by_query_type"] == {"W": 1}


@pytest.mark.parametrize("basis", BASES)
@pytest.mark.parametrize("bucket", BUCKETS)
@pytest.mark.parametrize(
    "first,last", [(date(9999, 12, 1), HIGHEST), (LOWEST, date(1, 1, 31)), (date(9999, 11, 15), HIGHEST)], ids=["to-max", "from-min", "over-month-end"]
)
def test_periods_touching_the_calendar_ends_return_exactly_the_required_buckets(client, db_session, edge_rows, basis, bucket, first, last):
    res = _get(client, edge_rows, period_start=first.isoformat(), period_end=last.isoformat(), basis=basis, bucket=bucket)
    assert res.status_code == 200, res.text
    got = [b["bucket_start"] for b in res.json()["by_date_bucket"]]
    assert got == [d.isoformat() for d in _expected_starts(first, last, bucket)]
    assert got == sorted(got) and len(got) == len(set(got))   # nothing beyond the final required bucket, nothing repeated


@pytest.mark.parametrize("basis", BASES)
@pytest.mark.parametrize("bucket", BUCKETS)
def test_the_whole_calendar_is_refused_with_400_not_a_server_error(client, db_session, edge_rows, basis, bucket):
    res = _get(client, edge_rows, period_start="0001-01-01", period_end="9999-12-31", basis=basis, bucket=bucket)
    assert res.status_code == 400, res.text
    assert "bucket" in res.json()["detail"].lower()


@pytest.mark.parametrize("params", [{"period_start": "0000-01-01", "period_end": "2026-01-01"}, {"period_start": "2026-01-01", "period_end": "10000-01-01"},
                                    {"period_start": "2026-02-30", "period_end": "2026-03-01"}])
def test_dates_outside_the_calendar_are_a_422_not_a_server_error(client, db_session, params):
    h = _marketing_headers(client, db_session)
    assert _get(client, h, **params).status_code == 422


@pytest.mark.parametrize("basis", BASES)
@pytest.mark.parametrize("bucket", BUCKETS)
def test_ordinary_dates_still_work_including_the_year_end_month_rollover(client, db_session, basis, bucket):
    h = _marketing_headers(client, db_session)
    res = _get(client, h, period_start="2026-12-01", period_end="2027-01-31", basis=basis, bucket=bucket)
    assert res.status_code == 200, res.text
    got = [b["bucket_start"] for b in res.json()["by_date_bucket"]]
    assert got == [d.isoformat() for d in _expected_starts(date(2026, 12, 1), date(2027, 1, 31), bucket)]
    if bucket == "month":
        assert got == ["2026-12-01", "2027-01-01"]


def test_an_unexpected_overflow_while_planning_the_period_is_a_400(client, db_session, monkeypatch):
    """Defence in depth: if date arithmetic ever overflowed again, the caller still gets a clear 400, not a 500."""
    def boom(*args, **kwargs):
        raise OverflowError("date value out of range")

    monkeypatch.setattr("app.api.marketplace_imports._cohort_window", boom)
    h = _marketing_headers(client, db_session)
    res = _get(client, h, period_start="2026-09-01", period_end="2026-09-30")
    assert res.status_code == 400 and "period" in res.json()["detail"].lower()
