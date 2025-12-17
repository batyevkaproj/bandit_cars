import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "cars.db"

def clean_database():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Слова, которые мы хотим удалить из базы
    junk_words = ["диски", "шини", "мотор", "двигун", "запчастини", "розборка", "причіп"]

    print(f"🧹 Очистка базы данных от мусора...")
    
    deleted_count = 0
    for word in junk_words:
        # Удаляем, если слово встречается в заголовке (LIKE %слово%)
        cur.execute(f"DELETE FROM cars WHERE title LIKE '%{word}%'")
        deleted_count += cur.rowcount
    
    conn.commit()
    conn.close()
    print(f"✅ Удалено {deleted_count} записей с запчастями/мусором.")

if __name__ == "__main__":
    clean_database()