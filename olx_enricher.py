import sqlite3
import time
import requests
import random
import json
import re
from pathlib import Path
from datetime import datetime, timezone

# =============================
# ⚙️ НАЛАШТУВАННЯ
# =============================
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "cars.db"

# Список реальних User-Agent, щоб міняти їх і не виглядати як один і той самий бот
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
]

def get_random_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://www.olx.ua/",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "same-origin",
        "Sec-Fetch-User": "?1",
    }

# =============================
# 🗄️ РОБОТА З БАЗОЮ
# =============================
def init_extended_db():
    """Додає нові колонки для зберігання детальної інфи"""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Список нових колонок, які ми хочемо додати
    new_columns = {
        "description": "TEXT",      # Повний опис
        "params": "TEXT",           # JSON з параметрами (рік, пробіг, двигун)
        "seller_name": "TEXT",      # Ім'я продавця
        "all_photos": "TEXT",       # JSON список всіх фото
        "is_active": "INTEGER",     # 1 - активне, 0 - видалене
        "last_full_check": "TEXT"   # Коли ми востаннє скачували повну інфу
    }

    cur.execute("PRAGMA table_info(cars)")
    existing = {row[1] for row in cur.fetchall()}

    for col, col_type in new_columns.items():
        if col not in existing:
            print(f"🛠 Міграція: додаємо колонку '{col}'...")
            cur.execute(f"ALTER TABLE cars ADD COLUMN {col} {col_type}")
    
    conn.commit()
    conn.close()

# =============================
# 🕵️‍♂️ ЛОГІКА ПАРСИНГУ
# =============================
def extract_olx_data(html_content):
    """
    Витягує прихований JSON (PRERENDERED_STATE) з HTML коду.
    Це найнадійніший спосіб отримати ВСІ дані.
    """
    data = {}
    
    # 1. Шукаємо JSON всередині window.__PRERENDERED_STATE__
    # Це стандарт для сайтів на React/Next.js, як OLX
    pattern = r'window\.__PRERENDERED_STATE__\s*=\s*({.*?});'
    match = re.search(pattern, html_content)
    
    if not match:
        # Спробуємо знайти JSON-LD (резервний варіант)
        return None

    try:
        # Парсимо знайдений JSON (це може бути складно через екранування)
        raw_json = match.group(1)
        # Іноді в JSON є спецсимволи, які ламають json.loads. 
        # Тут ми спрощуємо: якщо не вийшло, повертаємо None
        state = json.loads(raw_json)
        
        # OLX зберігає дані оголошення глибоко в структурі. 
        # Зазвичай це ad -> ad
        ad_data = state.get('ad', {}).get('ad', {})
        
        if not ad_data:
            return None

        # Збираємо дані
        data['description'] = ad_data.get('description', '')
        data['is_active'] = 1 if ad_data.get('status') == 'active' else 0
        data['seller_name'] = ad_data.get('user', {}).get('name', 'Unknown')
        
        # Параметри (Рік, Паливо, Пробіг...)
        params_list = ad_data.get('params', [])
        clean_params = {}
        for p in params_list:
            key = p.get('key')
            name = p.get('name')
            value = p.get('value', {}).get('label')
            if name and value:
                clean_params[name] = value
        data['params'] = json.dumps(clean_params, ensure_ascii=False)

        # Всі фото
        photos = ad_data.get('photos', [])
        photo_links = [p.get('link', '').replace('{width}', '1000').replace('{height}', '750') for p in photos]
        data['all_photos'] = json.dumps(photo_links)

        return data

    except Exception as e:
        print(f"⚠️ Помилка парсингу JSON: {e}")
        return None

