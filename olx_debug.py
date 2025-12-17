import sqlite3
import time
import requests
from pathlib import Path
from datetime import datetime, timezone

# =============================
# ⚙️ НАСТРОЙКИ
# =============================
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "cars.db"
API_URL = "https://www.olx.ua/api/v1/offers"
CATEGORY_CARS_ID = 1532  

STOP_WORDS = [
    "трактор", "мотоблок", "причіп", "прицеп", "скутер", 
    "мотоцикл", "квадроцикл", "навантажувач", "погрузчик", 
    "комбайн", "запчастини", "розборка", "шрот", "двигун", 
    "кпп", "сівалка", "плуг", "борона", "мопед", "велосипед",
    "scooter", "moto", "atv", "tractor"
]

SEARCH_CONFIG = {
    "q": "",                     
    "filter_float_price:from": 20000, 
    "filter_float_price:to": None,    
    "sort_by": "created_at:desc"      
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "uk-UA,uk;q=0.9",
}

# =============================
# 🗄️ БАЗА ДАННЫХ
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

def save_car_with_check(car: dict) -> bool:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
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
    
    if was_new:
        # ПРОВЕРКА ЗАПИСИ (CHECK)
        cur.execute("SELECT * FROM cars WHERE id = ?", (car['id'],))
        row = cur.fetchone()
        if row:
            db_record = dict(row)
            if db_record['title'] == car['title']:
                print(f"   ✅ [CHECK PASSED] Данные записаны и прочитаны верно.")
            else:
                print(f"   ❌ [CHECK FAILED] Ошибка целостности данных!")

    conn.close()
    return was_new

def fetch_page(offset: int):
    params = {
        "offset": offset, "limit": 50, "category_id": CATEGORY_CARS_ID,
        "sort_by": SEARCH_CONFIG["sort_by"]
    }
    if SEARCH_CONFIG["q"]: params["q"] = SEARCH_CONFIG["q"]
    if SEARCH_CONFIG["filter_float_price:from"]: params["filter_float_price:from"] = SEARCH_CONFIG["filter_float_price:from"]
    if SEARCH_CONFIG["filter_float_price:to"]: params["filter_float_price:to"] = SEARCH_CONFIG["filter_float_price:to"]

    return requests.get(API_URL, headers=HEADERS, params=params, timeout=15)

def extract_prices(offer_data: dict):
    price = offer_data.get("price")
    if not price and "params" in offer_data:
        for param in offer_data["params"]:
            if param.get("key") == "price":
                price = param.get("value")
                break
    if not price: return None, None, None
    value = price.get("value")
    currency = price.get("currency")
    converted = price.get("converted_value")
    price_uah = int(converted) if converted else (int(value) if currency == "UAH" and value else None)
    return value, currency, price_uah

# =============================
# 🚀 MAIN LOOP
# =============================
def main():
    init_db()
    print(f"🚀 ЗАПУСК В РЕЖИМЕ ОТЛАДКИ (DEBUG)")
    print(f"📂 Файл базы: {DB_PATH}")
    print("-" * 60)

    # Проверяем только 1 страницу для теста
    for offset in [0]:
        print(f"\n📡 Запрос к API (offset={offset})...")
        try:
            r = fetch_page(offset)
            print(f"   Статус ответа: {r.status_code}")
            
            if r.status_code != 200:
                print(f"   ❌ ОШИБКА API: {r.text[:200]}")
                continue

            offers = r.json().get("data", [])
            print(f"   📦 Найдено объявлений: {len(offers)}")

            if len(offers) == 0:
                print("   ⚠️ Список пуст! Возможно, слишком жесткие фильтры или сбой API.")

            count_saved = 0
            count_skipped_stopword = 0
            count_duplicate = 0

            for o in offers:
                # Фильтр категории
                if o.get("category_id") != CATEGORY_CARS_ID: 
                    # print(f"   ⏭ Пропуск: неверная категория {o.get('category_id')}")
                    continue
                
                # Фильтр стоп-слов
                title = o.get("title", "").lower()
                if any(w in title for w in STOP_WORDS):
                    count_skipped_stopword += 1
                    continue

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

                if save_car_with_check(car):
                    count_saved += 1
                    print(f"🟢 [NEW] {car['title']}")
                    print(f"   📜 DUMP (Raw DB Record): ID={car['id']}, Price={car['price_uah']}")
                    print("-" * 40)
                else:
                    count_duplicate += 1
            
            print(f"\n📊 ИТОГ СТРАНИЦЫ {offset}:")
            print(f"   ✅ Новых сохранено: {count_saved}")
            print(f"   💤 Дубликатов (уже в базе): {count_duplicate}")
            print(f"   🚫 Пропущено (стоп-слова): {count_skipped_stopword}")

        except Exception as e:
            print(f"❌ Критическая ошибка: {e}")

    print("\n🛑 Скрипт завершен.")

if __name__ == "__main__":
    main()