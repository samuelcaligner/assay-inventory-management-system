from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json
import os
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'assay_secret_key_2026'

USER_FILE = 'users.json'
MODULE_FILE = 'modules.json'

def load_users():
    if os.path.exists(USER_FILE):
        with open(USER_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USER_FILE, 'w') as f:
        json.dump(users, f)

def load_modules():
    if os.path.exists(MODULE_FILE):
        with open(MODULE_FILE, 'r') as f:
            return json.load(f)
    return []

def save_modules(modules):
    with open(MODULE_FILE, 'w') as f:
        json.dump(modules, f)

def get_items_file(module):
    safe_name = module.replace(' ', '_').replace('/', '_')
    return f'items_{safe_name}.json'

def get_history_file(module):
    safe_name = module.replace(' ', '_').replace('/', '_')
    return f'history_{safe_name}.json'

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        action = request.form['action']
        users = load_users()

        if action == 'login':
            if username in users and check_password_hash(users[username], password):
                session['user'] = username
                return redirect(url_for('dashboard'))
            else:
                return render_template('index.html', error='Invalid username or password')

        elif action == 'register':
            if username in users:
                return render_template('index.html', error='Username already exists')
            users[username] = generate_password_hash(password)
            save_users(users)
            session['user'] = username
            return redirect(url_for('dashboard'))

    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html', user=session['user'])

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('index'))

@app.route('/get_modules')
def get_modules():
    if 'user' not in session:
        return jsonify([])
    return jsonify(load_modules())

@app.route('/save_modules', methods=['POST'])
def save_modules_route():
    if 'user' not in session:
        return jsonify({'status': 'error'})
    modules = request.json.get('modules', [])
    save_modules(modules)
    return jsonify({'status': 'ok'})

@app.route('/add_module', methods=['POST'])
def add_module():
    if 'user' not in session:
        return jsonify({'status': 'error'})
    name = request.json.get('name', '')
    modules = load_modules()
    modules.append(name)
    save_modules(modules)
    return jsonify({'status': 'ok'})

@app.route('/delete_module', methods=['POST'])
def delete_module():
    if 'user' not in session:
        return jsonify({'status': 'error'})
    index = request.json.get('index', -1)
    modules = load_modules()
    if 0 <= index < len(modules):
        modules.pop(index)
        save_modules(modules)
    return jsonify({'status': 'ok'})

@app.route('/rename_module', methods=['POST'])
def rename_module():
    if 'user' not in session:
        return jsonify({'status': 'error'})
    index = request.json.get('index', -1)
    new_name = request.json.get('newName', '')
    modules = load_modules()
    if 0 <= index < len(modules) and new_name:
        modules[index] = new_name
        save_modules(modules)
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
    file = get_items_file(module)
    if os.path.exists(file):
        with open(file, 'r') as f:
            return jsonify(json.load(f))
    return jsonify([])

@app.route('/save_items/<module>', methods=['POST'])
def save_items(module):
    if 'user' not in session:
        return jsonify({'status': 'error'})
    items = request.json.get('items', [])
    file = get_items_file(module)
    with open(file, 'w') as f:
        json.dump(items, f)
    return jsonify({'status': 'ok'})

@app.route('/get_history/<module>')
def get_history(module):
    if 'user' not in session:
        return jsonify([])
    file = get_history_file(module)
    if os.path.exists(file):
        with open(file, 'r') as f:
            return jsonify(json.load(f))
    return jsonify([])

@app.route('/add_history/<module>', methods=['POST'])
def add_history(module):
    if 'user' not in session:
        return jsonify({'status': 'error'})

    data = request.json
    file = get_history_file(module)

    history = []
    if os.path.exists(file):
        with open(file, 'r') as f:
            history = json.load(f)

    history.append({
        'date': datetime.now().strftime('%Y-%m-%d'),
        'time': datetime.now().strftime('%H:%M:%S'),
        'user': session['user'],
        'item_code': data.get('item_code'),
        'item_desc': data.get('item_desc'),
        'in': data.get('in'),
        'out': data.get('out'),
        'soh': data.get('soh')
    })

    with open(file, 'w') as f:
        json.dump(history, f)

    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)