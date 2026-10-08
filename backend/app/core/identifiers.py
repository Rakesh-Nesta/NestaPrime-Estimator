"""Amendment 61 (Section 64): the one place a mobile number is parsed into its single canonical stored
form. `98765 43210`, `098765-43210`, `+91 98765 43210` and `91 9876543210` are all the same number and all
become `+919876543210`; a number from another country must be written with `+` and its country code.

Two input policies, approved by the Director, govern what is accepted:

1. Unicode decimal digits are validated by NUMERIC VALUE. The Indian mobile rule -- country code 91, exactly ten
   national digits, the first 6-9 -- therefore holds across digit scripts, including a country code spelled in
   Unicode digits, so a malformed Indian number cannot pass as a "generic international" one by using such digits.
   Validation reads a temporary ASCII digit-value form; the RETURNED spelling is the typed one, exactly as before
   (`+91` + a Devanagari 9 + `876543210` stays as typed), so stored identifiers and lookup keys do not move and
   nothing is canonicalized or looked up under an alternative form.
2. Whitespace of any kind, hyphens and dashes, dots and parentheses are formatting and are dropped. Letters, other
   punctuation (`/ , # _ [ ] *` and the like) and invisible format characters (zero-width space/joiner, word
   joiner) are refused instead of being erased.

Section 64 item 2 itself says only "Anything else is refused with a plain message"; it lists no tolerated
separators, so the formatting rule above is the approved policy, not a quotation of the spec."""

import re
import unicodedata

_INDIAN_MOBILE = re.compile(r"[6-9][0-9]{9}")


class InvalidMobileNumber(ValueError):
    """Raised with a plain, user-facing message -- callers turn it into a 400/422, never a 500."""


def _is_formatting(ch: str) -> bool:
    """Spaces (any kind, e.g. a no-break space), hyphens/dashes (Unicode Pd, e.g. a non-breaking hyphen), dots, parentheses."""
    return ch.isspace() or ch in ".()" or unicodedata.category(ch) == "Pd"


def normalize_mobile(raw: str) -> str:
    kept: list[str] = []    # the digits and "+" as typed: the spelling that is returned
    values: list[str] = []  # the same, with every digit as its ASCII numeric value: used only to validate
    for ch in raw.strip():
        if ch == "+":
            kept.append(ch)
            values.append(ch)
        elif ch.isdecimal():  # the same set as the regex \d: Unicode category Nd
            kept.append(ch)
            values.append(str(unicodedata.decimal(ch)))
        elif not _is_formatting(ch):
            raise InvalidMobileNumber(
                "A mobile number may contain only digits and a leading +, with spaces or - . ( ) between them"
            )
    typed = "".join(kept)
    by_value = "".join(values)
    if not typed:
        raise InvalidMobileNumber("Enter a mobile number")

    if typed.startswith("+"):
        national, national_by_value = typed[1:], by_value[1:]
        if not national_by_value.isdigit() or not national_by_value:
            raise InvalidMobileNumber("Enter a mobile number with digits only after the +")
        if national_by_value.startswith("91"):
            # India's country code, however its digits are spelled, is never part of a generic international number.
            if len(national_by_value) == 12 and _INDIAN_MOBILE.fullmatch(national_by_value[2:]):
                return "+" + national
            raise InvalidMobileNumber("A +91 number must be a 10-digit Indian mobile number starting 6-9")
        if 8 <= len(national) <= 15:
            return "+" + national
        raise InvalidMobileNumber("A mobile number must have 8-15 digits after the country code")

    # No leading "+": an Indian mobile number, optionally prefixed with a plain "0" or "91" (by value).
    if by_value.startswith("0") and _INDIAN_MOBILE.fullmatch(by_value[1:]):
        return "+91" + typed[1:]
    if by_value.startswith("91") and len(by_value) == 12 and _INDIAN_MOBILE.fullmatch(by_value[2:]):
        return "+91" + typed[2:]
    if _INDIAN_MOBILE.fullmatch(by_value):
        return "+91" + typed
    raise InvalidMobileNumber(
        "Enter a 10-digit Indian mobile number starting 6-9, or a number with + and its country code"
    )
