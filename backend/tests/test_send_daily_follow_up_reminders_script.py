"""WP8 (correction plan, 2026-09-29): the cron script's own time-window logic. The script
computes Asia/Kolkata time itself via zoneinfo rather than trusting the server's own OS
timezone -- these tests pin that math down directly, independent of whatever timezone the
machine running pytest happens to be in."""
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from send_daily_follow_up_reminders import IST, _in_window  # noqa: E402


def _ist(hour, minute):
    return datetime(2026, 9, 29, hour, minute, tzinfo=IST)


def test_window_opens_at_nine_am_ist_sharp():
    assert _in_window(_ist(9, 0)) is True


def test_window_closes_at_nine_thirty_ist():
    assert _in_window(_ist(9, 30)) is False


def test_window_excludes_before_nine():
    assert _in_window(_ist(8, 59)) is False


def test_window_includes_nine_twenty_nine():
    assert _in_window(_ist(9, 29)) is True


def test_window_excludes_the_rest_of_the_day():
    assert _in_window(_ist(0, 0)) is False
    assert _in_window(_ist(12, 0)) is False
    assert _in_window(_ist(23, 59)) is False


def test_ist_is_computed_independent_of_local_machine_timezone():
    """A UTC moment that IS 09:15 IST (UTC+5:30) must read as inside the window when
    converted, regardless of what timezone this test process itself runs in."""
    utc_moment = datetime(2026, 9, 29, 3, 45, tzinfo=ZoneInfo("UTC"))  # 09:15 IST
    as_ist = utc_moment.astimezone(IST)
    assert as_ist.hour == 9 and as_ist.minute == 15
    assert _in_window(as_ist) is True