# =============================
# 🚀 ГОЛОВНИЙ ЦИКЛ
# =============================
def main_loop():
    init_extended_db()
    print("🕵️‍♂️ Запуск 'Збагачувача даних' (Stealth Mode)...")
    
    # Створюємо сесію (зберігає куки, як браузер)
    session = requests.Session()

    while True:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Вибираємо оголошення:
        # 1. Ті, де ще немає опису (description IS NULL) - пріоритет
        # 2. Ті, які давно не перевіряли
        cur.execute("""
            SELECT id, ad_url, title 
            FROM cars 
            WHERE description IS NULL OR is_active IS NULL
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        rows = cur.fetchall()

        if not rows:
            print("💤 Всі нові оголошення оброблені. Перевіряю старі...")
            # Якщо нових немає, беремо старі на перевірку (чи не видалили їх)
            cur.execute("""
                SELECT id, ad_url, title 
                FROM cars 
                ORDER BY last_full_check ASC 
                LIMIT 5
            """)
            rows = cur.fetchall()

        if not rows:
            print("💤 База порожня. Сплю 2 хвилини...")
            conn.close()
            time.sleep(120)
            continue

        print(f"\n🔍 Обробка {len(rows)} оголошень...")

        for row in rows:
            car_id = row['id']
            url = row['ad_url']
            title = row['title']
            
            # Оновлюємо заголовки (імітація різних запитів)
            session.headers.update(get_random_headers())

            try:
                # Робимо запит
                r = session.get(url, timeout=15, allow_redirects=True)
                
                now_iso = datetime.now(timezone.utc).isoformat()
                
                # 1. Перевірка на "Мертве" оголошення (404 або редірект)
                if r.status_code == 404 or (r.url != url and "obyavlenie" not in r.url):
                    print(f"❌ [ВИДАЛЕНО] {title[:30]}... (404/Redirect)")
                    # Можна видаляти, а можна ставити прапорець is_active=0
                    cur.execute("DELETE FROM cars WHERE id = ?", (car_id,))
                    conn.commit()
                    
                    # Довга пауза після видалення
                    time.sleep(random.uniform(5, 10))
                    continue

                # 2. Витягуємо дані
                extracted = extract_olx_data(r.text)

                if extracted:
                    # Якщо статус в JSON не active - видаляємо
                    if extracted['is_active'] == 0:
                        print(f"❌ [ЗАКРИТО] {title[:30]}... (Status: Closed)")
                        cur.execute("DELETE FROM cars WHERE id = ?", (car_id,))
                    else:
                        print(f"✅ [ОНОВЛЕНО] {title[:30]}... (+Опис, +Параметри)")
                        cur.execute("""
                            UPDATE cars SET 
                                description = ?, 
                                params = ?, 
                                seller_name = ?, 
                                all_photos = ?, 
                                is_active = 1,
                                last_full_check = ?
                            WHERE id = ?
                        """, (
                            extracted['description'],
                            extracted['params'],
                            extracted['seller_name'],
                            extracted['all_photos'],
                            now_iso,
                            car_id
                        ))
                    conn.commit()
                else:
                    print(f"⚠️ Не вдалося розпарсити JSON для {title[:20]}...")
                    # Ставимо позначку, що перевіряли, щоб не зациклитись
                    cur.execute("UPDATE cars SET last_full_check = ? WHERE id = ?", (now_iso, car_id))
                    conn.commit()

            except Exception as e:
                print(f"⚠️ Помилка з'єднання: {e}")
            
            # 🔥 ЛЮДСЬКА ПАУЗА
            # Людина не клікає рівно кожні 2 секунди.
            # Іноді вона читає (10 сек), іноді швидко закриває (3 сек).
            sleep_time = random.uniform(4, 12)
            print(f"⏳ Читаю... ({sleep_time:.1f}s)")
            time.sleep(sleep_time)

        conn.close()
        
        # Пауза між пачками (щоб не навантажувати сервер)
        long_sleep = random.randint(20, 60)
        print(f"💤 Перерва на каву... ({long_sleep}s)")
        time.sleep(long_sleep)

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\n🛑 Зупинено.")