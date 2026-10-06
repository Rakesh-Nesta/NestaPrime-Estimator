"""READ-ONLY preflight: which STORED mobile identifiers would the approved normalization rule refuse?

Amendment 61 (Section 64, Part A item 2) as corrected: country code 91, exactly ten national digits, the first 6-9, with
Unicode decimal digits validated by numeric value; letters and excluded punctuation refused. Before that rule is
activated, an account whose stored `users.mobile` the rule would refuse can no longer be found by typing that number,
and creating or editing the same value is refused. This script finds them -- as COUNTS ONLY.

What it does and does not do
  * Reads `users` inside a transaction set READ ONLY at the database level (any write would raise) and rolls it back.
  * Prints aggregate counts. It never prints a phone number, an id, a name or an email.
  * Does not rewrite anything, does not assume an email fallback exists (it reports how many affected accounts have
    NO email), and adds no legacy sign-in path.
  * Is meant to be run by an authorised person against a database they choose -- NOT run against production by the
    developer who wrote it. It uses the application's own `normalize_mobile`, so it applies exactly the rule that
    sign-in, create and edit will apply.

Run it standalone from a checkout of the pinned commit (this is the way to run it BEFORE the rule is activated; the
currently deployed image does not contain this script):
  1. Working directory: the `backend` directory of the checkout (the script puts it on sys.path itself). Settings also read
     a `.env` file in the working directory if one exists, so run it somewhere that has none you do not intend.
  2. Dependencies: Python 3.12 and `pip install -r requirements.txt` (run in a virtual environment).
  3. Configuration, as environment variables (the application's settings validation is unchanged and requires both):
       DATABASE_URL  SQLAlchemy URL of the database to inspect, e.g. postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
                     (use a read-only database role if one exists; the session is READ ONLY regardless)
       SECRET_KEY    ANY placeholder string. The script never signs or verifies a token, so do NOT copy the production
                     signing secret for this assessment.
     bash:        export DATABASE_URL='...'; export SECRET_KEY='preflight-placeholder-not-a-real-secret'
     PowerShell:  $env:DATABASE_URL='...'; $env:SECRET_KEY='preflight-placeholder-not-a-real-secret'
  4. Run:  python scripts/preflight_mobile_identifiers.py [--json]
Once an image built from a commit that contains this script is deployed, it can instead be run in the container, which
already has its own configuration (WORKDIR /app):
    docker compose -f docker-compose.prod.yml exec backend python scripts/preflight_mobile_identifiers.py [--json]
Exit status: 0 success; 2 configuration could not be loaded; 3 database could not be connected to or read; 4 the session
could not be cleanly closed. Every failure prints one fixed line and nothing else (no exception text, traceback, URL,
credential or identifier), and a failure never prints partial counts.

Categories (every non-null stored mobile falls into exactly one):
  valid_ascii                  accepted, and equal to what the normalizer would store
  valid_unicode_spelling       accepted by value; stored with non-ASCII digits, spelling retained (no change)
  stored_form_not_canonical    accepted, but the stored text differs from the normalized form (typing the number will not
                               match it; this predates the rule)
  refused_ascii_indian_rule    ASCII, fails the Indian mobile rule (e.g. +91 with a first digit 5, or the wrong length)
  refused_unicode_indian_rule  contains non-ASCII digits, fails the Indian mobile rule by value
  refused_ascii_other          ASCII, fails another rule (e.g. a foreign number too short or too long)
  refused_unicode_other        contains non-ASCII digits, fails another rule
  refused_invalid_content      contains a letter or another excluded character
"""

import argparse
import contextlib
import gc
import io
import json
import logging
import re
import sys
import warnings
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # the backend directory, so `app` imports work when run directly

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.core.identifiers import InvalidMobileNumber, normalize_mobile
from app.models.user import User

CATEGORIES = [
    "valid_ascii",
    "valid_unicode_spelling",
    "stored_form_not_canonical",
    "refused_ascii_indian_rule",
    "refused_unicode_indian_rule",
    "refused_ascii_other",
    "refused_unicode_other",
    "refused_invalid_content",
]
REFUSED = [c for c in CATEGORIES if c.startswith("refused_")]


