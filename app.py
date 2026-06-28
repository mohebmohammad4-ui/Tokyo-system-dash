from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
import os
import requests
import json
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'tokyo_secret_key_2026')

# ====== إعدادات Discord OAuth2 ======
DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID', 'ضع_الـ_Client_ID_هنا')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET', 'ضع_الـ_Client_Secret_هنا')
DISCORD_REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI', 'http://localhost:5000/callback')
DISCORD_API_BASE = 'https://discord.com/api/v10'

# ====== دوال قاعدة البيانات ======
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
    
    conn.execute('''CREATE TABLE IF NOT EXISTS dashboard_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        discord_id TEXT UNIQUE,
        username TEXT,
        avatar TEXT,
        access_token TEXT,
        refresh_token TEXT,
        token_expires INTEGER,
        created_at TEXT
    )''')
    
    conn.commit()
    conn.close()
    print("✅ Database tables created successfully!")

init_db()

# ====== دالة التحقق من تسجيل الدخول ======
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ====== دالة جلب مستخدم من قاعدة البيانات ======
def get_user(discord_id):
    conn = get_db_connection()
    user = conn.execute(
        "SELECT * FROM dashboard_users WHERE discord_id = ?",
        (str(discord_id),)
    ).fetchone()
    conn.close()
    return user

