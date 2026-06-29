from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
import os
import requests
import json
from datetime import datetime
from functools import wraps

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'tokyo_secret_key_2026')

# ====== إعدادات Discord OAuth2 ======
DISCORD_CLIENT_ID = os.getenv('DISCORD_CLIENT_ID', '')
DISCORD_CLIENT_SECRET = os.getenv('DISCORD_CLIENT_SECRET', '')
DISCORD_REDIRECT_URI = os.getenv('DISCORD_REDIRECT_URI', 'http://localhost:5000/callback')
DISCORD_API_BASE = 'https://discord.com/api/v10'

# ====== دوال قاعدة البيانات ======
def get_db_connection():
    db_path = '/app/data/tokyo.db'
    if not os.path.exists(db_path):
        os.makedirs('/app/data', exist_ok=True)
        open(db_path, 'a').close()
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    try:
        conn = get_db_connection()
        conn.execute('''CREATE TABLE IF NOT EXISTS levels (
            user_id INTEGER PRIMARY KEY,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 0
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
        conn.execute('''CREATE TABLE IF NOT EXISTS dashboard_users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id TEXT UNIQUE,
            username TEXT,
            avatar TEXT,
            access_token TEXT,
            refresh_token TEXT,
            token_expires INTEGER,
            guilds TEXT,
            created_at TEXT
        )''')
        conn.commit()
        conn.close()
        print("✅ Database initialized")
    except Exception as e:
        print(f"❌ Database init error: {e}")

init_db()

# ====== دوال المستخدمين ======
def get_user_by_discord_id(discord_id):
    try:
        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM dashboard_users WHERE discord_id = ?",
            (str(discord_id),)
        ).fetchone()
        conn.close()
        return user
    except Exception as e:
        print(f"❌ get_user_by_discord_id error: {e}")
        return None

def create_or_update_user(discord_id, username, avatar, access_token, refresh_token, expires_in, guilds):
    try:
        conn = get_db_connection()
        expires_at = int(datetime.now().timestamp()) + expires_in
        guilds_json = json.dumps(guilds)
        conn.execute(
            """INSERT OR REPLACE INTO dashboard_users 
               (discord_id, username, avatar, access_token, refresh_token, token_expires, guilds, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(discord_id), username, avatar, access_token, refresh_token, expires_at, guilds_json, datetime.now().isoformat())
        )
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"❌ create_or_update_user error: {e}")
        return False

def get_user_guilds(discord_id):
    try:
        conn = get_db_connection()
        result = conn.execute(
            "SELECT guilds FROM dashboard_users WHERE discord_id = ?",
            (str(discord_id),)
        ).fetchone()
        conn.close()
        if result:
            return json.loads(result['guilds'])
        return []
    except Exception as e:
        print(f"❌ get_user_guilds error: {e}")
        return []

# ====== التحقق من تسجيل الدخول ======
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ====== مسارات المصادقة ======
@app.route('/login')
def login():
    if not DISCORD_CLIENT_ID or not DISCORD_CLIENT_SECRET:
        return "❌ Discord Client ID or Secret not configured", 500
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
        return f"❌ Error: {response.text}", 400
    
    token_data = response.json()
    access_token = token_data.get('access_token')
    refresh_token = token_data.get('refresh_token')
    expires_in = token_data.get('expires_in', 604800)
    
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
    
    clean_guilds = []
    for guild in raw_guilds:
        clean_guilds.append({
            'id': str(guild.get('id', '')),
            'name': guild.get('name', 'Unknown'),
            'icon': guild.get('icon', ''),
            'permissions': str(guild.get('permissions', '0')),
            'owner': bool(guild.get('owner', False))
        })
    
    create_or_update_user(
        user_data['id'],
        user_data['username'],
        user_data.get('avatar', ''),
        access_token,
        refresh_token,
        expires_in,
        clean_guilds
    )
    
    session['user_id'] = str(user_data['id'])
    session['username'] = user_data['username']
    session['avatar'] = user_data.get('avatar', '')
    
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ====== الصفحات ======
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        user_id = session.get('user_id')
        guilds = get_user_guilds(user_id)
        
        conn = get_db_connection()
        user_data = conn.execute(
            "SELECT xp, level FROM levels WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        conn.close()
        
        xp = user_data['xp'] if user_data else 0
        level = user_data['level'] if user_data else 0
        
        admin_guilds = []
        for guild in guilds:
            permissions = int(guild.get('permissions', 0))
            if permissions & 0x8:
                admin_guilds.append(guild)
        
        return render_template('dashboard.html', 
            user={
                'id': user_id, 
                'username': session.get('username', ''), 
                'avatar': session.get('avatar', ''),
                'xp': xp,
                'level': level
            },
            guilds=admin_guilds,
            all_guilds=guilds
        )
    except Exception as e:
        print(f"❌ Dashboard error: {e}")
        return f"❌ Error loading dashboard: {str(e)}", 500

@app.route('/server/<guild_id>')
@login_required
def server_dashboard(guild_id):
    try:
        user_id = session.get('user_id')
        guilds = get_user_guilds(user_id)
        
        selected_guild = None
        for guild in guilds:
            if guild['id'] == guild_id:
                selected_guild = guild
                break
        
        if not selected_guild:
            return "❌ Server not found", 404
        
        user_data = {
            'id': user_id,
            'username': session.get('username', 'Unknown'),
            'avatar': session.get('avatar', '')
        }
        
        return render_template('server_dashboard.html',
            user=user_data,
            guild=selected_guild,
            datetime=datetime
        )
    except Exception as e:
        print(f"❌ Server dashboard error: {e}")
        return f"❌ Error loading server: {str(e)}", 500

@app.route('/moderation')
@login_required
def moderation():
    try:
        return render_template('moderation.html')
    except Exception as e:
        print(f"❌ Moderation error: {e}")
        return f"❌ Error: {str(e)}", 500

@app.route('/automod')
@login_required
def automod():
    try:
        return render_template('automod.html')
    except Exception as e:
        print(f"❌ Automod error: {e}")
        return f"❌ Error: {str(e)}", 500

@app.route('/autoreply')
@login_required
def autoreply():
    try:
        conn = get_db_connection()
        replies = conn.execute('SELECT * FROM autoreply').fetchall()
        conn.close()
        return render_template('autoreply.html', replies=replies)
    except Exception as e:
        print(f"❌ Autoreply error: {e}")
        return f"❌ Error: {str(e)}", 500

@app.route('/welcome')
@login_required
def welcome():
    try:
        return render_template('welcome.html')
    except Exception as e:
        print(f"❌ Welcome error: {e}")
        return f"❌ Error: {str(e)}", 500

@app.route('/leveling')
@login_required
def leveling():
    try:
        conn = get_db_connection()
        top_10 = conn.execute(
            'SELECT user_id, level, xp FROM levels ORDER BY level DESC, xp DESC LIMIT 10'
        ).fetchall()
        conn.close()
        return render_template('leveling.html', top_10=top_10)
    except Exception as e:
        print(f"❌ Leveling error: {e}")
        return f"❌ Error: {str(e)}", 500

@app.route('/logs')
@login_required
def logs():
    try:
        return render_template('logs.html')
    except Exception as e:
        print(f"❌ Logs error: {e}")
        return f"❌ Error: {str(e)}", 500

@app.route('/tickets')
@login_required
def tickets():
    try:
        conn = get_db_connection()
        open_tickets = conn.execute(
            'SELECT * FROM tickets WHERE status = "open" ORDER BY created_at DESC'
        ).fetchall()
        conn.close()
        return render_template('tickets.html', open_tickets=open_tickets)
    except Exception as e:
        print(f"❌ Tickets error: {e}")
        return f"❌ Error: {str(e)}", 500

@app.route('/settings')
@login_required
def settings():
    try:
        conn = get_db_connection()
        settings = conn.execute('SELECT * FROM settings ORDER BY key').fetchall()
        conn.close()
        return render_template('settings.html', settings=settings)
    except Exception as e:
        print(f"❌ Settings error: {e}")
        return f"❌ Error: {str(e)}", 500

@app.route('/autoroles')
@login_required
def autoroles():
    try:
        return render_template('autoroles.html')
    except Exception as e:
        print(f"❌ Autoroles error: {e}")
        return f"❌ Error: {str(e)}", 500

@app.route('/starboard')
@login_required
def starboard():
    try:
        return render_template('starboard.html')
    except Exception as e:
        print(f"❌ Starboard error: {e}")
        return f"❌ Error: {str(e)}", 500

@app.route('/self_roles')
@login_required
def self_roles():
    try:
        return render_template('self_roles.html')
    except Exception as e:
        print(f"❌ Self roles error: {e}")
        return f"❌ Error: {str(e)}", 500

@app.route('/notifications')
@login_required
def notifications():
    try:
        return render_template('notifications.html')
    except Exception as e:
        print(f"❌ Notifications error: {e}")
        return f"❌ Error: {str(e)}", 500

@app.route('/temp_channels')
@login_required
def temp_channels():
    try:
        return render_template('temp_channels.html')
    except Exception as e:
        print(f"❌ Temp channels error: {e}")
        return f"❌ Error: {str(e)}", 500

@app.route('/colors')
@login_required
def colors():
    try:
        return render_template('colors.html')
    except Exception as e:
        print(f"❌ Colors error: {e}")
        return f"❌ Error: {str(e)}", 500

@app.route('/mod_actions')
@login_required
def mod_actions():
    try:
        conn = get_db_connection()
        actions = conn.execute('SELECT * FROM mod_actions ORDER BY id DESC LIMIT 50').fetchall()
        conn.close()
        return render_template('mod_actions.html', mod_actions=actions)
    except Exception as e:
        print(f"❌ Mod actions error: {e}")
        return f"❌ Error: {str(e)}", 500

# ====== APIs ======
@app.route('/api/guild_roles/<guild_id>')
@login_required
def get_guild_roles(guild_id):
    try:
        user_id = session.get('user_id')
        user = get_user_by_discord_id(user_id)
        
        if not user:
            return jsonify([])
        
        headers = {'Authorization': f'Bearer {user["access_token"]}'}
        response = requests.get(
            f"{DISCORD_API_BASE}/guilds/{guild_id}/roles",
            headers=headers
        )
        
        if response.status_code != 200:
            return jsonify([])
        
        return jsonify(response.json())
    except Exception as e:
        print(f"❌ API guild_roles error: {e}")
        return jsonify([])

@app.route('/api/guild_channels/<guild_id>')
@login_required
def get_guild_channels(guild_id):
    try:
        user_id = session.get('user_id')
        user = get_user_by_discord_id(user_id)
        
        if not user:
            return jsonify([])
        
        headers = {'Authorization': f'Bearer {user["access_token"]}'}
        response = requests.get(
            f"{DISCORD_API_BASE}/guilds/{guild_id}/channels",
            headers=headers
        )
        
        if response.status_code != 200:
            return jsonify([])
        
        return jsonify(response.json())
    except Exception as e:
        print(f"❌ API guild_channels error: {e}")
        return jsonify([])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
