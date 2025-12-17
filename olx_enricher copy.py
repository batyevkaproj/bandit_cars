import sqlite3
import time
import requests
import random
import json
import re
from pathlib import Path
from datetime import datetime, timezone, timedelta

# =============================
# 📜 SQL STRUCTURE (Reference)
# =============================
"""
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
    created_at TEXT,
    last_checked TEXT,
    description TEXT,
    full_description TEXT,  -- NEW FIELD ADDED
    params TEXT,
    seller_name TEXT,
    all_photos TEXT,
    is_active INTEGER,
    last_full_check TEXT,
    is_favorite INTEGER DEFAULT 0
);
"""

# =============================
# ⚙️ SETTINGS
# =============================
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "cars.db"

# How often to re-check "Favorites" (in minutes)
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
# 🗄️ DATABASE MANAGEMENT
# =============================
def init_extended_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    # Check/Create table if not exists (Basic structure)
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

    # Columns to ensure exist
    new_columns = {
        "description": "TEXT",
        "full_description": "TEXT", # <--- NEW FIELD
        "params": "TEXT",
        "seller_name": "TEXT",
        "all_photos": "TEXT",
        "is_active": "INTEGER",
        "last_full_check": "TEXT",
        "is_favorite": "INTEGER DEFAULT 0"
    }

    cur.execute("PRAGMA table_info(cars)")
    existing = {row[1] for row in cur.fetchall()}

    for col, col_type in new_columns.items():
        col_name = col.split()[0] # Remove DEFAULT if present
        if col_name not in existing:
            try:
                print(f"📦 Adding new column: {col_name}")
                cur.execute(f"ALTER TABLE cars ADD COLUMN {col} {col_type}")
            except Exception as e:
                print(f"Error adding column {col_name}: {e}")
    
    conn.commit()
    conn.close()

# =============================
# 🕵️‍♂️ PARSING LOGIC
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
    
    # Initialize defaults
    data['description'] = ""
    data['full_description'] = ""
    data['params'] = "{}"
    data['seller_name'] = "Unknown"
    data['all_photos'] = "[]"
    data['is_active'] = 1

    state = extract_json_smart(html_content)
    
    # 1. Try extracting from JSON (Best Quality)
    if state:
        try:
            ad_data = state.get('ad', {}).get('ad', {})
            if ad_data:
                # Get description
                raw_desc = ad_data.get('description', '')
                data['full_description'] = raw_desc # Full text
                data['description'] = raw_desc[:500] + "..." if len(raw_desc) > 500 else raw_desc
                
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

    # 2. Fallback: Parse HTML directly (If JSON fails)
    if '"status":"active"' in html_content:
        data['is_active'] = 1
    elif '"status":"closed"' in html_content or '"status":"removed"' in html_content:
        data['is_active'] = 0
    else:
        if "Це оголошення більше не доступне" in html_content or "Оголошення неактивне" in html_content:
            data['is_active'] = 0
        else:
            data['is_active'] = 1

    # Regex for description
    desc_match = re.search(r'data-cy="ad_description".*?><div>(.*?)</div>', html_content, re.DOTALL)
    if desc_match:
        clean_desc = desc_match.group(1).replace('<br />', '\n').replace('<br>', '\n')
        # Remove HTML tags if any remain
        clean_desc = re.sub(r'<[^>]+>', '', clean_desc).strip()
        
        data['full_description'] = clean_desc # Save full text here
        data['description'] = clean_desc[:500] + "..." # Truncated version
    else:
        data['description'] = "Опис не знайдено (Fallback)"
        data['full_description'] = "Опис не знайдено (Fallback)"

    return data

# =============================
# 🚀 MAIN LOOP
# =============================
def main_loop():
    init_extended_db()
    print("🕵️‍♂️ Запуск 'Збагачувача' з пріоритетом ВИБРАНИХ...")
    
    session = requests.Session()

    while True:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Threshold for favorites re-check
        check_threshold = (datetime.now(timezone.utc) - timedelta(minutes=FAVORITE_CHECK_INTERVAL)).isoformat()

        # ---------------------------------------------------------
        # 1. PRIORITY: FAVORITES
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
            # 2. PRIORITY: NEW (Missing full_description)
            # ---------------------------------------------------------
            cur.execute("""
                SELECT id, ad_url, title, is_favorite 
                FROM cars 
                WHERE full_description IS NULL OR full_description = '' OR is_active IS NULL
                ORDER BY created_at DESC 
                LIMIT 5
            """)
            rows = cur.fetchall()
            
            if not rows:
                # ---------------------------------------------------------
                # 3. PRIORITY: OLD (Standard Rotation)
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
                
                # Check 404
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
                        # Option: Delete or just mark inactive
                        cur.execute("DELETE FROM cars WHERE id = ?", (car_id,))
                    else:
                        prefix = "⭐ [ВИБРАНЕ]" if is_fav else "✅ [ОНОВЛЕНО]"
                        print(f"{prefix} {title[:30]}... (Active)")
                        
                        cur.execute("""
                            UPDATE cars SET 
                                description = ?, 
                                full_description = ?, 
                                params = ?, 
                                seller_name = ?, 
                                all_photos = ?, 
                                is_active = 1,
                                last_full_check = ?
                            WHERE id = ?
                        """, (
                            extracted['description'],
                            extracted['full_description'], # <--- SAVING NEW FIELD
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