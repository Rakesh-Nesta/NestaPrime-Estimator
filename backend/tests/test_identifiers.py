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
# A61 mobile-normalization (Section 64, Part A item 2) -- Director-approved input policies
#   POLICY 1 (Unicode): Unicode decimal digits are validated by NUMERIC VALUE. The Indian mobile rule -- country code 91,
#     exactly ten national digits, the first 6-9 -- holds across digit scripts, including Unicode spellings of the country
#     code. Validation uses a temporary digit-value form; the returned spelling and the lookup key are what they always were.
#   POLICY 2 (formatting): whitespace, hyphens/dashes, dots and parentheses are formatting; letters and other punctuation
#     (/ , # _ [ ] *) and invisible format characters (U+200B, U+200D, U+2060) are refused.
# The pre-correction function is kept below as `_legacy`: every difference from it is listed and intentional.
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


# ---- malformed ASCII +91 (required fix 1) ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "+915123456789", "+91987654321", "+91 98765 432101", "+9198765432100", "+9112345678901", "+91 6", "+91",
        "+91 (51234) 56789",
    ],
)
def test_a_malformed_ascii_plus_91_number_is_refused_not_accepted_as_a_generic_international_number(raw):
    with pytest.raises(InvalidMobileNumber, match="Indian mobile"):
        normalize_mobile(raw)


# ---- letters (required fix 2) ---------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw",
    [
        "abc9876543210xyz", "+91 98765 43210 ext", "98765 43210 ext", "9876543210x", "x9876543210", "+91 98765 4321O",
        "9876543210abc", "+14155550132x", "+1 415 555 0132 ext 5", "call 9876543210", "98765 4321अ",
    ],
)
def test_letters_are_refused_before_they_can_be_erased_into_an_accepted_number(raw):
    with pytest.raises(InvalidMobileNumber, match="digits"):
        normalize_mobile(raw)


# ---- POLICY 1: Unicode decimal digits are validated by numeric value -----------------------------------------------

# The Director's required examples.
REQUIRED_ACCEPTED = [("+91९876543210", "+91९876543210")]   # +91 then Devanagari 9: accepted, spelling retained
REQUIRED_REFUSED = [
    "+91512345678९",   # first national digit is 5
    "+9198765432९",    # nine national digits
    "+919876543210९",  # eleven national digits
]


@pytest.mark.parametrize("raw,expected", REQUIRED_ACCEPTED)
def test_required_example_a_valid_unicode_spelled_number_is_accepted_and_keeps_its_spelling(raw, expected):
    assert normalize_mobile(raw) == expected


@pytest.mark.parametrize("raw", REQUIRED_REFUSED)
def test_required_examples_malformed_numbers_containing_unicode_digits_are_refused(raw):
    assert _legacy(raw) != REFUSED                       # the legacy function accepted these: the change is intentional
    with pytest.raises(InvalidMobileNumber, match="Indian mobile"):
        normalize_mobile(raw)


# Invalid Indian numbers whose country code is spelled with Unicode digits must not bypass the rule.
UNICODE_COUNTRY_CODE_REFUSED = [
    "+９１5123456789",          # fullwidth 91, first national digit 5
    "+९१5123456789",          # Devanagari 91, first national digit 5
    "+९१ 98765 432101",       # Devanagari 91, eleven national digits
    "+９１98765432",            # fullwidth 91, eight national digits
    "+9१ 5123456789",              # a Latin 9 with a Devanagari 1: still the country code 91 by value
    "+९१",                    # a bare Unicode-spelled country code
]


@pytest.mark.parametrize("raw", UNICODE_COUNTRY_CODE_REFUSED)
def test_invalid_indian_numbers_with_a_unicode_spelled_country_code_are_refused(raw):
    with pytest.raises(InvalidMobileNumber, match="Indian mobile"):
        normalize_mobile(raw)


@pytest.mark.parametrize("raw", ["+91५123456789", "+9१५123456789"])
def test_a_unicode_digit_as_a_malformed_first_national_digit_is_refused(raw):
    with pytest.raises(InvalidMobileNumber, match="Indian mobile"):
        normalize_mobile(raw)


# Valid by value: the OUTPUT SPELLING is exactly what the legacy function produced (so lookup keys and stored values
# do not move), and these are the inputs the legacy function also accepted.
VALID_UNICODE_RETAINED = [
    ("+91९876543210", "+91९876543210"),
    ("+91 ९876543210", "+91९876543210"),
    ("9८76543210", "+919८76543210"),               # ASCII-leading national number with later Unicode digits
    ("+91 9८76543210", "+919८76543210"),
    ("+919८76543210", "+919८76543210"),
    ("+９１ 9876543210", "+９１9876543210"),  # fullwidth country code, valid national number: spelling kept
    ("+९१ 9876543210", "+९१9876543210"),  # Devanagari country code, valid national number
]


@pytest.mark.parametrize("raw,expected", VALID_UNICODE_RETAINED)
def test_valid_unicode_forms_keep_exactly_the_output_the_legacy_function_gave(raw, expected):
    assert _legacy(raw) == expected
    assert normalize_mobile(raw) == expected


