"""Intent routing. Regex first, then an LLM JSON classifier if no rule matches."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.llm import LLMError, complete_json

INTENTS = (
    "greeting",
    "booking",
    "out_of_scope",
    "medical_advice",
    "lead",
    "price",
    "comparison",
    "info",
)

_GREETING = re.compile(r"^\s*(hi|hello|hey|good morning|good afternoon|good evening)\b", re.IGNORECASE)
_BOOKING = re.compile(r"\b(book(?:\s+me)?|appointment|schedule|reserve)\b", re.IGNORECASE)
_OUT_OF_SCOPE = re.compile(
    r"\b(weather|dental implants?|forecast|news|sports|recipe)\b",
    re.IGNORECASE,
)
_MEDICAL = re.compile(
    r"\b(safe for (?:me|my)|my (?:diabetes|condition)|should i|dosage|diagnos|is (?:it|this) safe)\b",
    re.IGNORECASE,
)
_LEAD = re.compile(r"\b(contact me|call me|email me|free quote|be contacted)\b", re.IGNORECASE)
_COMPARISON = re.compile(r"\b(cheaper|compare|comparison|versus|vs\.?)\b", re.IGNORECASE)
_PRICE = re.compile(r"\b(how much|cost|price|priced|\$)\b", re.IGNORECASE)
_MONEY = re.compile(
    r"(?:\$\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s*(?:usd|dollars))\b",
    re.IGNORECASE,
)


@dataclass
class Route:
    intent: str
    user_numbers: list[str] = field(default_factory=list)
    method: str = "rule"


def _numbers(message: str) -> list[str]:
    return [match.group(0) for match in _MONEY.finditer(message)]


def route_rules(message: str) -> Route | None:
    numbers = _numbers(message)
    text = message.strip()
    if _GREETING.match(text) and len(text.split()) <= 6:
        return Route("greeting", numbers)
    if _BOOKING.search(text):
        return Route("booking", numbers)
    if _MEDICAL.search(text):
        return Route("medical_advice", numbers)
    if _OUT_OF_SCOPE.search(text):
        return Route("out_of_scope", numbers)
    if _LEAD.search(text):
        return Route("lead", numbers)
    if _COMPARISON.search(text):
        return Route("comparison", numbers)
    if _PRICE.search(text):
        return Route("price", numbers)
    if numbers:
        return Route("price", numbers)
    return None


def route(message: str) -> Route:
    ruled = route_rules(message)
    if ruled is not None:
        return ruled
    try:
        parsed = complete_json(
            "Classify the user message. Reply JSON only: "
            '{"intent":"greeting|booking|out_of_scope|medical_advice|lead|price|comparison|info"}. '
            "info means a question about the ITC clinic, its packages, or listed comparisons.",
            message,
        )
        intent = str(parsed.get("intent") or "info")
        if intent not in INTENTS:
            intent = "info"
        return Route(intent, _numbers(message), method="llm")
    except (LLMError, ValueError, TypeError):
        return Route("info", _numbers(message), method="fallback")
