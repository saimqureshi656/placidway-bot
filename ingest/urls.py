"""Allowlist of the seven PlacidWay source pages. Never fetch anything else."""

from dataclasses import dataclass


@dataclass(frozen=True)
class SourcePage:
    page_id: str
    page_type: str
    url: str


PAGES: tuple[SourcePage, ...] = (
    SourcePage(
        page_id="clinic_profile",
        page_type="clinic_profile",
        url="https://www.placidway.com/profile/5/Alternative-Cancer-Treatment-by-ITC-Immunity-Therapy-Center",
    ),
    SourcePage(
        page_id="package_7903",
        page_type="package",
        url="https://www.placidway.com/package/7903/Alternative-Adenocarcinoma-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC",
    ),
    SourcePage(
        page_id="package_7902",
        page_type="package",
        url="https://www.placidway.com/package/7902/Alternative-Adrenal-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC",
    ),
    SourcePage(
        page_id="package_7901",
        page_type="package",
        url="https://www.placidway.com/package/7901/Alternative-Anal-Cancer-Treatment-Package-in-Tijuana-Mexico-by-ITC",
    ),
    SourcePage(
        page_id="clinic_videos",
        page_type="clinic_videos",
        url="https://www.placidway.com/profile-videos/5/Alternative-Cancer-Treatment-by-ITC-Immunity-Therapy-Center",
    ),
    SourcePage(
        page_id="price_list",
        page_type="price_list",
        url="https://www.placidway.com/price-list/5/Alternative-Cancer-Treatment-by-ITC-Immunity-Therapy-Center",
    ),
    SourcePage(
        page_id="price_comparison",
        page_type="price_comparison",
        url="https://www.placidway.com/search-medical-pricings/Alternative-Medicine/All/1",
    ),
)

PAGES_BY_ID: dict[str, SourcePage] = {page.page_id: page for page in PAGES}
ALLOWLIST: frozenset[str] = frozenset(page.url for page in PAGES)


def assert_allowed(url: str) -> None:
    if url not in ALLOWLIST:
        raise ValueError(f"Refusing to request a URL that is not on the allowlist: {url}")
