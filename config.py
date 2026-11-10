"""
Configuration for the bilweb.se EV scraper.
═══════════════════════════════════════════════════════════════
  ✏️  EASY SETTINGS — edit ONLY this section
═══════════════════════════════════════════════════════════════
"""

MIN_PRICE = 15_000
MAX_PRICE = 260_000

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
  ⚙️  ADVANCED SETTINGS
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
        params = [
            f"make={make}",
            f"model={model}",
            f"priceFrom={MIN_PRICE}",
            f"priceTo={MAX_PRICE}",
        ]
        if "year_from" in car:
            params.append(f"yearFrom={car['year_from']}")
        if "year_to" in car:
            params.append(f"yearTo={car['year_to']}")
        params.append("page={page}")

        url = f"{BASE_URL}/sok?{'&'.join(params)}"

        filters = {}
        if "battery_kwh_min" in car:
            filters["battery_kwh_min"] = car["battery_kwh_min"]
        if "battery_kwh_max" in car:
            filters["battery_kwh_max"] = car["battery_kwh_max"]

        label = f"{make} {model}"
        if "year_from" in car:
            label += f" {car['year_from']}-{car.get('year_to', 'now')}"
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
