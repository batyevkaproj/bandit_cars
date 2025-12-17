import sqlite3
import time
import requests
from pathlib import Path
from datetime import datetime, timezone

# =============================
# ⚙️ КОНФИГУРАЦИЯ
# =============================
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "cars.db"
API_URL = "https://www.olx.ua/api/v1/offers"
CATEGORY_CARS_ID = 1532  # ID категории "Легковые автомобили"

# 🛑 СТОП-СЛОВА (Фильтр мусора)
# Если эти слова есть в заголовке, объявление пропускается.
STOP_WORDS = [
    "трактор", "мотоблок", "причіп", "прицеп", "скутер", 
    "мотоцикл", "квадроцикл", "навантажувач", "погрузчик", 
    "комбайн", "запчастини", "розборка", "шрот", "двигун", 
    "кпп", "сівалка", "плуг", "борона", "мопед", "велосипед",
    "scooter", "moto", "atv", "tractor", "разборка"
]

# 🔍 НАСТРОЙКИ ПОИСКА
SEARCH_CONFIG = {
    "q": "",                          # Поисковый запрос (например, "BMW"). Оставьте "", чтобы искать всё.
    "filter_float_price:from": 20000, # Минимальная цена (отсекает игрушки и мелкие запчасти)
    "filter_float_price:to": None,    # Максимальная цена (None = без ограничений)
    "sort_by": "created_at:desc"      # Сортировка: сначала новые
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
    """Создает таблицу, если она не существует."""
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
    """
    1. Записывает машину в БД.
    2. Сразу читает её обратно (DUMP).
    3. Сравнивает оригинал и запись (CHECK).
    Возвращает True, если это новая запись.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Позволяет обращаться к полям по имени
    cur = conn.cursor()
    
    start_changes = conn.total_changes

    # 1. ЗАПИСЬ (WRITE)
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
        # 2. ЧТЕНИЕ С ДИСКА (DUMP)
        cur.execute("SELECT * FROM cars WHERE id = ?", (car['id'],))
        row = cur.fetchone()
        
        if row:
            db_record = dict(row)
            
            # ВЫВОД ДАМПА
            print(f"\n💾 [DATA DUMP] Записано на диск:")
            print(f"   ID:    {db_record['id']}")
            print(f"   Title: {db_record['title']}")
            print(f"   Price: {db_record['price_uah']} UAH")
            
            # 3. ПРОВЕРКА ЦЕЛОСТНОСТИ (CHECK)
            # Сравниваем то, что в памяти, с тем, что в базе
            if db_record['title'] == car['title']:
                print(f"   ✅ [WRITE CHECK] PASSED: Данные верифицированы.")
            else:
                print(f"   ❌ [WRITE CHECK] FAILED: Ошибка записи! Данные не совпадают.")
            print("-" * 50)

    conn.close()
    return was_inserted

# =============================
# 🛠️ ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =============================
def extract_prices(offer_data: dict):
    """Извлекает цену из разных полей API."""
    price = offer_data.get("price")
    
    # Иногда цена спрятана в параметрах
    if not price and "params" in offer_data:
        for param in offer_data["params"]:
            if param.get("key") == "price":
                price = param.get("value")
                break

    if not price: 
        return None, None, None

    value = price.get("value")
    currency = price.get("currency")
    converted = price.get("converted_value")

    price_uah = int(converted) if converted else (int(value) if currency == "UAH" and value else None)
    return value, currency, price_uah

def fetch_page(offset: int):
    """Делает запрос к API с учетом фильтров."""
    params = {
        "offset": offset,
        "limit": 50,
        "category_id": CATEGORY_CARS_ID,
        "sort_by": SEARCH_CONFIG["sort_by"]
    }
    
    if SEARCH_CONFIG["q"]:
        params["q"] = SEARCH_CONFIG["q"]
    if SEARCH_CONFIG["filter_float_price:from"]:
        params["filter_float_price:from"] = SEARCH_CONFIG["filter_float_price:from"]
    if SEARCH_CONFIG["filter_float_price:to"]:
        params["filter_float_price:to"] = SEARCH_CONFIG["filter_float_price:to"]

    return requests.get(API_URL, headers=HEADERS, params=params, timeout=15)

# =============================
# 🚀 ОСНОВНОЙ ЦИКЛ
# =============================
def main():
    init_db()
    print(f"🚀 OLX Monitor запущен.")
    print(f"📂 База данных: {DB_PATH}")
    print(f"🛑 Стоп-слова: {len(STOP_WORDS)} шт.")
    print("-" * 50)

    while True:
        new_cars_count = 0
        
        # Проверяем первые 3 страницы (0, 50, 100)
        for offset in (0, 50, 100):
            try:
                r = fetch_page(offset)
                if r.status_code != 200:
                    print(f"⚠️ Ошибка API: {r.status_code}")
                    continue

                offers = r.json().get("data", [])
                
                for o in offers:
                    # 1. Проверка стоп-слов
                    title = o.get("title", "").lower()
                    if any(word in title for word in STOP_WORDS):
                        continue

                    # 2. Проверка наличия фото
                    photos = o.get("photos") or []
                    if not photos: 
                        continue

                    # 3. Подготовка данных
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

                    # 4. Сохранение + Dump + Check
                    if save_car_and_verify(car):
                        new_cars_count += 1
                        print(f"🟢 [NEW] {car['title']}")
                        print(f"   🔗 {car['ad_url']}")
                        print("=" * 50)

            except Exception as e:
                print(f"❌ Ошибка при обработке страницы {offset}: {e}")

        if new_cars_count == 0:
            print(f"💤 Новых авто нет. Жду 10 минут... (Время: {datetime.now().strftime('%H:%M:%S')})")
        else:
            print(f"✅ Цикл завершен. Добавлено новых авто: {new_cars_count}")

        time.sleep(600) # Пауза 10 минут

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🛑 Работа остановлена пользователем.")