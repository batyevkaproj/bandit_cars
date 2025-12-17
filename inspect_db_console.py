import sqlite3
from pathlib import Path

DB = Path(__file__).parent / "cars.db"

print("DB path:", DB.resolve())

conn = sqlite3.connect(DB)
cur = conn.cursor()

tables = cur.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall()

print("Tables:", tables)

if tables:
    t = tables[0][0]
    print("\nColumns in", t)
    for c in cur.execute(f"PRAGMA table_info('{t}')"):
        print(c)

conn.close()