def _legacy_accepts(raw: str) -> bool:
    """Would the normalizer as it was BEFORE the A61 corrections (17a67113) have accepted this text? (verbatim logic)"""
    stripped = re.sub(r"[^\d+]", "", raw.strip())
    if not stripped:
        return False
    indian = re.compile(r"^[6-9]\d{9}$")
    if stripped.startswith("+"):
        national = stripped[1:]
        if not national.isdigit() or not national:
            return False
        return (national.startswith("91") and len(national) == 12 and bool(indian.match(national[2:]))) or 8 <= len(national) <= 15
    return bool(
        (stripped.startswith("0") and indian.match(stripped[1:]))
        or (stripped.startswith("91") and len(stripped) == 12 and indian.match(stripped[2:]))
        or indian.match(stripped)
    )


def classify(stored: str) -> str:
    kind = "ascii" if stored.isascii() else "unicode"
    try:
        normalized = normalize_mobile(stored)
    except InvalidMobileNumber as exc:
        message = str(exc)
        if "may contain only digits" in message:
            return "refused_invalid_content"
        if "+91 number must be" in message or "10-digit Indian mobile" in message:
            return f"refused_{kind}_indian_rule"
        return f"refused_{kind}_other"
    if normalized != stored:
        return "stored_form_not_canonical"
    return "valid_ascii" if kind == "ascii" else "valid_unicode_spelling"


def run(db: Session) -> dict:
    """Aggregate counts only. The transaction is READ ONLY for its whole life and is rolled back."""
    try:
        db.execute(text("SET TRANSACTION READ ONLY"))  # must be the first statement of the transaction
        total_users = db.execute(select(func.count()).select_from(User)).scalar_one()
        rows = db.execute(select(User.mobile, User.is_active, User.email).where(User.mobile.is_not(None))).all()
        counts = Counter({c: 0 for c in CATEGORIES})
        refused = {"accounts": 0, "active": 0, "inactive": 0, "with_no_email": 0, "accepted_before_a61_corrections": 0}
        for mobile, is_active, email in rows:
            category = classify(mobile)
            counts[category] += 1
            if category in REFUSED:
                refused["accounts"] += 1
                refused["active" if is_active else "inactive"] += 1
                if not (email or "").strip():
                    refused["with_no_email"] += 1
                if _legacy_accepts(mobile):
                    refused["accepted_before_a61_corrections"] += 1
        return {
            "users_total": total_users,
            "users_with_mobile": len(rows),
            "by_category": {c: counts[c] for c in CATEGORIES},
            "refused_by_approved_rule": refused,
        }
    finally:
        db.rollback()  # ends the read-only transaction; nothing was or could be written


def render(result: dict) -> str:
    lines = [
        "A61 mobile-identifier preflight (READ ONLY; counts only; no phone numbers are printed)",
        f"users_total: {result['users_total']}",
        f"users_with_mobile: {result['users_with_mobile']}",
        "by_category:",
    ]
    lines += [f"  {name}: {count}" for name, count in result["by_category"].items()]
    lines.append("refused_by_approved_rule (accounts whose stored mobile the rule would refuse):")
    lines += [f"  {name}: {count}" for name, count in result["refused_by_approved_rule"].items()]
    lines.append("Affected accounts need a separately reviewed correction plan before the rule is activated.")
    return "\n".join(lines)


# Exit codes. Every failure prints ONE fixed line to stderr and nothing else: never an exception text, a traceback, a database
# URL, a credential or a user identifier (library errors routinely embed all of those).
EXIT_CONFIGURATION = 2
EXIT_ASSESSMENT = 3
EXIT_CLEANUP = 4
_MESSAGES = {
    EXIT_CONFIGURATION: (
        "Preflight failed: the application configuration could not be loaded. Run from the backend directory with the "
        "dependencies installed and DATABASE_URL and SECRET_KEY set (see the instructions at the top of this script). "
        "Details are withheld because they can contain connection settings."
    ),
    EXIT_ASSESSMENT: (
        "Preflight failed: the database could not be connected to or read. No results are reported. Check that "
        "DATABASE_URL points at the intended database and that it is reachable. Details are withheld because they can "
        "contain connection settings or data."
    ),
    EXIT_CLEANUP: (
        "Preflight failed: the read-only session cleanup failed (it could not be confirmed closed), so no results are reported. "
        "Re-run it. Details are withheld."
    ),
}


