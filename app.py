from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = 'assay_inventory_secret_key_2026'

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    return psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cur.fetchone()
        cur.close()
        conn.close()

        if user:
            session['username'] = username
            session['is_admin'] = user[3] if len(user) > 3 else False
            return redirect(url_for('dashboard'))
        return 'Invalid credentials'
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT module_name FROM modules ORDER BY id")
    modules = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return render_template('dashboard.html', modules=modules, username=session['username'], is_admin=session.get('is_admin', False))

@app.route('/module/<module_name>')
@login_required
def module_page(module_name):
    return render_template('module.html', module_name=module_name, is_admin=session.get('is_admin', False), username=session['username'])

@app.route('/get_items/<module>')
@login_required
def get_items(module):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT item_code as code, item_desc as desc, quantity, in_qty as in, out_qty as out, soh FROM items WHERE module = %s ORDER BY id", (module,))
    items = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(items)

@app.route('/save_items/<module>', methods=['POST'])
@login_required
def save_items(module):
    data = request.get_json()
    items = data.get('items', [])

    conn = get_db()
    cur = conn.cursor()

    for item in items:
        code = item.get('code', '').strip()
        desc = item.get('desc', '').strip()
        uom = item.get('uom', '').strip()
        in_qty = int(item.get('in', 0) or 0)
        out_qty = int(item.get('out', 0) or 0)
        soh = int(item.get('soh', 0) or 0)

        if code == '' and desc == '':
            continue

        # Compute quantity para di mawala pag refresh
        quantity = soh + out_qty - in_qty

        # Check kung exist na para iwas ON CONFLICT error
        cur.execute("SELECT id FROM items WHERE module = %s AND item_code = %s", (module, code))
        exists = cur.fetchone()

        if exists:
            cur.execute("""
                UPDATE items SET item_desc = %s, quantity = %s, in_qty = %s, out_qty = %s, soh = %s
                WHERE module = %s AND item_code = %s
            """, (desc, quantity, in_qty, out_qty, soh, module, code))
        else:
            cur.execute("""
                INSERT INTO items (module, item_code, item_desc, quantity, in_qty, out_qty, soh)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (module, code, desc, quantity, in_qty, out_qty, soh))

    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/add_history/<module>', methods=['POST'])
@login_required
def add_history(module):
    data = request.get_json()
    now = datetime.now()

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO history (module, date, time, username, item_code, item_desc, in_qty, out_qty, soh)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (module, now.date(), now.time(), session['username'], data['item_code'], data['item_desc'], data['in'], data['out'], data['soh']))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/get_history/<module>')
@login_required
def get_history(module):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT date, time, username as user, item_code, item_desc, in_qty as in, out_qty as out, soh FROM history WHERE module = %s ORDER BY id DESC", (module,))
    history = cur.fetchall()
    cur.close()
    conn.close()
    return jsonify(history)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
