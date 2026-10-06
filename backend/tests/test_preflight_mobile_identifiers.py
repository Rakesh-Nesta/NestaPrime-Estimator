"""A61: the read-only preflight of stored mobile identifiers, validated on LOCAL FIXTURES only.

It reports which stored `users.mobile` values the approved normalization rule would refuse, as aggregate counts. These tests
check the classification, the counts (including malformed ASCII identifiers as well as Unicode cases), that no phone number
reaches the output, and that the procedure is read-only."""

import importlib.util
import re
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from app.core.security import hash_password
from app.models.user import User, UserRole

_SPEC = importlib.util.spec_from_file_location(
    "preflight_mobile_identifiers", Path(__file__).resolve().parents[1] / "scripts" / "preflight_mobile_identifiers.py"
)
preflight = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(preflight)

# stored value -> (expected category, is_active, email)
FIXTURES = {
    "+919876543210": ("valid_ascii", True, "a@test.local"),
    "+919876543211": ("valid_ascii", True, None),
    "+91९876543212": ("valid_unicode_spelling", True, None),
    "98765 43213": ("stored_form_not_canonical", True, "c@test.local"),
    "+915123456789": ("refused_ascii_indian_rule", True, None),           # +91, first national digit 5
    "+91987654321": ("refused_ascii_indian_rule", False, None),           # nine national digits
    "+91512345678९": ("refused_unicode_indian_rule", True, "d@test.local"),
    "+９１5123456789": ("refused_unicode_indian_rule", True, None),
    "+123": ("refused_ascii_other", True, None),
    "+١٢": ("refused_unicode_other", True, None),
    "abc9876543210": ("refused_invalid_content", False, "e@test.local"),
}


@pytest.fixture
def stored(db_session):
    for i, (mobile, (_category, active, email)) in enumerate(FIXTURES.items()):
        db_session.add(
            User(name=f"Fixture {i}", email=email, mobile=mobile, hashed_password=hash_password("TestPass!1"),
                 role=UserRole.SALES, is_active=active)
        )
    db_session.commit()  # so the preflight's read-only transaction starts fresh
    return FIXTURES


@pytest.mark.parametrize("mobile,expected", [(m, v[0]) for m, v in FIXTURES.items()], ids=[v[0] for v in FIXTURES.values()])
def test_each_stored_shape_is_classified_by_the_approved_rule(mobile, expected):
    assert preflight.classify(mobile) == expected


def test_the_counts_are_exact_for_a_fixture_database(db_session, stored):
    result = preflight.run(db_session)
    assert result["users_with_mobile"] == len(FIXTURES)
    assert result["users_total"] >= len(FIXTURES)
    expected = {c: 0 for c in preflight.CATEGORIES}
    for category, _a, _e in FIXTURES.values():
        expected[category] += 1
    assert result["by_category"] == expected
    assert sum(result["by_category"].values()) == len(FIXTURES)
    refused = result["refused_by_approved_rule"]
    assert refused["accounts"] == 7                                       # the seven refused fixtures
    assert refused["active"] == 5 and refused["inactive"] == 2           # +91987654321 and abc... are inactive
    assert refused["with_no_email"] == 5                                  # affected accounts WITHOUT an email: no fallback assumed
    # accepted by the pre-A61 normalizer but refused now: both ASCII +91 cases, the two Unicode +91 cases, and the letters one
    assert refused["accepted_before_a61_corrections"] == 5


def test_the_output_contains_no_phone_number_id_or_email(db_session, stored, capsys):
    result = preflight.run(db_session)
    rendered = preflight.render(result)
    assert not re.search(r"\d{6,}", rendered)
    for mobile in FIXTURES:
        assert mobile not in rendered
    for _category, _active, email in FIXTURES.values():
        if email:
            assert email not in rendered
    assert "@" not in rendered


def test_the_procedure_is_read_only_and_leaves_the_data_unchanged(db_session, stored):
    before = db_session.execute(text("SELECT count(*), md5(string_agg(mobile, ',' ORDER BY mobile)) FROM users WHERE mobile IS NOT NULL")).one()
    db_session.commit()
    preflight.run(db_session)
    after = db_session.execute(text("SELECT count(*), md5(string_agg(mobile, ',' ORDER BY mobile)) FROM users WHERE mobile IS NOT NULL")).one()
    assert tuple(before) == tuple(after)


def test_a_write_inside_the_preflight_transaction_would_be_refused_by_the_database(db_session, stored, monkeypatch):
    """Prove the READ ONLY setting itself: run() starts its transaction with SET TRANSACTION READ ONLY, so a write attempted
    inside it raises. (The real procedure issues no write; this checks the guard is in force.)"""
    original = preflight.classify

    def classify_then_try_to_write(value):
        db_session.execute(text("UPDATE users SET name = name WHERE false"))   # even a no-op UPDATE is a write statement
        return original(value)

    monkeypatch.setattr(preflight, "classify", classify_then_try_to_write)
    with pytest.raises(DBAPIError):
        preflight.run(db_session)
    db_session.rollback()


