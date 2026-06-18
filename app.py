from flask import Flask, render_template_string, request, redirect, session
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = 'inventory_secret_key_2026_palitan_mo_to'

DB_CONFIG = {
    'host': 'db.dazhlgpqbbkgtgmhnrq.supabase.co',  # <-- PALITAN MO
    'database': 'postgres',
    'user': 'postgres',
    'password': 'PASSWORD_MO_DITO',  # <-- PALITAN MO
    'port': 5432
}

def get_db():
    try:
        return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
    except Exception as e:
        return str(e)

@app.route('/')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login.html')
    
    conn = get_db()
    if isinstance(conn, str):
        return f"DB Error: {conn}"  # para makita error agad
    
    cur = conn.cursor()
    
    try:
        cur.execute("SELECT * FROM modules ORDER BY id DESC")
        modules = cur.fetchall()
        
        cur.execute("""
            SELECT i.*, m.name as module_name 
            FROM items i 
            JOIN modules m ON i.module_id = m.id 
            ORDER BY i.id DESC
        """)
        items = cur.fetchall()
    except Exception as e:
        return f"SQL Error: {e}"  # para makita kung anong table kulang
    
    cur.close()
    conn.close()
    
    html = '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Inventory Dashboard</title>
        <style>
            body { font-family: Arial; padding: 20px; background: #f5f5f5; }
            .card { background: white; padding: 20px; margin-bottom: 20px; border-radius: 8px; }
            table { width: 100%; border-collapse: collapse; }
            th, td { padding: 10px; border: 1px solid #ddd; text-align: left; }
            th { background: #4CAF50; color: white; }
            .logout { float: right; background: red; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }
            .error { background: #ffdddd; padding: 15px; border-left: 5px solid red; }
        </style>
    </head>
    <body>
        <a href="/logout" class="logout">Logout</a>
        <h1>Inventory System Dashboard</h1>
        
        <div class="card">
            <h2>Modules</h2>
            {% if modules %}
            <table>
                <tr><th>ID</th><th>Module Name</th></tr>
                {% for m in modules %}
                <tr><td>{{ m.id }}</td><td>{{ m.name }}</td></tr>
                {% endfor %}
            </table>
            {% else %}
            <p>Walang modules pa. Add ka muna sa DB.</p>
            {% endif %}
        </div>

        <div class="card">
            <h2>Items</h2>
            {% if items %}
            <table>
                <tr><th>ID</th><th>Module</th><th>Item Name</th><th>Qty</th><th>Unit</th></tr>
                {% for i in items %}
                <tr>
                    <td>{{ i.id }}</td>
                    <td>{{ i.module_name }}</td>
                    <td>{{ i.name }}</td>
                    <td>{{ i.qty }}</td>
                    <td>{{ i.unit }}</td>
                </tr>
                {% endfor %}
            </table>
            {% else %}
            <p>Walang items pa.</p>
            {% endif %}
        </div>
    </body>
    </html>
    '''
    return render_template_string(html, modules=modules, items=items)

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
