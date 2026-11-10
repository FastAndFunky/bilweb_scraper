#!/usr/bin/env python3
"""
Main scraper — fetches search results, follows detail pages, stores data.
"""

import time
import logging
import requests

from config import SEARCH_URL, HEADERS, REQUEST_DELAY
from database import create_tables, insert_listing, export_csv
from parser import parse_search_page, parse_detail_page, has_next_page

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)


def fetch(url: str) -> str:
    """GET a URL and return the HTML body."""
    log.info(f"GET  {url}")
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    time.sleep(REQUEST_DELAY)
    return resp.text


def run_scraper():
    """Full scrape run: paginate search → visit each listing → store."""
    create_tables()

    page = 1
    new_count = 0
    skip_count = 0

    while True:
        url = SEARCH_URL.format(page=page)
        log.info(f"--- Search page {page} ---")

        try:
            html = fetch(url)
        except requests.HTTPError as exc:
            log.error(f"Search page returned {exc.response.status_code}. Stopping.")
            break

        stubs = parse_search_page(html)
        if not stubs:
            log.info("No listings found on this page. Done paginating.")
            break

        for stub in stubs:
            detail_url = stub["detail_url"]

            try:
                detail_html = fetch(detail_url)
            except Exception as exc:
                log.warning(f"Could not fetch detail page {detail_url}: {exc}")
                continue

            listing = parse_detail_page(detail_html, detail_url)

            inserted = insert_listing(listing)
            if inserted:
                new_count += 1
                log.info(
                    f"  ✅  NEW  {listing.get('registreringsnummer', '?')}  "
                    f"{listing.get('modell_ar')}  {listing.get('pris_sek')} SEK"
                )
            else:
                skip_count += 1
                log.debug(f"  ⏭️  SKIP (duplicate) {detail_url}")

        if not has_next_page(html):
            log.info("No next page link found. Done.")
            break

        page += 1

    log.info(f"=== Scrape complete: {new_count} new, {skip_count} skipped ===")
    export_csv()


if __name__ == "__main__":
    run_scraper()