# ---- the command-line error boundary: a failure is nonzero, fixed-message, and leaks nothing ----------------------------------
# Every sensitive-looking value below is fabricated.
LEAKS = ["leakuser", "leakpass", "leakdb", "leak.internal", "postgresql", "Traceback", "+919876543210", "9876543210",
         "input_value", "pydantic", "sqlalchemy", "psycopg"]   # (the NAME of a variable in the fixed message is not a leak)
FABRICATED_URL = "postgresql+psycopg://leakuser:leakpass@leak.internal:5432/leakdb"


def _assert_clean_failure(code, out, err, expected_fragment=None):
    assert code not in (0, None)
    combined = (out + err).lower()
    for leak in LEAKS:
        assert leak.lower() not in combined, f"leaked {leak!r}"
    assert "by_category" not in combined and "users_total" not in combined     # no counts after a failure
    assert (err or out).strip()                                                 # a useful message is given
    if expected_fragment:
        assert expected_fragment in combined


def test_missing_secret_key_configuration_failure_is_sanitized(tmp_path):
    """Run the real script in a fresh process, with a fabricated DATABASE_URL and NO SECRET_KEY: the settings validation fails
    while `app.db.session` is imported. Stdout and stderr are both captured."""
    import os
    import subprocess
    import sys

    env = {k: v for k, v in os.environ.items() if k.upper() not in ("DATABASE_URL", "SECRET_KEY")}
    env["DATABASE_URL"] = FABRICATED_URL
    proc = subprocess.run(
        [sys.executable, str(Path(preflight.__file__)), "--json"], capture_output=True, text=True, env=env, cwd=tmp_path, timeout=120
    )
    _assert_clean_failure(proc.returncode, proc.stdout, proc.stderr, "configuration")


# ---- real SQLAlchemy session/pool cleanup: the library's own logging must not reach stderr ------------------------------------
# The double and the subprocess rationale are in tests/preflight_pool_double.py.
_DOUBLE = Path(__file__).resolve().parent / "preflight_pool_double.py"
_POOL_LEAKS = ["fakeuser", "fakepassword", "fake.invalid", "fakedb", "+919876543210", "9876543210", "Traceback",
               "Exception during reset", "sqlalchemy", "RuntimeError", "File \""]


def _run_double(mode, scenario, config="default"):
    import subprocess
    import sys

    return subprocess.run([sys.executable, str(_DOUBLE), mode, scenario, config], capture_output=True, text=True, timeout=120)


def test_the_double_really_drives_sqlalchemys_logging_path_when_uncontained():
    """Positive control: without the preflight's containment the library writes the traceback, with the fabricated text, to the real
    stderr. If this ever stops reproducing, the containment tests below would be vacuous."""
    proc = _run_double("uncontained", "rollback_and_pool_reset_failure")
    assert "Exception during reset or similar" in proc.stderr
    assert "fakepassword" in proc.stderr and "Traceback" in proc.stderr


# Every logging configuration an environment might have. The preflight must be safe under ALL of them (see _contained()).
LOGGING_CONFIGS = [
    "default",                          # nothing configured: Python's last-resort handler would print the traceback
    "root_stream_handler",              # root StreamHandler holding the ORIGINAL stderr
    "pool_handler_no_propagate",        # sqlalchemy.pool StreamHandler, propagate=False
    "pool_null_handler_no_propagate",   # sqlalchemy.pool NullHandler, propagate=False: a root-based counter never sees the record
    "retaining_handlers",               # existing handlers that KEEP records: raw sensitive records must never reach them
    "pool_level_critical",              # logger level above ERROR: the record would not be created
    "pool_disabled",                    # logger.disabled = True
    "global_logging_disable",           # logging.disable(CRITICAL)
]
FAILURE_SCENARIOS = [
    ("query_failure", preflight.EXIT_ASSESSMENT),                       # assessment error
    ("rollback_and_pool_reset_failure", preflight.EXIT_ASSESSMENT),     # the reviewer's reproduction: assessment error wins
    ("connect_failure", preflight.EXIT_ASSESSMENT),
    ("pool_reset_failure_after_a_good_read", preflight.EXIT_CLEANUP),   # read fine, cleanup failed: NOT apparent success
    ("connection_close_failure", preflight.EXIT_CLEANUP),
]


@pytest.mark.parametrize("config", LOGGING_CONFIGS)
@pytest.mark.parametrize("scenario,expected_code", FAILURE_SCENARIOS)
def test_real_sqlalchemy_failures_print_only_the_fixed_message_under_any_logging_configuration(scenario, expected_code, config):
    proc = _run_double("main", scenario, config)
    # The helper exits 97 if the logging/warnings/stderr configuration was not restored, 98 if an existing handler was handed a
    # record; either would show here as a different exit code.
    assert proc.returncode == expected_code
    assert proc.stdout == ""                                                # counts withheld after any failure
    assert proc.stderr == preflight._MESSAGES[expected_code] + "\n"         # exactly the fixed line: nothing else, no traceback
    for leak in _POOL_LEAKS:
        assert leak not in proc.stdout + proc.stderr, f"leaked {leak!r}"


