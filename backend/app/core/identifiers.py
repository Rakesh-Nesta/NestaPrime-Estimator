"""Amendment 61 (Section 64): the one place a mobile number is parsed into its single canonical stored
form. `98765 43210`, `098765-43210`, `+91 98765 43210` and `91 9876543210` are all the same number and all
become `+919876543210`; a number from another country must be written with `+` and its country code."""

import re

_INDIAN_MOBILE = re.compile(r"^[6-9]\d{9}$")


class InvalidMobileNumber(ValueError):
    """Raised with a plain, user-facing message -- callers turn it into a 400/422, never a 500."""


def normalize_mobile(raw: str) -> str:
    stripped = re.sub(r"[^\d+]", "", raw.strip())
    if not stripped:
        raise InvalidMobileNumber("Enter a mobile number")

    if stripped.startswith("+"):
        national = stripped[1:]
        if not national.isdigit() or not national:
            raise InvalidMobileNumber("Enter a mobile number with digits only after the +")
        if national.startswith("91") and len(national) == 12 and _INDIAN_MOBILE.match(national[2:]):
            return "+" + national
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
