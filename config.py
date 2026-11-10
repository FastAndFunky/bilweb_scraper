"""Configuration for the Kia e-Niro scraper."""

BASE_URL = "https://bilweb.se"

# ← Verify this URL in your browser.  Bilweb may use a different query-string
#   format (e.g. /sok/kia/e-niro?yearFrom=2019&yearTo=2021&page={page}).
#   Open the search in your browser, copy the URL, and paste it here.
SEARCH_URL = (
    "https://bilweb.se/sok?"
    "make=Kia"
    "&model=e-Niro"
    "&yearFrom=2019"
    "&yearTo=2021"
    "&page={page}"
)

REQUEST_DELAY = 2          # seconds between requests
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

SCRAPE_TIME = "07:00"