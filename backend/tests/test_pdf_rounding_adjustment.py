"""The printed quotation totals must add up. M.6 rounds the TOTAL to the nearest Rs 10 (unchanged), but the Subtotal and GST
lines are printed to the rupee, so before this fix 'Subtotal + GST' differed from 'Total Project Cost' by a few rupees with
nothing explaining it. An explicit 'Rounding adjustment' row now reconciles them. Stored financial values are untouched.
"""
import re

import pytest

from app.pdf_utils import amount_in_words_inr, format_inr, round_to_nearest_10
from tests.test_pdf_documents import _director_headers, _pdf_text, _sent_quotation


def _rupees(token: str) -> int:
    sign = -1 if token.startswith("-") else 1
    return sign * int(re.sub(r"[^\d]", "", token))


def _printed_totals(text: str) -> dict:
    flat = re.sub(r"[ \t]*\n[ \t]*", " ", text)  # table cells may be extracted on separate lines
    money = r"([+-]?\s?Rs\s[\d,]+)"
    found = {
        "subtotal": re.search(r"Subtotal\s+" + money, flat),
        "gst": re.search(r"GST @ [\d.]+%\s+" + money, flat),
        "adjustment": re.search(r"Rounding adjustment[^R+-]*" + money, flat),
        "total": re.search(r"Total Project Cost\s+" + money, flat),
    }
    return {k: (_rupees(m.group(1).replace(" ", "")) if m else None) for k, m in found.items()}


# --- the printed PDF ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("cost,expected_adjustment", [(500000, 5), (123457, -4)])
def test_printed_pdf_arithmetic_adds_up_with_an_explicit_rounding_row(client, director_user, cost, expected_adjustment):
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers, cost_for_option=cost)
    res = client.get(f"/quotations/{quotation['id']}/pdf", headers=headers)
    assert res.status_code == 200
    text = _pdf_text(res)
    printed = _printed_totals(text)

    assert printed["adjustment"] == expected_adjustment
    # The printed lines reconcile to the printed total...
    assert printed["subtotal"] + printed["gst"] + printed["adjustment"] == printed["total"]
    # ...the total is the existing nearest-Rs-10 figure of the stored (unmodified) quotation_total...
    assert printed["total"] == int(round_to_nearest_10(quotation["quotation_total"]))
    assert printed["total"] % 10 == 0
    # ...and the amount in words states exactly that total.
    assert amount_in_words_inr(printed["total"]) in re.sub(r"\s+", " ", text)
    # Stored financial values are untouched by generating the document.
    again = client.get(f"/quotations/{quotation['id']}", headers=headers).json()
    for field in ("selling_after_discount", "gst_amount", "quotation_total"):
        assert again[field] == quotation[field]


def test_no_rounding_row_when_the_lines_already_reconcile(client, director_user):
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers, cost_for_option=850000)  # 1,075,949 + 193,671 = 1,269,620 exactly
    text = _pdf_text(client.get(f"/quotations/{quotation['id']}/pdf", headers=headers))
    printed = _printed_totals(text)
    assert printed["adjustment"] is None
    assert printed["subtotal"] + printed["gst"] == printed["total"]
    assert "Rounding adjustment" not in text


def test_rounding_row_never_contains_cost_or_margin(client, director_user):
    headers = _director_headers(client, director_user)
    quotation = _sent_quotation(client, headers, cost_for_option=500000)
    text = _pdf_text(client.get(f"/quotations/{quotation['id']}/pdf", headers=headers))
    assert format_inr(quotation["cost_total"]) not in text
    assert f"{quotation['margin_percent']:.2f}" not in text
