"""Amendment 22 (Section 28): Master Settings and Overrides store their
value as a plain string (some Settings are legitimately non-numeric --
company details, T&C text -- so the column can't be numeric-typed at
the schema level). Every call site that parses one numerically used a
bare float()/int(), which raised an opaque, undiagnosable ValueError
-> 500 the moment a bad value (a typo, a stale row) was actually used.

This wraps that parse so the failure names exactly which setting is
broken, at the point of use -- the earliest point a numeric type can
actually be known, since Settings/Overrides have no registry of which
keys are expected to be numeric."""

from fastapi import HTTPException


def parse_setting_number(key: str, value: str, kind: type[float] | type[int]):
    try:
        return kind(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Setting '{key}' has a non-numeric value ('{value}') and cannot be used here",
        ) from exc
