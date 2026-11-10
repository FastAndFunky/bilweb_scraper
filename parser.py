"""
Parsing logic for bilweb.se
────────────────────────────
Search cards : #vehicle-grid > div[data-vehicle-id]
Detail page  : spec grid (div.grid.grid-cols-2) + equipment panel (ul.columns-1)
"""

import re
from typing import Optional
from bs4 import BeautifulSoup, Tag
from config import BASE_URL


# ──────────────────────────────────────────────────────────────
#  Helpers
# ──────────────────────────────────────────────────────────────

def _text(el: Optional[Tag]) -> str:
    return el.get_text(strip=True) if el else ""


def _parse_int(raw: str) -> Optional[int]:
    digits = re.sub(r"[^\d]", "", raw)
    return int(digits) if digits else None


def _mil_to_km(raw: str) -> Optional[int]:
    """1 mil = 10 km.  If label already says 'km', return as-is."""
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
    return "Okänt"


# ──────────────────────────────────────────────────────────────
#  SEARCH PAGE  →  list of listing dicts (card-level data)
# ──────────────────────────────────────────────────────────────

def parse_search_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    listings: list[dict] = []

    cards = soup.select("#vehicle-grid > div[data-vehicle-id]")

    for card in cards:
        vehicle_id = card.get("data-vehicle-id", "").strip()
        if not vehicle_id:
            continue

        # ── Detail link (full-card overlay <a>) ──
        link_el = card.select_one("a.absolute.inset-0[href]")
        href = link_el["href"] if link_el else ""
        if href.startswith("/"):
            href = BASE_URL + href

        # ── Title  (h3 + p inside gradient overlay) ──
        title_box = card.select_one("div.absolute.left-3")
        title_h3 = _text(title_box.select_one("h3")) if title_box else ""
        title_p  = _text(title_box.select_one("h3 + p")) if title_box else ""
        full_title = f"{title_h3} {title_p}".strip()

        # ── Spec spans  (year · mil · räckvidd · fuel) ──
        specs_div = card.select_one(
            "div.flex.flex-col.p-3 div.flex.items-center.flex-wrap"
        )
        spec_texts: list[str] = []
        if specs_div:
            for span in specs_div.find_all("span", recursive=False):
                t = _text(span)
                if t:
                    spec_texts.append(t)

        modell_ar, miltal_raw = "", ""
        for t in spec_texts:
            tc = t.strip()
            if re.match(r"^\d{4}$", tc):
                modell_ar = tc
            elif "mil" in tc.lower():
                miltal_raw = tc

        if not modell_ar:
            m = re.search(r"(20(?:19|20|21|22|23|24|25))", full_title)
            if m:
                modell_ar = m.group(1)

        # ── Price ──
        price_el = card.select_one("p.text-lg.font-medium")
        pris_sek = _parse_int(_text(price_el))

        # ── Dealer / seller ──
        dealer_el = card.select_one("p.text-xs2.text-black.font-normal.truncate")
        saljare = _text(dealer_el)

        # ── Location + listing date ──
        loc_el = card.select_one("p.text-xs2.text-secondary")
        loc_spans = loc_el.find_all("span") if loc_el else []
        plats        = _text(loc_spans[0]).rstrip(",").strip() if len(loc_spans) >= 1 else ""
        datum_listad = _text(loc_spans[1])                      if len(loc_spans) >= 2 else ""

        # ── Trim ──
        utrustningspaket = guess_trim(full_title)

        # ── Private? ──
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
            "registreringsnummer": "",          # ← filled by detail page
            "datum_listad":        datum_listad,
            "utrustning":          "",          # ← filled by detail page
            "detail_url":          href,
        })

    return listings


# ──────────────────────────────────────────────────────────────
#  PAGINATION
# ──────────────────────────────────────────────────────────────

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


# ──────────────────────────────────────────────────────────────
#  DETAIL PAGE  →  registreringsnummer + utrustning
# ──────────────────────────────────────────────────────────────

def parse_detail_page(html: str, detail_url: str) -> dict:
    """
    Extract the two fields that are only available on the detail page:
      • registreringsnummer  (from the spec grid)
      • utrustning           (from the equipment panel)
    """
    soup = BeautifulSoup(html, "lxml")

    # ──────────────────────────────────────────────
    #  1.  Registreringsnummer
    #      Spec grid:  div.grid.grid-cols-2  >  div  >  p.label + p.value
    #      Label text: "Reg.nr"
    #      Value:      <p class="text-base font-normal text-black">AAB52J</p>
    # ──────────────────────────────────────────────
    reg_nr = ""
    spec_grid = soup.select_one("div.grid.grid-cols-2")
    if spec_grid:
        for cell in spec_grid.find_all("div", recursive=False):
            label_el = cell.find(
                "p",
                class_=lambda c: c and "text-gray-500" in c,
            )
            if label_el and "Reg.nr" in label_el.get_text(strip=True):
                # Value is the next <p> or <a> sibling after the label
                value_el = label_el.find_next_sibling(["p", "a"])
                if value_el:
                    reg_nr = value_el.get_text(strip=True)
                break

    # Fallback: regex on full page text  (Swedish plates: ABC12A / ABC 12A)
    if not reg_nr:
        full_text = soup.get_text(" ", strip=True)
        m = re.search(r"\b([A-Z]{3}\s?\d{2}[A-Z0-9])\b", full_text)
        if m:
            reg_nr = m.group(1)

    # ──────────────────────────────────────────────
    #  2.  Utrustning
    #      Container:  div.panel  >  div.px-4.pb-4  >  ul.columns-1
    #      Each item:  li  >  span.text-base.text-gray-900
    # ──────────────────────────────────────────────
    utrustning_items: list[str] = []

    # Find all panels, then pick the one(s) that contain the equipment <ul>
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
    }