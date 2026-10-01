"""Deterministic concurrency harness for P5's lock-order tests.

Not probabilistic thread racing: each operation runs on its OWN session/connection in a thread; an
operation can be 'gated' so its COMMIT is held until the test releases it, which keeps every lock it
took held. A second operation started meanwhile must BLOCK on a Postgres lock (observed through
pg_stat_activity, not guessed with sleeps); releasing the first lets the second proceed against the
committed state. That is exactly the 'whichever acquires the lock first' behaviour the contract
specifies, in a fixed, repeatable order."""

import threading
import time

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from tests.conftest import TEST_DATABASE_URL

# A hard ceiling so a broken lock order fails the test instead of hanging the suite.
_engine = create_engine(TEST_DATABASE_URL, poolclass=NullPool, connect_args={"options": "-c lock_timeout=20000"})
Session = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
_probe_engine = create_engine(TEST_DATABASE_URL, poolclass=NullPool)


def lock_waiters() -> int:
    with _probe_engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE datname = current_database() AND wait_event_type = 'Lock' AND pid <> pg_backend_pid()"
            )
        ).scalar()


def wait_until_blocked(expected: int = 1, timeout: float = 15.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if lock_waiters() >= expected:
            return
        time.sleep(0.05)
    raise AssertionError(f"expected {expected} backend(s) waiting on a lock, saw {lock_waiters()}")


class Op:
    """fn(session) runs in a thread on its own session. gate=True holds the COMMIT until release()."""

    def __init__(self, fn, gate: bool = False):
        self.session = Session()
        self.result = None
        self.exc: BaseException | None = None
        self.reached_commit = threading.Event()
        self._release = threading.Event()
        self._fn = fn
        if gate:
            original_commit = self.session.commit

            def gated_commit():
                self.reached_commit.set()
                if not self._release.wait(30):
                    raise AssertionError("gated commit was never released")
                original_commit()

            self.session.commit = gated_commit
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        try:
            self.result = self._fn(self.session)
        except BaseException as exc:  # noqa: BLE001 - the test inspects it
            self.exc = exc
            try:
                self.session.rollback()
            except Exception:
                pass

    def start(self) -> "Op":
        self.thread.start()
        return self

    def wait_holding_locks(self, timeout: float = 20.0) -> "Op":
        """Block until the op has done all its work and is parked at its (gated) commit."""
        if not self.reached_commit.wait(timeout):
            raise AssertionError(f"operation never reached commit; exception: {self.exc!r}")
        return self

    def release(self) -> "Op":
        self._release.set()
        return self

    def join(self, timeout: float = 30.0) -> "Op":
        self.thread.join(timeout)
        assert not self.thread.is_alive(), "operation did not finish (deadlock?)"
        self.session.close()
        return self


def run_to_completion(fn) -> Op:
    op = Op(fn).start()
    return op.join()


def blocked_pair(first_fn, second_fn):
    """first holds its locks at a gated commit; second starts and must block on a lock; first commits;
    second then proceeds. Returns (first_op, second_op), both finished."""
    first = Op(first_fn, gate=True).start().wait_holding_locks()
    second = Op(second_fn).start()
    wait_until_blocked(1)
    first.release().join()
    second.join()
    return first, second
