import sqlite3
import csv
from pathlib import Path

# Настройки
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "cars.db"
CSV_PATH = BASE_DIR / "olx_data.csv"

def export_db_to_csv():
    if not DB_PATH.exists():
        print(f"❌ База данных {DB_PATH} не найдена.")
        return

    print(f"📂 Чтение базы данных: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    try:
        # Выбираем все данные
        cur.execute("SELECT * FROM cars ORDER BY created_at DESC")
        rows = cur.fetchall()

        if not rows:
            print("⚠️ База пуста, нечего экспортировать.")
            return

        # Получаем названия колонок из базы
        column_names = [description[0] for description in cur.description]

        print(f"💾 Запись {len(rows)} строк в файл {CSV_PATH}...")

        # Записываем в CSV (кодировка utf-8-sig нужна для корректного открытия в Excel на Windows)
        with open(CSV_PATH, mode='w', newline='', encoding='utf-8-sig') as file:
            writer = csv.writer(file, delimiter=';') # Используем точку с запятой для Excel
            
            # Пишем заголовок
            writer.writerow(column_names)
            
            # Пишем данные
            writer.writerows(rows)

        print(f"✅ УСПЕХ! Файл создан: {CSV_PATH}")
        print("📊 Теперь вы можете открыть его в Excel.")

    except Exception as e:
        print(f"❌ Ошибка при экспорте: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    export_db_to_csv()