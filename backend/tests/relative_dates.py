"""Calendar-relative dates for fixtures that were authored with fixed calendar dates.

These tests were written on 2026-09-28 with literal dates such as "2026-10-01" as FUTURE follow-up dates.
The application (correctly) rejects a follow-up date earlier than date.today(), so those literals became
"in the past" on 2026-10-02 and the tests started failing permanently -- the production validation is right,
the fixtures were wrong. d() keeps every date exactly where the author put it RELATIVE to the day the fixtures
were written, by shifting it by the number of days since then. Orderings and intervals between dates are
untouched, and every shifted date is at least 3 days after today, so the result is immune to a run that
crosses local midnight (the shift is fixed once at import, not recomputed per call).

Deliberately fixed dates belong only in frozen-clock boundary tests, never here."""

from datetime import date

AUTHORED_ON = date(2026, 9, 28)
_SHIFT = date.today() - AUTHORED_ON


def d(iso: str) -> str:
    return (date.fromisoformat(iso) + _SHIFT).isoformat()
