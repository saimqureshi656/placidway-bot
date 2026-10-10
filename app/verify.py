"""Grounding checks. Keep this file small."""

from __future__ import annotations

import re

from app.normalize import extract_numbers
from app.templates import fallback, quote_url
from ingest.urls import ALLOWLIST

_URL = re.compile(r"https?://[^\s)>\"]+")
_RECOVERY_QUESTION = re.compile(r"\b(recovery|downtime|how long until normal)\b", re.IGNORECASE)
_DURATION = r"(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*(?:weeks?|days?|months?)"
_EXPLICIT_RECOVERY = re.compile(
    rf"\b(recovery time|recovery period|downtime)\b.{{0,80}}{_DURATION}|{_DURATION}.{{0,40}}\b(recovery time|recovery period|downtime)\b",
    re.IGNORECASE,
)
_SUCCESS_QUESTION = re.compile(r"\bsuccess rate\b", re.IGNORECASE)
_SURVIVAL_QUESTION = re.compile(r"\bsurvival\b", re.IGNORECASE)
_SIDE_EFFECT_QUESTION = re.compile(
    r"\bside effects?\b.{0,40}\b(?:duration|last|how long)\b|\bhow long\b.{0,40}\bside effects?\b",
    re.IGNORECASE,
)
_SUCCESS_STATED = re.compile(r"\bsuccess rate\b.{0,40}\d", re.IGNORECASE)
_SURVIVAL_STATED = re.compile(r"\bsurvival\b.{0,40}(?:\d|%|percent)", re.IGNORECASE)
_SIDE_EFFECT_STATED = re.compile(
    rf"\bside effects?\b.{{0,60}}{_DURATION}|{_DURATION}.{{0,40}}\bside effects?\b",
    re.IGNORECASE,
)
_CLINIC_PHRASE = re.compile(
    r"\b([A-Z][\w'&.®-]*(?:\s+[A-Z][\w'&.®-]*){0,6}\s+(?:Clinic|Center|Centre|Hospital))\b"
)


_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}


def source_numbers(chunks: list[dict], prices: list[dict]) -> set[int]:
    found: set[int] = set()
    for chunk in chunks:
        text = chunk.get("text") or ""
        found.update(extract_numbers(text))
        lowered = text.lower()
        for word, number in _NUMBER_WORDS.items():
            if re.search(rf"\b{word}\b", lowered):
                found.add(number)
    for record in prices:
        if record.get("price_low") is not None:
            found.add(int(record["price_low"]))
        if record.get("price_high") is not None:
            found.add(int(record["price_high"]))
        found.update(extract_numbers(record.get("raw_text") or ""))
    return found


def _chunk_text(chunks: list[dict]) -> str:
    return "\n".join(chunk.get("text") or "" for chunk in chunks)


def _window_has_duration(answer: str, label: str) -> bool:
    for match in re.finditer(rf"\b{label}\b([\s\S]{{0,80}})", answer, re.IGNORECASE):
        window = match.group(1)
        if "not listed" in window.lower():
            continue
        if re.search(_DURATION, window, re.IGNORECASE):
            return True
    return False


def unlisted_fact_reason(query: str, answer: str, chunks: list[dict]) -> str:
    """Reject inferred recovery, success, survival, or side-effect facts."""
    text = _chunk_text(chunks)
    lowered = answer.lower()
    if _RECOVERY_QUESTION.search(query) and not _EXPLICIT_RECOVERY.search(text):
        if "not listed" not in lowered:
            return "say that recovery time is not listed; program length is not recovery time"
        if _window_has_duration(answer, "recovery"):
            return "do not present the program length as the recovery time"
    if _SUCCESS_QUESTION.search(query) and not _SUCCESS_STATED.search(text):
        if "not listed" not in lowered:
            return "success rate is not listed; do not infer it"
        if _SUCCESS_STATED.search(answer):
            return "do not infer a success rate"
    if _SURVIVAL_QUESTION.search(query) and not _SURVIVAL_STATED.search(text):
        if "not listed" not in lowered:
            return "survival is not listed; do not infer it"
        if _SURVIVAL_STATED.search(answer):
            return "do not infer a survival figure"
    if _SIDE_EFFECT_QUESTION.search(query) and not _SIDE_EFFECT_STATED.search(text):
        if "not listed" not in lowered:
            return "side effect duration is not listed; do not infer it"
        if _window_has_duration(answer, "side effects") or _window_has_duration(answer, "side effect"):
            return "do not infer how long side effects last"
    if re.search(r"\brectal\b", query, re.IGNORECASE) and "not listed" not in lowered:
        return "rectal cancer is not listed"
    return ""


