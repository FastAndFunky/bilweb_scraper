#!/usr/bin/env python3
"""
Multi-model EV scraper for bilweb.se.
Dedup: unique_key = "{reg.nr}|{price}|{seller}"
"""

import time
import logging
import requests

from config import SEARCH_QUERIES, MIN_PRICE, MAX_PRICE, HEADERS, REQUEST_DELAY
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
    reg    = data.get("registreringsnummer", "").strip()
    price  = data.get("pris_sek", "")
    seller = data.get("saljare", "").strip()
    identifier = reg if reg else data.get("_vehicle_id", data.get("detail_url", ""))
    return f"{identifier}|{price}|{seller}"


def passes_filters(data: dict, filters: dict) -> bool:
    if "battery_kwh_min" in filters or "battery_kwh_max" in filters:
        kwh = data.get("battery_kwh")
        if kwh is None:
            return False
        lo = filters.get("battery_kwh_min", 0)
        hi = filters.get("battery_kwh_max", 9999)
        if not (lo <= kwh <= hi):
            return False

    price = data.get("pris_sek")
    if price is not None:
        if price < MIN_PRICE or price > MAX_PRICE:
            return False

    return True


def run_scraper():
    create_tables()

    log.info(f"Price range: {MIN_PRICE:,} – {MAX_PRICE:,} kr")
    log.info(f"Tracking {len(SEARCH_QUERIES)} queries")

    total_new = 0
    total_skip = 0
    total_filtered = 0

    for query in SEARCH_QUERIES:
        q_name   = query["name"]
        q_url    = query["url"]
        q_filt   = query.get("filters", {})
        q_marke  = query.get("make", "")
        q_modell = query.get("model", "")

        log.info(f"\n{'='*60}")
        log.info(f"  QUERY: {q_name}")
        log.info(f"{'='*60}")

        page = 1
        while True:
            url = q_url.format(page=page)
            log.info(f"--- {q_name} — page {page} ---")

            try:
                html = fetch(url)
            except requests.HTTPError as exc:
                log.error(f"HTTP {exc.response.status_code}. Stopping.")
                break

            stubs = parse_search_page(html)
            if not stubs:
                log.info("No listings on this page.")
                break

            for stub in stubs:
                detail_url = stub.get("detail_url", "")
                if not detail_url:
                    continue

                stub["_vehicle_id"] = stub.get("unique_key", "")

                try:
                    detail_html = fetch(detail_url)
                    detail_data = parse_detail_page(detail_html, detail_url)
                except Exception as exc:
                    log.warning(f"Detail failed ({detail_url}): {exc}")
                    detail_data = {
                        "marke": "", "modell": "",
                        "registreringsnummer": "", "utrustning": "",
                        "battery_kwh": None, "rackvidd_km": None,
                    }

                # ── Merge ──
                listing = stub.copy()
                detail_rv = detail_data.pop("rackvidd_km", None)
                listing.update(detail_data)
                if detail_rv is not None:
                    listing["rackvidd_km"] = detail_rv

                # ── Fallback: config values if <h1> didn't yield anything ──
                if not listing.get("marke"):
                    listing["marke"] = q_marke
                if not listing.get("modell"):
                    listing["modell"] = q_modell

                # ── Filters ──
                if not passes_filters(listing, q_filt):
                    total_filtered += 1
                    continue

                # ── Dedup ──
                listing["unique_key"] = build_unique_key(listing)

                # ── Insert ──
                inserted = insert_listing(listing)
                if inserted:
                    total_new += 1
                    log.info(
                        f"  ✅  NEW  "
                        f"{listing.get('registreringsnummer', '???'):<8s}  "
                        f"{listing.get('marke', '?')} "
                        f"{listing.get('modell', '?')} "
                        f"{listing.get('modell_ar', '?')}  "
                        f"{listing.get('pris_sek', '?'):>7,} kr  "
                        f"{listing.get('battery_kwh', '?')} kWh  "
                        f"{listing.get('rackvidd_km', '?')} km"
                    )
                else:
                    total_skip += 1

            if not has_next_page(html):
                break
            page += 1

    log.info(
        f"\n{'='*60}\n"
        f"  DONE  ✅ {total_new} new  ⏭️ {total_skip} skipped  "
        f"🚫 {total_filtered} filtered\n"
        f"{'='*60}"
    )
    export_csv()


if __name__ == "__main__":
    run_scraper()
