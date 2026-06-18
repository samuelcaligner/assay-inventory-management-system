from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json
import os
import re
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)

# ================= SAFE SECRET KEY (RENDER READY) =================
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret_change_me")

# ================= FILES =================
USER_FILE = "users.json"
MODULE_FILE = "modules.json"

# ================= SAFE JSON HANDLER =================
def safe_load(file, default):
    if not os.path.exists(file):
        return default
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return default

def safe_save(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

# ================= MODULE SAFE NAME =================
def safe_name(name):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)

def get_items_file(module):
    return f"items_{safe_name(module)}.json"

def get_history_file(module):
    return f"history_{safe_name(module)}.json"

# ================= USERS =================
def load_users():
    return safe_load(USER_FILE, {})

def save_users(data):
    safe_save(USER_FILE, data)

# ================= MODULES =================
def load_modules():
    return safe_load(MODULE_FILE, [])

def save_modules(data):
    safe_save(MODULE_FILE, data)

# ================= ROOT LOGIN =================
@app.route("/", methods=["GET", "POST"])
def index():
    users = load_users()

    # auto-create admin safely
    if "admin" not in users:
        users["admin"] = {
            "password": generate_password_hash("admin123"),
            "role": "admin"
        }
        save_users(users)

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        action = request.form.get("action")

        users = load_users()

        if action == "login":
            if username in users:
                user_data = users[username]

                if "password" in user_data and check_password_hash(user_data["password"], password):
                    session["user"] = username
                    return redirect("/dashboard")

            return render_template("index.html", error="Invalid username or password")

        if action == "register":
            if username in users:
                return render_template("index.html", error="User already exists")

            users[username] = {
                "password": generate_password_hash(password),
                "role": "user"
            }

            save_users(users)
            session["user"] = username
            return redirect("/dashboard")

    return render_template("index.html")

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    user = session.get("user")
    if not user:
        return redirect("/")

    users = load_users()
    role = users.get(user, {}).get("role", "user")

    return render_template(
        "dashboard.html",
        user=user,
        is_admin=(role == "admin")
    )

# ================= LOGOUT =================
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ================= MODULES =================
@app.route("/get_modules")
def get_modules():
    return jsonify(load_modules())

@app.route("/save_modules", methods=["POST"])
def save_modules_route():
    save_modules(request.json.get("modules", []))
    return jsonify({"status": "ok"})

@app.route("/add_module", methods=["POST"])
def add_module():
    name = request.json.get("name", "").strip()
    modules = load_modules()

    if name and name not in modules:
        modules.append(name)
        save_modules(modules)

    return jsonify({"status": "ok"})

@app.route("/delete_module", methods=["POST"])
def delete_module():
    i = request.json.get("index", -1)
    modules = load_modules()

    if 0 <= i < len(modules):
        modules.pop(i)
        save_modules(modules)

    return jsonify({"status": "ok"})

@app.route("/rename_module", methods=["POST"])
def rename_module():
    i = request.json.get("index", -1)
    new_name = request.json.get("newName", "").strip()

    modules = load_modules()

    if 0 <= i < len(modules) and new_name:
        modules[i] = new_name
        save_modules(modules)

    return jsonify({"status": "ok"})

# ================= MODULE PAGE =================
@app.route("/module/<name>")
def module(name):
    user = session.get("user")
    if not user:
        return redirect("/")

    users = load_users()
    role = users.get(user, {}).get("role", "user")

    return render_template("module.html", module_name=name, is_admin=(role == "admin"))

# ================= ITEMS =================
@app.route("/get_items/<module>")
def get_items(module):
    return jsonify(safe_load(get_items_file(module), []))

@app.route("/save_items/<module>", methods=["POST"])
def save_items(module):
    safe_save(get_items_file(module), request.json.get("items", []))
    return jsonify({"status": "ok"})

# ================= HISTORY =================
@app.route("/get_history/<module>")
def get_history(module):
    return jsonify(safe_load(get_history_file(module), []))

@app.route("/add_history/<module>", methods=["POST"])
def add_history(module):
    file = get_history_file(module)
    history = safe_load(file, [])

    data = request.json

    history.append({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": datetime.now().strftime("%H:%M:%S"),
        "user": session.get("user", "unknown"),
        "item_code": data.get("item_code"),
        "item_desc": data.get("item_desc"),
        "in": data.get("in", 0),
        "out": data.get("out", 0),
        "soh": data.get("soh", 0)
    })

    safe_save(file, history)
    return jsonify({"status": "ok"})

# ================= LOW STOCK =================
@app.route("/low_stock/<module>")
def low_stock(module):
    items = safe_load(get_items_file(module), [])
    return jsonify([i for i in items if int(i.get("soh", 0)) <= 5])

# ================= START APP =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
