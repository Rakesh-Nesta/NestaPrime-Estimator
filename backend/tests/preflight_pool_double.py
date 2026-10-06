"""Subprocess helper for test_preflight_mobile_identifiers.py -- NOT a test module.

Runs the real preflight `main()` in a FRESH interpreter, against a REAL SQLAlchemy engine/session/pool whose DBAPI connection is an
in-memory SQLite double that can be made to fail at chosen points with fabricated URL/password/phone text. A fresh process matters:
SQLAlchemy reports pool-cleanup failures through the `logging` module, and with no handler configured Python's last-resort handler
writes the library traceback to the real stderr. Inside pytest, logging capture hides that path, so in-process doubles miss it.

Usage: python preflight_pool_double.py <scenario>
No network, no PostgreSQL, fabricated values only. (This exercises error OUTPUT, not PostgreSQL READ ONLY enforcement; the READ ONLY
statement is emulated as a no-op here, and enforced by the database in the other tests.)"""

import importlib.util
import sqlite3
import sys
import types
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

FABRICATED = "postgresql://fakeuser:fakepassword@fake.invalid/fakedb phone +919876543210"
BACKEND = Path(__file__).resolve().parents[1]


class CursorDouble:
    def __init__(self, cursor, owner):
        self.cursor, self.owner = cursor, owner

    def __getattr__(self, name):
        return getattr(self.cursor, name)

    def execute(self, sql, *args):
        if sql == "SET TRANSACTION READ ONLY":
            sql = "SELECT 1"  # emulate only its success
        elif self.owner.fail_query and "FROM users" in sql:
            raise RuntimeError(FABRICATED)
        return self.cursor.execute(sql, *args)


class ConnectionDouble:
    def __init__(self, fail_rollback_after=None, fail_close=False, fail_query=False):
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute("CREATE TABLE users (mobile TEXT, is_active BOOLEAN, email TEXT)")
        for mobile, active, email in [("+919876543210", 1, "a@x.invalid"), ("+915123456789", 1, None), ("abc9876543210", 0, None)]:
            self.connection.execute("INSERT INTO users VALUES (?, ?, ?)", (mobile, active, email))
        self.connection.commit()
        self.rollback_calls = 0
        self.fail_rollback_after, self.fail_close, self.fail_query = fail_rollback_after, fail_close, fail_query

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def cursor(self, *args, **kwargs):
        return CursorDouble(self.connection.cursor(*args, **kwargs), self)

    def rollback(self):
        self.rollback_calls += 1
        if self.fail_rollback_after is not None and self.rollback_calls > self.fail_rollback_after:
            raise RuntimeError(FABRICATED)
        return self.connection.rollback()

    def close(self):
        if self.fail_close:
            raise RuntimeError(FABRICATED)
        return self.connection.close()


# scenario -> (connection options, creator raises?). The first rollback is SQLAlchemy's dialect initialisation.
SCENARIOS = {
    "success": ({}, False),
    "query_failure": ({"fail_query": True}, False),
    "rollback_and_pool_reset_failure": ({"fail_rollback_after": 1}, False),  # the reviewer's reproduction
    "pool_reset_failure_after_a_good_read": ({"fail_rollback_after": 2}, False),
    "connection_close_failure": ({"fail_close": True}, False),
    "connect_failure": ({}, True),
}


def load_preflight():
    spec = importlib.util.spec_from_file_location("preflight_under_test", BACKEND / "scripts" / "preflight_mobile_identifiers.py")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(BACKEND))
    spec.loader.exec_module(module)
    return module


def make_session_factory(scenario):
    options, creator_raises = SCENARIOS[scenario]
    connection = ConnectionDouble(**options)

    def creator():
        if creator_raises:
            raise RuntimeError(FABRICATED)
        return connection

    return sessionmaker(bind=create_engine("sqlite://", creator=creator))


if __name__ == "__main__":
    mode, scenario = sys.argv[1], sys.argv[2]
    preflight = load_preflight()
    factory = make_session_factory(scenario)
    sys.modules["app.db.session"] = types.SimpleNamespace(SessionLocal=factory)  # what main() imports
    if mode == "main":
        sys.exit(preflight.main(["--json"]))
    if mode == "uncontained":
        # POSITIVE CONTROL: the same session/pool cleanup WITHOUT the preflight's containment. It must reproduce the library's own
        # stderr diagnostic, proving the double really drives SQLAlchemy's logging path.
        db = factory()
        try:
            preflight.run(db)
        except Exception:
            pass
        finally:
            try:
                db.close()
            except Exception:
                pass
        sys.exit(0)
    raise SystemExit(f"unknown mode {mode}")
