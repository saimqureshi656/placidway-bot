"""Intent routing. Regex first, then an LLM JSON classifier if no rule matches."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.llm import LLMError, complete_router_json

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
    r"\b(safe for (?:me|my)|my (?:diabetes|condition)|should i|dosage|diagnos|is (?:it|this) safe|cure|will it work|success rate|survival|is it effective)\b",
    re.IGNORECASE,
)
_LEAD = re.compile(r"\b(contact me|call me|email me|free quote|be contacted)\b", re.IGNORECASE)
_COMPARISON = re.compile(r"\b(cheaper|compare|comparison|versus|vs\.?)\b", re.IGNORECASE)
_PRICE = re.compile(r"\b(how much|cost|price|priced|\$)\b", re.IGNORECASE)
_INFO = re.compile(
    r"\b(included|include|recovery|itinerary|follow-?up|address|what is|how does|when is)\b",
    re.IGNORECASE,
)
_MONEY = re.compile(
    r"(?:\$\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s*(?:usd|dollars))\b",
    re.IGNORECASE,
)
_FOLLOWUP = re.compile(r"^\s*(and\b|what about|how about|also\b)\b", re.IGNORECASE)
_ARABIC = re.compile(r"[\u0600-\u06FF]")
_SPANISH = re.compile(r"[¿¡]|\b(cuánto|cuesta|tratamiento|incluye)\b", re.IGNORECASE)

_COMBINED = """Rewrite the latest user message into one standalone English search query and classify it.
Use the history so a follow-up keeps the treatment, clinic, and country.
Do not think. Reply with JSON only, no markdown:
{"intent":"greeting|booking|out_of_scope|medical_advice|lead|price|comparison|info","standalone_query_en":"","language":"en","entities":{"treatment":"","country":"","program":""},"is_followup":false,"user_numbers":[]}
info means a question about the ITC clinic, its packages, or listed comparisons.
medical_advice includes cure, whether it will work, success rate, survival, and whether it is effective.
language is the language of the latest message.
user_numbers lists money amounts the user stated, such as "$50".
"What about recovery time?" after adenocarcinoma asks about recovery time after that adenocarcinoma program.
"What about in Turkey?" keeps the prior treatment and changes the country.
"""

_SAFETY = ("medical_advice", "booking", "out_of_scope")


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
    if _INFO.search(text):
        return Route("info", numbers)
    if numbers:
        return Route("price", numbers)
    return None


def _blank_rewrite(message: str, *, followup: bool) -> dict:
    language = "en"
    if _ARABIC.search(message):
        language = "ar"
    elif _SPANISH.search(message):
        language = "es"
    return {
        "standalone_query_en": message,
        "language": language,
        "entities": {"treatment": "", "clinic": "", "country": "", "program": ""},
        "is_followup": followup,
        "intent": "info",
    }


def is_followup(message: str, history: list[dict] | None) -> bool:
    if not history:
        return False
    text = message.strip()
    if _FOLLOWUP.search(text):
        return True
    return len(text.split()) <= 8


def _history_text(history: list[dict]) -> str:
    return "\n".join(f"{turn.get('role', 'user')}: {turn.get('content', '')}" for turn in history[-6:])


def choose_intent(rule_intent: str | None, llm_intent: str) -> str:
    """Agree when both say the same thing. Otherwise the safest template intent wins."""
    if rule_intent and rule_intent == llm_intent:
        return llm_intent
    present = [intent for intent in _SAFETY if intent in {rule_intent, llm_intent}]
    if present:
        return present[0]
    if llm_intent in INTENTS:
        return llm_intent
    return rule_intent or "info"


def _user_numbers(parsed: dict, message: str) -> list[str]:
    raw = parsed.get("user_numbers")
    numbers = [str(item) for item in raw if str(item).strip()] if isinstance(raw, list) else []
    for found in _numbers(message):
        if found not in numbers:
            numbers.append(found)
    return numbers


def _from_llm(parsed: dict, message: str) -> dict:
    entities = parsed.get("entities") if isinstance(parsed.get("entities"), dict) else {}
    standalone = str(parsed.get("standalone_query_en") or "").strip() or message
    intent = str(parsed.get("intent") or "info")
    if intent not in INTENTS:
        intent = "info"
    return {
        "standalone_query_en": standalone,
        "language": str(parsed.get("language") or "en"),
        "entities": {
            "treatment": str(entities.get("treatment") or ""),
            "clinic": str(entities.get("clinic") or ""),
            "country": str(entities.get("country") or ""),
            "program": str(entities.get("program") or ""),
        },
        "is_followup": bool(parsed.get("is_followup")),
        "intent": intent,
    }


def resolve(message: str, history: list[dict] | None = None) -> tuple[Route, dict]:
    """Always rewrite and classify in one call, then apply template rules."""
    history = history or []
    parsed = complete_router_json(
        _COMBINED,
        f"History:\n{_history_text(history)}\n\nLatest:\n{message}",
    )
    rewritten = _from_llm(parsed, message)
    rewritten["is_followup"] = bool(rewritten["is_followup"] or is_followup(message, history))
    ruled = route_rules(message)
    intent = choose_intent(ruled.intent if ruled else None, rewritten["intent"])
    method = "agree" if ruled and ruled.intent == intent else "llm"
    return Route(intent, _user_numbers(parsed, message), method=method), rewritten


def route(message: str) -> Route:
    ruled = route_rules(message)
    if ruled is not None:
        return ruled
    return Route("info", _numbers(message), method="fallback")
