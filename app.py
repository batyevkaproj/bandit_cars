from flask import Flask, render_template, g, request
import sqlite3
from pathlib import Path

app = Flask(__name__)

BASE_DIR = Path(__file__).parent.resolve()
DB_PATH = BASE_DIR / "cars.db"

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

@app.route('/')
def index():
    # 1. Получаем параметры из URL (например, ?min_price=1000)
    min_price = request.args.get('min_price')
    max_price = request.args.get('max_price')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = "SELECT id, title, price_uah, image_url, ad_url, created_at FROM cars WHERE image_url IS NOT NULL"
    params = []

    # 2. Добавляем условия фильтрации, если параметры переданы
    if min_price and min_price.isdigit():
        query += " AND price_uah >= ?"
        params.append(int(min_price))
    
    if max_price and max_price.isdigit():
        query += " AND price_uah <= ?"
        params.append(int(max_price))

    if start_date:
        query += " AND created_at >= ?"
        params.append(start_date)

    if end_date:
        # Добавляем конец дня, чтобы включить записи за этот день
        query += " AND created_at <= ?"
        params.append(end_date + "T23:59:59")

    # 3. Сортировка и лимит
    query += " ORDER BY created_at DESC LIMIT 200"

    cur = get_db().cursor()
    cur.execute(query, params)
    cars = cur.fetchall()

    # Возвращаем страницу и текущие значения фильтров (чтобы они остались в полях ввода)
    return render_template('index.html', cars=cars, 
                           min_price=min_price, max_price=max_price,
                           start_date=start_date, end_date=end_date)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)