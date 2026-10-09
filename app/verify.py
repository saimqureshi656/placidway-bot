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
    if not draft.get("grounded", False):
        return False, "grounded is false"
    ordered_ids = [chunk["chunk_id"] for chunk in chunks]
    chunk_ids = set(ordered_ids)

    def resolve(chunk_id: str) -> str:
        if str(chunk_id).isdigit():
            index = int(chunk_id) - 1
            if 0 <= index < len(ordered_ids):
                return ordered_ids[index]
        return str(chunk_id)

    price_ids = {record["id"] for record in prices}
    cited: set[str] = set()
    for claim in draft.get("claims") or []:
        resolved = [resolve(chunk_id) for chunk_id in claim.get("chunk_ids") or []]
        claim["chunk_ids"] = resolved
        for chunk_id in resolved:
            if chunk_id not in chunk_ids:
                return False, f"unknown chunk id {chunk_id}"
            cited.add(chunk_id)
    for price_id in draft.get("used_price_ids") or []:
        if price_id not in price_ids:
            return False, f"unknown price id {price_id}"
    cited_chunks = [chunk for chunk in chunks if chunk["chunk_id"] in cited] or chunks
    used_prices = [record for record in prices if record["id"] in set(draft.get("used_price_ids") or [])]
    allowed_numbers = source_numbers(cited_chunks, used_prices or prices)
    for number in extract_numbers(draft.get("answer") or ""):
        if number not in allowed_numbers:
            return False, f"number {number} is not in the cited sources"
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


def premise_correction(user_numbers: list[str], prices: list[dict], treatment: str) -> str | None:
    if not user_numbers:
        return None
    claimed = set(extract_numbers(" ".join(user_numbers)))
    if not claimed:
        return None
    topic = [
        record
        for record in prices
        if record.get("answerable", True)
        and treatment
        and treatment.lower() in str(record.get("treatment") or "").lower()
    ]
    pool = topic or [record for record in prices if record.get("answerable", True)]
    listed = {int(record["price_low"]) for record in pool} | {int(record["price_high"]) for record in pool}
    if claimed & listed:
        return None
    if not pool:
        return None
    record = pool[0]
    amount = int(record["price_low"])
    shown = f"{amount:,}"
    if int(record["price_high"]) != amount:
        shown = f"{amount:,}-{int(record['price_high']):,}"
    qualifier = record.get("qualifier") or "listed"
    program = record.get("program") or record.get("duration") or "the listed program"
    name = treatment or record.get("treatment") or "this treatment"
    return (
        f"I can't confirm that. Our page lists {shown} {record.get('currency') or 'USD'} "
        f"({qualifier}, {program}) for {name}."
    )


def premise_ok(answer: str, correction: str | None) -> bool:
    if not correction:
        return True
    return answer.startswith("I can't confirm that.")


def fallback_draft() -> dict:
    return {
        "answer": fallback(),
        "claims": [],
        "used_price_ids": [],
        "grounded": False,
    }