_CITATION = re.compile(r"\[(?:\s*P?\d+\s*(?:,\s*P?\d+\s*)*)\]", re.IGNORECASE)
_QUALIFIERS = ("starting from", "approximately", "range")
_DIACRITICS = re.compile(r"[\u064B-\u0652\u0670\u0640]")
_COST_QUESTION = re.compile(r"\b(how much|cost|price|priced)\b", re.IGNORECASE)
_COMPONENT_PRICE = re.compile(
    r"\b(lak|ambulance|intratumoral|specialist|blood|exclusion|excluded|optional|pint|price list|profile|average|ozone|stem health|difference)\b",
    re.IGNORECASE,
)
_QUALIFIER_ALIASES = {
    "starting from": (
        "starting from",
        "from",
        "desde",
        "a partir de",
        "comienza",
        "يبدأ من",
        "تبدأ من",
        "ابتداء من",
    ),
    "approximately": (
        "approximately",
        "about",
        "aproximadamente",
        "حوالي",
        "تقريبا",
    ),
    "range": ("range",),
}
_WEEK_WORDS = ("week", "semana", "اسبوع", "اسابيع")


def strip_citations(answer: str) -> str:
    return re.sub(r"[ \t]{2,}", " ", _CITATION.sub("", answer)).strip()


def _answer_has_amount(answer: str, amount: int) -> bool:
    return amount in extract_numbers(answer)


def _fold_qualifier(text: str) -> str:
    folded = _DIACRITICS.sub("", text.lower())
    folded = folded.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه")
    return re.sub(r"\s+", " ", folded)


def _has_qualifier(answer: str, qualifier: str) -> bool:
    folded = _fold_qualifier(answer)
    for phrase in _QUALIFIER_ALIASES.get(qualifier, (qualifier,)):
        token = _fold_qualifier(phrase)
        if re.search(rf"(?<!\w){re.escape(token)}(?!\w)", folded):
            return True
    return False


def missing_qualifier(answer: str, prices: list[dict]) -> str:
    for record in prices:
        amounts = []
        if record.get("price_low") is not None:
            amounts.append(int(record["price_low"]))
        if record.get("price_high") is not None:
            amounts.append(int(record["price_high"]))
        if not any(_answer_has_amount(answer, amount) for amount in amounts):
            continue
        qualifier = str(record.get("qualifier") or "").strip().lower()
        if qualifier in _QUALIFIERS and not _has_qualifier(answer, qualifier):
            return f"price must include the qualifier {qualifier}"
    return ""


def missing_program_prices(query: str, answer: str, prices: list[dict]) -> str:
    """A treatment cost question has to name every package program price."""
    if not _COST_QUESTION.search(query) or _COMPONENT_PRICE.search(query):
        return ""
    programs = [record for record in prices if record.get("category") == "package_program"]
    if not programs:
        return ""
    missing = []
    for record in programs:
        amount = int(record["price_low"])
        if not _answer_has_amount(answer, amount):
            missing.append(str(record.get("program") or amount))
    if missing:
        return "include every program price: " + ", ".join(missing)
    folded = _fold_qualifier(answer)
    for record in programs:
        duration = str(record.get("duration") or "").lower()
        if "week" in duration and not any(word in folded for word in _WEEK_WORDS):
            return f"include the program duration {record.get('duration')}"
        for number in extract_numbers(duration):
            if number not in extract_numbers(answer):
                return f"include the program duration {record.get('duration')}"
    return ""


def verify(
    draft: dict,
    chunks: list[dict],
    prices: list[dict],
    *,
    clinic_names: list[str] | None = None,
    query: str = "",
) -> tuple[bool, str]:
    status = str(draft.get("answer_status") or "")
    if status not in {"full", "partial", "not_listed"}:
        return False, "answer_status must be full, partial, or not_listed"
    answer = strip_citations(draft.get("answer") or "")
    draft["answer"] = answer
    if "couldn't find that" in answer.lower():
        return False, "answer refused even though passages were retrieved"
    ordered_ids = [chunk["chunk_id"] for chunk in chunks]
    chunk_ids = set(ordered_ids)

    def resolve(chunk_id: str) -> tuple[str, str] | None:
        token = str(chunk_id).strip().strip("[]")
        price_match = re.fullmatch(r"P(\d+)", token, re.IGNORECASE)
        if price_match:
            index = int(price_match.group(1)) - 1
            if 0 <= index < len(prices):
                return ("price", str(index))
            return None
        if token.isdigit():
            index = int(token) - 1
            if 0 <= index < len(ordered_ids):
                return ("chunk", ordered_ids[index])
        return None

    cited: set[str] = set()
    cited_prices: list[int] = []
    for claim in draft.get("claims") or []:
        resolved: list[str] = []
        for chunk_id in claim.get("chunk_ids") or []:
            mapped = resolve(chunk_id)
            if mapped is None:
                return False, f"invalid citation {chunk_id}"
            kind, value = mapped
            if kind == "chunk":
                resolved.append(value)
                cited.add(value)
            else:
                cited_prices.append(int(value))
        claim["chunk_ids"] = resolved
    draft["cited_price_indexes"] = cited_prices
    if status == "not_listed" and not cited:
        return False, "not_listed answer must cite chunk ids"
    allowed_numbers = source_numbers(chunks, prices)
    for number in extract_numbers(answer):
        if 1 <= number <= 12 and number in allowed_numbers:
            continue
        if number not in allowed_numbers:
            return False, f"number {number} is not in the retrieved chunks or price records"
    allowed_urls = set(ALLOWLIST) | {quote_url()}
    for url in _URL.findall(draft.get("answer") or ""):
        cleaned = url.rstrip(".,")
        if cleaned not in allowed_urls:
            return False, f"url not allowed: {cleaned}"
    known = {name.lower() for name in (clinic_names or []) if name}
    for match in _CLINIC_PHRASE.findall(draft.get("answer") or ""):
        if not any(match.lower() in name or name in match.lower() for name in known):
            return False, f"clinic not in the knowledge base: {match}"
    fact_reason = unlisted_fact_reason(query, answer, chunks)
    if fact_reason:
        return False, fact_reason
    qualifier_reason = missing_qualifier(answer, prices)
    if qualifier_reason:
        return False, qualifier_reason
    program_reason = missing_program_prices(query, answer, prices)
    if program_reason:
        return False, program_reason
    return True, ""