def save_user(discord_id, username, avatar, access_token, refresh_token, expires_in):
    conn = get_db_connection()
    expires_at = int(datetime.now().timestamp()) + expires_in
    conn.execute(
        """INSERT OR REPLACE INTO dashboard_users 
           (discord_id, username, avatar, access_token, refresh_token, token_expires, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (str(discord_id), username, avatar, access_token, refresh_token, expires_at, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

# ====== 🔥 دالة لتنظيف البيانات قبل التخزين في Session ======
def clean_guilds(guilds):
    """تحويل بيانات السيرفرات إلى صيغة JSON آمنة"""
    safe_guilds = []
    for guild in guilds:
        safe_guilds.append({
            'id': str(guild.get('id', '')),
            'name': guild.get('name', 'Unknown'),
            'icon': guild.get('icon', ''),
            'permissions': str(guild.get('permissions', '0')),
            'owner': bool(guild.get('owner', False))
        })
    return safe_guilds

# ====== مسارات المصادقة ======
@app.route('/login')
def login():
    auth_url = (
        f"{DISCORD_API_BASE}/oauth2/authorize"
        f"?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={DISCORD_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20guilds"
    )
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return "❌ No code provided", 400
    
    data = {
        'client_id': DISCORD_CLIENT_ID,
        'client_secret': DISCORD_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': DISCORD_REDIRECT_URI,
        'scope': 'identify guilds'
    }
    
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    response = requests.post(f"{DISCORD_API_BASE}/oauth2/token", data=data, headers=headers)
    
    if response.status_code != 200:
        return f"❌ Error: {response.json()}", 400
    
    token_data = response.json()
    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    expires_in = token_data.get('expires_in')
    
    user_response = requests.get(
        f"{DISCORD_API_BASE}/users/@me",
        headers={'Authorization': f'Bearer {access_token}'}
    )
    
    if user_response.status_code != 200:
        return "❌ Failed to get user info", 400
    
    user_data = user_response.json()
    
    guilds_response = requests.get(
        f"{DISCORD_API_BASE}/users/@me/guilds",
        headers={'Authorization': f'Bearer {access_token}'}
    )
    
    raw_guilds = guilds_response.json() if guilds_response.status_code == 200 else []
    
    save_user(
        user_data['id'],
        user_data['username'],
        user_data.get('avatar', ''),
        access_token,
        refresh_token,
        expires_in
    )
    
    # ====== 🔥 استخدام دالة التنظيف ======
    safe_guilds = clean_guilds(raw_guilds)
    
    session['user'] = {
        'id': str(user_data['id']),
        'username': user_data['username'],
        'avatar': user_data.get('avatar', ''),
        'guilds': safe_guilds
    }
    
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ====== لوحة التحكم الرئيسية ======
@app.route('/dashboard')
@login_required
def dashboard():
    user = session.get('user', {})
    guilds = user.get('guilds', [])
    
    admin_guilds = []
    for guild in guilds:
        permissions = int(guild.get('permissions', 0))
        if permissions & 0x8:
            admin_guilds.append(guild)
    
    return render_template('dashboard.html', 
        user=user,
        guilds=admin_guilds,
        all_guilds=guilds
    )

# ====== الصفحة الرئيسية ======
@app.route('/')
def index():
    if 'user' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

# ====== عرض بيانات السيرفر المحدد ======
@app.route('/server/<guild_id>')
@login_required
def server_dashboard(guild_id):
    user = session.get('user', {})
    guilds = user.get('guilds', [])
    
    selected_guild = None
    for guild in guilds:
        if guild['id'] == guild_id:
            selected_guild = guild
            break
    
    if not selected_guild:
        return "❌ Server not found", 404
    
    return render_template('server_dashboard.html',
        user=user,
        guild=selected_guild,
        datetime=datetime
    )

# ====== باقي الصفحات (مع التحقق من الدخول) ======
@app.route('/moderation')
@login_required
def moderation():
    return render_template('moderation.html')

@app.route('/automod')
@login_required
def automod():
    return render_template('automod.html')

@app.route('/autoreply')
@login_required
def autoreply():
    conn = get_db_connection()
    replies = conn.execute('SELECT * FROM autoreply').fetchall()
    conn.close()
    return render_template('autoreply.html', replies=replies)

@app.route('/welcome')
@login_required
def welcome():
    return render_template('welcome.html')

@app.route('/leveling')
@login_required
def leveling():
    conn = get_db_connection()
    top_10 = conn.execute(
        'SELECT user_id, level, xp FROM levels ORDER BY level DESC, xp DESC LIMIT 10'
    ).fetchall()
    conn.close()
    return render_template('leveling.html', top_10=top_10)

@app.route('/logs')
@login_required
def logs():
    return render_template('logs.html')

@app.route('/tickets')
@login_required
def tickets():
    conn = get_db_connection()
    open_tickets = conn.execute(
        'SELECT * FROM tickets WHERE status = "open" ORDER BY created_at DESC'
    ).fetchall()
    conn.close()
    return render_template('tickets.html', open_tickets=open_tickets)

@app.route('/settings')
@login_required
def settings():
    conn = get_db_connection()
    settings = conn.execute('SELECT * FROM settings ORDER BY key').fetchall()
    conn.close()
    return render_template('settings.html', settings=settings)

@app.route('/autoroles')
@login_required
def autoroles():
    return render_template('autoroles.html')

@app.route('/starboard')
@login_required
def starboard():
    return render_template('starboard.html')

@app.route('/self_roles')
@login_required
def self_roles():
    return render_template('self_roles.html')

@app.route('/notifications')
@login_required
def notifications():
    return render_template('notifications.html')

@app.route('/temp_channels')
@login_required
def temp_channels():
    return render_template('temp_channels.html')

@app.route('/colors')
@login_required
def colors():
    return render_template('colors.html')

@app.route('/mod_actions')
@login_required
def mod_actions():
    conn = get_db_connection()
    actions = conn.execute('SELECT * FROM mod_actions ORDER BY id DESC LIMIT 50').fetchall()
    conn.close()
    return render_template('mod_actions.html', mod_actions=actions)

# ====== APIs ======
@app.route('/api/addselfrole', methods=['POST'])
@login_required
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
@login_required
def api_remove_self_role(role_id):
    conn = get_db_connection()
    conn.execute("DELETE FROM self_roles WHERE role_id = ?", (role_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/removelevelrole/<int:level>', methods=['POST'])
@login_required
def api_remove_level_role(level):
    conn = get_db_connection()
    conn.execute("DELETE FROM auto_roles WHERE level = ?", (level,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/setstarboard', methods=['POST'])
@login_required
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
@login_required
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
@login_required
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
@login_required
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
@login_required
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
