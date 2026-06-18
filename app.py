from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import os
import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'assay_secret_key_2026'

DATABASE_URL = os.getenv('DATABASE_URL')

def get_db_connection():
    conn = psycopg2.connect(DATABASE_URL)
    return conn

def init_db():
    conn = get_db_connection()
    cur = conn.cursor()

    # Users table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(255) UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    # Modules table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS modules (
            id SERIAL PRIMARY KEY,
            name VARCHAR(255) UNIQUE NOT NULL
        )
    ''')

    # Items table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id SERIAL PRIMARY KEY,
            module VARCHAR(255) NOT NULL,
            item_code VARCHAR(255),
            item_desc TEXT,
            quantity INTEGER DEFAULT 0,
            in_qty INTEGER DEFAULT 0,
            out_qty INTEGER DEFAULT 0,
            soh INTEGER DEFAULT 0
        )
    ''')

    # History table
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

    # Default admin account
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

        if action == 'login':
            cur.execute("SELECT password FROM users WHERE username = %s", (username,))
            result = cur.fetchone()
            if result and check_password_hash(result[0], password):
                session['user'] = username
                cur.close()
                conn.close()
                return redirect(url_for('dashboard'))
            else:
                cur.close()
                conn.close()
                return render_template('index.html', error='Invalid username or password')

        elif action == 'register':
            cur.execute("SELECT username FROM users WHERE username = %s", (username,))
            if cur.fetchone():
                cur.close()
                conn.close()
                return render_template('index.html', error='Username already exists')
            hashed = generate_password_hash(password)
            cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, hashed))
            conn.commit()
            session['user'] = username
            cur.close()
            conn.close()
            return redirect(url_for('dashboard'))

        cur.close()
        conn.close()
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html', user=session['user'], is_admin=session['user']=='admin')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

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
def save_modules_route():
    if 'user' not in session:
        return jsonify({'status': 'error'})
    modules = request.json.get('modules', [])
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM modules")
    for name in modules:
        cur.execute("INSERT INTO modules (name) VALUES (%s)", (name,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/add_module', methods=['POST'])
def add_module():
    if 'user' not in session or session['user']!= 'admin':
        return jsonify({'status': 'error', 'message': 'Admin only'})
    name = request.json.get('name', '')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("INSERT INTO modules (name) VALUES (%s) ON CONFLICT (name) DO NOTHING", (name,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/delete_module', methods=['POST'])
def delete_module():
    if 'user' not in session or session['user']!= 'admin':
        return jsonify({'status': 'error', 'message': 'Admin only'})
    index = request.json.get('index', -1)
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM modules ORDER BY id")
    modules = [row[0] for row in cur.fetchall()]
    if 0 <= index < len(modules):
        module_name = modules[index]
        cur.execute("DELETE FROM modules WHERE name = %s", (module_name,))
        cur.execute("DELETE FROM items WHERE module = %s", (module_name,))
        cur.execute("DELETE FROM history WHERE module = %s", (module_name,))
        conn.commit()
    cur.close()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/rename_module', methods=['POST'])
def rename_module():
    if 'user' not in session or session['user']!= 'admin':
        return jsonify({'status': 'error', 'message': 'Admin only'})
    index = request.json.get('index', -1)
    new_name = request.json.get('newName', '')
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM modules ORDER BY id")
    modules = [row[0] for row in cur.fetchall()]
    if 0 <= index < len(modules) and new_name:
        old_name = modules[index]
        cur.execute("UPDATE modules SET name = %s WHERE name = %s", (new_name, old_name))
        cur.execute("UPDATE items SET module = %s WHERE module = %s", (new_name, old_name))
        cur.execute("UPDATE history SET module = %s WHERE module = %s", (new_name, old_name))
        conn.commit()
    cur.close()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/module/<name>')
def module_page(name):
    if 'user' not in session:
        return redirect(url_for('index'))
    is_admin = session['user'] == 'admin'
    return render_template('module.html', module_name=name, is_admin=is_admin)

@app.route('/get_items/<module>')
def get_items(module):
    if 'user' not in session:
        return jsonify([])
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT item_code, item_desc, quantity, in_qty, out_qty, soh FROM items WHERE module = %s", (module,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    items = [{'item_code': r[0], 'item_desc': r[1], 'quantity': r[2], 'in': r[3], 'out': r[4], 'soh': r[5]} for r in rows]
    return jsonify(items)

@app.route('/save_items/<module>', methods=['POST'])
def save_items(module):
    if 'user' not in session:
        return jsonify({'status': 'error'})
    items = request.json.get('items', [])
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM items WHERE module = %s", (module,))
    for item in items:
        cur.execute(
            "INSERT INTO items (module, item_code, item_desc, quantity, in_qty, out_qty, soh) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (module, item.get('item_code'), item.get('item_desc'), item.get('quantity', 0),
             item.get('in', 0), item.get('out', 0), item.get('soh', 0))
        )
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
    cur.execute("SELECT date, time, username, item_code, item_desc, in_qty, out_qty, soh FROM history WHERE module = %s ORDER BY id DESC", (module,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    history = [{'date': str(r[0]), 'time': str(r[1]), 'user': r[2], 'item_code': r[3], 'item_desc': r[4], 'in': r[5], 'out': r[6], 'soh': r[7]} for r in rows]
    return jsonify(history)

@app.route('/add_history/<module>', methods=['POST'])
def add_history(module):
    if 'user' not in session:
        return jsonify({'status': 'error'})
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO history (module, date, time, username, item_code, item_desc, in_qty, out_qty, soh) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (module, datetime.now().date(), datetime.now().time(), session['user'],
         data.get('item_code'), data.get('item_desc'), data.get('in'), data.get('out'), data.get('soh'))
    )
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
