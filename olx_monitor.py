import requests
import sqlite3
import time
import random
from pathlib import Path
from datetime import datetime, UTC

# =============================
# CONFIG
# =============================
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "cars.db"

API_URL = "https://www.olx.ua/api/v1/offers"

SLEEP_MIN = 8 * 60
SLEEP_MAX = 12 * 60

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Accept-Language": "uk-UA,uk;q=0.9,ru-UA;q=0.8,ru;q=0.7",
}

# =============================
# DB / MIGRATIONS
# =============================
REQUIRED_COLUMNS = {
    "id": "TEXT PRIMARY KEY",
    "title": "TEXT",
    "price_value": "INTEGER",
    "price_currency": "TEXT",
    "price_uah": "INTEGER",
    "price_raw": "TEXT",
    "location_raw": "TEXT",
    "image_url": "TEXT",
    "ad_url": "TEXT",
    "created_at": "TEXT",
}


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cars (
            id TEXT PRIMARY KEY
        )
    """)

    cur.execute("PRAGMA table_info(cars)")
    existing = {row[1] for row in cur.fetchall()}

    for col, col_type in REQUIRED_COLUMNS.items():
        if col not in existing:
            print(f"🛠 DB migration: adding column '{col}'")
            cur.execute(f"ALTER TABLE cars ADD COLUMN {col} {col_type}")

    conn.commit()
    conn.close()


def save_car(car: dict):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO cars (
            id, title,
            price_value, price_currency, price_uah, price_raw,
            location_raw, image_url, ad_url, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        car["id"],
        car["title"],
        car["price_value"],
        car["price_currency"],
        car["price_uah"],
        car["price_raw"],
        car["location_raw"],
        car["image_url"],
        car["ad_url"],
        car["created_at"],
    ))
    conn.commit()
    conn.close()


# =============================
# PRICE LOGIC (IMPORTANT)
# =============================
def extract_prices(price: dict):
    """
    Повертає:
    - price_value      (оригінал з OLX, напр. 3400)
    - price_currency   (USD / UAH / EUR / None)
    - price_uah        (int або None, ТІЛЬКИ якщо реально відомо)
    """
    if not price:
        return None, None, None

    value = price.get("value")
    currency = price.get("currency")
    converted = price.get("converted_value")

    price_uah = None

    if converted:
        # OLX уже порахував у гривні
        price_uah = int(converted)
    elif currency == "UAH" and value:
        price_uah = int(value)
    else:
        # USD / EUR без converted_value — НЕ знаємо грн
        price_uah = None

    return value, currency, price_uah


# =============================
# MAIN
# =============================
def fetch_page(offset: int):
    return requests.get(
        API_URL,
        headers=HEADERS,
        params={
            "offset": offset,
            "limit": 50,
        },
        timeout=15
    )


def main():
    init_db()
    print("🚀 OLX API monitor started (RAW COLLECT MODE)\n")

    saved = 0
    skipped_no_photo = 0

    for offset in (0, 50, 100):
        r = fetch_page(offset)
        print(f"HTTP {r.status_code} | offset={offset}")

        if r.status_code != 200:
            print("❌ API rejected:", r.text[:120])
            continue

        offers = r.json().get("data", [])
        print(f"ℹ Offers at offset {offset}: {len(offers)}")

        for o in offers:
            photos = o.get("photos") or []
            if not photos:
                skipped_no_photo += 1
                continue

            price_value, price_currency, price_uah = extract_prices(o.get("price"))

            car = {
                "id": o["id"],
                "title": o.get("title"),
                "price_value": price_value,
                "price_currency": price_currency,
                "price_uah": price_uah,
                "price_raw": str(o.get("price")),
                "location_raw": str(o.get("location")),
                "image_url": photos[0]["link"]
                    .replace("{width}", "640")
                    .replace("{height}", "480"),
                "ad_url": o.get("url"),
                "created_at": datetime.now(UTC).isoformat(),
            }

            save_car(car)
            saved += 1

    print(f"\n✅ Total saved cars: {saved}")
    print(f"❌ Skipped without photo: {skipped_no_photo}")

    sleep_time = random.randint(SLEEP_MIN, SLEEP_MAX)
    print(f"\n⏳ Sleeping {sleep_time // 60} min {sleep_time % 60} sec...\n")
    time.sleep(sleep_time)


if __name__ == "__main__":
    while True:
        try:
            main()
        except KeyboardInterrupt:
            print("\n🛑 Stopped by user")
            break
        except Exception as e:
            print("⚠ ERROR:", e)
            time.sleep(30)
