from flask import Flask, render_template, request, redirect, session, jsonify
import json
import os
import re
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)

# ================= SECRET KEY (RENDER SAFE) =================
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret_key")

# ================= FILES =================
USER_FILE = "users.json"
MODULE_FILE = "modules.json"

# ================= SAFE JSON =================
def load_json(file, default):
    if not os.path.exists(file):
        return default
    try:
        with open(file, "r") as f:
            return json.load(f)
    except:
        return default

def save_json(file, data):
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
    return load_json(USER_FILE, {})

def save_users(users):
    save_json(USER_FILE, users)

# ================= AUTO ADMIN =================
def ensure_admin():
    users = load_users()

    if "admin" not in users:
        users["admin"] = {
            "password": generate_password_hash("admin123"),
            "role": "admin"
        }
        save_users(users)

ensure_admin()

# ================= LOGIN (FIXED USERNAME BUG) =================
@app.route("/", methods=["GET", "POST"])
def index():
    users = load_users()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        action = request.form.get("action")

        # ================= LOGIN =================
        if action == "login":
            if username in users:
                user_data = users[username]

                # OLD FORMAT SUPPORT (string password)
                if isinstance(user_data, str):
                    if check_password_hash(user_data, password):
                        session["user"] = username
                        return redirect("/dashboard")

                # NEW FORMAT SUPPORT (dict password)
                elif isinstance(user_data, dict):
                    if "password" in user_data:
                        if check_password_hash(user_data["password"], password):
                            session["user"] = username
                            return redirect("/dashboard")

            return render_template("index.html", error="Invalid username or password")

        # ================= REGISTER =================
        if action == "register":
            if username in users:
                return render_template("index.html", error="Username already exists")

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
    if "user" not in session:
        return redirect("/")

    users = load_users()
    role = users.get(session["user"], {}).get("role", "user")

    return render_template(
        "dashboard.html",
        user=session["user"],
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
    return jsonify(load_json(MODULE_FILE, []))

@app.route("/save_modules", methods=["POST"])
def save_modules():
    save_json(MODULE_FILE, request.json.get("modules", []))
    return jsonify({"status": "ok"})

@app.route("/add_module", methods=["POST"])
def add_module():
    name = request.json.get("name", "").strip()
    modules = load_json(MODULE_FILE, [])

    if name and name not in modules:
        modules.append(name)
        save_json(MODULE_FILE, modules)

    return jsonify({"status": "ok"})

@app.route("/delete_module", methods=["POST"])
def delete_module():
    i = request.json.get("index", -1)
    modules = load_json(MODULE_FILE, [])

    if 0 <= i < len(modules):
        modules.pop(i)
        save_json(MODULE_FILE, modules)

    return jsonify({"status": "ok"})

@app.route("/rename_module", methods=["POST"])
def rename_module():
    i = request.json.get("index", -1)
    new_name = request.json.get("newName", "").strip()

    modules = load_json(MODULE_FILE, [])

    if 0 <= i < len(modules) and new_name:
        modules[i] = new_name
        save_json(MODULE_FILE, modules)

    return jsonify({"status": "ok"})

# ================= MODULE PAGE =================
@app.route("/module/<name>")
def module(name):
    if "user" not in session:
        return redirect("/")

    users = load_users()
    role = users.get(session["user"], {}).get("role", "user")

    return render_template(
        "module.html",
        module_name=name,
        is_admin=(role == "admin")
    )

# ================= ITEMS =================
@app.route("/get_items/<module>")
def get_items(module):
    return jsonify(load_json(get_items_file(module), []))

@app.route("/save_items/<module>", methods=["POST"])
def save_items(module):
    save_json(get_items_file(module), request.json.get("items", []))
    return jsonify({"status": "ok"})

# ================= HISTORY =================
@app.route("/add_history/<module>", methods=["POST"])
def add_history(module):
    file = get_history_file(module)
    history = load_json(file, [])

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

    save_json(file, history)
    return jsonify({"status": "ok"})

# ================= LOW STOCK =================
@app.route("/low_stock/<module>")
def low_stock(module):
    items = load_json(get_items_file(module), [])
    return jsonify([i for i in items if int(i.get("soh", 0)) <= 5])

# ================= RUN =================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
