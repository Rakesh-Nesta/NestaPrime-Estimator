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
#   REQUIRED FIX 1. a malformed ASCII +91 number must not fall through to generic international acceptance;
#   REQUIRED FIX 2. letters must be refused, not silently erased into an accepted number.
# EVERYTHING ELSE is compared against the function as it was before these corrections (`_legacy`), which is the
# differential baseline for compatibility: benign formatting and Unicode-digit behaviour must not have changed.
# ---------------------------------------------------------------------------

import re as _re

_LEGACY_INDIAN_MOBILE = _re.compile(r"^[6-9]\d{9}$")
REFUSED = "REFUSED"


def _legacy(raw: str) -> str:
    """normalize_mobile exactly as it was at 17a67113 (before the A61 corrections), returning REFUSED instead of raising."""
    stripped = _re.sub(r"[^\d+]", "", raw.strip())
    if not stripped:
        return REFUSED
    if stripped.startswith("+"):
        national = stripped[1:]
        if not national.isdigit() or not national:
            return REFUSED
        if national.startswith("91") and len(national) == 12 and _LEGACY_INDIAN_MOBILE.match(national[2:]):
            return "+" + national
        if 8 <= len(national) <= 15:
            return "+" + national
        return REFUSED
    if stripped.startswith("0") and _LEGACY_INDIAN_MOBILE.match(stripped[1:]):
        return "+91" + stripped[1:]
    if stripped.startswith("91") and len(stripped) == 12 and _LEGACY_INDIAN_MOBILE.match(stripped[2:]):
        return "+91" + stripped[2:]
    if _LEGACY_INDIAN_MOBILE.match(stripped):
        return "+91" + stripped
    return REFUSED


def _current(raw: str) -> str:
    try:
        return normalize_mobile(raw)
    except InvalidMobileNumber:
        return REFUSED


# ---- required fix 1: malformed ASCII +91 --------------------------------------------------------------------------


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
        "+91 (51234) 56789",  # the same malformation with permitted formatting
    ],
)
def test_a_malformed_ascii_plus_91_number_is_refused_not_accepted_as_a_generic_international_number(raw):
    with pytest.raises(InvalidMobileNumber, match="Indian mobile"):
        normalize_mobile(raw)


# ---- required fix 2: letters ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "abc9876543210xyz", "+91 98765 43210 ext", "98765 43210 ext", "9876543210x", "x9876543210",
        "+91 98765 4321O",    # the letter O in place of a zero
        "9876543210abc",
        "+14155550132x",      # an otherwise valid international number with a stray letter
        "+1 415 555 0132 ext 5", "call 9876543210",
        "98765 4321अ",   # a non-Latin letter (Devanagari A)
    ],
)
def test_letters_are_refused_before_they_can_be_erased_into_an_accepted_number(raw):
    with pytest.raises(InvalidMobileNumber, match="digits"):
        normalize_mobile(raw)


# ---- compatibility: benign formatting is accepted exactly as before ---------------------------------------------------

BENIGN_FORMATTING = [
    "98765.43210", "(98765) 43210", "+91 (98765) 43210", "(+91) 98765-43210", "+91.98765.43210",     # dots, parentheses
    "98765 43210", "+91 98765 43210",                                                  # internal no-break space
    "98765 43210", "98765　43210", "98765\t43210",                                          # other space characters
    "98765‑43210", "98765‐43210", "98765–43210", "98765—43210",                   # non-breaking hyphen and dashes
    "98765-43210", "98765 43210", "  98765 43210  ",                                                  # approved spaces / hyphens
]


@pytest.mark.parametrize("raw", BENIGN_FORMATTING)
def test_benign_formatting_is_accepted_and_gives_the_same_result_as_before_the_corrections(raw):
    assert _legacy(raw) == "+919876543210"          # baseline: it was accepted
    assert normalize_mobile(raw) == "+919876543210"  # and still is, with the same stored value


