"""Grounding checks. Keep this file small."""

from __future__ import annotations

import re

from app.normalize import extract_money, extract_numbers
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
        "approximate",
        "approx",
        "about",
        "aproximadamente",
        "حوالي",
        "تقريبا",
    ),
    "range": ("range",),
}
_WEEK_WORDS = ("week", "semana", "اسبوع", "اسابيع")


def tidy_spacing(text: str) -> str:
    text = re.sub(r"[ \t]{2,}", " ", text)
    return re.sub(r"[ \t]+([.,;:!?؟،])(?=\s|$)", r"\1", text).strip()


def strip_citations(answer: str) -> str:
    return tidy_spacing(_CITATION.sub("", answer))


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


# Entity-price binding. A price belongs to the treatment or program it is written next to.
# It must come from a price record for that entity, or from one passage line that names
# the entity and the amount together.
TREATMENT_TERMS = (
    "adenocarcinoma",
    "adrenal",
    "anal",
    "appendix",
    "rectal",
    "colorectal",
    "colon",
    "breast",
    "prostate",
    "lung",
    "pancreatic",
    "ovarian",
    "cervical",
    "liver",
    "kidney",
    "leukemia",
    "lymphoma",
    "melanoma",
    "skin",
    "brain",
    "stomach",
    "esophageal",
    "sarcoma",
    "bone",
    "bladder",
    "ozone",
    "acupuncture",
    "panchakarma",
    "stem cell",
    "live cell",
    "naturopathic",
)
_NON_CANCER = {"ozone", "acupuncture", "panchakarma", "stem cell", "live cell", "naturopathic"}
PROGRAM_TERMS = {"In-Patient Program": r"\bin[- ]?patient\b", "Out-Patient Program": r"\bout[- ]?patient\b"}
_PROGRAM_MENTION = re.compile(r"\b(?:in|out)[- ]?patient\b", re.IGNORECASE)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?؟])\s+|\n+")
COMPOSITE_QUESTION = re.compile(r"\bplus\b|\s\+\s|\bcombined\b|\baltogether\b|\badd(?:s|ed)? up\b", re.IGNORECASE)
_VAGUE_MISSING = re.compile(
    r"\bdo(?:es)? not (?:list|state|mention|specify)\b|\bnot (?:mentioned|specified|stated)\b|\bno mention\b",
    re.IGNORECASE,
)
NOT_LISTED = re.compile(r"\b(?:not listed|isn't listed|aren't listed|is not listed|are not listed)\b", re.IGNORECASE)


def terms_in(text: str) -> list[str]:
    lowered = text.lower()
    return [term for term in TREATMENT_TERMS if re.search(rf"\b{re.escape(term)}\b", lowered)]


def programs_in(text: str) -> list[str]:
    return [name for name, pattern in PROGRAM_TERMS.items() if re.search(pattern, text, re.IGNORECASE)]


def subject_name(term: str) -> str:
    return term if term in _NON_CANCER else f"{term} cancer"


def is_cost_question(query: str) -> bool:
    return bool(re.search(r"\b(how much|cost|costs|price|priced|charge|charges|fee|fees)\b", query, re.IGNORECASE))


def _record_has_term(record: dict, term: str) -> bool:
    return re.search(rf"\b{re.escape(term)}\b", str(record.get("treatment") or "").lower()) is not None


def _record_amounts(record: dict) -> set[int]:
    return {int(record[key]) for key in ("price_low", "price_high") if record.get(key) is not None}


def _lines(chunks: list[dict]) -> list[str]:
    return [line for chunk in chunks for line in (chunk.get("text") or "").splitlines() if line.strip()]


def _line_links(lines: list[str], term: str, amount: int | None = None) -> bool:
    for line in lines:
        if not re.search(rf"\b{re.escape(term)}\b", line, re.IGNORECASE):
            continue
        money = extract_money(line)
        if money and (amount is None or amount in money):
            return True
    return False


def has_programs(term: str, catalog: list[dict]) -> bool:
    return any(
        record.get("category") == "package_program" and _record_has_term(record, term) for record in catalog
    )


