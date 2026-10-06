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
