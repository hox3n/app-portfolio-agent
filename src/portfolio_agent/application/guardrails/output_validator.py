"""Checks that every number quoted in a text appears in the structured data behind it."""

import math
import re
from typing import Any

_MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"
_DATE = re.compile(
    rf"\b\d{{4}}-\d{{2}}-\d{{2}}\b|\b{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?\b|"
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+{_MONTH}",
    re.IGNORECASE,
)
_RANK = re.compile(r"\b(?:top|first|last|largest|biggest)\s+\d+\b", re.IGNORECASE)
_NUMBER = re.compile(r"(?<![\w.])-?\$?\d[\d,]*(?:\.\d+)?(?:[kKmM]\b)?%?")
_SCALE = {"k": 1_000, "m": 1_000_000}
_WORDS = {
    word: str(n)
    for n, word in enumerate(
        [
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
            "thirteen",
            "fourteen",
            "fifteen",
            "sixteen",
            "seventeen",
            "eighteen",
            "nineteen",
            "twenty",
        ]
    )
}
_WORD = re.compile(rf"\b({'|'.join(_WORDS)})\b", re.IGNORECASE)
SAMPLE_PREFIX = "top_"


def numbers_in(data: Any) -> list[float]:
    found: list[float] = []

    def walk(value: Any, key: str = "") -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, int | float):
            found.append(float(value))
        elif isinstance(value, dict):
            for k, item in value.items():
                walk(item, str(k))
        elif isinstance(value, list | tuple):
            # "top_" lists show only the largest items, so their length is not a fact.
            if not key.startswith(SAMPLE_PREFIX):
                found.append(float(len(value)))
            for item in value:
                walk(item)

    walk(data)
    return found


def _prepare(text: str) -> str:
    text = _RANK.sub(" ", _DATE.sub(" ", text))
    return _WORD.sub(lambda m: _WORDS[m.group(1).lower()], text)


def unsupported_numbers(text: str, data: Any) -> list[str]:
    values = numbers_in(data)
    unsupported: list[str] = []
    for token in _NUMBER.findall(_prepare(text)):
        raw = token.replace("$", "").replace(",", "").replace("%", "")
        scale = _SCALE.get(raw[-1].lower(), 1) if raw[-1].isalpha() else 1
        raw = raw.rstrip("kKmM")
        try:
            number = abs(float(raw)) * scale
        except ValueError:
            continue
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        if scale == 1 and decimals == 0 and (number <= 1 or 1900 <= number <= 2100):
            continue
        if not any(_matches(v, number, decimals, scale) for v in values):
            unsupported.append(token)
    return unsupported


def _matches(value: float, number: float, decimals: int, scale: float) -> bool:
    factor = 10**decimals / scale
    target = round(number * factor)
    for candidate in (abs(value), abs(value) * 100):
        shown = candidate * factor
        # The quoted figure must be the true value rounded or truncated at the shown precision.
        if target in (math.floor(shown + 1e-9), math.floor(shown + 0.5)):
            return True
    return False
