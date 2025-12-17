# -*- coding: utf-8 -*-

import sqlite3
import time
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "cars.db")

REFRESH_SECONDS = 10  # як часто оновлювати вивід


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def format_price(value, currency, price_uah=None):
    if value and currency:
        return f"{value:,} {currency}".replace(",", " ")
    if price_uah:
        return f"{price_uah:,} UAH".replace(",", " ")
    return "Ціна не вказана"


def format_row(row):
    (
        _id,
        title,
        price_value,
        price_currency,
        price_uah,
        location_raw,
        image_url,
        ad_url,
        created_at,
    ) = row

    price_text = format_price(price_value, price_currency, price_uah)

    try:
        created = datetime.fromisoformat(created_at).strftime("%Y-%m-%d %H:%M")
    except Exception:
        created = created_at

    return (
        f"🚗 {title}\n"
        f"💲 {price_text}\n"
        f"📍 {location_raw}\n"
        f"🖼 {image_url}\n"
        f"🔗 {ad_url}\n"
        f"🕒 {created}\n"
        + "-" * 80
    )


def main():
    print("📊 OLX DB monitor started")
    print("💡 Stop with Ctrl + C\n")

    try:
        while True:
            clear_screen()

            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()

            rows = cur.execute("""
                SELECT
                    id,
                    title,
                    price_value,
                    price_currency,
                    price_uah,
                    location_raw,
                    image_url,
                    ad_url,
                    created_at
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

            time.sleep(REFRESH_SECONDS)

    except KeyboardInterrupt:
        print("\n🛑 DB monitor stopped")


if __name__ == "__main__":
    main()
