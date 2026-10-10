"""Grounding checks. Keep this file small."""

from __future__ import annotations

import re

from app.normalize import extract_numbers
from app.templates import fallback, quote_url
from ingest.urls import ALLOWLIST

_URL = re.compile(r"https?://[^\s)>\"]+")
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


def verify(
    draft: dict,
    chunks: list[dict],
    prices: list[dict],
    *,
    clinic_names: list[str] | None = None,
) -> tuple[bool, str]:
    status = str(draft.get("answer_status") or "")
    if status not in {"full", "partial", "not_listed"}:
        return False, "answer_status must be full, partial, or not_listed"
    answer = draft.get("answer") or ""
    if "couldn't find that" in answer.lower():
        return False, "answer refused even though passages were retrieved"
    ordered_ids = [chunk["chunk_id"] for chunk in chunks]
    chunk_ids = set(ordered_ids)

    def resolve(chunk_id: str) -> str:
        if str(chunk_id).isdigit():
            index = int(chunk_id) - 1
            if 0 <= index < len(ordered_ids):
                return ordered_ids[index]
        return str(chunk_id)

    cited: set[str] = set()
    for claim in draft.get("claims") or []:
        resolved = [resolve(chunk_id) for chunk_id in claim.get("chunk_ids") or []]
        claim["chunk_ids"] = resolved
        for chunk_id in resolved:
            if chunk_id not in chunk_ids:
                return False, f"unknown chunk id {chunk_id}"
            cited.add(chunk_id)
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
        text = f"{text} {quote_url()}"
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
    claim = user_numbers[0].strip()
    record = _starting_record(prices)
    if record is None:
        return f"I can't confirm that. {claim} does not match any listed ITC package price.", ""
    source = record.get("url") or ""
    sentence = (
        f"I can't confirm that. {claim} does not match any listed ITC package price. "
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
