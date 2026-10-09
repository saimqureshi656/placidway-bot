"""Money and number normalization used by the verifier."""

from __future__ import annotations

import re

_DIGIT_MAP = str.maketrans(
    {
        "٠": "0",
        "١": "1",
        "٢": "2",
        "٣": "3",
        "٤": "4",
        "٥": "5",
        "٦": "6",
        "٧": "7",
        "٨": "8",
        "٩": "9",
        "۰": "0",
        "۱": "1",
        "۲": "2",
        "۳": "3",
        "۴": "4",
        "۵": "5",
        "۶": "6",
        "۷": "7",
        "۸": "8",
        "۹": "9",
        "٬": ",",
        "،": ",",
    }
)

_TOKEN = re.compile(
    r"(?:us\$|\$)\s?\d{1,3}(?:[.,]\d{3})+"
    r"|(?:us\$|\$)\s?\d+(?:\.\d+)?"
    r"|\d{1,3}(?:[.,]\d{3})+(?:\s*(?:usd|dollars))?"
    r"|\d+(?:\.\d+)?\s*(?:usd|dollars)"
    r"|\d+\s*k\b",
    re.IGNORECASE,
)


def fold_digits(text: str) -> str:
    return text.translate(_DIGIT_MAP)


def parse_amount(token: str) -> int | None:
    cleaned = fold_digits(token).lower().replace(" ", "")
    cleaned = cleaned.replace("us$", "").replace("$", "")
    cleaned = cleaned.replace("dollars", "").replace("usd", "")
    if cleaned.endswith("k") and cleaned[:-1].isdigit():
        return int(cleaned[:-1]) * 1000
    if re.fullmatch(r"\d{1,3}([.,]\d{3})+", cleaned):
        return int(re.sub(r"[.,]", "", cleaned))
    if re.fullmatch(r"\d+", cleaned):
        return int(cleaned)
    return None


def extract_numbers(text: str) -> list[int]:
    folded = fold_digits(text)
    numbers: list[int] = []
    covered: list[tuple[int, int]] = []
    for match in _TOKEN.finditer(folded):
        amount = parse_amount(match.group(0))
        if amount is None:
            continue
        numbers.append(amount)
        covered.append(match.span())
    for match in re.finditer(r"\d+", folded):
        if any(start <= match.start() < end for start, end in covered):
            continue
        numbers.append(int(match.group(0)))
    return numbers