def format_price(record: dict) -> str:
    low = int(record["price_low"])
    high = int(record["price_high"])
    currency = record.get("currency") or "USD"
    if high != low:
        shown = f"${low:,}-{high:,} {currency}"
    else:
        shown = f"${low:,} {currency}"
    qualifier = str(record.get("qualifier") or "").strip()
    if qualifier and qualifier.lower() != "listed":
        shown += f" ({qualifier})"
    return shown


def add_related_facts(answer: str, chunks: list[dict]) -> str:
    """not_listed replies must name the related program length and follow-up when the pages have them."""
    blob = " ".join((chunk.get("text") or "") for chunk in chunks).lower()
    text = answer.strip()
    lowered = text.lower()
    if any(phrase in blob for phrase in ("3 week", "3 weeks", "three week", "three weeks")) and "week" not in lowered:
        text = f"{text} The listed program duration is 3 weeks."
        lowered = text.lower()
    if any(phrase in blob for phrase in ("3 month", "3 months", "three month", "three months")) and "month" not in lowered:
        text = f"{text} A follow-up consultation is listed after 3 months."
    if quote_url() not in text:
        text = f"{text} Request a free quote: {quote_url()}"
    return text.strip()


def _starting_record(prices: list[dict]) -> dict | None:
    answerable = [record for record in prices if record.get("answerable", True)]
    for record in answerable:
        if record.get("id") == "p_profile_starting":
            return record
    for record in answerable:
        if record.get("category") == "package_starting_from":
            return record
    return None


def _no_topic(user_numbers: list[str], prices: list[dict]) -> tuple[str, str]:
    record = _starting_record(prices)
    if record is None:
        return "I can't confirm that. That amount does not match any listed ITC package price.", ""
    source = record.get("url") or ""
    sentence = (
        f"I can't confirm that. That amount does not match any listed ITC package price. "
        f"The pages list {format_price(record)}."
    )
    if source:
        sentence += f" Source: {source}"
    return sentence, source


def _topic_records(prices: list[dict], treatment: str, clinic: str) -> list[dict]:
    answerable = [record for record in prices if record.get("answerable", True)]
    treatment_l = treatment.lower().strip()
    clinic_l = clinic.lower().strip()
    topic = []
    if treatment_l:
        topic = [
            record
            for record in answerable
            if treatment_l in str(record.get("treatment") or "").lower()
            or str(record.get("treatment") or "").lower() in treatment_l
        ]
        if clinic_l:
            narrowed = [
                record
                for record in topic
                if clinic_l in str(record.get("clinic") or "").lower()
                or str(record.get("clinic") or "").lower() in clinic_l
            ]
            if narrowed:
                topic = narrowed
        return topic
    if clinic_l:
        return [
            record
            for record in answerable
            if clinic_l in str(record.get("clinic") or "").lower()
            or str(record.get("clinic") or "").lower() in clinic_l
        ]
    return []


def premise_correction(
    user_numbers: list[str],
    prices: list[dict],
    treatment: str,
    clinic: str = "",
) -> tuple[str, str] | None:
    if not user_numbers:
        return None
    claimed = set(extract_numbers(" ".join(user_numbers)))
    if not claimed:
        return None
    topic = _topic_records(prices, treatment, clinic)
    if not treatment.strip() and not clinic.strip():
        return _no_topic(user_numbers, prices)
    if not topic:
        return _no_topic(user_numbers, prices)
    listed = {int(record["price_low"]) for record in topic} | {int(record["price_high"]) for record in topic}
    if claimed & listed:
        return None
    rank = {"package_starting_from": 0, "package_program": 1}
    record = sorted(topic, key=lambda item: rank.get(item.get("category"), 9))[0]
    name = treatment or record.get("treatment") or "this treatment"
    return (
        f"I can't confirm that. Our page lists {format_price(record)} for {name}.",
        record.get("url") or "",
    )


def premise_ok(answer: str, correction: str | None) -> bool:
    if not correction:
        return True
    return answer.startswith("I can't confirm that.")


def fallback_draft() -> dict:
    return {
        "answer": fallback(),
        "claims": [],
        "answer_status": "",
    }
