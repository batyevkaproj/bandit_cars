import sqlite3
import time
import requests
import random
import re  # Модуль для пошуку точних фраз (Regular Expressions)
from pathlib import Path
from datetime import datetime, timezone

# =============================
# ⚙️ НАЛАШТУВАННЯ
# =============================
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "cars.db"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Referer": "https://www.olx.ua/",
}

def init_migration():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    try:
        cur.execute("SELECT last_checked FROM cars LIMIT 1")
    except sqlite3.OperationalError:
        cur.execute("ALTER TABLE cars ADD COLUMN last_checked TEXT")
        conn.commit()
    conn.close()

def smart_cleanup():
    init_migration()
    print("🛡️ Запуск БЕЗПЕЧНОГО очищувача (Smart Cleanup v2)...")

    while True:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # Беремо оголошення, які давно не перевіряли
        cur.execute("""
            SELECT id, ad_url, title, last_checked 
            FROM cars 
            ORDER BY last_checked ASC NULLS FIRST 
            LIMIT 10
        """)
        rows = cur.fetchall()

        if not rows:
            print("💤 База порожня. Чекаю...")
            conn.close()
            time.sleep(60)
            continue

        print(f"\n🔍 Перевірка {len(rows)} оголошень...")

        for row in rows:
            car_id = row['id']
            url = row['ad_url']
            title = row['title']
            now_iso = datetime.now(timezone.utc).isoformat()

            try:
                r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)
                
                should_delete = False
                reason = ""

                # 1. Перевірка 404 (Сторінки немає)
                if r.status_code == 404:
                    should_delete = True
                    reason = "404 Not Found"
                
                # 2. Перевірка редіректу (Перекинуло на категорію)
                elif r.url != url and "obyavlenie" not in r.url:
                    should_delete = True
                    reason = "Redirected"

                # 3. 🔥 ПЕРЕВІРКА JSON СТАТУСУ (Найнадійніший метод)
                else:
                    # Шукаємо в коді рядок типу "status":"active" або "status":"closed"
                    # re.search шукає точний збіг шаблону
                    status_match = re.search(r'"status"\s*:\s*"(\w+)"', r.text)
                    
                    if status_match:
                        status = status_match.group(1) # Отримуємо слово (active/closed/removed)
                        
                        if status == "active":
                            should_delete = False # Точно живе!
                        elif status in ["closed", "removed", "moderated", "disabled"]:
                            should_delete = True
                            reason = f"Status is '{status}'"
                    else:
                        # Якщо статус не знайдено в коді - НЕ видаляємо про всяк випадок
                        should_delete = False

                if should_delete:
                    print(f"❌ [ВИДАЛЯЮ] {title[:30]}... -> {reason}")
                    cur.execute("DELETE FROM cars WHERE id = ?", (car_id,))
                    conn.commit()
                else:
                    print(f"✅ [ЖИВЕ] {title[:30]}...")
                    cur.execute("UPDATE cars SET last_checked = ? WHERE id = ?", (now_iso, car_id))
                    conn.commit()

            except Exception as e:
                print(f"⚠️ Помилка: {e}")
                cur.execute("UPDATE cars SET last_checked = ? WHERE id = ?", (now_iso, car_id))
                conn.commit()

            time.sleep(random.uniform(2, 4))

        conn.close()
        print("💤 Пауза 30 секунд...")
        time.sleep(30)

if __name__ == "__main__":
    try:
        smart_cleanup()
    except KeyboardInterrupt:
        print("\n🛑 Зупинено.")