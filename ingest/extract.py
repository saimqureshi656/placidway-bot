"""Extract main content from the seven cached pages.

One extractor per page type. They share the helpers below.
Boilerplate H2/H3 sections are dropped with BOILERPLATE_HEADING_PATTERNS.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

from ingest.urls import PAGES, SourcePage

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
KB_DIR = ROOT / "data" / "kb"

# Section 2 carousel / chrome headings. "..." in the plan is a wildcard.
# Case-insensitive. Edit this list live to drop another heading.
BOILERPLATE_HEADING_PATTERNS: tuple[str, ...] = (
    r"explore\b.*stories,\s*testimonials",
    r"learn more with these\b.*articles",
    r"transformative\b.*experiences",
    r"solutions near you",
    r"unlock the best\b.*packages",
    r"trusted medical tourism platform",
    r"accreditations\s*(?:&|and)\s*certifications",
    r"the placidway network",
    r"related experiences",
    r"share with ai",
    r"request your free quote",
    r"no slots available",
    r"request a video call",
    r"confirm your virtual consultation",
    r"book a consultation",
    r"request a consultation",
    r"\bcertificates\b",
)

HEADING_TAGS = {"h1", "h2", "h3"}
REMOVE_TAGS = ["script", "style", "nav", "header", "footer", "form", "iframe", "noscript"]
SHARE_WIDGET_CLASSES = {
    "ai-share-sec",
    "social-popup-main",
    "social-list",
    "share-btns",
    "modal-share__copy",
    "article-social-section",
}
SHARE_LINE_RE = re.compile(
    r"^(?:"
    r"share(?:\s+with\s+ai)?"
    r"|share this (?:page|listing)(?:\s+with ai assistants.*)?|"
    r"copy link|chatgpt|perplexity|grok|google gemini|claude|"
    r"facebook|twitter|linkedin|whatsapp|pinterest|email"
    r")$",
    re.IGNORECASE,
)
STARTING_PRICE_RE = re.compile(r"price starting from", re.IGNORECASE)
PRICE_ONLY_RE = re.compile(r"^\$[\d,]+(?:\s*usd)?$", re.IGNORECASE)
TEMPLATE_TAG_RE = re.compile(r"<\?.*?\?>|=\$\w+\?>", re.DOTALL)
VIEW_COUNT_TOKEN_RE = re.compile(r"(?<![\d$])\b\d+(?:\.\d+)?K\b", re.IGNORECASE)
STANDALONE_COUNT_RE = re.compile(r"^(?:\d+(?:\.\d+)?K|\d{3,7})$", re.IGNORECASE)
OFTEN_NOT_INCLUDED_INTRO_RE = re.compile(
    r"These are the items most patients expect to see inside a standard alternative medicine package abroad\.\s*"
    r"The exact clinic package can still vary, so users should confirm details in writing\.?",
    re.IGNORECASE,
)
REVIEWER_HEADINGS = {"jana c", "chris p", "frank h", "reviews", "recent reviews", "medical center reviews"}
REVIEW_COUNT_LINE_RE = re.compile(r"^\d+\s+reviews?$", re.IGNORECASE)
UI_STRING_RE = re.compile(
    r"\b(?:View Center Reviews|Write a review|Read More|Chat with Center)\b",
    re.IGNORECASE,
)
BROKEN_RANGE_SENTENCE_RE = re.compile(
    r"[^.]*prices range between in Tijuana[^.]*\.",
    re.IGNORECASE | re.DOTALL,
)
MIN_REAL_TEXT = 40

def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _is_boilerplate_heading(heading: str) -> bool:
    text = _collapse(heading)
    if not text:
        return False
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in BOILERPLATE_HEADING_PATTERNS)


def _boilerplate_drops_descendants(title: str) -> bool:
    """Carousel headings take their nested cards with them.

    A Certificates heading also wraps the doctors subsection, which is real
    clinic content, so only that heading is dropped.
    """
    return re.search(r"\bcertificates\b", title, re.IGNORECASE) is None


def _is_center_aside(tag: Tag) -> bool:
    return "pack-about-aside" in set(tag.get("class") or [])


def _is_video_title_heading(tag: Tag) -> bool:
    if "title" not in set(tag.get("class") or []):
        return False
    parent = tag.parent
    while isinstance(parent, Tag):
        classes = set(parent.get("class") or [])
        if classes & {"related-videos", "related-videos-card", "related-videos-sec"}:
            return True
        parent = parent.parent
    return False


def _is_share_line(text: str) -> bool:
    return bool(SHARE_LINE_RE.match(_collapse(text)))


def _inside(node: object, ancestor: Tag) -> bool:
    parent = getattr(node, "parent", None)
    while parent is not None:
        if parent is ancestor:
            return True
        parent = getattr(parent, "parent", None)
    return False


def _is_hidden(tag: Tag) -> bool:
    style = (tag.get("style") or "").replace(" ", "").lower()
    if "display:none" in style:
        return True
    classes = set(tag.get("class") or [])
    return bool(classes & {"hide", "d-none", "hidden"})


def _is_share_widget(tag: Tag) -> bool:
    classes = set(tag.get("class") or [])
    if classes & SHARE_WIDGET_CLASSES:
        return True
    return bool(tag.get("data-share-type"))


def _is_image_only(tag: Tag) -> bool:
    if _collapse(tag.get_text(" ", strip=True)):
        return False
    return tag.find(["img", "svg", "picture"]) is not None


def _cell_text(cell: Tag) -> str:
    date = cell.select_one(".date-meta-info")
    date_text = _collapse(date.get_text(" ", strip=True)) if date else ""
    if date is not None:
        date.extract()
    name = cell.select_one(".centr_name")
    location = cell.select_one(".center_loc")
    if name is not None and location is not None:
        text = f"{_collapse(name.get_text(' ', strip=True))}, {_collapse(location.get_text(' ', strip=True))}"
    else:
        text = _collapse(cell.get_text(" ", strip=True))
    if date_text:
        text = f"{text} ({date_text})".strip()
    return text


def _table_rows(table: Tag) -> list[str]:
    parsed: list[tuple[Tag, list[str]]] = []
    for tr in table.find_all("tr"):
        if tr.find_parent("table") is not table:
            continue
        cells = [_cell_text(cell) for cell in tr.find_all(["th", "td"], recursive=False)]
        if any(cell.strip() for cell in cells):
            parsed.append((tr, cells))
    if not parsed:
        return []

    header: list[str] | None = None
    data = parsed
    thead = table.find("thead")
    if thead is not None:
        header_rows = [row for row in parsed if _inside(row[0], thead)]
        body_rows = [row for row in parsed if not _inside(row[0], thead)]
        if header_rows:
            header = header_rows[0][1]
            data = body_rows
    elif parsed[0][0].find("th") is not None:
        header = parsed[0][1]
        data = parsed[1:]
    elif len(parsed) > 1 and _looks_like_header(parsed[0][1]):
        header = parsed[0][1]
        data = parsed[1:]

    rendered: list[str] = []
    if header and not data:
        rendered.append(" | ".join(header))
        return rendered
    for _, cells in data:
        if not header:
            rendered.append(" | ".join(cells))
            continue
        parts: list[str] = []
        for index, cell in enumerate(cells):
            label = header[index].strip() if index < len(header) else ""
            parts.append(f"{label}: {cell}" if label else cell)
        rendered.append(" | ".join(parts).strip())
    return rendered


def _looks_like_header(cells: list[str]) -> bool:
    joined = " ".join(cells).lower()
    if "$" in joined:
        return False
    hints = ("price", "cost", "procedure", "program", "duration", "component", "clinic")
    return any(hint in joined for hint in hints)


def _render_list(list_tag: Tag, indent: int = 0) -> str:
    lines: list[str] = []
    prefix = "  " * indent
    for li in list_tag.find_all("li", recursive=False):
        chunks: list[str] = []
        for child in li.children:
            if isinstance(child, Tag) and child.name in {"ul", "ol"}:
                continue
            if isinstance(child, Tag):
                chunks.append(child.get_text(" ", strip=True))
            else:
                chunks.append(str(child))
        text = _collapse(" ".join(chunks))
        if text and not _is_share_line(text):
            lines.append(f"{prefix}- {text}")
        for nested in li.find_all(["ul", "ol"], recursive=False):
            nested_text = _render_list(nested, indent + 1)
            if nested_text:
                lines.append(nested_text)
    return "\n".join(lines)


def _render_dl(dl: Tag) -> str:
    lines: list[str] = []
    paired = False
    for row in dl.find_all("div", recursive=False):
        term = row.find("dt")
        value = row.find("dd")
        if term is None or value is None:
            continue
        paired = True
        lines.append(f"{_collapse(term.get_text(' ', strip=True))}: {_collapse(value.get_text(' ', strip=True))}")
    if paired:
        return "\n".join(lines)
    terms = dl.find_all("dt")
    values = dl.find_all("dd")
    for term, value in zip(terms, values):
        lines.append(f"{_collapse(term.get_text(' ', strip=True))}: {_collapse(value.get_text(' ', strip=True))}")
    return "\n".join(lines)


def _append_text_lines(lines: list[str], text: str) -> None:
    for part in text.splitlines():
        part = _collapse(part)
        if not part or _is_share_line(part):
            continue
        if lines and lines[-1] == part:
            continue
        lines.append(part)


def _collect_section(heading: Tag, stop: Tag | None) -> tuple[str, list[list[str]]]:
    lines: list[str] = []
    tables: list[list[str]] = []
    skip_root: Tag | None = None

    for el in heading.next_elements:
        if _inside(el, heading):
            continue
        if stop is not None and el is stop:
            break
        if isinstance(el, Tag) and el.name in HEADING_TAGS:
            break
        if skip_root is not None:
            if el is skip_root or _inside(el, skip_root):
                continue
            skip_root = None

        if isinstance(el, Comment):
            continue
        if isinstance(el, NavigableString):
            _append_text_lines(lines, str(el))
            continue
        if not isinstance(el, Tag):
            continue
        if stop is not None and _inside(stop, el):
            continue
        if _is_center_aside(el) and not _inside(heading, el):
            break
        if _is_hidden(el) or _is_share_widget(el):
            skip_root = el
            continue
        if _is_image_only(el):
            skip_root = el
            continue

        if el.name == "table":
            rows = _table_rows(el)
            if rows:
                tables.append(rows)
                lines.extend(rows)
            skip_root = el
            continue
        if el.name in {"ul", "ol"}:
            rendered = _render_list(el)
            if rendered:
                _append_text_lines(lines, rendered)
            skip_root = el
            continue
        if el.name == "dl":
            rendered = _render_dl(el)
            if rendered:
                _append_text_lines(lines, rendered)
            skip_root = el
            continue
        if el.name in {"p", "h4", "blockquote", "pre", "address"}:
            _append_text_lines(lines, el.get_text("\n", strip=True))
            skip_root = el
            continue
        if el.name in {"div", "span", "a", "li", "button", "strong", "em"}:
            if el.find(["p", "ul", "ol", "table", "dl", "h4", "blockquote", "div", "li"]):
                continue
            text = _collapse(el.get_text(" ", strip=True))
            if text and not _is_share_line(text):
                lines.append(f"- {text}" if el.name == "li" else text)
            skip_root = el
    return "\n".join(lines).strip(), tables


def _heading_text(tag: Tag) -> str:
    return _collapse(tag.get_text(" ", strip=True))


def _sections_from_soup(soup: BeautifulSoup) -> list[dict]:
    for tag in soup.find_all(REMOVE_TAGS):
        tag.decompose()

    h1 = soup.find("h1")
    if h1 is None:
        raise ValueError("Page has no H1")

    headings = [h1, *h1.find_all_next(["h2", "h3"])]
    sections: list[dict] = []
    index = 0
    while index < len(headings):
        heading = headings[index]
        title = _heading_text(heading)
        level = int(heading.name[1])
        if _is_boilerplate_heading(title):
            logger.info("dropping boilerplate %s: %s", heading.name, title)
            index += 1
            if _boilerplate_drops_descendants(title):
                while index < len(headings) and int(headings[index].name[1]) > level:
                    logger.info(
                        "dropping nested %s under boilerplate: %s",
                        headings[index].name,
                        _heading_text(headings[index]),
                    )
                    index += 1
            continue
        if not title:
            index += 1
            continue
        stop = headings[index + 1] if index + 1 < len(headings) else None
        text, tables = _collect_section(heading, stop)
        section = {"heading": title, "text": text, "tables": tables}
        if _is_video_title_heading(heading):
            section["is_video_title"] = True
        sections.append(section)
        index += 1
    return sections


def _strip_templates(text: str) -> str:
    cleaned = TEMPLATE_TAG_RE.sub("", text)
    lines = [_collapse(line) for line in cleaned.splitlines()]
    return "\n".join(line for line in lines if line)


def _strip_view_counts(text: str, *, count_area: bool) -> str:
    """Drop standalone view counts. Leave prices that use $ or USD."""
    kept: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line
        if "$" not in line and "usd" not in line.lower():
            line = VIEW_COUNT_TOKEN_RE.sub("", line)
            line = _collapse(line)
        if count_area and line and STANDALONE_COUNT_RE.match(line) and "$" not in line and "usd" not in line.lower():
            continue
        if line:
            kept.append(line)
    return "\n".join(kept)


def _drop_starting_price_lines(text: str) -> str:
    lines = text.splitlines()
    kept: list[str] = []
    for index, line in enumerate(lines):
        nxt = lines[index + 1] if index + 1 < len(lines) else ""
        if STARTING_PRICE_RE.search(line):
            if kept and PRICE_ONLY_RE.match(kept[-1]):
                kept.pop()
            continue
        if PRICE_ONLY_RE.match(line) and STARTING_PRICE_RE.search(nxt):
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def _strip_ui_strings(text: str) -> str:
    cleaned_lines: list[str] = []
    for line in text.splitlines():
        line = UI_STRING_RE.sub("", line)
        line = re.sub(r"\s*\|\s*Actions:\s*(?=\||$)", "", line)
        line = _collapse(line)
        if line:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def _strip_review_count_lines(text: str) -> str:
    kept = []
    for line in text.splitlines():
        if REVIEW_COUNT_LINE_RE.match(line.strip()) or line.strip().lower() == "medical center reviews":
            continue
        kept.append(line)
    return "\n".join(kept).strip()


def _is_review_count_only(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return bool(lines) and all(REVIEW_COUNT_LINE_RE.match(line) for line in lines)


def _drop_broken_range_sentence(text: str) -> str:
    cleaned = BROKEN_RANGE_SENTENCE_RE.sub("", text)
    return "\n".join(line for line in (_collapse(part) for part in cleaned.splitlines()) if line).strip()


def _without_video_title_list(text: str) -> str:
    kept = [line for line in text.splitlines() if "medical center videos" not in line.lower()]
    return "\n".join(kept).strip()


def _real_text_length(text: str) -> int:
    return len(_collapse(text))


def _clean_sections(sections: list[dict], *, page: SourcePage, comparison: bool) -> list[dict]:
    cleaned: list[dict] = []
    for index, section in enumerate(sections):
        heading = section["heading"]
        count_area = index == 0 or heading.strip().lower() == "medical center reviews"
        text = _strip_view_counts(_strip_templates(section["text"]), count_area=count_area)
        text = _strip_ui_strings(text)
        if _is_review_count_only(text) or heading.strip().lower() == "medical center reviews":
            logger.info("dropping review-count section %s: %s", page.page_id, heading)
            continue
        text = _strip_review_count_lines(text)
        tables = [[_strip_ui_strings(row) for row in table] for table in section["tables"]]
        tables = [[row for row in table if row] for table in tables]
        tables = [table for table in tables if table]
        if comparison and heading.strip().lower() == "medical center reviews":
            text = _drop_starting_price_lines(text)
        if "often not included" in heading.lower():
            text = OFTEN_NOT_INCLUDED_INTRO_RE.sub("", text)
            text = "\n".join(line for line in (_collapse(part) for part in text.splitlines()) if line)
        if page.page_type == "price_list" and "prices range between in tijuana" in text.lower():
            text = _drop_broken_range_sentence(text)
        if page.page_type == "clinic_videos" and heading.strip().lower() == "center details":
            text = _without_video_title_list(text)
        section = {**section, "text": text.strip(), "tables": tables}
        if _is_review_count_only(section["text"]):
            logger.info("dropping review-count section %s: %s", page.page_id, heading)
            continue
        has_price = "$" in section["text"] or "usd" in section["text"].lower() or bool(section["tables"])
        if section["text"] and _real_text_length(section["text"]) < MIN_REAL_TEXT and not has_price:
            logger.info(
                "dropping short section %s: %s (%s chars)",
                page.page_id,
                heading,
                _real_text_length(section["text"]),
            )
            continue
        if section["text"] or section["tables"]:
            cleaned.append(section)
    return cleaned


def _collapse_video_titles(sections: list[dict]) -> list[dict]:
    titles = [section["heading"] for section in sections if section.get("is_video_title")]
    if not titles:
        return sections
    kept = [section for section in sections if not section.get("is_video_title")]
    block = {"heading": "Clinic video titles", "text": "\n".join(titles), "tables": []}
    insert_at = len(kept)
    for index, section in enumerate(kept):
        if section["heading"].strip().lower() in {"recent reviews", "jana c", "chris p", "frank h"}:
            insert_at = index
            break
    kept.insert(insert_at, block)
    return kept


def _render_aside(aside: Tag) -> str:
    lines: list[str] = []
    title = aside.select_one(".about-title-img-row a")
    if title is not None:
        label = _collapse(title.get_text(" ", strip=True))
        if label:
            lines.append(label)
    items = aside.find("ul")
    if items is not None:
        rendered = _render_list(items)
        if rendered:
            lines.append(rendered)
    for button in aside.find_all("button"):
        label = _collapse(button.get_text(" ", strip=True))
        if label:
            lines.append(label)
    return "\n".join(lines)


def _append_unheaded_asides(soup: BeautifulSoup, sections: list[dict]) -> None:
    """A center card with no heading was being swallowed by the previous review."""
    for aside in soup.select("div.pack-about-aside"):
        if aside.find(["h1", "h2", "h3"]):
            continue
        text = _render_aside(aside).strip()
        if not text:
            continue
        sections.append({"heading": "Center details", "text": text, "tables": []})


def _section_type(section: dict) -> str:
    heading = section["heading"].strip()
    lower = heading.lower()
    text = section["text"].lower()
    if lower == "clinic video titles":
        return "video_list"
    if lower in {"center details", "about medical center", "about package"}:
        return "center_details"
    if lower == "location" and any(marker in text for marker in ("price range", "packages:", "blvd.")):
        return "center_details"
    if lower in REVIEWER_HEADINGS or lower.startswith("what do real families say") or lower.endswith(" reviews"):
        return "testimonial"
    if (
        section["tables"]
        or lower == "package price"
        or lower.startswith("quick facts")
        or lower.startswith("cost of ")
        or "pricings" in lower
        or lower.startswith("how much does")
        or lower.startswith("cost breakdown")
        or lower.startswith("which clinics")
    ):
        return "price_table"
    if "frequently asked" in lower or lower.startswith("faqs") or re.match(r"^\d+\.\s", heading):
        return "faq"
    if lower.endswith("?") and not lower.startswith(
        ("who should consider", "ready to explore", "what is usually included")
    ):
        return "faq"
    return "content"


def _finalize_sections(soup: BeautifulSoup, page: SourcePage) -> list[dict]:
    sections = _sections_from_soup(soup)
    if page.page_type == "package":
        _move_package_starting_price(sections)
    if page.page_type == "clinic_videos":
        sections = _collapse_video_titles(sections)
    _append_unheaded_asides(soup, sections)
    sections = _clean_sections(sections, page=page, comparison=page.page_type == "price_comparison")
    finalized: list[dict] = []
    for section in sections:
        section.pop("is_video_title", None)
        finalized.append(
            {
                "heading": section["heading"],
                "section_type": _section_type(section),
                "text": section["text"],
                "tables": section["tables"],
            }
        )
    return finalized


def _price_meta(soup: BeautifulSoup) -> dict[str, str | None] | None:
    amount = soup.find("meta", attrs={"property": "product:price.amount"})
    currency = soup.find("meta", attrs={"property": "product:price.currency"})
    if amount is None and currency is None:
        return None
    return {
        "price_amount": amount.get("content") if amount is not None else None,
        "price_currency": currency.get("content") if currency is not None else None,
    }


def _move_package_starting_price(sections: list[dict]) -> None:
    """The visible '$… Price starting from' sits after the reviews heading."""
    moved: list[str] = []
    for section in sections:
        if section["heading"].strip().lower() == "package price":
            continue
        kept: list[str] = []
        lines = section["text"].splitlines()
        index = 0
        while index < len(lines):
            line = lines[index]
            nxt = lines[index + 1] if index + 1 < len(lines) else ""
            if STARTING_PRICE_RE.search(line):
                if kept and PRICE_ONLY_RE.match(kept[-1]):
                    moved.append(kept.pop())
                moved.append(line)
            elif PRICE_ONLY_RE.match(line) and STARTING_PRICE_RE.search(nxt):
                moved.append(line)
            else:
                kept.append(line)
            index += 1
        section["text"] = "\n".join(kept).strip()
    if not moved:
        return
    block = "\n".join(moved)
    for section in sections:
        if section["heading"].strip().lower() == "package price":
            section["text"] = "\n".join(part for part in (block, section["text"]) if part).strip()
            return
    sections.insert(0, {"heading": "Package Price", "text": block, "tables": []})


def _document(
    soup: BeautifulSoup,
    page: SourcePage,
    sections: list[dict],
    meta: dict[str, str | None] | None = None,
) -> dict:
    h1 = soup.find("h1")
    title = _heading_text(h1) if isinstance(h1, Tag) else ""
    if not title and soup.title:
        title = _collapse(soup.title.get_text(" ", strip=True))
    document = {
        "url": page.url,
        "page_type": page.page_type,
        "title": title,
    }
    if meta is not None:
        document["meta"] = meta
    document["sections"] = sections
    return document


def extract_clinic_profile(soup: BeautifulSoup, page: SourcePage) -> dict:
    return _document(soup, page, _finalize_sections(soup, page))


def extract_package(soup: BeautifulSoup, page: SourcePage) -> dict:
    meta = _price_meta(soup)
    return _document(soup, page, _finalize_sections(soup, page), meta=meta)


def extract_clinic_videos(soup: BeautifulSoup, page: SourcePage) -> dict:
    return _document(soup, page, _finalize_sections(soup, page))


def extract_price_list(soup: BeautifulSoup, page: SourcePage) -> dict:
    return _document(soup, page, _finalize_sections(soup, page))


def extract_price_comparison(soup: BeautifulSoup, page: SourcePage) -> dict:
    return _document(soup, page, _finalize_sections(soup, page))


EXTRACTORS = {
    "clinic_profile": extract_clinic_profile,
    "package": extract_package,
    "clinic_videos": extract_clinic_videos,
    "price_list": extract_price_list,
    "price_comparison": extract_price_comparison,
}


def extract_page(page: SourcePage) -> dict:
    html_path = RAW_DIR / f"{page.page_id}.html"
    if not html_path.exists():
        raise FileNotFoundError(f"Missing cached HTML for {page.page_id}: {html_path}")
    soup = BeautifulSoup(html_path.read_bytes(), "lxml")
    extractor = EXTRACTORS[page.page_type]
    document = extractor(soup, page)
    KB_DIR.mkdir(parents=True, exist_ok=True)
    out_path = KB_DIR / f"{page.page_id}.json"
    out_path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("wrote %s (%s sections)", out_path.name, len(document["sections"]))
    return document


def extract_all() -> list[dict]:
    return [extract_page(page) for page in PAGES]


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    extract_all()


if __name__ == "__main__":
    main()
