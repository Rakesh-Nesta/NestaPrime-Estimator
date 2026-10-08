"""Subprocess helper for test_preflight_mobile_identifiers.py -- NOT a test module.

Runs the real preflight `main()` in a FRESH interpreter, against a REAL SQLAlchemy engine/session/pool whose DBAPI connection is an
in-memory SQLite double that can be made to fail at chosen points with fabricated URL/password/phone text. A fresh process matters:
SQLAlchemy reports pool-cleanup failures through the `logging` module, and with no handler configured Python's last-resort handler
writes the library traceback to the real stderr. Inside pytest, logging capture hides that path, so in-process doubles miss it.

Usage: python preflight_pool_double.py <scenario>
No network, no PostgreSQL, fabricated values only. (This exercises error OUTPUT, not PostgreSQL READ ONLY enforcement; the READ ONLY
statement is emulated as a no-op here, and enforced by the database in the other tests.)"""

import importlib.util
import logging
import sqlite3
import sys
import types
import warnings
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


# ---- logging configurations the preflight must be safe under (applied in the child BEFORE main() runs) ----------------------------
class Retaining(logging.Handler):
    """An existing handler that keeps whatever it is given -- the way a log shipper or an in-memory buffer would."""

    def __init__(self):
        super().__init__(level=logging.NOTSET)
        self.records = []

    def emit(self, record):
        self.records.append(record)


def apply_logging_config(name):
    root, pool = logging.getLogger(), logging.getLogger("sqlalchemy.pool")
    retained = Retaining()
    if name == "default":
        pass
    elif name == "root_stream_handler":  # retains the ORIGINAL stderr object, so redirecting sys.stderr later cannot catch it
        root.addHandler(logging.StreamHandler(sys.stderr))
    elif name == "pool_handler_no_propagate":
        pool.addHandler(logging.StreamHandler(sys.stderr))
        pool.propagate = False
    elif name == "pool_null_handler_no_propagate":  # nothing downstream will ever see the record: a root-based counter is blind
        pool.addHandler(logging.NullHandler())
        pool.propagate = False
    elif name == "retaining_handlers":
        for target in (root, pool, logging.getLogger("sqlalchemy")):
            target.addHandler(retained)
    elif name == "pool_level_critical":  # the record would not even be created
        pool.setLevel(logging.CRITICAL)
        root.addHandler(logging.StreamHandler(sys.stderr))
    elif name == "pool_disabled":
        pool.disabled = True
        root.addHandler(logging.StreamHandler(sys.stderr))
    elif name == "global_logging_disable":
        logging.disable(logging.CRITICAL)
        root.addHandler(logging.StreamHandler(sys.stderr))
    else:
        raise SystemExit(f"unknown logging config {name}")
    return retained


def snapshot():
    root, pool = logging.getLogger(), logging.getLogger("sqlalchemy.pool")
    return (tuple(root.handlers), tuple(pool.handlers), tuple(logging.getLogger("sqlalchemy").handlers), pool.propagate, pool.level,
            pool.disabled, root.level, logging.root.manager.disable, sys.stderr, sys.stdout, sys.unraisablehook,
            list(warnings.filters), warnings.showwarning, logging.Logger.handle, logging.Logger.callHandlers,
            logging.Logger.isEnabledFor, logging.lastResort)


EXIT_NOT_RESTORED = 97
EXIT_RETAINED_RECORD = 98


if __name__ == "__main__":
    mode, scenario = sys.argv[1], sys.argv[2]
    config = sys.argv[3] if len(sys.argv) > 3 else "default"
    preflight = load_preflight()
    factory = make_session_factory(scenario)
    sys.modules["app.db.session"] = types.SimpleNamespace(SessionLocal=factory)  # what main() imports
    retained = apply_logging_config(config)
    before = snapshot()
    if mode == "main":
        code = preflight.main(["--json"])
        if snapshot() != before:
            sys.exit(EXIT_NOT_RESTORED)
        if retained.records:  # an existing handler was handed a (raw, sensitive) record
            sys.exit(EXIT_RETAINED_RECORD)
        sys.exit(code)
    if mode == "main_interrupted":
        # EXCEPTIONAL exit: the run is interrupted from inside the contained region; the configuration must still be restored.
        def interrupted(_diagnostics):
            raise KeyboardInterrupt

        preflight._assess = interrupted
        try:
            preflight.main(["--json"])
        except KeyboardInterrupt:
            pass
        sys.exit(0 if snapshot() == before else EXIT_NOT_RESTORED)
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