def unpriced_terms(query: str, catalog: list[dict], corpus: list[dict]) -> list[str]:
    """Treatments the question names that have no price record and no passage line with a price."""
    lines = _lines(corpus)
    answerable = [record for record in catalog if record.get("answerable", True)]
    return [
        term
        for term in terms_in(query)
        if not any(_record_has_term(record, term) for record in answerable) and not _line_links(lines, term)
    ]


def _bound(amount: int, treatments: list[str], programs: list[str], catalog: list[dict], lines: list[str]) -> bool:
    for record in catalog:
        if not record.get("answerable", True) or amount not in _record_amounts(record):
            continue
        if treatments and not any(_record_has_term(record, term) for term in treatments):
            continue
        if programs and str(record.get("program") or "") not in programs:
            continue
        return True
    return bool(treatments) and any(_line_links(lines, term, amount) for term in treatments)


def price_binding_reason(query: str, answer: str, chunks: list[dict], catalog: list[dict]) -> str:
    topic = terms_in(query)
    for term in topic:
        if _PROGRAM_MENTION.search(answer) and not has_programs(term, catalog):
            return (
                f"Out-Patient and In-Patient programs are listed only for the adenocarcinoma, adrenal, "
                f"and anal packages; do not mention them for {subject_name(term)}"
            )
    lines = _lines(chunks)
    for sentence in _SENTENCE_SPLIT.split(answer):
        amounts = extract_money(sentence)
        if not amounts:
            continue
        treatments = terms_in(sentence) or topic
        programs = programs_in(sentence)
        if not treatments and not programs:
            continue
        for amount in amounts:
            if not _bound(amount, treatments, programs, catalog, lines):
                names = ", ".join(subject_name(term) for term in treatments) or ", ".join(programs)
                return f"price {amount} is not listed for {names}; quote only a price stated for that item, or say it is not listed"
    return ""


def composite_reason(query: str, answer: str) -> str:
    if COMPOSITE_QUESTION.search(query) and not NOT_LISTED.search(answer):
        return "list each component price and say a combined total is not listed; do not add prices"
    return ""


_NEGATIVE_INCLUSION = re.compile(
    r"\b(?:not included|isn't included|aren't included|does not include|doesn't include|do not include|"
    r"don't include|excluded|excludes|not covered|isn't covered|aren't covered)\b",
    re.IGNORECASE,
)
_EXCLUSION_MARKER = re.compile(
    r"not included|excluded|exclusion|additional cost|not covered|charged separately", re.IGNORECASE
)
_PLAIN_WORDS = {
    "included", "include", "includes", "price", "prices", "package", "program", "treatment", "listed",
    "pages", "excluded", "excludes", "covered", "which", "there", "their", "these", "those", "about",
    "cancer", "alternative", "clinic", "costs", "under", "would", "other", "items",
}


def exclusion_reason(answer: str, chunks: list[dict]) -> str:
    """Saying something is excluded needs a passage that lists it as excluded.
    The comparison page's "Often Not Included" list is general and does not count."""
    marked = [
        chunk.get("text") or ""
        for chunk in chunks
        if _EXCLUSION_MARKER.search(chunk.get("text") or "")
        and "often not included" not in (chunk.get("text") or "").lower()
    ]
    for sentence in _SENTENCE_SPLIT.split(answer):
        if not _NEGATIVE_INCLUSION.search(sentence) or NOT_LISTED.search(sentence):
            continue
        words = {word for word in re.findall(r"[a-z]{5,}", sentence.lower()) if word not in _PLAIN_WORDS}
        if not any(any(word in text.lower() for word in words) for text in marked):
            return "the pages do not say this is excluded; say it is not listed instead"
    return ""


_CLINICAL = re.compile(r"\b(safe|safely|safety|effective|effectiveness|efficacy|colostomy|outcomes?|cures?|cured)\b", re.IGNORECASE)
_ATTRIBUTED = re.compile(
    r"according to|the clinic's page|the page (?:says|states)|states that|según|de acuerdo con|وفق|حسب",
    re.IGNORECASE,
)


def attribution_reason(answer: str) -> str:
    if _CLINICAL.search(answer) and not _ATTRIBUTED.search(answer):
        return "attribute clinical claims: start with \"According to the clinic's page,\""
    return ""


