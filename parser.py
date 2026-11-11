"""
Parsing logic for bilweb.se
Search cards : #vehicle-grid > div[data-vehicle-id]
Detail page  : spec grid + full-text regex fallbacks
"""

import re
from typing import Optional
from bs4 import BeautifulSoup, Tag
from config import BASE_URL


def _text(el: Optional[Tag]) -> str:
    return el.get_text(strip=True) if el else ""


def _parse_int(raw: str) -> Optional[int]:
    digits = re.sub(r"[^\d]", "", raw)
    return int(digits) if digits else None


def _mil_to_km(raw: str) -> Optional[int]:
    value = _parse_int(raw)
    if value is None:
        return None
    if "mil" in raw.lower() and "km" not in raw.lower():
        return value * 10
    return value


def guess_trim(text: str) -> str:
    t = text.upper()
    if "ADVANCE PLUS" in t or "ADVANCE+" in t:
        return "Advance Plus"
    if "ADVANCE" in t:
        return "Advance"
    if "ESSENTIAL" in t:
        return "Essential"
    if "STYLE" in t:
        return "Style"
    if "PRO S" in t:
        return "Pro S"
    if "PRO" in t:
        return "Pro"
    if "LIFE" in t:
        return "Life"
    if "MAX" in t:
        return "Max"
    return "Okänt"


# ──────────────────────────────────────────────
#  SEARCH PAGE
# ──────────────────────────────────────────────

def parse_search_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    listings: list[dict] = []

    cards = soup.select("#vehicle-grid > div[data-vehicle-id]")

    for card in cards:
        vehicle_id = card.get("data-vehicle-id", "").strip()
        if not vehicle_id:
            continue

        link_el = card.select_one("a.absolute.inset-0[href]")
        href = link_el["href"] if link_el else ""
        if href.startswith("/"):
            href = BASE_URL + href

        title_box = card.select_one("div.absolute.left-3")
        title_h3 = _text(title_box.select_one("h3")) if title_box else ""
        title_p  = _text(title_box.select_one("h3 + p")) if title_box else ""
        full_title = f"{title_h3} {title_p}".strip()

        specs_div = card.select_one(
            "div.flex.flex-col.p-3 div.flex.items-center.flex-wrap"
        )
        spec_texts: list[str] = []
        if specs_div:
            for span in specs_div.find_all("span", recursive=False):
                t = _text(span)
                if t:
                    spec_texts.append(t)

        modell_ar, miltal_raw, rackvidd_raw = "", "", ""
        for t in spec_texts:
            tc = t.strip()
            if re.match(r"^\d{4}$", tc):
                modell_ar = tc
            elif "mil" in tc.lower():
                miltal_raw = tc
            elif "räckvidd" in tc.lower() or (
                "km" in tc.lower() and "mil" not in tc.lower()
            ):
                rackvidd_raw = tc

        if not modell_ar:
            m = re.search(r"(20(?:1[89]|2[0-5]))", full_title)
            if m:
                modell_ar = m.group(1)

        price_el = card.select_one("p.text-lg.font-medium")
        pris_sek = _parse_int(_text(price_el))

        dealer_el = card.select_one(
            "p.text-xs2.text-black.font-normal.truncate"
        )
        saljare = _text(dealer_el)

        loc_el = card.select_one("p.text-xs2.text-secondary")
        loc_spans = loc_el.find_all("span") if loc_el else []
        plats = (
            _text(loc_spans[0]).rstrip(",").strip()
            if len(loc_spans) >= 1 else ""
        )
        datum_listad = (
            _text(loc_spans[1]) if len(loc_spans) >= 2 else ""
        )

        utrustningspaket = guess_trim(full_title)
        privat = "Nej" if saljare else "Ja"

        listings.append({
            "unique_key":          vehicle_id,
            "modell_ar":           modell_ar,
            "miltal_km":           _mil_to_km(miltal_raw),
            "pris_sek":            pris_sek,
            "plats":               plats,
            "saljare":             saljare,
            "privat":              privat,
            "utrustningspaket":    utrustningspaket,
            "registreringsnummer": "",
            "datum_listad":        datum_listad,
            "utrustning":          "",
            "battery_kwh":         None,
            "rackvidd_km":         _parse_int(rackvidd_raw),
            "detail_url":          href,
        })

    return listings


