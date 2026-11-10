#!/usr/bin/env python3
"""
Main scraper — paginate search results, visit each detail page,
merge data, and store.

Deduplication logic:
  unique_key = "{reg.nr}|{price}|{seller}"
  → same car, same price, same seller  = SKIP
  → same car, new price or new seller  = INSERT (new row)
  → new car                            = INSERT (new row)
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
    log.info(f"GET  {url}")
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    time.sleep(REQUEST_DELAY)
    return resp.text


def build_unique_key(data: dict) -> str:
    """
    Composite key so that a listing is only re-inserted when
    the price or seller actually changes.

    Format:  "AAB52J|254900|Hedin Automotive KIA Tagene"
    Fallback (no reg.nr):  "460908|254900|Hedin Automotive KIA Tagene"
    """
    reg    = data.get("registreringsnummer", "").strip()
    price  = data.get("pris_sek", "")
    seller = data.get("saljare", "").strip()

    identifier = reg if reg else data.get("_vehicle_id", data.get("detail_url", ""))
    return f"{identifier}|{price}|{seller}"


def run_scraper():
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
            log.error(f"Search page {exc.response.status_code}. Stopping.")
            break

        stubs = parse_search_page(html)
        if not stubs:
            log.info("No listings on this page. Done paginating.")
            break

        for stub in stubs:
            detail_url = stub.get("detail_url", "")
            if not detail_url:
                continue

            # Keep the raw vehicle-id for the fallback key
            stub["_vehicle_id"] = stub.get("unique_key", "")

            # ── Fetch detail page for reg.nr + utrustning ──
            try:
                detail_html = fetch(detail_url)
                detail_data = parse_detail_page(detail_html, detail_url)
            except Exception as exc:
                log.warning(f"Detail page failed ({detail_url}): {exc}")
                detail_data = {
                    "registreringsnummer": "",
                    "utrustning": "",
                }

            # ── Merge: search-card data  +  detail-page data ──
            listing = stub.copy()
            listing.update(detail_data)

            # ── Build composite unique_key ──
            listing["unique_key"] = build_unique_key(listing)

            # ── Insert (DB UNIQUE constraint handles dedup) ──
            inserted = insert_listing(listing)
            if inserted:
                new_count += 1
                reg = listing.get("registreringsnummer", "???")
                log.info(
                    f"  ✅  NEW  {reg:<8s}  "
                    f"{listing.get('modell_ar', '?')}  "
                    f"{listing.get('pris_sek', '?')} SEK  "
                    f"{listing.get('saljare', '?'):<30s}  "
                    f"[{listing.get('utrustningspaket', '?')}]"
                )
            else:
                skip_count += 1
                log.debug(
                    f"  ⏭️  SKIP (same price & seller)  "
                    f"{listing.get('registreringsnummer', '?')}  "
                    f"{listing.get('pris_sek', '?')} SEK"
                )

        if not has_next_page(html):
            log.info("No next-page link. Done.")
            break
        page += 1

    log.info(f"=== Scrape complete: {new_count} new, {skip_count} skipped ===")
    export_csv()


if __name__ == "__main__":
    run_scraper()