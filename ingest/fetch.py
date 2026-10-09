"""Fetch the seven allowlisted pages and cache raw HTML.

Checks robots.txt before each page. One request per second. Three retries
with exponential backoff on 5xx responses and timeouts.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from ingest.urls import ALLOWLIST, PAGES, SourcePage, assert_allowed

logger = logging.getLogger(__name__)

USER_AGENT = "PlacidWayAssessmentBot/1.0 (+mailto:saimqureshi656@gmail.com)"
TIMEOUT_SECONDS = 20.0
MAX_RETRIES = 3
REQUEST_INTERVAL_SECONDS = 1.0

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
MANIFEST_PATH = RAW_DIR / "manifest.json"


def _robots_url(page_url: str) -> str:
    parsed = urlparse(page_url)
    return f"{parsed.scheme}://{parsed.netloc}/robots.txt"


def _request(client: httpx.Client, url: str) -> httpx.Response:
    """GET url. Retry up to MAX_RETRIES times on 5xx and timeouts."""
    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            response = client.get(url, timeout=TIMEOUT_SECONDS)
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_error = exc
            if attempt >= MAX_RETRIES:
                break
            delay = 2**attempt
            logger.warning(
                "timeout/transport error for %s (retry %s/%s in %ss): %s",
                url,
                attempt + 1,
                MAX_RETRIES,
                delay,
                exc,
            )
            time.sleep(delay)
            continue

        if response.status_code >= 500:
            last_error = httpx.HTTPStatusError(
                f"server error {response.status_code}",
                request=response.request,
                response=response,
            )
            if attempt >= MAX_RETRIES:
                break
            delay = 2**attempt
            logger.warning(
                "HTTP %s for %s (retry %s/%s in %ss)",
                response.status_code,
                url,
                attempt + 1,
                MAX_RETRIES,
                delay,
            )
            time.sleep(delay)
            continue

        return response

    assert last_error is not None
    raise last_error


def _load_robots(client: httpx.Client, sample_url: str) -> RobotFileParser:
    """Fetch robots.txt for the allowlist origin only.

    robots.txt is not a knowledge-base page. It is requested solely so
    urllib.robotparser can decide whether each allowlisted URL may be fetched.
    """
    robots_url = _robots_url(sample_url)
    if urlparse(robots_url).netloc != urlparse(sample_url).netloc:
        raise ValueError(f"Refusing robots URL on a different host: {robots_url}")
    response = _request(client, robots_url)
    parser = RobotFileParser()
    parser.parse(response.text.splitlines())
    return parser


def _manifest_entry(
    url: str,
    status: int | str,
    body: bytes | None = None,
    etag: str | None = None,
    last_modified: str | None = None,
) -> dict:
    return {
        "url": url,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "sha256": hashlib.sha256(body).hexdigest() if body is not None else None,
        "etag": etag,
        "last_modified": last_modified,
    }


def fetch_page(
    client: httpx.Client,
    robots: RobotFileParser,
    page: SourcePage,
) -> dict:
    assert_allowed(page.url)
    if not robots.can_fetch(USER_AGENT, page.url):
        logger.warning("robots.txt disallows %s; skipping", page.url)
        return _manifest_entry(page.url, "disallowed")

    try:
        response = _request(client, page.url)
    except (httpx.TimeoutException, httpx.TransportError, httpx.HTTPStatusError) as exc:
        logger.error("failed to fetch %s: %s", page.url, exc)
        return _manifest_entry(page.url, "error")

    if response.status_code != 200:
        logger.error("HTTP %s for %s; not caching body", response.status_code, page.url)
        return _manifest_entry(
            page.url,
            response.status_code,
            etag=response.headers.get("etag"),
            last_modified=response.headers.get("last-modified"),
        )

    body = response.content
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"{page.page_id}.html").write_bytes(body)
    logger.info("saved %s (%s bytes)", page.page_id, len(body))
    return _manifest_entry(
        page.url,
        response.status_code,
        body=body,
        etag=response.headers.get("etag"),
        last_modified=response.headers.get("last-modified"),
    )


def fetch_all() -> dict[str, dict]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, dict] = {}
    headers = {"User-Agent": USER_AGENT}
    with httpx.Client(headers=headers, follow_redirects=False) as client:
        robots = _load_robots(client, PAGES[0].url)
        for page in PAGES:
            if page.url not in ALLOWLIST:
                raise ValueError(f"Page URL missing from allowlist: {page.url}")
            time.sleep(REQUEST_INTERVAL_SECONDS)
            manifest[page.page_id] = fetch_page(client, robots, page)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    logger.info("wrote %s", MANIFEST_PATH)
    return manifest


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    fetch_all()


if __name__ == "__main__":
    main()
