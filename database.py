"""SQLite database helpers with auto-migration."""

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
            marke               TEXT,
            modell              TEXT,
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
            battery_kwh         INTEGER,
            rackvidd_km         INTEGER,
            detail_url          TEXT,
            scraped_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_reg_nr
        ON listings (registreringsnummer);
    """)
    conn.commit()

    for col, col_type in [
        ("battery_kwh", "INTEGER"),
        ("rackvidd_km", "INTEGER"),
        ("marke",       "TEXT"),
        ("modell",      "TEXT"),
    ]:
        try:
            conn.execute(f"ALTER TABLE listings ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass
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
                unique_key, marke, modell, modell_ar, miltal_km,
                pris_sek, plats, saljare, privat, utrustningspaket,
                registreringsnummer, datum_listad, utrustning,
                battery_kwh, rackvidd_km, detail_url
            ) VALUES (
                :unique_key, :marke, :modell, :modell_ar, :miltal_km,
                :pris_sek, :plats, :saljare, :privat, :utrustningspaket,
                :registreringsnummer, :datum_listad, :utrustning,
                :battery_kwh, :rackvidd_km, :detail_url
            )
            """,
            {
                "unique_key":          unique_key,
                "marke":               data.get("marke", ""),
                "modell":              data.get("modell", ""),
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
                "battery_kwh":         data.get("battery_kwh"),
                "rackvidd_km":         data.get("rackvidd_km"),
                "detail_url":          data.get("detail_url", ""),
            },
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def export_csv():
    import pandas as pd
    from config import CSV_PATH

    conn = get_connection()
    df = pd.read_sql_query(
        """
        SELECT marke, modell, registreringsnummer, modell_ar,
               miltal_km, pris_sek, battery_kwh, rackvidd_km,
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
