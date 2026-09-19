"""Amendment 23 (Section 29): retry helper for sequence-number-style
generators (_generate_project_no, _po_number) that read existing rows
and compute the next number in Python, with no row lock or DB sequence
-- two concurrent requests can compute the identical number, and the
second commit collides against the column's unique constraint.

Rather than adding a locked sequence-counter table (heavier, needs a
migration), this retries the whole build-and-commit on a collision:
build() is called again, which re-reads the now-updated row set and
computes a genuinely new number, so the retry succeeds transparently
instead of surfacing a raw 500 to the user."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def create_with_retry(db: Session, build, attempts: int = 3):
    """build() performs one full attempt's unit of work -- typically
    constructing the primary ORM instance, calling db.add() on it (and
    db.flush() first if child rows need its generated id), adding any
    child rows, then returning the primary instance. Not committed yet.
    Each retry calls build() again, so a collision re-reads the
    now-updated row set and computes a genuinely new sequence number
    rather than retrying with the same doomed-to-collide value. Commits,
    refreshes, and returns the instance, retrying on IntegrityError up
    to `attempts` times before re-raising the last error."""
    last_error: IntegrityError | None = None
    for _ in range(attempts):
        obj = build()
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            last_error = exc
            continue
        db.refresh(obj)
        return obj
    assert last_error is not None
    raise last_error