@pytest.mark.parametrize("config", LOGGING_CONFIGS)
def test_a_real_sqlalchemy_success_is_unaffected_by_the_logging_configuration(config):
    import json

    proc = _run_double("main", "success", config)
    assert proc.returncode == 0 and proc.stderr == ""
    assert json.loads(proc.stdout)["users_with_mobile"] == 3


@pytest.mark.parametrize("config", ["default", "pool_null_handler_no_propagate", "retaining_handlers", "global_logging_disable"])
def test_the_logging_configuration_is_restored_even_when_the_run_is_interrupted(config):
    proc = _run_double("main_interrupted", "success", config)
    assert proc.returncode == 0, "logging/warnings/stderr state was not restored after an exceptional exit"


class _FakeSession:
    """Records the cleanup calls; each step can be made to fail with a message full of sensitive-looking text."""

    def __init__(self, execute_error=None, rollback_error=None, close_error=None, rows=None):
        self.execute_error, self.rollback_error, self.close_error, self.rows = execute_error, rollback_error, close_error, rows
        self.calls = []

    def execute(self, statement, *a, **k):
        self.calls.append("execute")
        if self.execute_error:
            raise self.execute_error
        raise AssertionError("unexpected execute")

    def rollback(self):
        self.calls.append("rollback")
        if self.rollback_error:
            raise self.rollback_error

    def close(self):
        self.calls.append("close")
        if self.close_error:
            raise self.close_error


def _boom(label):
    return RuntimeError(f"{label}: {FABRICATED_URL} user +919876543210 password leakpass")


def _run_main(monkeypatch, capsys, factory, *args):
    import app.db.session as session_module

    monkeypatch.setattr(session_module, "SessionLocal", factory)
    code = preflight.main(list(args))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_session_creation_failure_is_sanitized(monkeypatch, capsys):
    def factory():
        raise _boom("cannot create session")

    code, out, err = _run_main(monkeypatch, capsys, factory)
    _assert_clean_failure(code, out, err)


def test_query_failure_is_sanitized_and_the_session_is_rolled_back_and_closed(monkeypatch, capsys):
    session = _FakeSession(execute_error=_boom("query failed"))
    code, out, err = _run_main(monkeypatch, capsys, lambda: session, "--json")
    _assert_clean_failure(code, out, err)
    assert session.calls == ["execute", "rollback", "close"]


def test_a_real_connection_failure_is_sanitized(monkeypatch, capsys):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    unreachable = sessionmaker(bind=create_engine("postgresql+psycopg://leakuser:leakpass@127.0.0.1:1/leakdb"))
    code, out, err = _run_main(monkeypatch, capsys, unreachable)
    _assert_clean_failure(code, out, err)
    assert "127.0.0.1" not in out + err


def test_rollback_failure_after_a_query_failure_is_still_a_sanitized_failure(monkeypatch, capsys):
    session = _FakeSession(execute_error=_boom("query failed"), rollback_error=_boom("rollback failed"))
    code, out, err = _run_main(monkeypatch, capsys, lambda: session)
    _assert_clean_failure(code, out, err)
    assert session.calls == ["execute", "rollback", "close"]


def test_close_failure_after_a_query_failure_is_still_a_sanitized_failure(monkeypatch, capsys):
    session = _FakeSession(execute_error=_boom("query failed"), close_error=_boom("close failed"))
    code, out, err = _run_main(monkeypatch, capsys, lambda: session)
    _assert_clean_failure(code, out, err)
    assert session.calls == ["execute", "rollback", "close"]


def test_cleanup_failure_after_a_successful_assessment_is_not_apparent_success(db_session, stored, monkeypatch, capsys):
    """The assessment itself succeeded, but ending the session failed: nonzero, sanitized, and the counts are withheld because
    the read-only transaction could not be confirmed ended."""
    real_close = db_session.close

    def failing_close():
        real_close()
        raise _boom("close failed")

    monkeypatch.setattr(db_session, "close", failing_close)
    code, out, err = _run_main(monkeypatch, capsys, lambda: db_session, "--json")
    _assert_clean_failure(code, out, err, "cleanup")


def test_a_rollback_failure_after_a_successful_query_is_not_apparent_success(db_session, stored, monkeypatch, capsys):
    monkeypatch.setattr(db_session, "rollback", lambda: (_ for _ in ()).throw(_boom("rollback failed")))
    code, out, err = _run_main(monkeypatch, capsys, lambda: db_session)
    _assert_clean_failure(code, out, err)


def test_success_through_the_command_line_entry_prints_counts_only_and_exits_zero(db_session, stored, monkeypatch, capsys):
    import json

    from sqlalchemy.orm import sessionmaker

    code, out, err = _run_main(monkeypatch, capsys, sessionmaker(bind=db_session.get_bind()), "--json")
    assert code == 0 and err == ""
    result = json.loads(out)
    assert result["users_with_mobile"] == len(FIXTURES)
    assert result["refused_by_approved_rule"]["accounts"] == 7
    assert not re.search(r"\d{6,}", out) and "@" not in out
