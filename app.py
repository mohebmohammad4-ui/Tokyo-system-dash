from flask import Flask, render_template, request, jsonify
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'tokyo_secret_key_2026')

# ====== دالة جلب البيانات ======
def get_db_connection():
    possible_paths = [
        '/app/data/tokyo.db',
        'data/tokyo.db',
        '../TOKYO-BOT/data/tokyo.db',
        '/app/TOKYO-BOT/data/tokyo.db',
    ]
    
    db_path = None
    for path in possible_paths:
        if os.path.exists(path):
            db_path = path
            break
    
    if not db_path:
        os.makedirs('/app/data', exist_ok=True)
        db_path = '/app/data/tokyo.db'
        open(db_path, 'a').close()
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# ====== إنشاء الجداول ======
def init_db():
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS levels (
        user_id INTEGER PRIMARY KEY,
        xp INTEGER DEFAULT 0,
        level INTEGER DEFAULT 0,
        total_messages INTEGER DEFAULT 0
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS warnings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        reason TEXT,
        moderator_id INTEGER,
        timestamp TEXT
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS tickets (
        channel_id INTEGER PRIMARY KEY,
        user_id INTEGER,
        status TEXT DEFAULT 'open',
        assigned_to INTEGER DEFAULT NULL,
        created_at TEXT
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS autoreply (
        trigger TEXT PRIMARY KEY,
        response TEXT
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS auto_roles (
        level INTEGER PRIMARY KEY,
        role_id INTEGER
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS mod_actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT,
        target_id INTEGER,
        moderator_id INTEGER,
        reason TEXT,
        timestamp TEXT
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS self_roles (
        role_id INTEGER PRIMARY KEY,
        emoji TEXT
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service TEXT,
        identifier TEXT,
        channel_id INTEGER
    )''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS starboard_messages (
        message_id INTEGER PRIMARY KEY,
        content TEXT,
        author_id INTEGER,
        stars INTEGER,
        timestamp TEXT
    )''')
    
    conn.commit()
    conn.close()
    print("✅ Database tables created successfully!")

# استدعاء إنشاء الجداول
init_db()

# ====== الصفحة الرئيسية ======
@app.route('/')
def index():
    try:
        conn = get_db_connection()
        members = conn.execute('SELECT COUNT(*) FROM levels').fetchone()[0] or 0
        warnings = conn.execute('SELECT COUNT(*) FROM warnings').fetchone()[0] or 0
        tickets = conn.execute('SELECT COUNT(*) FROM tickets WHERE status = "open"').fetchone()[0] or 0
        conn.close()
        
        return render_template('index.html',
            members=members,
            warnings=warnings,
            tickets=tickets
        )
    except Exception as e:
        return f"❌ Error loading data: {str(e)}", 500

@app.route('/test')
def test():
    return "✅ Test route is working!"

# ====== باقي الصفحات ======
@app.route('/moderation')
def moderation():
    return render_template('moderation.html')

@app.route('/automod')
def automod():
    return render_template('automod.html')

@app.route('/autoreply')
def autoreply():
    conn = get_db_connection()
    replies = conn.execute('SELECT * FROM autoreply').fetchall()
    conn.close()
    return render_template('autoreply.html', replies=replies)

@app.route('/welcome')
def welcome():
    return render_template('welcome.html')

@app.route('/leveling')
def leveling():
    conn = get_db_connection()
    top_10 = conn.execute(
        'SELECT user_id, level, xp FROM levels ORDER BY level DESC, xp DESC LIMIT 10'
    ).fetchall()
    conn.close()
    return render_template('leveling.html', top_10=top_10)

@app.route('/logs')
def logs():
    return render_template('logs.html')

@app.route('/tickets')
def tickets():
    conn = get_db_connection()
    open_tickets = conn.execute(
        'SELECT * FROM tickets WHERE status = "open" ORDER BY created_at DESC'
    ).fetchall()
    conn.close()
    return render_template('tickets.html', open_tickets=open_tickets)

@app.route('/settings')
def settings():
    conn = get_db_connection()
    settings = conn.execute('SELECT * FROM settings ORDER BY key').fetchall()
    conn.close()
    return render_template('settings.html', settings=settings)

@app.route('/autoroles')
def autoroles():
    return render_template('autoroles.html')

@app.route('/starboard')
def starboard():
    return render_template('starboard.html')

@app.route('/self_roles')
def self_roles():
    return render_template('self_roles.html')

@app.route('/notifications')
def notifications():
    return render_template('notifications.html')

@app.route('/temp_channels')
def temp_channels():
    return render_template('temp_channels.html')

@app.route('/colors')
def colors():
    return render_template('colors.html')

@app.route('/mod_actions')
def mod_actions():
    conn = get_db_connection()
    actions = conn.execute('SELECT * FROM mod_actions ORDER BY id DESC LIMIT 50').fetchall()
    conn.close()
    return render_template('mod_actions.html', mod_actions=actions)

# ====== APIs ======
@app.route('/api/addselfrole', methods=['POST'])
def api_add_self_role():
    data = request.json
    role_id = data.get('role_id')
    emoji = data.get('emoji', '')
    
    if not role_id:
        return jsonify({'error': 'role_id مطلوب'}), 400
    
    conn = get_db_connection()
    conn.execute(
        "INSERT OR REPLACE INTO self_roles (role_id, emoji) VALUES (?, ?)",
        (role_id, emoji)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/removeselfrole/<role_id>', methods=['POST'])
def api_remove_self_role(role_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM self_roles WHERE role_id = ?", (role_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/removelevelrole/<int:level>', methods=['POST'])
def api_remove_level_role(level):
    conn = get_db_connection()
    conn.execute("DELETE FROM auto_roles WHERE level = ?", (level,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/setstarboard', methods=['POST'])
def api_set_starboard():
    data = request.json
    channel_id = data.get('channel_id')
    threshold = data.get('threshold')
    
    conn = get_db_connection()
    if channel_id:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('starboard_channel', ?)",
            (channel_id,)
        )
    if threshold:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES ('starboard_threshold', ?)",
            (str(threshold),)
        )
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/addtwitch', methods=['POST'])
def api_add_twitch():
    data = request.json
    streamer = data.get('streamer')
    channel = data.get('channel')
    
    if not streamer or not channel:
        return jsonify({'error': 'بيانات ناقصة'}), 400
    
    conn = get_db_connection()
    conn.execute(
        "INSERT OR REPLACE INTO notifications (service, identifier, channel_id) VALUES ('twitch', ?, ?)",
        (streamer.lower(), channel)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/addyoutube', methods=['POST'])
def api_add_youtube():
    data = request.json
    channel_id = data.get('channel_id')
    channel = data.get('channel')
    
    if not channel_id or not channel:
        return jsonify({'error': 'بيانات ناقصة'}), 400
    
    conn = get_db_connection()
    conn.execute(
        "INSERT OR REPLACE INTO notifications (service, identifier, channel_id) VALUES ('youtube', ?, ?)",
        (channel_id, channel)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/removenotification', methods=['POST'])
def api_remove_notification():
    data = request.json
    service = data.get('service')
    identifier = data.get('identifier')
    
    if not service or not identifier:
        return jsonify({'error': 'بيانات ناقصة'}), 400
    
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM notifications WHERE service = ? AND identifier = ?",
        (service, identifier)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/settempcat', methods=['POST'])
def api_set_tempcat():
    data = request.json
    category_id = data.get('category_id')
    
    if not category_id:
        return jsonify({'error': 'category_id مطلوب'}), 400
    
    conn = get_db_connection()
    conn.execute(
        "INSERT OR REPLACE INTO settings (key, value) VALUES ('temp_category', ?)",
        (category_id,)
    )
    conn.commit()
    conn.close()
    return jsonify({'success': True})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
