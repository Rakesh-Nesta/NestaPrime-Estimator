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

Run, from the backend directory with DATABASE_URL pointing at the database to inspect:
    python scripts/preflight_mobile_identifiers.py [--json]
or, in the deployed container, the way the repository's other scripts are run:
    docker compose exec -e PYTHONPATH=/app backend python scripts/preflight_mobile_identifiers.py [--json]

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
import json
import re
import sys
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
    db.execute(text("SET TRANSACTION READ ONLY"))  # must be the first statement of the transaction
    try:
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Read-only preflight of stored mobile identifiers (aggregate counts only).")
    parser.add_argument("--json", action="store_true", help="print the counts as JSON")
    args = parser.parse_args(argv)
    from app.db.session import SessionLocal  # imported here so importing this module never opens a connection

    db = SessionLocal()
    try:
        result = run(db)
    finally:
        db.close()
    print(json.dumps(result, indent=2) if args.json else render(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
