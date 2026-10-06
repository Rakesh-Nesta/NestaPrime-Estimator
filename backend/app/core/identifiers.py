"""Amendment 61 (Section 64): the one place a mobile number is parsed into its single canonical stored
form. `98765 43210`, `098765-43210`, `+91 98765 43210` and `91 9876543210` are all the same number and all
become `+919876543210`; a number from another country must be written with `+` and its country code.

Section 64 item 2 says "Anything else is refused with a plain message" and shows spaces and a hyphen in its
examples; it does not list which separators are tolerated. So this module makes two required corrections and
otherwise keeps what the function always did:
  * a malformed `+91` number is refused: with an ASCII `+91` the rest must be exactly ten digits, the first 6-9,
    instead of falling through to "any international number" (`+91` is India's country code and nobody else's);
  * a letter is refused instead of being erased (`abc9876543210xyz` is not a number).
Benign formatting is dropped exactly as before: spaces of any kind (including a no-break space), hyphens and
dashes (including a non-breaking hyphen), dots and parentheses. Any other character is refused, which is
stricter than before -- slashes, commas, brackets, symbols and invisible format characters used to be erased
silently -- and is an open decision, not a source-supported rule (see the tests that name each of them).

Unicode decimal digits are deliberately untouched: `\\d` and `str.isdecimal` accept them as they always did, the
stored form is whatever was typed, and the strict `+91` rule applies only when every digit is ASCII. A `+91`
number containing a non-ASCII digit therefore keeps its previous outcome until the Unicode-digit policy is
decided (canonicalize, refuse, or leave)."""

import re
import unicodedata

_INDIAN_MOBILE = re.compile(r"^[6-9]\d{9}$")


class InvalidMobileNumber(ValueError):
    """Raised with a plain, user-facing message -- callers turn it into a 400/422, never a 500."""


def _is_benign_separator(ch: str) -> bool:
    """Spaces (any kind, e.g. a no-break space), hyphens/dashes (Unicode Pd, e.g. a non-breaking hyphen), dots, parentheses."""
    return ch.isspace() or ch in ".()" or unicodedata.category(ch) == "Pd"


def normalize_mobile(raw: str) -> str:
    text = raw.strip()
    kept = []
    for ch in text:
        if ch.isdecimal() or ch == "+":  # isdecimal() is the same set as the regex \d: Unicode category Nd
            kept.append(ch)
        elif not _is_benign_separator(ch):
            raise InvalidMobileNumber(
                "A mobile number may contain only digits and a leading +, with spaces or - . ( ) between them"
            )
    stripped = "".join(kept)
    if not stripped:
        raise InvalidMobileNumber("Enter a mobile number")

    if stripped.startswith("+"):
        national = stripped[1:]
        if not national.isdigit() or not national:
            raise InvalidMobileNumber("Enter a mobile number with digits only after the +")
        if national.startswith("91") and national.isascii():
            # India's country code is never part of a generic international number: it must be a valid Indian mobile.
            if len(national) == 12 and _INDIAN_MOBILE.match(national[2:]):
                return "+" + national
            raise InvalidMobileNumber("A +91 number must be a 10-digit Indian mobile number starting 6-9")
        if 8 <= len(national) <= 15:
            return "+" + national
        raise InvalidMobileNumber("A mobile number must have 8-15 digits after the country code")

    # No leading "+": an Indian mobile number, optionally prefixed with a plain "0" or "91".
    if stripped.startswith("0") and _INDIAN_MOBILE.match(stripped[1:]):
        return "+91" + stripped[1:]
    if stripped.startswith("91") and len(stripped) == 12 and _INDIAN_MOBILE.match(stripped[2:]):
        return "+91" + stripped[2:]
    if _INDIAN_MOBILE.match(stripped):
        return "+91" + stripped
    raise InvalidMobileNumber(
        "Enter a 10-digit Indian mobile number starting 6-9, or a number with + and its country code"
    )