# ──────────────────────────────────────────────
#  PAGINATION
# ──────────────────────────────────────────────

def has_next_page(html: str) -> bool:
    soup = BeautifulSoup(html, "lxml")
    for sel in [
        "a[rel='next']",
        "a.next",
        "li.next a",
        "button[aria-label*='nästa' i]",
        "a[aria-label*='nästa' i]",
    ]:
        if soup.select_one(sel):
            return True
    return False


# ──────────────────────────────────────────────
#  DETAIL PAGE
# ──────────────────────────────────────────────

def _spec_value(spec_grid: Tag, label: str) -> str:
    for cell in spec_grid.find_all("div", recursive=False):
        label_el = cell.find(
            "p", class_=lambda c: c and "text-gray-500" in c
        )
        if label_el and label.lower() in label_el.get_text(strip=True).lower():
            value_el = label_el.find_next_sibling(["p", "a"])
            if value_el:
                return value_el.get_text(strip=True)
    return ""


def parse_detail_page(html: str, detail_url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    full_text = soup.get_text(" ", strip=True)
    spec_grid = soup.select_one("div.grid.grid-cols-2")

    # ── 1. Registreringsnummer ──
    reg_nr = ""
    if spec_grid:
        reg_nr = _spec_value(spec_grid, "Reg.nr")
    if not reg_nr:
        m = re.search(r"\b([A-Z]{3}\s?\d{2}[A-Z0-9])\b", full_text)
        if m:
            reg_nr = m.group(1)

    # ── 2. Räckvidd (km) ──
    rackvidd_km = None
    if spec_grid:
        rv_raw = _spec_value(spec_grid, "Räckvidd")
        if rv_raw:
            rackvidd_km = _parse_int(rv_raw)
    if rackvidd_km is None:
        for pattern in [
            r"(\d{2,4})\s*km\s*räckvidd",
            r"räckvidd[:\s]+(\d{2,4})\s*km",
            r"(\d{2,4})\s*km\s*\(WLTP\)",
        ]:
            m = re.search(pattern, full_text, re.IGNORECASE)
            if m:
                rackvidd_km = int(m.group(1))
                break

    # ── 3. Battery (kWh) ──
    battery_kwh = None
    if spec_grid:
        for label in ["Batterikapacitet", "Batteri", "Battery"]:
            bat_raw = _spec_value(spec_grid, label)
            if bat_raw:
                battery_kwh = _parse_int(bat_raw)
                break
    if battery_kwh is None:
        m = re.search(r"(\d{2,3})\s*kW\s*h", full_text, re.IGNORECASE)
        if m:
            battery_kwh = int(m.group(1))
    if battery_kwh is None:
        m = re.search(r"(\d{2,3})\s*kwh", detail_url, re.IGNORECASE)
        if m:
            battery_kwh = int(m.group(1))
    if battery_kwh is None:
        title_tag = soup.find("title")
        if title_tag:
            m = re.search(r"(\d{2,3})\s*kW\s*h", title_tag.get_text(), re.IGNORECASE)
            if m:
                battery_kwh = int(m.group(1))

    # ── 4. Utrustning ──
    utrustning_items: list[str] = []
    for panel in soup.select("div.panel"):
        ul = panel.select_one("ul.columns-1")
        if not ul:
            continue
        for li in ul.find_all("li", recursive=False):
            span = li.select_one("span.text-base.text-gray-900")
            if span:
                item = span.get_text(strip=True)
                if item:
                    utrustning_items.append(item)
    utrustning = ", ".join(utrustning_items)

    return {
        "registreringsnummer": reg_nr,
        "utrustning":          utrustning,
        "battery_kwh":         battery_kwh,
        "rackvidd_km":         rackvidd_km,
    }
