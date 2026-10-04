"""Pure helpers behind the quotation PDF's explicit rounding-adjustment row. M.6 rounds the TOTAL to the nearest Rs 10 (unchanged), but the Subtotal and GST
lines are printed to the rupee, so before this fix 'Subtotal + GST' differed from 'Total Project Cost' by a few rupees with
nothing explaining it. An explicit 'Rounding adjustment' row now reconciles them. Stored financial values are untouched.
"""
import pytest

from app.pdf_utils import format_signed_inr, rounding_adjustment, round_to_nearest_10


# --- pure helpers ---------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "subtotal,gst,total,expected",
    [
        (632911.39, 113924.05, 746835.44, 5),  # printed 632,911 + 113,924 = 746,835; total rounds to 746,840
        (156274.68, 28129.44, 184404.13, -4),  # printed 156,275 + 28,129 = 184,404; total rounds to 184,400
        (1075949.37, 193670.89, 1269620.25, 0),  # already reconciles
        (1000.6, 180.1, 1180.7, -1),  # printed 1,001 + 180 = 1,181; total rounds to 1,180
    ],
)
def test_rounding_adjustment_is_printed_total_minus_printed_lines(subtotal, gst, total, expected):
    printed_total = round_to_nearest_10(total)
    adj = rounding_adjustment(subtotal, gst, printed_total)
    assert adj == expected
    assert int(round(subtotal)) + int(round(gst)) + adj == int(printed_total)


def test_format_signed_inr():
    assert format_signed_inr(5) == "+Rs 5"
    assert format_signed_inr(-4) == "-Rs 4"
    assert format_signed_inr(0) == "Rs 0"


def test_nearest_ten_policy_is_unchanged():
    assert round_to_nearest_10(746835.44) == 746840
    assert round_to_nearest_10(184404.13) == 184400
    assert round_to_nearest_10(1235) == 1240
