import sqlite3
import time
import requests
from pathlib import Path

# ⚙️ НАЛАШТУВАННЯ
BOT_TOKEN = "ВАШ_ТОКЕН_ТУТ"
CHAT_ID = "ВАШ_ID_ТУТ"
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "cars.db"

def init_tg_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("ALTER TABLE cars ADD COLUMN sent_to_tg INTEGER DEFAULT 0")
    except:
        pass
    conn.close()

def send_telegram_message(car):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    caption = f"🚗 <b>{car['title']}</b>\n💰 {car['price_uah']} грн\n🔗 {car['ad_url']}"
    
    payload = {'chat_id': CHAT_ID, 'caption': caption, 'parse_mode': 'HTML'}
    files = None
    
    # Якщо є фото, шлемо фото, якщо ні - просто текст
    if car['image_url']:
        payload['photo'] = car['image_url']
        try:
            requests.post(url, data=payload)
        except:
            # Якщо фото не вантажиться, шлемо текст
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            payload = {'chat_id': CHAT_ID, 'text': caption, 'parse_mode': 'HTML'}
            requests.post(url, data=payload)
    else:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {'chat_id': CHAT_ID, 'text': caption, 'parse_mode': 'HTML'}
        requests.post(url, data=payload)

def run_notifier():
    init_tg_db()
    print("📢 Telegram Notifier запущено...")
    
    while True:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        
        # Беремо нові авто, які ще не відправляли
        cur.execute("SELECT * FROM cars WHERE sent_to_tg = 0 OR sent_to_tg IS NULL LIMIT 5")
        rows = cur.fetchall()
        
        for row in rows:
            try:
                send_telegram_message(row)
                print(f"✈️ Відправлено: {row['title']}")
                cur.execute("UPDATE cars SET sent_to_tg = 1 WHERE id = ?", (row['id'],))
                conn.commit()
                time.sleep(1) # Пауза щоб не спамити
            except Exception as e:
                print(f"⚠️ Помилка відправки: {e}")
        
        conn.close()
        time.sleep(10) # Перевірка кожні 10 сек

if __name__ == "__main__":
    run_notifier()