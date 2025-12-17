import sqlite3
import time
import requests
import random
from pathlib import Path

# =============================
# ⚙️ НАЛАШТУВАННЯ
# =============================
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "cars.db"

# Заголовки як у браузера (щоб не забанили)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Referer": "https://www.olx.ua/",
}

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def check_and_clean():
    print("🧹 Запуск очищувача бази даних...")
    
    while True:
        conn = get_db_connection()
        cur = conn.cursor()

        # Беремо 20 оголошень для перевірки (можна сортувати RANDOM, щоб перевіряти різні)
        # Або перевіряти старі: ORDER BY created_at ASC
        cur.execute("SELECT id, ad_url, title FROM cars ORDER BY RANDOM() LIMIT 20")
        rows = cur.fetchall()
        
        if not rows:
            print("💤 База порожня. Чекаю 1 хвилину...")
            conn.close()
            time.sleep(60)
            continue

        print(f"\n🔍 Перевірка {len(rows)} оголошень на актуальність...")

        ids_to_delete = []

        for row in rows:
            car_id = row['id']
            url = row['ad_url']
            title = row['title']

            try:
                # Робимо запит. allow_redirects=True дозволяє відстежити перенаправлення
                r = requests.get(url, headers=HEADERS, timeout=10, allow_redirects=True)

                # 1. Якщо статус 404 - сторінки немає
                if r.status_code == 404:
                    print(f"❌ [404] Видаляємо: {title}")
                    ids_to_delete.append(car_id)
                
                # 2. Якщо нас перекинуло на іншу URL (наприклад, на категорію), значить оголошення видалено
                # OLX часто перекидає на список оголошень, якщо конкретне видалено
                elif r.url != url and "olx.ua/d/uk/obyavlenie" not in r.url:
                    print(f"❌ [Redirect] Видаляємо (перекинуло на {r.url}): {title}")
                    ids_to_delete.append(car_id)

                # 3. Якщо статус 200, але в тексті є "Оголошення неактивне" (це складніше, залежить від мови)
                # Для надійності поки покладаємось на редіректи.
                
                else:
                    print(f"✅ [Active] Живе: {title[:30]}...")

            except Exception as e:
                print(f"⚠️ Помилка перевірки {url}: {e}")
            
            # Пауза між запитами, щоб не забанили IP
            time.sleep(random.uniform(2, 5))

        # Видалення з бази
        if ids_to_delete:
            print(f"🗑 Видаляю {len(ids_to_delete)} записів з БД...")
            cur.executemany("DELETE FROM cars WHERE id = ?", [(i,) for i in ids_to_delete])
            conn.commit()
        
        conn.close()
        
        # Пауза перед наступною пачкою
        wait_time = random.randint(30, 60)
        print(f"💤 Пауза {wait_time} сек перед наступною пачкою...")
        time.sleep(wait_time)

if __name__ == "__main__":
    try:
        check_and_clean()
    except KeyboardInterrupt:
        print("\n🛑 Очищувач зупинено.")