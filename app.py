from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'assay_secret_key_2026')

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    # Users
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    # Modules
    cur.execute('''
        CREATE TABLE IF NOT EXISTS modules (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL
        )
    ''')

    # Items - UNIQUE para di magduplicate
    cur.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id SERIAL PRIMARY KEY,
            module VARCHAR(255) NOT NULL,
            item_code VARCHAR(255),
            item_desc TEXT,
            quantity INTEGER DEFAULT 0,
            in_qty INTEGER DEFAULT 0,
            out_qty INTEGER DEFAULT 0,
            soh INTEGER DEFAULT 0,
            UNIQUE(module, item_code)
        )
    ''')

    # History
    cur.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id SERIAL PRIMARY KEY,
            module VARCHAR(255) NOT NULL,
            date DATE,
            time TIME,
            username VARCHAR(255),
            item_code VARCHAR(255),
            item_desc TEXT,
            in_qty INTEGER,
            out_qty INTEGER,
            soh INTEGER
        )
    ''')

    # Default admin
    cur.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cur.fetchone():
        hashed = generate_password_hash('admin123')
        cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", ('admin', hashed))

    conn.commit()
    cur.close()
    conn.close()
    print("DB Initialized OK")

init_db()

@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        action = request.form['action']

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT password FROM users WHERE username = %s", (username,))
        user = cur.fetchone()

        if action == 'login':
            if user and check_password_hash(user[0], password):
                session['user'] = username
                cur.close()
                conn.close()
                return redirect(url_for('dashboard'))
            error = 'Invalid username or password'

        elif action == 'register':
            if user:
                error = 'Username already exists'
            else:
                hashed = generate_password_hash(password)
                cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed))
                conn.commit()
                session['user'] = username
                cur.close()
                conn.close()
                return redirect(url_for('dashboard'))

        cur.close()
        conn.close()

    return render_template('index.html', error=error)

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM modules ORDER BY id")
    modules = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()

    return render_template('dashboard.html', user=session['user'], modules=modules, is_admin=(session['user']=='admin'))

@app.route('/get_modules')
def get_modules():
    if 'user' not in session:
        return jsonify([])
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM modules ORDER BY id")
    modules = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(modules)

@app.route('/module/<name>')
def module_page(name):
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('module.html', module_name=name, user=session['user'], is_admin=(session['user']=='admin'))

@app.route('/get_items/<module>')
def get_items(module):
    if 'user' not in session:
        return jsonify([])
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT item_code, item_desc, quantity, in_qty, out_qty, soh FROM items WHERE module = %s ORDER BY id", (module,))
        rows = cur.fetchall()
        cur.close()
        conn.close()
        items = [{'item_code': r[0], 'item_desc': r[1], 'quantity': r[2], 'in': r[3], 'out': r[4], 'soh': r[5]} for r in rows]
        print(f"Loaded {len(items)} items for {module}")
        return jsonify(items)
    except Exception as e:
        print(f"ERROR sa get_items: {e}")
        return jsonify([])

@app.route('/save_items/<module>', methods=['POST'])
def save_items(module):
    if 'user' not in session:
        return jsonify({'status': 'error'})

    data = request.get_json()
    items = data.get('items', [])

    print(f"SAVING {len(items)} items for module {module}")

    conn = get_db_connection()
    cur = conn.cursor()

    for item in items:
        item_code = item.get('item_code', '').strip()
        if not item_code:
            continue

        # UPDATE KUNG MERON, INSERT KUNG WALA - WALANG DELETE!
        cur.execute("SELECT id FROM items WHERE module = %s AND item_code = %s", (module, item_code))
        existing = cur.fetchone()

        if existing:
            cur.execute("""
                UPDATE items SET item_desc=%s, quantity=%s, in_qty=%s, out_qty=%s, soh=%s
                WHERE module=%s AND item_code=%s
            """, (item.get('item_desc'), item.get('quantity', 0),
                  item.get('in', 0), item.get('out', 0), item.get('soh', 0),
                  module, item_code))
        else:
            cur.execute("""
                INSERT INTO items (module, item_code, item_desc, quantity, in_qty, out_qty, soh)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (module, item_code, item.get('item_desc'), item.get('quantity', 0),
                  item.get('in', 0), item.get('out', 0), item.get('soh', 0)))

        # SAVE HISTORY DIN
        cur.execute("""
            INSERT INTO history (module, date, time, username, item_code, item_desc, in_qty, out_qty, soh)
            VALUES (%s, CURRENT_DATE, CURRENT_TIME, %s, %s, %s, %s, %s, %s)
        """, (module, session['user'], item_code, item.get('item_desc'),
              item.get('in', 0), item.get('out', 0), item.get('soh', 0)))

    conn.commit()
    print(f"COMMITTED TO DB FOR {module}")
    cur.close()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/add_history/<module>', methods=['POST'])
def add_history(module):
    if 'user' not in session:
        return jsonify({'status': 'error'})

    data = request.get_json()
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO history (module, date, time, username, item_code, item_desc, in_qty, out_qty, soh)
        VALUES (%s, CURRENT_DATE, CURRENT_TIME, %s, %s, %s, %s, %s, %s)
    """, (module, session['user'], data.get('item_code'), data.get('item_desc'),
          data.get('in', 0), data.get('out', 0), data.get('soh', 0)))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/get_history/<module>')
def get_history(module):
    if 'user' not in session:
        return jsonify([])
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT date, time, username, item_code, item_desc, in_qty, out_qty, soh
            FROM history
            WHERE module = %s
            ORDER BY id DESC
            LIMIT 100
        """, (module,))
        rows = cur.fetchall()
        cur.close()
        conn.close()

        history = [{
            'date': str(r[0]),
            'time': str(r[1]),
            'user': r[2],
            'item_code': r[3],
            'item_desc': r[4],
            'in': r[5],
            'out': r[6],
            'soh': r[7]
        } for r in rows]
        return jsonify(history)
    except Exception as e:
        print(f"ERROR sa get_history: {e}")
        return jsonify([])

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
