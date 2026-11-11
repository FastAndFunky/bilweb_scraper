"""
Configuration for the bilweb.se EV scraper.
═══════════════════════════════════════════════════════════════
  ✏️  EASY SETTINGS — edit ONLY this section
═══════════════════════════════════════════════════════════════
"""

# ── Price limits (ALL cars) ──
MIN_PRICE = 15_000
MAX_PRICE = 260_000

# ── Year limits (default for ALL cars, override per car below) ──
DEFAULT_YEAR_FROM = 2019
DEFAULT_YEAR_TO   = 2025

# ── Cars to track ──
CARS = [
    {
        "make": "Kia",
        "model": "e-Niro",
        "year_from": 2019,
        "year_to": 2021,
    },
    {
        "make": "Hyundai",
        "model": "Kona",
        "battery_kwh_min": 60,
        "battery_kwh_max": 68,
    },
    {
        "make": "Volkswagen",
        "model": "ID.3",
    },
]

"""
═══════════════════════════════════════════════════════════════
  ⚙️  ADVANCED — do not edit unless you know what you're doing
═══════════════════════════════════════════════════════════════
"""

BASE_URL = "https://bilweb.se"
REQUEST_DELAY = 2
DB_PATH       = "data/listings.db"
CSV_PATH      = "data/listings.csv"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "sv-SE,sv;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def _build_search_queries() -> list[dict]:
    queries = []
    for car in CARS:
        make  = car["make"]
        model = car["model"]
        yf    = car.get("year_from", DEFAULT_YEAR_FROM)
        yt    = car.get("year_to",   DEFAULT_YEAR_TO)

        params = [
            f"make={make}",
            f"model={model}",
            f"yearFrom={yf}",
            f"yearTo={yt}",
            f"priceFrom={MIN_PRICE}",
            f"priceTo={MAX_PRICE}",
            "page={page}",
        ]
        url = f"{BASE_URL}/sok?{'&'.join(params)}"

        filters = {}
        if "battery_kwh_min" in car:
            filters["battery_kwh_min"] = car["battery_kwh_min"]
        if "battery_kwh_max" in car:
            filters["battery_kwh_max"] = car["battery_kwh_max"]

        label = f"{make} {model} {yf}-{yt}"
        if "battery_kwh_min" in car:
            label += f" {car['battery_kwh_min']}-{car['battery_kwh_max']}kWh"

        queries.append({
            "name":    label,
            "url":     url,
            "filters": filters,
            "make":    make,
            "model":   model,
        })
    return queries


SEARCH_QUERIES = _build_search_queries()
