import requests
import sqlite3
import time
import random
from pathlib import Path
from datetime import datetime

# =============================
# CONFIG
# =============================
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "cars.db"

API_URL = "https://www.olx.ua/api/v1/offers"

MIN_PRICE_UAH = 2000
MAX_PRICE_UAH = 300000

SLEEP_MIN = 8 * 60
SLEEP_MAX = 12 * 60

KYIV_KEYWORDS = [
    "київ", "киев", "kyiv",
    "київська", "киевская",
    "область", "обл"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Accept-Language": "uk-UA,uk;q=0.9,ru-UA;q=0.8,ru;q=0.7",
}

# =============================
# DB
# =============================
def init_db():
    conn = sqlite3.connect(DB_PATH)
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
            created_at TEXT,
            price_uah INTEGER
        )
    """)
    conn.commit()
    conn.close()


def save_car(car: dict):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        INSERT OR IGNORE INTO cars (
            id, title, price_value, price_currency,
            location, image_url, ad_url,
            created_at, price_uah
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        car["id"],
        car["title"],
        car["price_value"],
        car["price_currency"],
        car["location"],
        car["image_url"],
        car["ad_url"],
        car["created_at"],
        car["price_uah"],
    ))
    conn.commit()
    conn.close()


# =============================
# HELPERS
# =============================
def normalize(text: str) -> str:
    return (text or "").lower()


def location_ok(location: str) -> bool:
    loc = normalize(location)
    return any(k in loc for k in KYIV_KEYWORDS)


def price_to_uah(price: dict) -> int | None:
    if not price:
        return None
    if price.get("currency") != "UAH":
        return None
    return price.get("value")


def is_car(offer: dict) -> bool:
    cat = offer.get("category") or {}
    slug = cat.get("slug", "")
    parent = cat.get("parent", "")
    return slug == "transport" or parent == "transport"


# =============================
# MAIN
# =============================
def fetch_page(offset: int):
    params = {
        "offset": offset,
        "limit": 50,
    }
    return requests.get(API_URL, headers=HEADERS, params=params, timeout=15)


def main():
    init_db()
    print("🚀 OLX API monitor started (Kyiv / Kyiv region)\n")

    matched = 0
    filtered_price = 0
    filtered_location = 0
    filtered_category = 0

    for offset in (0, 50, 100):
        r = fetch_page(offset)
        print(f"HTTP {r.status_code} | offset={offset}")

        if r.status_code != 200:
            print("❌ API rejected request:", r.text[:150])
            continue

        offers = r.json().get("data", [])
        print(f"ℹ Offers at offset {offset}: {len(offers)}")

        for o in offers:
            if not is_car(o):
                filtered_category += 1
                continue

            price_uah = price_to_uah(o.get("price"))
            if not price_uah or not (MIN_PRICE_UAH <= price_uah <= MAX_PRICE_UAH):
                filtered_price += 1
                continue

            location = o.get("location", {}).get("label", "")
            if not location_ok(location):
                filtered_location += 1
                continue

            photos = o.get("photos") or []
            image_url = ""
            if photos:
                image_url = photos[0]["link"].replace("{width}", "640").replace("{height}", "480")

            car = {
                "id": o["id"],
                "title": o.get("title"),
                "price_value": o.get("price", {}).get("value"),
                "price_currency": o.get("price", {}).get("currency"),
                "location": location,
                "image_url": image_url,
                "ad_url": o.get("url"),
                "created_at": datetime.utcnow().isoformat(),
                "price_uah": price_uah,
            }

            save_car(car)
            matched += 1

    print(f"\n✅ Total matched cars: {matched}")
    print(f"❌ Filtered by category: {filtered_category}")
    print(f"❌ Filtered by price: {filtered_price}")
    print(f"❌ Filtered by location: {filtered_location}")

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
