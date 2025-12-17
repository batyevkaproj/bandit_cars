import requests
import time
import random
import sqlite3
import os
from datetime import datetime, timezone

# ===================== CONFIG =====================

API_URL = "https://www.olx.ua/api/v1/offers/"
CATEGORY_ID = 108

MAX_PRICE_USD = 2000
USD_TO_UAH = 40  # грубий фільтр

CHECK_MIN = 8
CHECK_MAX = 12
OFFSETS = [0, 50, 100]

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "olx.db")

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://www.olx.ua/",
}

BASE_PARAMS = {
    "category_id": CATEGORY_ID,
    "sort_by": "created_at:desc",
    "limit": 50,
}

# ===================== DB =====================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # базова таблиця
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cars (
            id TEXT PRIMARY KEY,
            title TEXT,
            price_value INTEGER,
            price_currency TEXT,
            location TEXT,
            image_url TEXT,
            ad_url TEXT,
            created_at TEXT
        )
    """)

    # ---- АВТО-МІГРАЦІЯ ----
    cols = [r[1] for r in cur.execute("PRAGMA table_info(cars)").fetchall()]
    if "price_uah" not in cols:
        print("🛠 DB migration: adding column price_uah")
        cur.execute("ALTER TABLE cars ADD COLUMN price_uah INTEGER")

    conn.commit()
    return conn

def save_car(conn, car):
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO cars
        (id, title, price_value, price_currency, price_uah,
         location, image_url, ad_url, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        car["id"],
        car["title"],
        car["price_value"],
        car["price_currency"],
        car["price_uah"],
        car["location"],
        car["image_url"],
        car["ad_url"],
        car["created_at"]
    ))
    conn.commit()

# ===================== UTILS =====================

def random_sleep():
    sec = int(random.uniform(CHECK_MIN, CHECK_MAX) * 60)
    print(f"\n⏳ Sleeping {sec//60} min {sec%60} sec...\n")
    time.sleep(sec)

def extract_location(o):
    loc = o.get("location")
    if isinstance(loc, dict):
        city = loc.get("city")
        if isinstance(city, dict):
            return city.get("name")
        if isinstance(city, str):
            return city
    return None

def extract_price(o):
    for p in o.get("params") or []:
        if p.get("key") == "price":
            v = p.get("value") or {}
            value = v.get("value")
            currency = v.get("currency")

            if not value or not currency:
                return None

            if currency == "USD":
                price_uah = int(value * USD_TO_UAH)
            elif currency == "UAH":
                price_uah = int(value)
            else:
                return None

            return int(value), currency, price_uah

    return None

# ===================== API =====================

def fetch_from_api(session):
    results = []

    for offset in OFFSETS:
        params = BASE_PARAMS | {"offset": offset}
        r = session.get(API_URL, headers=HEADERS, params=params, timeout=30)

        print(f"HTTP {r.status_code} | offset={offset}")
        if r.status_code != 200:
            continue

        offers = r.json().get("data", [])
        print(f"ℹ Offers at offset {offset}: {len(offers)}")

        for o in offers:
            price = extract_price(o)
            if not price:
                continue

            price_value, price_currency, price_uah = price

            # 🔥 ФІЛЬТР ≤ 2000$
            if price_currency == "USD" and price_value > MAX_PRICE_USD:
                continue
            if price_currency == "UAH" and price_uah > MAX_PRICE_USD * USD_TO_UAH:
                continue

            ad_url = o.get("url")
            if ad_url and ad_url.startswith("/"):
                ad_url = "https://www.olx.ua" + ad_url

            image_url = None
            photos = o.get("photos")
            if photos:
                image_url = photos[0].get("link")

            results.append({
                "id": str(o.get("id")),
                "title": o.get("title"),
                "price_value": price_value,
                "price_currency": price_currency,
                "price_uah": price_uah,
                "location": extract_location(o),
                "image_url": image_url,
                "ad_url": ad_url,
                "created_at": datetime.now(timezone.utc).isoformat()
            })

    print(f"✅ Total matched cars: {len(results)}")
    return results

# ===================== MAIN =====================

def main():
    print("🚀 OLX API monitor started\n")

    conn = init_db()
    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        while True:
            print("🔍 Checking OLX API...")
            cars = fetch_from_api(session)

            for car in cars:
                save_car(conn, car)
                print(
                    f"🚗 {car['title']} | "
                    f"{car['price_value']} {car['price_currency']} "
                    f"(~{car['price_uah']} грн) | {car['location']}"
                )
                print(car["ad_url"])
                print("-" * 70)

            random_sleep()

    except KeyboardInterrupt:
        print("\n🛑 Stopped by user")
    finally:
        conn.close()

# ===================== START =====================

if __name__ == "__main__":
    main()
