from flask import Flask, render_template, g, request, jsonify
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

def init_db_updates():
    """Automatically adds is_favorite column if missing"""
    with app.app_context():
        db = get_db()
        cur = db.cursor()
        try:
            cur.execute("SELECT is_favorite FROM cars LIMIT 1")
        except sqlite3.OperationalError:
            print("🛠 Migration: adding 'is_favorite' column...")
            cur.execute("ALTER TABLE cars ADD COLUMN is_favorite INTEGER DEFAULT 0")
            db.commit()

@app.route('/toggle_favorite/<car_id>', methods=['POST'])
def toggle_favorite(car_id):
    """Toggles favorite status (AJAX)"""
    db = get_db()
    cur = db.cursor()
    
    # Toggle 0 -> 1 or 1 -> 0
    cur.execute("""
        UPDATE cars 
        SET is_favorite = CASE WHEN is_favorite = 1 THEN 0 ELSE 1 END 
        WHERE id = ?
    """, (car_id,))
    db.commit()
    
    # Get new status
    cur.execute("SELECT is_favorite FROM cars WHERE id = ?", (car_id,))
    row = cur.fetchone()
    new_status = row['is_favorite'] if row else 0
    
    # FIXED: variable name was wrong in previous version
    return jsonify({'status': 'success', 'is_favorite': new_status})

@app.route('/')
def index():
    # Filter parameters
    min_price = request.args.get('min_price')
    max_price = request.args.get('max_price')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    show_favorites = request.args.get('show_favorites')

    query = "SELECT * FROM cars WHERE image_url IS NOT NULL"
    params = []

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
        query += " AND created_at <= ?"
        params.append(end_date + "T23:59:59")

    if show_favorites == '1':
        query += " AND is_favorite = 1"

    query += " ORDER BY created_at DESC LIMIT 300"

    cur = get_db().cursor()
    cur.execute(query, params)
    cars = cur.fetchall()

    # --- PRICE ANALYTICS ---
    prices = [c['price_uah'] for c in cars if c['price_uah'] and c['price_uah'] > 0]
    avg_price = sum(prices) / len(prices) if prices else 0

    return render_template('index.html', cars=cars, 
                           min_price=min_price, max_price=max_price,
                           start_date=start_date, end_date=end_date,
                           show_favorites=show_favorites,
                           avg_price=int(avg_price))

if __name__ == '__main__':
    init_db_updates()
    app.run(debug=True, host='0.0.0.0', port=5000)