from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'assay_secret_key_2026_change_this')

def get_db():
    return psycopg2.connect(os.environ['DATABASE_URL'], sslmode='require')

# ========== LOGIN / REGISTER ==========
@app.route('/', methods=['GET', 'POST'])
def index():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        action = request.form.get('action')

        conn = get_db()
        cur = conn.cursor()

        if action == 'login':
            cur.execute("SELECT id, username, password, is_admin FROM users WHERE username = %s", (username,))
            user = cur.fetchone()
            if user and check_password_hash(user[2], password):
                session['user_id'] = user[0]
                session['username'] = user[1]
                session['is_admin'] = user[3]
                cur.close()
                conn.close()
                return redirect(url_for('dashboard'))
            else:
                error = 'Invalid username or password'

        elif action == 'register':
            cur.execute("SELECT id FROM users WHERE username = %s", (username,))
            if cur.fetchone():
                error = 'Username already exists'
            else:
                hashed = generate_password_hash(password)
                cur.execute("INSERT INTO users (username, password, is_admin) VALUES (%s, %s, FALSE) RETURNING id", (username, hashed))
                user_id = cur.fetchone()[0]
                conn.commit()
                session['user_id'] = user_id
                session['username'] = username
                session['is_admin'] = False
                cur.close()
                conn.close()
                return redirect(url_for('dashboard'))

        cur.close()
        conn.close()
    return render_template('login.html', error=error)

# ========== DASHBOARD ==========
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT module_name FROM modules ORDER BY id")
    modules = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()

    return render_template('dashboard.html', username=session['username'], modules=modules, is_admin=session['is_admin'])

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ========== MODULE PAGE ==========
@app.route('/module/<name>')
def module_page(name):
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('module.html', module_name=name, is_admin=session['is_admin'])

# ========== MODULES CRUD - ADMIN ONLY ==========
@app.route('/get_modules')
def get_modules():
    if 'user_id' not in session:
        return jsonify([])
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT module_name FROM modules ORDER BY id")
    modules = [row[0] for row in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(modules)

@app.route('/add_module', methods=['POST'])
def add_module():
    if 'user_id' not in session or not session['is_admin']:
        return jsonify({'status': 'error', 'message': 'Admin only'})
    name = request.json.get('name', '').strip()
    if not name:
        return jsonify({'status': 'error', 'message': 'Empty name'})

    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO modules (module_name) VALUES (%s)", (name,))
        conn.commit()
        status = 'ok'
    except psycopg2.errors.UniqueViolation:
        conn.rollback()
        status = 'exists'
    cur.close()
    conn.close()
    return jsonify({'status': status})

@app.route('/delete_module', methods=['POST'])
def delete_module():
    if 'user_id' not in session or not session['is_admin']:
        return jsonify({'status': 'error', 'message': 'Admin only'})
    name = request.json.get('name', '')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM modules WHERE module_name = %s", (name,))
    cur.execute("DELETE FROM items WHERE module_name = %s", (name,))
    cur.execute("DELETE FROM history WHERE module_name = %s", (name,))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'status': 'ok'})

@app.route('/rename_module', methods=['POST'])
def rename_module():
    if 'user_id' not in session or not session['is_admin']:
        return jsonify({'status': 'error', 'message': 'Admin only'})
    old_name = request.json.get('oldName', '')
    new_name = request.json.get('newName', '').strip()
    if not new_name:
        return jsonify({'status': 'error', 'message': 'Empty name'})

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE modules SET module_name = %s WHERE module_name = %s", (new_name, old_name))
    cur.execute("UPDATE items SET module_name = %s WHERE module_name = %s", (new_name, old_name))
    cur.execute("UPDATE history SET module_name = %s WHERE module_name = %s", (new_name, old_name))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'status': 'ok'})

# ========== ITEMS ==========
@app.route('/get_items/<module>')
def get_items(module):
    if 'user_id' not in session:
        return jsonify([])
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT item_code, item_desc, uom, out_qty, in_qty, soh, remark FROM items WHERE module_name = %s ORDER BY id", (module,))
    items = [{'item_code':r[0],'item_desc':r[1],'uom':r[2],'out':r[3],'in':r[4],'soh':r[5],'remark':r[6]} for r in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(items)

@app.route('/save_items/<module>', methods=['POST'])
def save_items(module):
    if 'user_id' not in session:
        return jsonify({'status': 'error'})
    items = request.json.get('items', [])

    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM items WHERE module_name = %s", (module,))
    for item in items:
        if item['item_code'].strip():
            cur.execute("INSERT INTO items (module_name, item_code, item_desc, uom, out_qty, in_qty, soh, remark) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (module, item['item_code'], item['item_desc'], item['uom'], int(item['out'] or 0), int(item['in'] or 0), int(item['soh'] or 0), item['remark']))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'status': 'ok'})

# ========== HISTORY ==========
@app.route('/get_history/<module>')
def get_history(module):
    if 'user_id' not in session:
        return jsonify([])
    conn = get_db()
    cur = conn.cursor()
    cur.execute('SELECT item_code, item_desc, in_qty, out_qty, soh, date, time, "user" FROM history WHERE module_name = %s ORDER BY id DESC LIMIT 100', (module,))
    history = [{'item_code':r[0],'item_desc':r[1],'in':r[2],'out':r[3],'soh':r[4],'date':str(r[5]),'time':str(r[6]),'user':r[7]} for r in cur.fetchall()]
    cur.close()
    conn.close()
    return jsonify(history)

@app.route('/add_history/<module>', methods=['POST'])
def add_history(module):
    if 'user_id' not in session:
        return jsonify({'status':'error'})
    data = request.json
    now = datetime.now()

    conn = get_db()
    cur = conn.cursor()
    cur.execute('INSERT INTO history (module_name, item_code, item_desc, in_qty, out_qty, soh, date, time, "user") VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)',
                (module, data.get('item_code'), data.get('item_desc'), int(data.get('in') or 0), int(data.get('out') or 0), int(data.get('soh') or 0), now.date(), now.time().strftime('%H:%M:%S'), session['username']))
    conn.commit()
    cur.close()
    conn.close()
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
