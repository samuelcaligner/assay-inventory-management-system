from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import json, os, re
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_key")

# ================= FILES =================
USER_FILE = "users.json"
MODULE_FILE = "modules.json"

# ================= HELPERS =================
def safe_json(file, default):
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

def safe_name(name):
    return re.sub(r"[^a-zA-Z0-9_-]", "_", name)

def get_items_file(module):
    return f"items_{safe_name(module)}.json"

def get_history_file(module):
    return f"history_{safe_name(module)}.json"

# ================= USERS =================
def load_users():
    return safe_json(USER_FILE, {})

def save_users(users):
    save_json(USER_FILE, users)

# ================= MODULES =================
def load_modules():
    return safe_json(MODULE_FILE, [])

def save_modules(mods):
    save_json(MODULE_FILE, mods)

# ================= LOGIN =================
@app.route("/", methods=["GET", "POST"])
def index():
    users = load_users()

    if "admin" not in users:
        users["admin"] = {
            "password": generate_password_hash("admin123"),
            "role": "admin"
        }
        save_users(users)

    if request.method == "POST":
        u = request.form["username"].strip()
        p = request.form["password"]
        action = request.form["action"]

        users = load_users()

        if action == "login":
            if u in users and check_password_hash(users[u]["password"], p):
                session["user"] = u
                return redirect("/dashboard")
            return render_template("index.html", error="Invalid login")

        if action == "register":
            if u in users:
                return render_template("index.html", error="User exists")

            users[u] = {
                "password": generate_password_hash(p),
                "role": "user"
            }
            save_users(users)
            session["user"] = u
            return redirect("/dashboard")

    return render_template("index.html")

# ================= DASHBOARD =================
@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")

    users = load_users()
    role = users.get(session["user"], {}).get("role", "user")

    return render_template("dashboard.html", user=session["user"], is_admin=(role == "admin"))

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
    mods = load_modules()

    if name and name not in mods:
        mods.append(name)
        save_modules(mods)

    return jsonify({"status": "ok"})

@app.route("/delete_module", methods=["POST"])
def delete_module():
    i = request.json.get("index", -1)
    mods = load_modules()

    if 0 <= i < len(mods):
        mods.pop(i)
        save_modules(mods)

    return jsonify({"status": "ok"})

@app.route("/rename_module", methods=["POST"])
def rename_module():
    i = request.json.get("index", -1)
    name = request.json.get("newName", "").strip()

    mods = load_modules()

    if 0 <= i < len(mods) and name:
        mods[i] = name
        save_modules(mods)

    return jsonify({"status": "ok"})

# ================= MODULE PAGE =================
@app.route("/module/<name>")
def module(name):
    if "user" not in session:
        return redirect("/")
    users = load_users()
    role = users.get(session["user"], {}).get("role", "user")

    return render_template("module.html", module_name=name, is_admin=(role == "admin"))

# ================= ITEMS =================
@app.route("/get_items/<module>")
def get_items(module):
    return jsonify(safe_json(get_items_file(module), []))

@app.route("/save_items/<module>", methods=["POST"])
def save_items(module):
    save_json(get_items_file(module), request.json.get("items", []))
    return jsonify({"status": "ok"})

# ================= HISTORY =================
@app.route("/get_history/<module>")
def get_history(module):
    return jsonify(safe_json(get_history_file(module), []))

@app.route("/add_history/<module>", methods=["POST"])
def add_history(module):
    file = get_history_file(module)
    history = safe_json(file, [])

    data = request.json

    history.append({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "time": datetime.now().strftime("%H:%M:%S"),
        "user": session["user"],
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
    items = safe_json(get_items_file(module), [])
    return jsonify([i for i in items if int(i.get("soh", 0)) <= 5])

# ================= RUN =================
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
