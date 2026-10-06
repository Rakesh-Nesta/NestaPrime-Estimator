"""Amendment 61 (Section 64) item 2: one canonical stored form for a mobile number."""

import pytest

from app.core.identifiers import InvalidMobileNumber, normalize_mobile


@pytest.mark.parametrize(
    "raw",
    ["9876543210", "98765 43210", "098765-43210", "0 98765 43210", "919876543210", "91 9876543210",
     "+919876543210", "+91 98765 43210", "+91-98765-43210"],
)
def test_every_common_way_of_writing_the_same_indian_number_normalizes_identically(raw):
    assert normalize_mobile(raw) == "+919876543210"


def test_a_foreign_number_is_accepted_with_a_plus_and_country_code():
    assert normalize_mobile("+1 415 555 0132") == "+14155550132"


@pytest.mark.parametrize("raw", ["12345", "5876543210", "98765432100", "987654321", "abcdefghij"])
def test_something_that_is_not_a_valid_indian_number_is_refused(raw):
    with pytest.raises(InvalidMobileNumber):
        normalize_mobile(raw)


def test_a_foreign_number_that_is_too_short_is_refused():
    with pytest.raises(InvalidMobileNumber):
        normalize_mobile("+123")


def test_a_foreign_number_that_is_too_long_is_refused():
    with pytest.raises(InvalidMobileNumber):
        normalize_mobile("+1234567890123456")


def test_a_plus_with_no_digits_is_refused():
    with pytest.raises(InvalidMobileNumber):
        normalize_mobile("+")


def test_blank_is_refused():
    with pytest.raises(InvalidMobileNumber):
        normalize_mobile("   ")


# ---------------------------------------------------------------------------
# A61 mobile-normalization corrections (Section 64, Part A item 2)
#   1. a malformed +91 number must not fall through to generic international acceptance;
#   2. letters and other stray content must be refused, not silently erased into an accepted number.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "+915123456789",      # +91 then a national number starting 5 (not 6-9)
        "+91987654321",       # nine national digits
        "+91 98765 432101",   # eleven national digits (overlength)
        "+9198765432100",     # twelve national digits
        "+9112345678901",     # thirteen national digits, 91-prefixed: India's code is never a generic number
        "+91 6",              # far too short
        "+91",                # a bare country code
    ],
)
def test_a_malformed_plus_91_number_is_refused_not_accepted_as_a_generic_international_number(raw):
    with pytest.raises(InvalidMobileNumber, match="Indian mobile"):
        normalize_mobile(raw)


@pytest.mark.parametrize(
    "raw",
    [
        "abc9876543210xyz",
        "+91 98765 43210 ext",
        "98765 43210 ext",
        "9876543210x",
        "x9876543210",
        "+91 98765 4321O",    # the letter O in place of a zero
        "9876543210abc",
        "+14155550132x",      # an otherwise valid international number with a stray letter
        "+1 415 555 0132 ext 5",
        "call 9876543210",
    ],
)
def test_letters_are_refused_before_they_can_be_erased_into_an_accepted_number(raw):
    with pytest.raises(InvalidMobileNumber, match="digits, spaces, hyphens"):
        normalize_mobile(raw)


@pytest.mark.parametrize("raw", ["98765.43210", "(98765) 43210", "98765/43210", "98765,43210", "98765#43210", "98765_43210"])
def test_other_stray_characters_are_refused_too(raw):
    with pytest.raises(InvalidMobileNumber, match="digits, spaces, hyphens"):
        normalize_mobile(raw)


@pytest.mark.parametrize("raw", ["98765 43210", "98765–43210", "98765‑43210", "98765​43210"])
def test_policy_dependent_unicode_spacing_and_dashes_are_refused_for_now(raw):
    """NOT a settled policy: a non-breaking space, en dash, non-breaking hyphen or zero-width space (as pasted from a PDF or a
    chat) used to be erased silently. The approved spec permits spaces and hyphens only; until the Director rules otherwise
    these are refused with a plain message. Changing the policy means changing this one test and the allowed set."""
    with pytest.raises(InvalidMobileNumber):
        normalize_mobile(raw)


@pytest.mark.parametrize(
    "raw",
    ["98765 43210", "098765-43210", "+91 98765 43210", "91 9876543210"],
)
def test_the_four_approved_inputs_still_normalize_to_the_same_number(raw):
    assert normalize_mobile(raw) == "+919876543210"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+91-98765-43210", "+919876543210"),
        ("+ 91 98765 43210", "+919876543210"),          # existing tolerance: a space after the plus
        ("  98765 43210  ", "+919876543210"),           # surrounding whitespace is trimmed, as before
        ("+1 415 555 0132", "+14155550132"),
        ("+44 7911 123456", "+447911123456"),
        ("+971 50 123 4567", "+971501234567"),
        ("+86 138 0013 8000", "+8613800138000"),
    ],
)
def test_valid_existing_variants_and_valid_international_numbers_still_work(raw, expected):
    assert normalize_mobile(raw) == expected


def test_the_refusal_messages_are_plain_and_say_what_to_fix():
    with pytest.raises(InvalidMobileNumber) as bad_91:
        normalize_mobile("+915123456789")
    assert "10-digit" in str(bad_91.value) and "6-9" in str(bad_91.value)
    with pytest.raises(InvalidMobileNumber) as letters:
        normalize_mobile("abc9876543210xyz")
    assert "digits, spaces, hyphens" in str(letters.value)
