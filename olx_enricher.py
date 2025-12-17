import sqlite3
import time
import requests
import random
import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

# =============================
# ⚙️ НАЛАШТУВАННЯ
# =============================
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "cars.db"

# Як часто перевіряти "Вибрані" (в хвилинах)
FAVORITE_CHECK_INTERVAL = 15 

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36"
]

def get_random_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Referer": "https://www.olx.ua/",
    }

# =============================
# 🗄️ РОБОТА З БАЗОЮ
# =============================
def init_extended_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    new_columns = {
        "description": "TEXT",
        "params": "TEXT",
        "seller_name": "TEXT",
        "all_photos": "TEXT",
        "is_active": "INTEGER",
        "last_full_check": "TEXT",
        "is_favorite": "INTEGER DEFAULT 0" # Переконаємось, що ця колонка є
    }

    cur.execute("PRAGMA table_info(cars)")
    existing = {row[1] for row in cur.fetchall()}

    for col, col_type in new_columns.items():
        col_name = col.split()[0] # Відрізаємо DEFAULT якщо є
        if col_name not in existing:
            try:
                cur.execute(f"ALTER TABLE cars ADD COLUMN {col} {col_type}")
            except:
                pass
    
    conn.commit()
    conn.close()

# =============================
# 🕵️‍♂️ ЛОГІКА ПАРСИНГУ
# =============================
def extract_json_smart(html_content):
    start_marker = "window.__PRERENDERED_STATE__="
    start_idx = html_content.find(start_marker)
    
    if start_idx == -1:
        start_marker = "window.__PRERENDERED_STATE__ ="
        start_idx = html_content.find(start_marker)
        if start_idx == -1:
            return None

    json_start = html_content.find("{", start_idx)
    if json_start == -1:
        return None

    balance = 0
    json_end = -1
    
    for i in range(json_start, len(html_content)):
        char = html_content[i]
        if char == "{":
            balance += 1
        elif char == "}":
            balance -= 1
            if balance == 0:
                json_end = i + 1
                break
    
    if json_end == -1:
        return None

    try:
        return json.loads(html_content[json_start:json_end])
    except:
        return None

def extract_olx_data(html_content):
    data = {}
    state = extract_json_smart(html_content)
    
    if state:
        try:
            ad_data = state.get('ad', {}).get('ad', {})
            if ad_data:
                data['description'] = ad_data.get('description', '')
                data['is_active'] = 1 if ad_data.get('status') == 'active' else 0
                data['seller_name'] = ad_data.get('user', {}).get('name', 'Unknown')
                
                params_list = ad_data.get('params', [])
                clean_params = {}
                for p in params_list:
                    name = p.get('name') or p.get('key')
                    value = p.get('value', {}).get('label')
                    if name and value:
                        clean_params[name] = value
                data['params'] = json.dumps(clean_params, ensure_ascii=False)

                photos = ad_data.get('photos', [])
                photo_links = [p.get('link', '').replace('{width}', '1000').replace('{height}', '750') for p in photos]
                data['all_photos'] = json.dumps(photo_links)
                
                return data
        except:
            pass

    # Fallback
    if '"status":"active"' in html_content:
        data['is_active'] = 1
    elif '"status":"closed"' in html_content or '"status":"removed"' in html_content:
        data['is_active'] = 0
    else:
        if "Це оголошення більше не доступне" in html_content or "Оголошення неактивне" in html_content:
            data['is_active'] = 0
        else:
            data['is_active'] = 1

    desc_match = re.search(r'data-cy="ad_description".*?><div>(.*?)</div>', html_content, re.DOTALL)
    if desc_match:
        clean_desc = desc_match.group(1).replace('<br />', '\n').replace('<br>', '\n')
        data['description'] = clean_desc[:500] + "..."
    else:
        data['description'] = "Опис не знайдено (Fallback)"

    data['params'] = "{}"
    data['seller_name'] = "Unknown"
    data['all_photos'] = "[]"
    
    return data

