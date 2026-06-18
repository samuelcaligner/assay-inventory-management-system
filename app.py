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

    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS modules (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id SERIAL PRIMARY KEY,
            module_name VARCHAR(255) NOT NULL,
            item_code VARCHAR(255),
            description TEXT,
            quantity INTEGER DEFAULT 0,
            in_qty INTEGER DEFAULT 0,
            out_qty INTEGER DEFAULT 0,
            soh INTEGER DEFAULT 0
        )
    ''')

    cur.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id SERIAL PRIMARY KEY,
            module_name VARCHAR(255) NOT NULL,
            item_code VARCHAR(255),
            description TEXT,
            action_type VARCHAR(50),
            quantity INTEGER,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            username VARCHAR(255)
        )
    ''')

    cur.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cur.fetchone():
        hashed = generate_password_hash('admin123')
        cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", ('admin', hashed))

    conn.commit()
    cur.close()
    conn.close()

init_db()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        action = request.form['action']

        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("SELECT password FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if action == 'login':
            if user and check_password_hash(user[0], password):
                session['user'] = username
                return redirect(url_for('dashboard'))
            return render_template('index.html', error='Invalid credentials')

        elif action == 'register':
            if user:
                return render_template('index.html', error='Username exists')
            hashed = generate_password_hash(password)
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed))
            conn.commit()
            cur.close()
            conn.close()
            session['user'] = username
            return redirect(url_for('dashboard'))

    return render_template('index.html')

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

@app.route('/save_modules', methods=['POST'])
def save_modules():
    if 'user' not in session or session['user']!= 'admin':
        return jsonify({'status': 'error'})
    data = request.get_json()
    modules = data.get('modules', [])

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM modules")
    for name in modules:
        if name.strip():
            cur.execute("INSERT INTO modules (name) VALUES (%s)", (name.strip(),))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/module/<name>')
def module_page(name):
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('module.html', module_name=name, user=session['user'], is_admin=(session['user']=='admin'))

@app.route('/get_items/<module>')
def get_items(module):
    if 'user' not in session:
        return jsonify([])
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT item_code, description, quantity, in_qty, out_qty, soh FROM items WHERE module_name = %s ORDER BY id", (module,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    items = [{'item_code': r[0], 'description': r[1], 'quantity': r[2], 'in': r[3], 'out': r[4], 'soh': r[5]} for r in rows]
    return jsonify(items)

@app.route('/save_items/<module>', methods=['POST'])
def save_items(module):
    if 'user' not in session:
        return jsonify({'status': 'error'})
    data = request.get_json()
    items = data.get('items', [])

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM items WHERE module_name = %s", (module,))
    for item in items:
        cur.execute("""
            INSERT INTO items (module_name, item_code, description, quantity, in_qty, out_qty, soh)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (module, item.get('item_code'), item.get('description'),
              item.get('quantity', 0), item.get('in', 0), item.get('out', 0), item.get('soh', 0)))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/get_history/<module>')
def get_history(module):
    if 'user' not in session:
        return jsonify([])
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT date, time, username, item_code, description, action_type, quantity
        FROM history WHERE module_name = %s ORDER BY timestamp DESC LIMIT 100
    """, (module,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    history = [{'date': str(r[0]), 'time': str(r[1]), 'user': r[2], 'item_code': r[3],
                'description': r[4], 'type': r[5], 'quantity': r[6]} for r in rows]
    return jsonify(history)

@app.route('/add_history/<module>', methods=['POST'])
def add_history(module):
    if 'user' not in session:
        return jsonify({'status': 'error'})
    data = request.get_json()

    conn = get_db_connection()
    cur = conn.cursor()
    now = datetime.now()
    cur.execute("""
        INSERT INTO history (module_name, date, time, username, item_code, description, action_type, quantity, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (module, now.date(), now.time(), session['user'], data.get('item_code'),
          data.get('description'), data.get('type'), data.get('quantity'), now))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
