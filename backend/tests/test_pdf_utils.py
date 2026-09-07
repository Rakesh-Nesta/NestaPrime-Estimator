from app.pdf_utils import amount_in_words_inr, format_inr, round_to_nearest_10


def test_format_inr_indian_grouping():
    assert format_inr(1_250_000) == "Rs 12,50,000"
    assert format_inr(850_000) == "Rs 8,50,000"
    assert format_inr(999) == "Rs 999"
    assert format_inr(1000) == "Rs 1,000"
    assert format_inr(12_345_678) == "Rs 1,23,45,678"


def test_format_inr_rounds_to_nearest_rupee():
    assert format_inr(1234.6) == "Rs 1,235"


def test_format_inr_negative():
    assert format_inr(-500) == "-Rs 500"


def test_round_to_nearest_10():
    assert round_to_nearest_10(1234.6) == 1230
    assert round_to_nearest_10(1235) == 1240
    assert round_to_nearest_10(1237) == 1240


def test_amount_in_words_basic_cases():
    assert amount_in_words_inr(0) == "Zero Rupees Only"
    assert amount_in_words_inr(1) == "One Rupee Only"
    assert amount_in_words_inr(100) == "One Hundred Rupees Only"
    assert amount_in_words_inr(1_000_000) == "Ten Lakh Rupees Only"


def test_amount_in_words_matches_m6_style_example():
    assert amount_in_words_inr(1_250_000) == "Twelve Lakh Fifty Thousand Rupees Only"


def test_amount_in_words_crore():
    assert amount_in_words_inr(12_345_678) == "One Crore Twenty Three Lakh Forty Five Thousand Six Hundred Seventy Eight Rupees Only"


def test_amount_in_words_negative():
    assert amount_in_words_inr(-500) == "Minus Five Hundred Rupees Only"
