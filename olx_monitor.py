import sqlite3
import time
import requests
from pathlib import Path
from datetime import datetime, timezone

# =============================
# CONFIGURATION
# =============================
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "cars.db"

API_URL = "https://www.olx.ua/api/v1/offers"
CATEGORY_CARS_ID = 1532  

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "uk-UA,uk;q=0.9",
}

# =============================
# DATABASE FUNCTIONS
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
            price_uah INTEGER,
            price_raw TEXT,
            location_raw TEXT,
            image_url TEXT,
            ad_url TEXT,
            created_at TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_car_safe(car: dict) -> bool:
    """
    Saves car to DB. Returns True if it was a NEW entry.
    """
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # check total changes to detect if insert happened
    start_changes = conn.total_changes

    cur.execute("""
        INSERT OR IGNORE INTO cars (
            id, title, price_value, price_currency, price_uah, 
            price_raw, location_raw, image_url, ad_url, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        car["id"], car["title"], car["price_value"], car["price_currency"], 
        car["price_uah"], car["price_raw"], car["location_raw"], 
        car["image_url"], car["ad_url"], car["created_at"],
    ))

    conn.commit()
    was_new = (conn.total_changes > start_changes)
    conn.close()
    return was_new

# =============================
# DATA EXTRACTION
# =============================
def extract_prices(offer_data: dict):
    # 1. Try standard 'price' key
    price = offer_data.get("price")
    
    # 2. Fallback: Sometimes price is inside 'params' array
    if not price and "params" in offer_data:
        for param in offer_data["params"]:
            if param.get("key") == "price":
                price = param.get("value")
                break

    if not price:
        return None, None, None

    # Extraction
    value = price.get("value")
    currency = price.get("currency")
    converted = price.get("converted_value")

    price_uah = None
    if converted:
        price_uah = int(converted)
    elif currency == "UAH" and value:
        price_uah = int(value)
    
    return value, currency, price_uah

def fetch_page(offset: int):
    return requests.get(
        API_URL, headers=HEADERS,
        params={"offset": offset, "limit": 50, "category_id": CATEGORY_CARS_ID},
        timeout=15
    )

# =============================
# MAIN LOOP
# =============================
def main():
    init_db()
    print(f"🚀 OLX Monitor Running (Production Mode)")
    print(f"📂 Database: {DB_PATH}\n")

    while True:
        saved_count = 0
        
        # Check first 3 pages
        for offset in (0, 50, 100):
            try:
                r = fetch_page(offset)
                if r.status_code != 200:
                    print(f"⚠️ API Error {r.status_code}")
                    continue

                offers = r.json().get("data", [])
                
                for o in offers:
                    # Optional: Strict Category Check
                    # if o.get("category_id") != CATEGORY_CARS_ID: continue

                    photos = o.get("photos") or []
                    if not photos: continue

                    p_val, p_curr, p_uah = extract_prices(o)

                    car = {
                        "id": str(o["id"]),
                        "title": o.get("title"),
                        "price_value": p_val,
                        "price_currency": p_curr,
                        "price_uah": p_uah,
                        "price_raw": str(o.get("price")),
                        "location_raw": str(o.get("location")),
                        "image_url": photos[0]["link"].replace("{width}", "640").replace("{height}", "480"),
                        "ad_url": o.get("url"),
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }

                    if save_car_safe(car):
                        saved_count += 1
                        # Pretty Output
                        price_str = f"{car['price_uah']} UAH" if car['price_uah'] else "Price Negotiable/Unknown"
                        print(f"🟢 [NEW] {car['title']}")
                        print(f"   💰 {price_str}")
                        print(f"   🔗 {car['ad_url']}")
                        print(f"   🆔 {car['id']}")
                        print("-" * 40)

            except Exception as e:
                print(f"❌ Error on offset {offset}: {e}")

        if saved_count > 0:
            print(f"✅ Cycle finished. Saved {saved_count} new cars.")
        else:
            print(f"💤 No new cars found. Waiting...")

        # Wait 10 minutes before checking again
        time.sleep(600)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Stopped by user")