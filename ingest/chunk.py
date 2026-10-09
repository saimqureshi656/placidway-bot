"""Split extracted sections into retrieval chunks.

Testimonial and video_list chunks are kept in the index and marked flagged.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from ingest.urls import PAGES

ROOT = Path(__file__).resolve().parents[1]
KB_DIR = ROOT / "data" / "kb"
CHUNKS_PATH = KB_DIR / "chunks.jsonl"

MAX_TOKENS = 450
TABLE_ROW_OVERLAP = 2

PAGE_FACTS = {
    "clinic_profile": {
        "clinic": "ITC Immunity Therapy Center",
        "treatment": "Alternative Cancer Treatment",
        "country": "Mexico",
    },
    "clinic_videos": {
        "clinic": "ITC Immunity Therapy Center",
        "treatment": "Alternative Cancer Treatment",
        "country": "Mexico",
    },
    "price_list": {
        "clinic": "ITC Immunity Therapy Center",
        "treatment": "Alternative Cancer Treatment",
        "country": "Mexico",
    },
    "package_7903": {
        "clinic": "ITC Immunity Therapy Center",
        "treatment": "Alternative Adenocarcinoma Cancer Treatment",
        "country": "Mexico",
    },
    "package_7902": {
        "clinic": "ITC Immunity Therapy Center",
        "treatment": "Alternative Adrenal Cancer Treatment",
        "country": "Mexico",
    },
    "package_7901": {
        "clinic": "ITC Immunity Therapy Center",
        "treatment": "Alternative Anal Cancer Treatment",
        "country": "Mexico",
    },
    "price_comparison": {
        "clinic": "",
        "treatment": "Alternative Medicine",
        "country": "",
    },
}


def token_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _is_table_row(line: str, table_rows: set[str]) -> bool:
    return line in table_rows or (line.count("|") >= 2 and ":" in line)


def _units(text: str, table_rows: set[str]) -> list[tuple[str, str]]:
    units: list[tuple[str, str]] = []
    buffer: list[str] = []

    def flush() -> None:
        if buffer:
            units.append(("text", "\n".join(buffer)))
            buffer.clear()

    for line in text.splitlines():
        if not line.strip():
            flush()
            continue
        if _is_table_row(line, table_rows):
            flush()
            units.append(("row", line))
            continue
        is_item = line.lstrip().startswith("- ")
        if buffer:
            previous_item = buffer[-1].lstrip().startswith("- ")
            if is_item != previous_item:
                flush()
        buffer.append(line)
    flush()
    return units


def _expand_long_units(units: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """Split an oversized paragraph on line boundaries. Table rows stay whole."""
    expanded: list[tuple[str, str]] = []
    for kind, text in units:
        if kind == "row" or token_count(text) <= MAX_TOKENS:
            expanded.append((kind, text))
            continue
        for line in text.splitlines():
            if line.strip():
                expanded.append(("text", line))
    return expanded


def _pack(units: list[tuple[str, str]]) -> list[str]:
    units = _expand_long_units(units)
    if not units:
        return []
    chunks: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    current_tokens = 0
    for unit in units:
        size = token_count(unit[1])
        if current and current_tokens + size > MAX_TOKENS:
            chunks.append(current)
            overlap = [item for item in current if item[0] == "row"][-TABLE_ROW_OVERLAP:]
            current = list(overlap)
            current_tokens = sum(token_count(item[1]) for item in current)
        current.append(unit)
        current_tokens += size
    if current:
        chunks.append(current)
    bodies = []
    for chunk_units in chunks:
        body = "\n".join(unit[1] for unit in chunk_units).strip()
        if body:
            bodies.append(body)
    return bodies


def _chunk_record(page_id: str, document: dict, section: dict, section_index: int, part: int, body: str) -> dict:
    facts = PAGE_FACTS[page_id]
    section_type = section["section_type"]
    text = f"Page: {document['title']} | Section: {section['heading']}\n{body}"
    return {
        "chunk_id": f"{page_id}:{section_index}:{part}",
        "url": document["url"],
        "page_type": document["page_type"],
        "section": section["heading"],
        "section_type": section_type,
        "clinic": facts["clinic"],
        "treatment": facts["treatment"],
        "country": facts["country"],
        "flagged": section_type in {"testimonial", "video_list"},
        "text": text,
        "tokens": token_count(text),
    }


def build_chunks() -> list[dict]:
    chunks: list[dict] = []
    for page in PAGES:
        document = json.loads((KB_DIR / f"{page.page_id}.json").read_text(encoding="utf-8"))
        for section_index, section in enumerate(document["sections"]):
            table_rows = {row for table in section["tables"] for row in table}
            bodies = _pack(_units(section["text"], table_rows))
            if not bodies and section["text"].strip():
                bodies = [section["text"].strip()]
            for part, body in enumerate(bodies):
                chunks.append(_chunk_record(page.page_id, document, section, section_index, part, body))
    CHUNKS_PATH.write_text(
        "".join(json.dumps(chunk, ensure_ascii=False) + "\n" for chunk in chunks),
        encoding="utf-8",
    )
    return chunks


def main() -> None:
    chunks = build_chunks()
    print(f"wrote {CHUNKS_PATH} ({len(chunks)} chunks)")


if __name__ == "__main__":
    main()
