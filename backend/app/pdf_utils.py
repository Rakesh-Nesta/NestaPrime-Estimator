"""M.6: 'Rs with Indian grouping (Rs 12,50,000); totals rounded to
nearest Rs 10; the quotation total printed in words.' Pure, independently
testable helpers -- no reportlab/DB imports here."""

_ONES = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
    "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
    "Seventeen", "Eighteen", "Nineteen",
]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def round_to_nearest_10(amount: float) -> float:
    return round(amount / 10) * 10


def format_inr(amount: float) -> str:
    """1250000 -> 'Rs 12,50,000' (last 3 digits, then groups of 2)."""
    rounded = round(amount)
    sign = "-" if rounded < 0 else ""
    digits = str(abs(int(rounded)))
    if len(digits) <= 3:
        grouped = digits
    else:
        last3, rest = digits[-3:], digits[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        grouped = ",".join(groups) + "," + last3
    return f"{sign}Rs {grouped}"


def _two_digit_words(n: int) -> str:
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return _TENS[tens] + (f" {_ONES[ones]}" if ones else "")


def _three_digit_words(n: int) -> str:
    parts = []
    if n >= 100:
        parts.append(f"{_ONES[n // 100]} Hundred")
        n %= 100
    if n > 0:
        parts.append(_two_digit_words(n))
    return " ".join(parts)


def amount_in_words_inr(amount: float) -> str:
    """1250000 -> 'Twelve Lakh Fifty Thousand Rupees Only' (Indian
    crore/lakh/thousand grouping, not the international billion/million)."""
    n = int(round(amount))
    if n == 0:
        return "Zero Rupees Only"
    negative = n < 0
    n = abs(n)
    rupee_word = "Rupee" if n == 1 else "Rupees"

    crore, n = divmod(n, 10_000_000)
    lakh, n = divmod(n, 100_000)
    thousand, n = divmod(n, 1_000)
    rest = n

    parts = []
    if crore:
        parts.append(f"{_three_digit_words(crore)} Crore")
    if lakh:
        parts.append(f"{_three_digit_words(lakh)} Lakh")
    if thousand:
        parts.append(f"{_three_digit_words(thousand)} Thousand")
    if rest:
        parts.append(_three_digit_words(rest))

    return ("Minus " if negative else "") + " ".join(parts) + f" {rupee_word} Only"
