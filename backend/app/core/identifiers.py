"""Amendment 61 (Section 64): the one place a mobile number is parsed into its single canonical stored
form. `98765 43210`, `098765-43210`, `+91 98765 43210` and `91 9876543210` are all the same number and all
become `+919876543210`; a number from another country must be written with `+` and its country code.

Two rules keep a typo from being quietly turned into somebody else's number:
  * `+91` is India's country code and nobody else's, so a `+91` number must be a real Indian mobile number
    (exactly ten national digits, the first 6-9); it never falls through to "any international number";
  * only digits, a leading `+` and the two formatting characters the spec permits (space and hyphen) may be
    typed. Letters and every other character are refused, not erased -- `abc9876543210xyz` is not a number.

Unchanged and deliberately not decided here: what counts as a digit (`\\d`, so non-ASCII digits behave as they
always did) and any wider list of tolerated punctuation (dots, parentheses, a non-breaking space, an en dash) --
those are refused for now, with a plain message."""

import re

_INDIAN_MOBILE = re.compile(r"^[6-9]\d{9}$")
_ALLOWED_CONTENT = re.compile(r"[\d +\-]+")


class InvalidMobileNumber(ValueError):
    """Raised with a plain, user-facing message -- callers turn it into a 400/422, never a 500."""


def normalize_mobile(raw: str) -> str:
    text = raw.strip()
    if not text:
        raise InvalidMobileNumber("Enter a mobile number")
    if not _ALLOWED_CONTENT.fullmatch(text):
        raise InvalidMobileNumber("A mobile number may contain only digits, spaces, hyphens and a leading +")
    stripped = re.sub(r"[ \-]", "", text)

    if stripped.startswith("+"):
        national = stripped[1:]
        if not national.isdigit() or not national:
            raise InvalidMobileNumber("Enter a mobile number with digits only after the +")
        if national.startswith("91"):
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
