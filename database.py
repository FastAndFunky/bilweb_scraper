"""
SQLite database helpers.

Deduplication is handled by the UNIQUE constraint on `unique_key`,
which is now a composite of  reg.nr | price | seller.
→ Same car, same price, same seller  → INSERT fails (duplicate) → skip.
→ Same car, new price or new seller  → INSERT succeeds → new row.
"""

import sqlite3
import os
from config import DB_PATH


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def create_tables():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS listings (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            unique_key          TEXT    UNIQUE NOT NULL,
            modell_ar           TEXT,
            miltal_km           INTEGER,
            pris_sek            INTEGER,
            plats               TEXT,
            saljare             TEXT,
            privat              TEXT,
            utrustningspaket    TEXT,
            registreringsnummer TEXT,
            datum_listad        TEXT,
            utrustning          TEXT,
            detail_url          TEXT,
            scraped_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    # Index for fast reg.nr lookups (useful for future queries)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_reg_nr
        ON listings (registreringsnummer);
    """)
    conn.commit()
    conn.close()


def listing_exists(unique_key: str) -> bool:
    conn = get_connection()
    cur = conn.execute(
        "SELECT 1 FROM listings WHERE unique_key = ?", (unique_key,)
    )
    exists = cur.fetchone() is not None
    conn.close()
    return exists


def insert_listing(data: dict) -> bool:
    """
    Insert a listing.
    Returns True if inserted, False if an identical
    (reg.nr + price + seller) row already exists.
    """
    unique_key = data.get("unique_key", "")
    if not unique_key:
        return False

    if listing_exists(unique_key):
        return False

    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO listings (
                unique_key, modell_ar, miltal_km, pris_sek, plats,
                saljare, privat, utrustningspaket, registreringsnummer,
                datum_listad, utrustning, detail_url
            ) VALUES (
                :unique_key, :modell_ar, :miltal_km, :pris_sek, :plats,
                :saljare, :privat, :utrustningspaket, :registreringsnummer,
                :datum_listad, :utrustning, :detail_url
            )
            """,
            {
                "unique_key":          unique_key,
                "modell_ar":           data.get("modell_ar", ""),
                "miltal_km":           data.get("miltal_km"),
                "pris_sek":            data.get("pris_sek"),
                "plats":               data.get("plats", ""),
                "saljare":             data.get("saljare", ""),
                "privat":              data.get("privat", ""),
                "utrustningspaket":    data.get("utrustningspaket", ""),
                "registreringsnummer": data.get("registreringsnummer", ""),
                "datum_listad":        data.get("datum_listad", ""),
                "utrustning":          data.get("utrustning", ""),
                "detail_url":          data.get("detail_url", ""),
            },
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        # Race condition guard — another process inserted the same key
        return False
    finally:
        conn.close()


def export_csv():
    import pandas as pd
    from config import CSV_PATH

    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT registreringsnummer, modell_ar, miltal_km, pris_sek,
               plats, saljare, privat, utrustningspaket,
               datum_listad, utrustning, detail_url, scraped_at
        FROM listings
        ORDER BY scraped_at DESC
        """,
        conn,
    )
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig", sep=";")
    conn.close()
    print(f"[CSV] Exported {len(df)} rows → {CSV_PATH}")