# =============================
# 🚀 ГОЛОВНИЙ ЦИКЛ
# =============================
def main_loop():
    init_extended_db()
    print("🕵️‍♂️ Запуск 'Збагачувача' з пріоритетом ВИБРАНИХ...")
    
    session = requests.Session()

    while True:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Розрахунок часу для повторної перевірки вибраних
        # (Зараз мінус 15 хвилин)
        check_threshold = (datetime.now(timezone.utc) - timedelta(minutes=FAVORITE_CHECK_INTERVAL)).isoformat()

        # ---------------------------------------------------------
        # 1. ПРІОРИТЕТ: ВИБРАНІ (Favorites)
        # Перевіряємо, якщо вони не перевірялися останні 15 хв
        # ---------------------------------------------------------
        cur.execute("""
            SELECT id, ad_url, title, is_favorite 
            FROM cars 
            WHERE is_favorite = 1 
            AND (last_full_check IS NULL OR last_full_check < ?)
            ORDER BY last_full_check ASC
            LIMIT 5
        """, (check_threshold,))
        rows = cur.fetchall()
        priority_mode = False

        if rows:
            print(f"\n⭐ ПЕРЕВІРКА ВИБРАНИХ ({len(rows)} шт)...")
            priority_mode = True
        else:
            # ---------------------------------------------------------
            # 2. ПРІОРИТЕТ: НОВІ (Без опису)
            # ---------------------------------------------------------
            cur.execute("""
                SELECT id, ad_url, title, is_favorite 
                FROM cars 
                WHERE description IS NULL OR is_active IS NULL
                ORDER BY created_at DESC 
                LIMIT 5
            """)
            rows = cur.fetchall()
            
            if not rows:
                # ---------------------------------------------------------
                # 3. ПРІОРИТЕТ: СТАРІ (Звичайне коло перевірки)
                # ---------------------------------------------------------
                cur.execute("""
                    SELECT id, ad_url, title, is_favorite 
                    FROM cars 
                    WHERE is_favorite = 0
                    ORDER BY last_full_check ASC 
                    LIMIT 5
                """)
                rows = cur.fetchall()

        if not rows:
            print("💤 База порожня або всі перевірені. Сплю 2 хвилини...")
            conn.close()
            time.sleep(120)
            continue

        if not priority_mode:
            print(f"\n🔍 Обробка {len(rows)} оголошень...")

        for row in rows:
            car_id = row['id']
            url = row['ad_url']
            title = row['title']
            is_fav = row['is_favorite']
            
            session.headers.update(get_random_headers())

            try:
                r = session.get(url, timeout=15, allow_redirects=True)
                now_iso = datetime.now(timezone.utc).isoformat()
                
                # Перевірка 404
                if r.status_code == 404 or (r.url != url and "obyavlenie" not in r.url):
                    print(f"❌ [ВИДАЛЕНО] {title[:30]}... (404/Redirect)")
                    cur.execute("DELETE FROM cars WHERE id = ?", (car_id,))
                    conn.commit()
                    time.sleep(random.uniform(2, 5))
                    continue

                extracted = extract_olx_data(r.text)

                if extracted:
                    if extracted['is_active'] == 0:
                        print(f"❌ [ЗАКРИТО] {title[:30]}... (Status: Closed)")
                        cur.execute("DELETE FROM cars WHERE id = ?", (car_id,))
                    else:
                        prefix = "⭐ [ВИБРАНЕ]" if is_fav else "✅ [ОНОВЛЕНО]"
                        print(f"{prefix} {title[:30]}... (Active)")
                        
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
                    print(f"⚠️ Не вдалося отримати дані для {title[:20]} (Skip)")
                    cur.execute("UPDATE cars SET last_full_check = ? WHERE id = ?", (now_iso, car_id))
                    conn.commit()

            except Exception as e:
                print(f"⚠️ Помилка з'єднання: {e}")
            
            sleep_time = random.uniform(3, 8)
            print(f"⏳ Пауза... ({sleep_time:.1f}s)")
            time.sleep(sleep_time)

        conn.close()
        
        long_sleep = random.randint(15, 45)
        print(f"💤 Перерва... ({long_sleep}s)")
        time.sleep(long_sleep)

if __name__ == "__main__":
    try:
        main_loop()
    except KeyboardInterrupt:
        print("\n🛑 Зупинено.")