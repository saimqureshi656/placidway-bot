"""Build structured price records from the extracted pages.

The blank price-list row is stored with treatment null and answerable false.
The comparison page's $35-$30000 range is comparison_summary only, not an ITC price.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ingest.urls import PAGES, SourcePage

ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "data" / "kb"
PRICES_PATH = KB_DIR / "prices.json"

ITC = "ITC Immunity Therapy Center"
TIJUANA = "Tijuana, Mexico"

PACKAGE_TREATMENTS = {
    "package_7903": "Alternative Adenocarcinoma Cancer Treatment",
    "package_7902": "Alternative Adrenal Cancer Treatment",
    "package_7901": "Alternative Anal Cancer Treatment",
}


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
    return slug[:48] or "item"


def _money_values(text: str) -> list[int]:
    values = [int(amount.replace(",", "")) for amount in re.findall(r"\$\s?(\d[\d,]*)", text)]
    if values:
        return values
    usd = re.search(r"\b(\d[\d,]*)\s*usd\b", text, re.IGNORECASE)
    if usd:
        return [int(usd.group(1).replace(",", ""))]
    return []


def _qualifier(text: str) -> str:
    if re.search(r"\bapprox", text, re.IGNORECASE):
        return "approximately"
    if re.search(r"starting from|\bstart at\b", text, re.IGNORECASE):
        return "starting from"
    return ""


def _labeled_row(row: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for part in row.split("|"):
        if ":" not in part:
            continue
        key, value = part.split(":", 1)
        fields[_collapse(key).lower()] = value.strip()
    return fields


def _record(
    *,
    record_id: str,
    category: str,
    url: str,
    raw_text: str,
    price_low: int,
    price_high: int,
    clinic: str | None = None,
    location: str | None = None,
    treatment: str | None = None,
    program: str = "",
    duration: str = "",
    qualifier: str = "",
    includes_section: str = "",
    answerable: bool = True,
    flag: str | None = None,
) -> dict:
    record = {
        "id": record_id,
        "clinic": clinic,
        "location": location,
        "treatment": treatment,
        "program": program,
        "duration": duration,
        "price_low": price_low,
        "price_high": price_high,
        "currency": "USD",
        "qualifier": qualifier,
        "category": category,
        "includes_section": includes_section,
        "url": url,
        "raw_text": raw_text,
        "answerable": answerable,
    }
    if flag:
        record["flag"] = flag
    return record


def _load_pages() -> list[tuple[SourcePage, dict]]:
    loaded = []
    for page in PAGES:
        path = KB_DIR / f"{page.page_id}.json"
        loaded.append((page, json.loads(path.read_text(encoding="utf-8"))))
    return loaded


def _section(document: dict, heading_startswith: str) -> dict | None:
    needle = heading_startswith.lower()
    for section in document["sections"]:
        if section["heading"].lower().startswith(needle):
            return section
    return None


def _package_records(page: SourcePage, document: dict) -> list[dict]:
    treatment = PACKAGE_TREATMENTS[page.page_id]
    prefix = page.page_id.removeprefix("package_")
    records: list[dict] = []
    price_section = _section(document, "Package Price")
    if price_section:
        raw = _collapse(price_section["text"])
        amounts = _money_values(raw)
        if amounts:
            records.append(
                _record(
                    record_id=f"p_{prefix}_starting",
                    category="package_starting_from",
                    url=page.url,
                    raw_text=raw,
                    price_low=amounts[0],
                    price_high=amounts[0],
                    clinic=ITC,
                    location=TIJUANA,
                    treatment=treatment,
                    qualifier="starting from",
                )
            )
    cost = _section(document, "Cost of")
    if cost:
        for row in cost["tables"][0] if cost["tables"] else []:
            fields = _labeled_row(row)
            program = fields.get("program type", "")
            duration = fields.get("duration", "")
            price = fields.get("total cost (usd)", "")
            amounts = _money_values(price)
            if not program or not amounts:
                continue
            kind = "inpatient" if "in-patient" in program.lower() else "outpatient"
            records.append(
                _record(
                    record_id=f"p_{prefix}_{kind}",
                    category="package_program",
                    url=page.url,
                    raw_text=f"{program} | {duration} | {price}",
                    price_low=amounts[0],
                    price_high=amounts[-1],
                    clinic=ITC,
                    location=TIJUANA,
                    treatment=treatment,
                    program=program,
                    duration=duration,
                    includes_section=f"Included in the {program}",
                )
            )
    optional = _section(document, "Optional Specialized")
    if optional:
        for line in optional["text"].splitlines():
            if not line.startswith("- ") or not _money_values(line):
                continue
            body = line[2:]
            name, _, _rest = body.partition(":")
            amounts = _money_values(body)
            records.append(
                _record(
                    record_id=f"p_{prefix}_{_slug(name)}",
                    category="optional_procedure",
                    url=page.url,
                    raw_text=_collapse(body),
                    price_low=amounts[0],
                    price_high=amounts[-1],
                    clinic=ITC,
                    location=TIJUANA,
                    treatment=treatment,
                    program=_collapse(name),
                    qualifier=_qualifier(body),
                )
            )
    excluded = _section(document, "Excluded Services")
    if excluded:
        for line in excluded["text"].splitlines():
            if not line.startswith("- ") or not _money_values(line):
                continue
            body = line[2:]
            name, _, _rest = body.partition(":")
            amounts = _money_values(body)
            records.append(
                _record(
                    record_id=f"p_{prefix}_{_slug(name)}",
                    category="exclusion_approx",
                    url=page.url,
                    raw_text=_collapse(body),
                    price_low=amounts[0],
                    price_high=amounts[-1],
                    clinic=ITC,
                    location=TIJUANA,
                    treatment=treatment,
                    program=_collapse(name),
                    qualifier=_qualifier(body),
                )
            )
    return records


def _profile_records(page: SourcePage, document: dict) -> list[dict]:
    for section in document["sections"]:
        for line in section["text"].splitlines():
            if re.search(r"start at\s+\$18,995", line, re.IGNORECASE):
                amounts = _money_values(line)
                return [
                    _record(
                        record_id="p_profile_starting",
                        category="package_starting_from",
                        url=page.url,
                        raw_text=_collapse(line),
                        price_low=amounts[0],
                        price_high=amounts[0],
                        clinic=ITC,
                        location=TIJUANA,
                        treatment="Alternative Cancer Treatment",
                        qualifier="starting from",
                    )
                ]
    return []


def _price_list_records(page: SourcePage, document: dict) -> list[dict]:
    records: list[dict] = []
    table_section = next((section for section in document["sections"] if section["tables"]), None)
    if table_section is None:
        return records
    for row in table_section["tables"][0]:
        fields = _labeled_row(row)
        procedure = fields.get("procedure", "")
        amounts = _money_values(fields.get("price in usd", row))
        if not amounts:
            continue
        if not procedure:
            records.append(
                _record(
                    record_id="p_list_blank",
                    category="price_list_row",
                    url=page.url,
                    raw_text=row,
                    price_low=amounts[0],
                    price_high=amounts[0],
                    clinic=ITC,
                    location=TIJUANA,
                    treatment=None,
                    answerable=False,
                    flag="blank_procedure",
                )
            )
            continue
        records.append(
            _record(
                record_id=f"p_list_{_slug(procedure)}",
                category="price_list_row",
                url=page.url,
                raw_text=row,
                price_low=amounts[0],
                price_high=amounts[0],
                    clinic=ITC,
                    location=TIJUANA,
                    treatment=procedure,
                )
        )
    return records


def _split_clinic(cell: str) -> tuple[str, str]:
    match = re.search(r",\s*([^,]+,\s*(?:Mexico|Turkey|Croatia|Thailand))\s*$", cell)
    if not match:
        return cell, ""
    location = re.sub(r"\s+,", ",", match.group(1)).strip()
    clinic = cell[: match.start()].strip().rstrip(",")
    return clinic, location


def _comparison_records(page: SourcePage, document: dict) -> list[dict]:
    records: list[dict] = []
    facts = _section(document, "Quick Facts")
    if facts:
        for line in facts["text"].splitlines():
            if line.lower().startswith("average price"):
                amounts = _money_values(line)
                if amounts:
                    records.append(
                        _record(
                            record_id="p_cmp_average",
                            category="comparison_summary",
                            url=page.url,
                            raw_text=line,
                            price_low=amounts[0],
                            price_high=amounts[0],
                            location="Abroad",
                            treatment="Alternative Medicine",
                            qualifier="",
                        )
                    )
            elif line.lower().startswith("price range"):
                amounts = _money_values(line)
                if len(amounts) >= 2:
                    records.append(
                        _record(
                            record_id="p_cmp_range",
                            category="comparison_summary",
                            url=page.url,
                            raw_text=line,
                            price_low=amounts[0],
                            price_high=amounts[1],
                            location="Abroad",
                            treatment="Alternative Medicine",
                        )
                    )
    for section in document["sections"]:
        for table in section["tables"]:
            for row in table:
                fields = _labeled_row(row)
                if "low" in fields and "procedure" in fields:
                    amounts = _money_values(row)
                    if len(amounts) < 2:
                        continue
                    procedure = fields["procedure"]
                    duration = ""
                    duration_match = re.search(r"\((\d+\s+days)\)", procedure, re.IGNORECASE)
                    if duration_match:
                        duration = duration_match.group(1).title()
                    records.append(
                        _record(
                            record_id=f"p_cmp_proc_{_slug(procedure)}",
                            category="comparison_procedure_range",
                            url=page.url,
                            raw_text=row,
                            price_low=amounts[0],
                            price_high=amounts[1],
                            treatment=procedure,
                            duration=duration,
                        )
                    )
                elif "component" in fields:
                    amounts = _money_values(row)
                    if len(amounts) < 2:
                        continue
                    component = fields["component"]
                    records.append(
                        _record(
                            record_id=f"p_cmp_comp_{_slug(component)}",
                            category="comparison_component",
                            url=page.url,
                            raw_text=row,
                            price_low=amounts[0],
                            price_high=amounts[1],
                            treatment=component,
                        )
                    )
                elif "clinic / surgeon" in fields:
                    amounts = _money_values(fields.get("standard", row))
                    if not amounts:
                        continue
                    clinic, location = _split_clinic(fields["clinic / surgeon"])
                    records.append(
                        _record(
                            record_id=f"p_cmp_clinic_{_slug(clinic)}",
                            category="comparison_clinic",
                            url=page.url,
                            raw_text=row,
                            price_low=amounts[0],
                            price_high=amounts[0],
                            clinic=clinic,
                            location=location,
                            treatment=fields.get("procedure", "Alternative Medicine"),
                        )
                    )
    return records


def build_prices() -> list[dict]:
    records: list[dict] = []
    for page, document in _load_pages():
        if page.page_type == "package":
            records.extend(_package_records(page, document))
        elif page.page_type == "clinic_profile":
            records.extend(_profile_records(page, document))
        elif page.page_type == "price_list":
            records.extend(_price_list_records(page, document))
        elif page.page_type == "price_comparison":
            records.extend(_comparison_records(page, document))
    ids = [record["id"] for record in records]
    if len(ids) != len(set(ids)):
        duplicates = sorted({item for item in ids if ids.count(item) > 1})
        raise ValueError(f"Duplicate price ids: {duplicates}")
    PRICES_PATH.write_text(json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return records


def main() -> None:
    records = build_prices()
    answerable = sum(1 for record in records if record["answerable"])
    print(f"wrote {PRICES_PATH} ({len(records)} records, {answerable} answerable)")


if __name__ == "__main__":
    main()