# Valid by value that the legacy function REFUSED (a consequence of validating by value; new acceptances).
NEWLY_ACCEPTED_BY_VALUE = [
    ("९876543210", "+91९876543210"),         # a bare Indian number whose first digit is a Devanagari 9
    ("0९876543210", "+91९876543210"),        # with the optional leading 0
    ("９１ 9876543210", "+919876543210"),      # fullwidth 91 without a plus: the optional 91 prefix by value
]


@pytest.mark.parametrize("raw,expected", NEWLY_ACCEPTED_BY_VALUE)
def test_a_number_that_is_valid_by_value_is_accepted_even_where_the_legacy_function_refused_it(raw, expected):
    assert _legacy(raw) == REFUSED
    assert normalize_mobile(raw) == expected


# ---- POLICY 2: formatting ----------------------------------------------------------------------------------------------

BENIGN_FORMATTING = [
    "98765.43210", "(98765) 43210", "+91 (98765) 43210", "(+91) 98765-43210", "+91.98765.43210",
    "98765 43210", "+91 98765 43210", "98765 43210", "98765　43210", "98765\t43210",
    "98765‑43210", "98765‐43210", "98765–43210", "98765—43210",
    "98765-43210", "98765 43210", "  98765 43210  ",
]


@pytest.mark.parametrize("raw", BENIGN_FORMATTING)
def test_whitespace_dashes_dots_and_parentheses_are_formatting_and_give_the_legacy_result(raw):
    assert _legacy(raw) == "+919876543210"
    assert normalize_mobile(raw) == "+919876543210"


EXCLUDED_CHARACTERS = [
    ("/", "U+002F"), (",", "U+002C"), ("#", "U+0023"), ("_", "U+005F"), ("[", "U+005B"), ("]", "U+005D"), ("*", "U+002A"),
    ("​", "U+200B"), ("‍", "U+200D"), ("⁠", "U+2060"),
]


@pytest.mark.parametrize("ch,code", EXCLUDED_CHARACTERS, ids=[c for _, c in EXCLUDED_CHARACTERS])
def test_excluded_punctuation_and_invisible_format_characters_are_refused(ch, code):
    """Approved: letters and these characters are refused (the legacy function silently erased them)."""
    raw = f"98765{ch}43210"
    assert _legacy(raw) == "+919876543210"
    with pytest.raises(InvalidMobileNumber, match="digits"):
        normalize_mobile(raw)


# ---- the four approved inputs, existing valid variants and international controls --------------------------------------


@pytest.mark.parametrize("raw", ["98765 43210", "098765-43210", "+91 98765 43210", "91 9876543210"])
def test_the_four_approved_inputs_still_normalize_to_the_same_number(raw):
    assert normalize_mobile(raw) == "+919876543210"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+91-98765-43210", "+919876543210"),
        ("+ 91 98765 43210", "+919876543210"),
        ("0 98765 43210", "+919876543210"),
        ("919876543210", "+919876543210"),
        ("+1 415 555 0132", "+14155550132"),
        ("+44 7911 123456", "+447911123456"),
        ("+971 50 123 4567", "+971501234567"),
        ("+86 138 0013 8000", "+8613800138000"),
    ],
)
def test_valid_existing_variants_and_valid_international_numbers_still_work(raw, expected):
    assert normalize_mobile(raw) == expected
    assert _legacy(raw) == expected


@pytest.mark.parametrize("raw", ["+١ 415 555 0132", "+٤٤ 7911 123456"])
def test_a_valid_international_number_spelled_in_unicode_digits_keeps_its_spelling(raw):
    """Not India's code (1 and 44 by value): the generic 8-15 digit rule applies, spelling kept, as before."""
    assert normalize_mobile(raw) == _legacy(raw) != REFUSED


# ---- messages and the complete differential -----------------------------------------------------------------------


def test_the_refusal_messages_are_plain_and_say_what_to_fix():
    with pytest.raises(InvalidMobileNumber) as bad_91:
        normalize_mobile("+915123456789")
    assert "10-digit" in str(bad_91.value) and "6-9" in str(bad_91.value)
    with pytest.raises(InvalidMobileNumber) as bad_unicode_91:
        normalize_mobile("+91512345678९")
    assert str(bad_unicode_91.value) == str(bad_91.value)
    with pytest.raises(InvalidMobileNumber) as letters:
        normalize_mobile("abc9876543210xyz")
    assert "digits" in str(letters.value)
    with pytest.raises(InvalidMobileNumber, match="digits only after the"):
        normalize_mobile("+91+9876543210")


@pytest.mark.parametrize(
    "raw",
    BENIGN_FORMATTING + [r for r, _ in VALID_UNICODE_RETAINED]
    + ["9876543210", "919876543210", "+919876543210", "5876543210", "12345", "+123", "+1234567890123456", "+", "   ",
       "98765432100", "+١ 415 555 0132"],
)
def test_the_corrections_change_nothing_else_differential_against_the_legacy_function(raw):
    """Outside the listed intentional differences (letters; excluded punctuation; malformed Indian numbers incl. Unicode
    spellings; numbers valid by value that the legacy function refused) the result equals the legacy function's."""
    assert _current(raw) == _legacy(raw)