@pytest.mark.parametrize("raw", ["98765 43210", "098765-43210", "+91 98765 43210", "91 9876543210"])
def test_the_four_approved_inputs_still_normalize_to_the_same_number(raw):
    assert normalize_mobile(raw) == "+919876543210"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+91-98765-43210", "+919876543210"),
        ("+ 91 98765 43210", "+919876543210"),          # existing tolerance: a space after the plus
        ("+1 415 555 0132", "+14155550132"),
        ("+44 7911 123456", "+447911123456"),
        ("+971 50 123 4567", "+971501234567"),
        ("+86 138 0013 8000", "+8613800138000"),
    ],
)
def test_valid_existing_variants_and_valid_international_numbers_still_work(raw, expected):
    assert normalize_mobile(raw) == expected
    assert _legacy(raw) == expected


# ---- compatibility: Unicode decimal digits behave exactly as before (policy NOT changed here) -------------------------

UNICODE_DIGIT_INPUTS = [
    "+91९876543210",         # +91 then Devanagari 9 as the first national digit
    "+91 ९876543210",
    "+91५123456789",         # +91 then Devanagari 5 (a malformed Indian number if read by digit value)
    "9८76543210",            # ASCII-leading national number with later Unicode digits
    "+91 9८76543210",
    "+919८76543210",
    "+９１ 9876543210",   # fullwidth country-code digits (a valid-looking 91 country code)
    "+９１5123456789",    # fullwidth country code + a malformed national number
    "９１ 9876543210",    # fullwidth 91 without a plus
]


@pytest.mark.parametrize("raw", UNICODE_DIGIT_INPUTS)
def test_unicode_digit_behaviour_is_identical_to_the_legacy_function(raw):
    """The standing instruction: leave the Unicode-digit policy alone. No canonicalization, no ASCII-only rejection. A `+91`
    number containing a non-ASCII digit therefore keeps its legacy outcome, so the malformed-+91 rule is enforced only for
    ASCII digits (see the proposed decision in the handoff). This test pins that: current == legacy for every input."""
    assert _current(raw) == _legacy(raw)


def test_a_previously_accepted_unicode_identifier_is_still_accepted_and_stored_as_written():
    assert normalize_mobile("+91९876543210") == "+91९876543210"
    assert normalize_mobile("+91 ९876543210") == "+91९876543210"


# ---- the formatting characters that are still refused (undecided; each one is named here) ---------------------------


@pytest.mark.parametrize("raw", ["98765/43210", "98765,43210", "98765#43210", "98765_43210", "[98765] 43210", "98765*43210"])
def test_other_symbols_are_refused_for_now(raw):
    """UNDECIDED, not source-supported either way: Section 64 item 2 says 'Anything else is refused with a plain message'
    but does not list which separators are tolerated. These were erased silently before; they are refused until a ruling.
    Tolerating them again means widening one set in identifiers.py and editing this test."""
    assert _legacy(raw) == "+919876543210"
    with pytest.raises(InvalidMobileNumber):
        normalize_mobile(raw)


@pytest.mark.parametrize("raw", ["98765​43210", "98765‍43210", "98765⁠43210"])
def test_zero_width_characters_are_refused_for_now(raw):
    """UNDECIDED: invisible format characters (zero-width space/joiner, word joiner) were erased silently before."""
    assert _legacy(raw) == "+919876543210"
    with pytest.raises(InvalidMobileNumber):
        normalize_mobile(raw)


# ---- refusal messages and the general differential ------------------------------------------------------------------


def test_the_refusal_messages_are_plain_and_say_what_to_fix():
    with pytest.raises(InvalidMobileNumber) as bad_91:
        normalize_mobile("+915123456789")
    assert "10-digit" in str(bad_91.value) and "6-9" in str(bad_91.value)
    with pytest.raises(InvalidMobileNumber) as letters:
        normalize_mobile("abc9876543210xyz")
    assert "digits" in str(letters.value)


@pytest.mark.parametrize(
    "raw",
    BENIGN_FORMATTING + UNICODE_DIGIT_INPUTS
    + ["9876543210", "919876543210", "+919876543210", "5876543210", "12345", "+123", "+1234567890123456", "+", "   ", "98765432100"],
)
def test_the_corrections_change_nothing_else_differential_against_the_legacy_function(raw):
    """Every input that is not a letter case, not a malformed ASCII +91 and not one of the named undecided symbols gives
    exactly the legacy result (a number or a refusal)."""
    assert _current(raw) == _legacy(raw)
