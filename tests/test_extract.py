from pathlib import Path

from bs4 import BeautifulSoup

from ingest.extract import _sections_from_soup

FIXTURE = Path(__file__).parent / "fixtures" / "boilerplate.html"


def test_boilerplate_heading_removed_and_table_kept():
    soup = BeautifulSoup(FIXTURE.read_bytes(), "lxml")
    sections = _sections_from_soup(soup)
    headings = [section["heading"] for section in sections]
    assert not any("free quote" in heading.lower() for heading in headings)
    assert any("Included in the program" == heading for heading in headings)
    tables = [row for section in sections for table in section["tables"] for row in table]
    assert any("$30,000" in row for row in tables)
    assert any("In-Patient Program" in row for row in tables)
