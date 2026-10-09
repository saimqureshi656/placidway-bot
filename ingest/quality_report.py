"""Write data/quality_report.md from the extracted pages, prices, and chunks."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ingest.chunk import CHUNKS_PATH, build_chunks
from ingest.prices import PRICES_PATH, build_prices
from ingest.urls import PAGES

ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "data" / "kb"
REPORT_PATH = ROOT / "data" / "quality_report.md"


def _documents() -> list[tuple[str, dict]]:
    loaded = []
    for page in PAGES:
        document = json.loads((KB_DIR / f"{page.page_id}.json").read_text(encoding="utf-8"))
        loaded.append((page.page_id, document))
    return loaded


def write_report() -> Path:
    if not PRICES_PATH.exists():
        build_prices()
    if not CHUNKS_PATH.exists():
        build_chunks()
    prices = json.loads(PRICES_PATH.read_text(encoding="utf-8"))
    chunks = [json.loads(line) for line in CHUNKS_PATH.read_text(encoding="utf-8").splitlines() if line]
    documents = _documents()

    blank = next((record for record in prices if record.get("flag") == "blank_procedure"), None)
    colorectal = next(
        (record for record in prices if record.get("treatment") == "Colorectal Cancer"),
        None,
    )
    comparison = next(document for page_id, document in documents if page_id == "price_comparison")
    clinic_rows = [
        record for record in prices if record["category"] == "comparison_clinic"
    ]
    visani = next((record for record in clinic_rows if "VISANI" in (record.get("clinic") or "")), None)
    appendix_pages = [
        page_id
        for page_id, document in documents
        if "Appendix" in json.dumps(document, ensure_ascii=False)
    ]
    priced_urls = {record["url"] for record in prices if record["answerable"]}
    pages_without_price = [page.page_id for page in PAGES if page.url not in priced_urls]
    section_counts = {page_id: len(document["sections"]) for page_id, document in documents}
    chunk_counts = Counter(chunk["chunk_id"].split(":", 1)[0] for chunk in chunks)
    load_more = any("Load More" in section["text"] for section in comparison["sections"])
    about = next(
        section["text"]
        for page_id, document in documents
        if page_id == "price_list"
        for section in document["sections"]
        if section["heading"].startswith("About ITC")
    )

    lines = [
        "# Data quality report",
        "",
        "Findings from the seven allowlisted pages after extract, prices, and chunking.",
        "",
        "## Blank price-list row",
        "",
        "The price list has a row with an empty procedure name. It is stored with `treatment: null`, `answerable: false`, and `flag: blank_procedure`. It is not an answerable price.",
        "",
        f"- `{blank['raw_text']}`" if blank else "- Blank row was not found.",
        "",
        "## Colorectal details cell",
        "",
        'The colorectal row\'s Details cell is the text "18995 USD". The price cell is $18995.',
        "",
        f"- `{colorectal['raw_text']}`" if colorectal else "- Colorectal row was not found.",
        "",
        "## Unrendered priceRange tag",
        "",
        "The price-list About HTML contains the unrendered PHP tag `<?=$priceRange?>`. The extract removes that token, so the sentence has no numeric range. The price-list table still shows $18995.",
        "",
        "```",
        about.splitlines()[0] if about else "",
        "```",
        "",
        "## Load More truncation",
        "",
        "The comparison clinic table is the first batch only. The page includes a Load More control, so later clinics are not in the saved HTML."
        if load_more
        else "Load More was not found in the comparison extract.",
        "",
        f"Comparison clinic records: {len(clinic_rows)}.",
        "",
        "## VISANI Puebla vs Mexico City",
        "",
        "The clinic link text says Puebla and the location cell says Mexico City.",
        "",
        (
            f"- clinic `{visani['clinic']}`, location `{visani['location']}`, price ${visani['price_low']}"
            if visani
            else "- VISANI record was not found."
        ),
        "",
        "## Appendix package referenced but not in sources",
        "",
        "Center cards name Alternative Appendix Cancer Treatment Package. That package is not one of the seven allowlisted URLs and was not fetched.",
        "",
        "Mentioned on: " + (", ".join(appendix_pages) if appendix_pages else "none"),
        "",
        "## Pages with no price",
        "",
        "Answerable price records are missing for: " + (", ".join(pages_without_price) if pages_without_price else "none"),
        "",
        "The video page has titles and a center card. It has no answerable treatment price. A sidebar line `Price Range: $18995 - $18995` is not turned into an ITC price record, because the price-list rows already state $18995.",
        "",
        "## Missing recovery time",
        "",
        "The three package pages list a 3-week program and a follow-up consult after 3 months. They do not list a recovery duration. Phrases such as \"partner in your own recovery\" are not a time.",
        "",
        "## No video transcripts",
        "",
        "The video page stores titles in one section, one title per line. There are no transcripts. Those chunks are indexed and flagged.",
        "",
        "## Section counts",
        "",
    ]
    for page_id, count in section_counts.items():
        lines.append(f"- {page_id}: {count}")
    lines.extend(["", "## Chunk counts", ""])
    for page in PAGES:
        lines.append(f"- {page.page_id}: {chunk_counts.get(page.page_id, 0)}")
    lines.append(f"- total: {len(chunks)}")
    lines.append("")
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return REPORT_PATH


def main() -> None:
    path = write_report()
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