def _fail(code: int) -> int:
    print(_MESSAGES[code], file=sys.stderr)
    return code


class _Diagnostics:
    """How many error-level diagnostics the libraries emitted while contained. A COUNT only: no text is kept or written anywhere."""

    def __init__(self):
        self.count = 0


class _Discard(io.TextIOBase):
    def write(self, text):
        return len(text)


class _CountingHandler(logging.Handler):
    def __init__(self, diagnostics):
        super().__init__(level=logging.ERROR)
        self._diagnostics = diagnostics

    def emit(self, record):
        self._diagnostics.count += 1  # never formats or stores the record: it can carry URLs, credentials and identifiers


@contextlib.contextmanager
def _contained(diagnostics):
    """Library-generated diagnostics must not reach the terminal. SQLAlchemy reports a failed rollback or pool reset through
    `logging` with the full traceback, and with no handler configured Python's last-resort handler writes it to stderr, quoting
    whatever the driver put in the exception (URLs, passwords, identifiers). So for the whole run -- configuration import,
    assessment, session close, engine disposal and the garbage collection that runs finalizers -- this:
      * gives the root logger a handler, so the last-resort handler is never used; the handler only counts ERROR+ records;
      * drops warnings and "exception ignored" reports (counted), and discards anything else written to stderr.
    Local to this standalone command only: it changes no application logging or database behaviour, writes nothing anywhere, and
    is undone on exit. Native code writing directly to file descriptor 2 is outside what Python can contain (see the limits in
    the PR description)."""
    root = logging.getLogger()
    handler = _CountingHandler(diagnostics)
    root.addHandler(handler)
    previous_hook = sys.unraisablehook

    def count_unraisable(_args):
        diagnostics.count += 1

    sys.unraisablehook = count_unraisable
    try:
        with warnings.catch_warnings(), contextlib.redirect_stderr(_Discard()):
            warnings.simplefilter("ignore")
            yield
    finally:
        sys.unraisablehook = previous_hook
        root.removeHandler(handler)


def _assess(diagnostics):
    """Returns (exit_code_or_None, result). Runs inside _contained()."""
    try:
        # Imported here so importing this module never loads settings or opens a connection. A configuration error (for
        # example a missing SECRET_KEY) is raised by this import, and its text can quote the DATABASE_URL.
        from app.db.session import SessionLocal
    except Exception:
        return EXIT_CONFIGURATION, None

    db = None
    result = None
    assessment_failed = False
    try:
        db = SessionLocal()
        result = run(db)  # READ ONLY for its whole life; rolls back in its own `finally`
    except Exception:
        assessment_failed = True

    cleanup_failed = False
    if db is not None:
        try:
            db.close()
        except Exception:
            cleanup_failed = True
    # Release the pooled connections now, while contained, so a failure closing one is seen here and not at interpreter exit.
    kw = getattr(SessionLocal, "kw", None)
    bind = kw.get("bind") if isinstance(kw, dict) else None
    if bind is not None and hasattr(bind, "dispose"):
        try:
            bind.dispose()
        except Exception:
            cleanup_failed = True
    gc.collect()  # runs finalizers while still contained

    # A failed assessment is reported as such even if cleanup also failed. A successful read whose cleanup failed -- including a
    # failure the library only LOGGED (for example a pool reset) -- is NOT reported as success: its read-only transaction could not
    # be confirmed ended, and its counts are withheld. Containing the diagnostics must never turn an error into apparent success.
    if assessment_failed:
        return EXIT_ASSESSMENT, None
    if cleanup_failed or diagnostics.count:
        return EXIT_CLEANUP, None
    return None, result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only preflight of stored mobile identifiers (aggregate counts only).")
    parser.add_argument("--json", action="store_true", help="print the counts as JSON")
    args = parser.parse_args(argv)

    diagnostics = _Diagnostics()
    with _contained(diagnostics):
        code, result = _assess(diagnostics)
    if code is not None:
        return _fail(code)
    print(json.dumps(result, indent=2) if args.json else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
