import sqlite3
import time
import os
from datetime import datetime
import os
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "olx.db")

REFRESH_SECONDS = 10   # як часто оновлювати вивід

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def format_row(row):
    return (
        f"🚗 {row[1]}\n"
        f"💲 {row[2]} {row[3]}\n"
        f"📍 {row[4]}\n"
        f"🖼 {row[5]}\n"
        f"🔗 {row[6]}\n"
        f"🕒 {row[7]}\n"
        + "-" * 80
    )

def main():
    print("📊 OLX DB monitor started")
    print("💡 Stop with Ctrl + C\n")

    last_seen_ids = set()

    try:
        while True:
            clear_screen()

            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()

            rows = cur.execute("""
                SELECT id, title, price_value, price_currency,
                       location, image_url, ad_url, created_at
                FROM cars
                ORDER BY created_at DESC
            """).fetchall()

            conn.close()

            print(f"📦 Records in DB: {len(rows)}")
            print("=" * 80)

            if not rows:
                print("ℹ Database is empty yet")

            for row in rows:
                print(format_row(row))

                # нові записи виділяємо
                if row[0] not in last_seen_ids:
                    last_seen_ids.add(row[0])

            time.sleep(REFRESH_SECONDS)

    except KeyboardInterrupt:
        print("\n🛑 DB monitor stopped")

if __name__ == "__main__":
    main()