COUNTRIES = (
    "thailand", "turkey", "mexico", "croatia", "india", "georgia", "spain", "colombia", "costa rica",
    "germany", "south korea", "korea", "brazil", "canada", "panama", "poland", "hungary", "dubai",
    "malaysia", "singapore", "philippines", "vietnam", "greece", "cyprus", "jordan", "egypt", "peru",
    "argentina", "dominican republic", "japan", "china", "switzerland", "italy", "portugal", "france",
    "united kingdom", "saudi arabia", "pakistan", "indonesia", "cuba", "ecuador", "chile",
)


def destination_gap(query: str, corpus: list[dict], catalog: list[dict]) -> tuple[str, str] | None:
    """(country, subject) when every country the question names is unlisted for its treatment."""
    lowered = query.lower()
    countries = [country for country in COUNTRIES if re.search(rf"\b{country}\b", lowered)]
    topic = terms_in(query)
    subjects = topic or (["cancer"] if re.search(r"\bcancer\b", lowered) else [])
    if not countries or not subjects:
        return None
    # Country and treatment must share one line or one clinic-table row, not just one chunk.
    texts = [
        segment.lower()
        for chunk in corpus
        for segment in re.split(r"\n|(?=Clinic / Surgeon:)", chunk.get("text") or "")
    ]
    texts += [
        f"{record.get('treatment') or ''} {record.get('location') or ''} {record.get('raw_text') or ''}".lower()
        for record in catalog
    ]
    for country in countries:
        if any(country in text and any(re.search(rf"\b{s}\b", text) for s in subjects) for text in texts):
            return None
    if not topic:
        return countries[0].title(), "cancer treatment"
    subject = subject_name(topic[0])
    return countries[0].title(), subject if topic[0] in _NON_CANCER else f"{subject} treatment"


def verify(
    draft: dict,
    chunks: list[dict],
    prices: list[dict],
    *,
    clinic_names: list[str] | None = None,
    query: str = "",
    catalog: list[dict] | None = None,
    unpriced: list[str] | None = None,
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
    if status == "not_listed" and not cited and not cited_prices:
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
    for reason in (
        price_binding_reason(query, answer, chunks, catalog if catalog is not None else prices),
        composite_reason(query, answer),
        exclusion_reason(answer, chunks),
        attribution_reason(answer),
    ):
        if reason:
            return False, reason
    if _VAGUE_MISSING.search(answer) and not NOT_LISTED.search(answer):
        return False, 'when the pages do not state something, write that it "is not listed"'
    if unpriced and is_cost_question(query):
        if not NOT_LISTED.search(answer):
            return False, f"the price for {subject_name(unpriced[0])} is not listed; say so"
        if extract_money(answer):
            return False, f"the price for {subject_name(unpriced[0])} is not listed; do not quote other prices"
        draft["answer_status"] = "not_listed"
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


def add_related_facts(answer: str, chunks: list[dict], query: str = "") -> str:
    """not_listed replies must name the related program length and follow-up when the pages have them.
    Price questions skip this: a program length must not be attached to an unlisted item."""
    text = answer.strip()
    if is_cost_question(query):
        if quote_url() not in text:
            text = f"{text} Request a free quote: {quote_url()}"
        return text.strip()
    blob = " ".join((chunk.get("text") or "") for chunk in chunks).lower()
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
    program: str = "",
) -> tuple[str, str] | None:
    """Compare a stated price with the item asked about: the program if one is named, else the treatment."""
    if not user_numbers:
        return None
    claimed = set(extract_numbers(" ".join(user_numbers)))
    if not claimed:
        return None
    if program:
        pool = _topic_records(prices, treatment, clinic) if treatment.strip() else prices
        topic = [
            record
            for record in pool
            if record.get("answerable", True) and str(record.get("program") or "").lower() == program.lower()
        ]
        if topic:
            listed = set().union(*(_record_amounts(record) for record in topic))
            if claimed & listed:
                return None
            record = topic[0]
            duration = f" ({record['duration']})" if record.get("duration") else ""
            where = f" of the {treatment}" if treatment.strip() else ""
            return (
                f"I can't confirm that. Our page lists {format_price(record)} for the "
                f"{record.get('program')}{duration}{where}.",
                record.get("url") or "",
            )
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
