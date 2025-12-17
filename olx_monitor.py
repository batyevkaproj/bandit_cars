import sqlite3
import time
import requests
from pathlib import Path
from datetime import datetime, timezone, timedelta
import random


# =============================
# ⚙️ КОНФИГУРАЦИЯ
# =============================
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "cars.db"
API_URL = "https://www.olx.ua/api/v1/offers"
CATEGORY_CARS_ID = 1532

# 🛑 СТОП-СЛОВА
STOP_WORDS = [
    "трактор", "мотоблок", "причіп", "прицеп", "скутер", 
    "мотоцикл", "квадроцикл", "навантажувач", "погрузчик", 
    "комбайн", "запчастини", "розборка", "шрот", "двигун", 
    "кпп", "сівалка", "плуг", "борона", "мопед", "велосипед",
    "scooter", "moto", "atv", "tractor", "разборка"
]

# 🔍 НАСТРОЙКИ ПОИСКА И ФИЛЬТРОВ
SEARCH_CONFIG = {
    "q": "",                          
    "filter_float_price:from": 20000, 
    "filter_float_price:to": None,    
    "sort_by": "created_at:desc",
    
    # 🔥 НОВИЙ ФІЛЬТР: Не зберігати оголошення, старіші за цю дату
    # Формат: "РРРР-ММ-ДД" (наприклад, "2023-01-01")
    # Якщо None - зберігаємо все.
    "filter_date_from": "2025-12-01" 
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "uk-UA,uk;q=0.9",
}

# =============================
# 🗄️ РАБОТА С БАЗОЙ ДАННЫХ
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

def save_car_and_verify(car: dict) -> bool:
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
    
    was_inserted = (conn.total_changes > start_changes)
    
    if was_inserted:
        cur.execute("SELECT * FROM cars WHERE id = ?", (car['id'],))
        row = cur.fetchone()
        if row:
            db_record = dict(row)
            # Виводимо реальну дату створення оголошення
            print(f"\n💾 [SAVED] ID: {db_record['id']}")
            print(f"   📅 Date:  {db_record['created_at']}") 
            print(f"   💰 Price: {db_record['price_uah']} UAH")
            print("-" * 50)

    conn.close()
    return was_inserted

# =============================
# 🛠️ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================
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

def fetch_page(offset: int):
    params = {
        "offset": offset,
        "limit": 50,
        "category_id": CATEGORY_CARS_ID,
        # "sort_by": SEARCH_CONFIG["sort_by"]  <-- ЗАКОММЕНТИРОВАЛИ ЭТО (частая причина ошибки 500)
    }
    
    # Добавляем фильтры только если они есть
    if SEARCH_CONFIG["q"]: 
        params["q"] = SEARCH_CONFIG["q"]
        
    if SEARCH_CONFIG["filter_float_price:from"]: 
        params["filter_float_price:from"] = SEARCH_CONFIG["filter_float_price:from"]
        
    if SEARCH_CONFIG["filter_float_price:to"]: 
        params["filter_float_price:to"] = SEARCH_CONFIG["filter_float_price:to"]

    # Обновленный заголовок, чтобы меньше походить на бота
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.olx.ua/",
    }

    return requests.get(API_URL, headers=headers, params=params, timeout=15)

# =============================
# 🚀 ОСНОВНОЙ ЦИКЛ
# =============================
def main():
    init_db()
    print(f"🚀 OLX Monitor запущен.")
    print(f"📂 База данных: {DB_PATH}")
    
    min_date = SEARCH_CONFIG.get("filter_date_from")
    if min_date:
        print(f"📅 Фільтр дати: зберігаємо тільки новіші за {min_date}")
    
    print("-" * 50)

    while True:
        new_cars_count = 0
        
        for offset in (0, 50, 100):
            try:
                sleep_time = random.uniform(3, 7)
                print(f"⏳ Чекаю {sleep_time:.1f} сек перед запитом...")
                time.sleep(sleep_time)

                r = fetch_page(offset)
                if r.status_code != 200:
                    print(f"⚠️ Ошибка API: {r.status_code}")
                    continue

                offers = r.json().get("data", [])
                
                for o in offers:
                    # 1. Стоп-слова
                    title = o.get("title", "").lower()
                    if any(word in title for word in STOP_WORDS): continue

                    # 2. Фото
                    photos = o.get("photos") or []
                    if not photos: continue

                    # 3. 🔥 ОТРИМАННЯ РЕАЛЬНОЇ ДАТИ
                    # API повертає created_time (напр. "2023-12-17T14:30:00+02:00")
                    real_date_str = o.get("created_time") or o.get("last_refresh_time")
                    
                    if not real_date_str:
                        # Якщо дати немає, беремо поточну
                        real_date_str = datetime.now(timezone.utc).isoformat()

                    # 4. 🔥 ФІЛЬТР ПО ДАТІ (В СКРИПТІ)
                    if min_date:
                        # Порівнюємо рядки (ISO формат дозволяє це робити коректно)
                        # Беремо перші 10 символів (YYYY-MM-DD)
                        if real_date_str[:10] < min_date:
                            # print(f"⏭ Пропуск: старе оголошення від {real_date_str[:10]}")
                            continue

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
                        "created_at": real_date_str, # Зберігаємо реальну дату
                    }

                    if save_car_and_verify(car):
                        new_cars_count += 1
                        print(f"🟢 [NEW] {car['title']}")
                        print(f"   🔗 {car['ad_url']}")
                        print("=" * 50)

            except Exception as e:
                print(f"❌ Ошибка: {e}")

        if new_cars_count == 0:
            print(f"💤 Нових авто немає. Чекаю 10 хвилин...")
        else:
            print(f"✅ Додано {new_cars_count} нових авто.")

        wait_time = random.randint(600, 900)
        print(f"💤 Сплю {wait_time} секунд...")
        time.sleep(wait_time)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Зупинено.")