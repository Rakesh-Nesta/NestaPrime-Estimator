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
