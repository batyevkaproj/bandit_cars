import sqlite3
from pathlib import Path

# Путь к базе данных
BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "cars.db"

def check_database():
    if not DB_PATH.exists():
        print(f"❌ Файл базы данных не найден: {DB_PATH}")
        return

    print(f"📂 Открываю базу данных: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Чтобы получать данные как словарь
    cur = conn.cursor()

    # 1. ПРОВЕРКА КОЛИЧЕСТВА (Write Check)
    try:
        cur.execute("SELECT count(*) FROM cars")
        count = cur.fetchone()[0]
        print(f"✅ УСПЕХ: В базе данных найдено {count} записей.")
    except sqlite3.OperationalError:
        print("❌ ОШИБКА: Таблица 'cars' не найдена. База повреждена или пуста.")
        return

    if count == 0:
        print("⚠️ База пуста. Запустите монитор, чтобы собрать данные.")
        return

    # 2. ДАМП ПОСЛЕДНИХ 5 ЗАПИСЕЙ (Dump Data)
    print("\n📜 --- ДАМП ПОСЛЕДНИХ 5 ЗАПИСЕЙ ---")
    cur.execute("SELECT * FROM cars ORDER BY created_at DESC LIMIT 5")
    rows = cur.fetchall()

    for row in rows:
        item = dict(row)
        print(f"🆔 ID: {item['id']}")
        print(f"🚗 Title: {item['title']}")
        print(f"💰 Price: {item['price_uah']} UAH")
        print(f"🔗 URL: {item['ad_url']}")
        print(f"🕒 Saved: {item['created_at']}")
        print("-" * 40)
    
    print("\n✅ Проверка целостности завершена. Данные читаются корректно.")
    conn.close()

if __name__ == "__main__":
    check_database()