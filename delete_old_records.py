import sqlite3
from pathlib import Path
from datetime import datetime, timedelta, timezone

# =============================
# ⚙️ НАЛАШТУВАННЯ
# =============================
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "cars.db"

# Скільки годин зберігати історію? (Все, що старіше - видаляємо)
HOURS_TO_KEEP = 48

def clean_old_records():
    if not DB_PATH.exists():
        print(f"❌ База даних не знайдена: {DB_PATH}")
        return

    # 1. Вираховуємо дату "відсікання" (зараз мінус 48 годин)
    # Використовуємо UTC, оскільки основний скрипт пише час в UTC
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=HOURS_TO_KEEP)
    cutoff_str = cutoff_time.isoformat()

    print(f"🕒 Поточний час (UTC): {datetime.now(timezone.utc).isoformat()}")
    print(f"✂️ Видаляємо все, що старіше за: {cutoff_str}")
    print("-" * 50)

    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()

        # 2. Перевіряємо, скільки записів буде видалено (для інформації)
        cur.execute("SELECT count(*) FROM cars WHERE created_at < ?", (cutoff_str,))
        count_to_delete = cur.fetchone()[0]

        if count_to_delete == 0:
            print("✅ Старих записів не знайдено. База чиста.")
        else:
            # 3. Виконуємо видалення
            cur.execute("DELETE FROM cars WHERE created_at < ?", (cutoff_str,))
            conn.commit()
            print(f"🗑 УСПІШНО ВИДАЛЕНО: {count_to_delete} старих оголошень.")
            
            # Оптимізація розміру файлу бази даних після видалення
            cur.execute("VACUUM") 
            print("📦 База даних оптимізована (VACUUM).")

    except Exception as e:
        print(f"❌ Помилка при роботі з базою: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    clean_old_records()