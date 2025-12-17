import requests
import time
import random
import sqlite3
from datetime import datetime
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "olx.db")

# ================= CONFIG =================

API_URL = "https://www.olx.ua/api/v1/offers/"

MAX_PRICE_USD = 1500

CHECK_MIN = 8
CHECK_MAX = 12



HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json",
    "Accept-Language": "uk-UA,uk;q=0.9,en;q=0.8",
    "Referer": "https://www.olx.ua/",
}

PARAMS = {
    "category_id": 108,          # Легкові авто
    "currency": "USD",
    "sort_by": "created_at:desc",
    "limit": 50,
    "offset": 0
}

# ================= DB =================

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
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
    conn.commit()
    return conn

def save_car(conn, car):
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO cars
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        car["id"],
        car["title"],
        car["price_value"],
        car["price_currency"],
        car["location"],
        car["image_url"],
        car["ad_url"],
        car["created_at"]
    ))
    conn.commit()

# ================= UTILS =================

def random_sleep():
    sec = int(random.uniform(CHECK_MIN, CHECK_MAX) * 60)
    print(f"\n⏳ Sleeping {sec//60} min {sec%60} sec...\n")
    time.sleep(sec)

# ================= API SCRAPER =================

def fetch_from_api(session):
    r = session.get(API_URL, headers=HEADERS, params=PARAMS, timeout=30)

    print(f"HTTP: {r.status_code}")

    if r.status_code != 200:
        return []

    data = r.json()

    offers = data.get("data", [])
    print(f"ℹ Offers from API: {len(offers)}")

    results = []

    for o in offers:
        price = o.get("price", {})
        value = price.get("value")
        currency = price.get("currency")

        if currency != "USD" or value is None or value > MAX_PRICE_USD:
            continue

        photos = o.get("photos", [])
        image_url = photos[0].get("link") if photos else None

        results.append({
            "id": str(o.get("id")),
            "title": o.get("title"),
            "price_value": value,
            "price_currency": currency,
            "location": o.get("location", {}).get("city"),
            "image_url": image_url,
            "ad_url": o.get("url"),
            "created_at": datetime.utcnow().isoformat()
        })

    return results

# ================= MAIN =================

def main():
    print("🚀 OLX API monitor started")
    print("💡 Stop with Ctrl + C\n")

    conn = init_db()

    session = requests.Session()
    session.headers.update(HEADERS)

    try:
        while True:
            print("🔍 Checking OLX API...")

            cars = fetch_from_api(session)

            if not cars:
                print("ℹ No matching cars found")

            for car in cars:
                save_car(conn, car)

                print("\n🚗 NEW CAR")
                print("📌", car["title"])
                print("💲", car["price_value"], car["price_currency"])
                print("📍", car["location"])
                print("🖼", car["image_url"])
                print("🔗", car["ad_url"])
                print("🕒", car["created_at"])
                print("-" * 70)

            random_sleep()

    except KeyboardInterrupt:
        print("\n🛑 Stopped by user")
    finally:
        conn.close()

if __name__ == "__main__":
    main()
