from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'tokyo_secret_key_2026')

# ====== دالة جلب البيانات من قاعدة البوت ======
def get_db_connection():
    # مسار قاعدة البيانات (تأكد من أنه صحيح)
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'TOKYO-BOT', 'data', 'tokyo.db')
    if not os.path.exists(db_path):
        db_path = 'data/tokyo.db'  # مسار بديل
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

# ====== الصفحة الرئيسية ======
@app.route('/')
def index():
    conn = get_db_connection()
    
    # إحصائيات سريعة
    members = conn.execute('SELECT COUNT(*) FROM levels').fetchone()[0] or 0
    warnings = conn.execute('SELECT COUNT(*) FROM warnings').fetchone()[0] or 0
    tickets = conn.execute('SELECT COUNT(*) FROM tickets WHERE status = "open"').fetchone()[0] or 0
    
    # أعلى 5 مستويات
    top_levels = conn.execute(
        'SELECT user_id, level, xp FROM levels ORDER BY level DESC, xp DESC LIMIT 5'
    ).fetchall()
    
    # آخر 5 تحذيرات
    recent_warnings = conn.execute(
        'SELECT * FROM warnings ORDER BY id DESC LIMIT 5'
    ).fetchall()
    
    # عدد التكتات المغلقة
    closed_tickets = conn.execute('SELECT COUNT(*) FROM tickets WHERE status = "closed"').fetchone()[0] or 0
    
    conn.close()
    
    return render_template('index.html',
        members=members,
        warnings=warnings,
        tickets=tickets,
        closed_tickets=closed_tickets,
        top_levels=top_levels,
        recent_warnings=recent_warnings
    )

# ====== صفحة الإدارة ======
@app.route('/moderation')
def moderation():
    conn = get_db_connection()
    mod_actions = conn.execute('SELECT * FROM mod_actions ORDER BY id DESC LIMIT 20').fetchall()
    conn.close()
    return render_template('moderation.html', mod_actions=mod_actions)

# ====== صفحة الحماية التلقائية ======
@app.route('/automod')
def automod():
    return render_template('automod.html')

# ====== صفحة الردود التلقائية ======
@app.route('/autoreply')
def autoreply():
    conn = get_db_connection()
    replies = conn.execute('SELECT * FROM autoreply').fetchall()
    conn.close()
    return render_template('autoreply.html', replies=replies)

# ====== صفحة الترحيب ======
@app.route('/welcome')
def welcome():
    conn = get_db_connection()
    welcome_channel = conn.execute(
        "SELECT value FROM settings WHERE key = 'welcome_channel'"
    ).fetchone()
    welcome_messages = conn.execute(
        "SELECT value FROM settings WHERE key = 'welcome_messages'"
    ).fetchone()
    conn.close()
    return render_template('welcome.html', 
        welcome_channel=welcome_channel,
        welcome_messages=welcome_messages
    )

# ====== صفحة المستويات ======
@app.route('/leveling')
def leveling():
    conn = get_db_connection()
    top_10 = conn.execute(
        'SELECT user_id, level, xp FROM levels ORDER BY level DESC, xp DESC LIMIT 10'
    ).fetchall()
    total_members = conn.execute('SELECT COUNT(*) FROM levels').fetchone()[0] or 0
    conn.close()
    return render_template('leveling.html', top_10=top_10, total_members=total_members)

# ====== صفحة اللوقات ======
@app.route('/logs')
def logs():
    conn = get_db_connection()
    settings = conn.execute("SELECT * FROM settings WHERE key LIKE 'log_%'").fetchall()
    conn.close()
    return render_template('logs.html', settings=settings)

# ====== صفحة التكتات ======
@app.route('/tickets')
def tickets():
    conn = get_db_connection()
    open_tickets = conn.execute(
        'SELECT * FROM tickets WHERE status = "open" ORDER BY created_at DESC'
    ).fetchall()
    closed_tickets = conn.execute(
        'SELECT * FROM tickets WHERE status = "closed" ORDER BY created_at DESC LIMIT 10'
    ).fetchall()
    conn.close()
    return render_template('tickets.html', 
        open_tickets=open_tickets,
        closed_tickets=closed_tickets
    )

# ====== صفحة الإعدادات ======
@app.route('/settings')
def settings():
    conn = get_db_connection()
    settings = conn.execute('SELECT * FROM settings ORDER BY key').fetchall()
    conn.close()
    return render_template('settings.html', settings=settings)

# ====== صفحة الرتب التلقائية ======
@app.route('/autoroles')
def autoroles():
    conn = get_db_connection()
    join_role = conn.execute(
        "SELECT value FROM settings WHERE key = 'auto_join_role'"
    ).fetchone()
    auto_roles = conn.execute('SELECT * FROM auto_roles ORDER BY level ASC').fetchall()
    conn.close()
    return render_template('autoroles.html', 
        join_role=join_role,
        auto_roles=auto_roles
    )

# ====== صفحة Starboard ======
@app.route('/starboard')
def starboard():
    conn = get_db_connection()
    starboard_channel = conn.execute(
        "SELECT value FROM settings WHERE key = 'starboard_channel'"
    ).fetchone()
    starred_messages = conn.execute(
        'SELECT * FROM starboard_messages ORDER BY timestamp DESC LIMIT 10'
    ).fetchall()
    conn.close()
    return render_template('starboard.html', 
        starboard_channel=starboard_channel,
        starred_messages=starred_messages
    )

# ====== صفحة الرتب الاختيارية ======
@app.route('/self_roles')
def self_roles():
    conn = get_db_connection()
    self_roles = conn.execute('SELECT * FROM self_roles').fetchall()
    conn.close()
    return render_template('self_roles.html', self_roles=self_roles)

# ====== صفحة الإشعارات ======
@app.route('/notifications')
def notifications():
    conn = get_db_connection()
    twitch_list = conn.execute(
        "SELECT * FROM notifications WHERE service = 'twitch'"
    ).fetchall()
    youtube_list = conn.execute(
        "SELECT * FROM notifications WHERE service = 'youtube'"
    ).fetchall()
    conn.close()
    return render_template('notifications.html', 
        twitch_list=twitch_list,
        youtube_list=youtube_list
    )

# ====== صفحة الرومات المؤقتة ======
@app.route('/temp_channels')
def temp_channels():
    conn = get_db_connection()
    temp_category = conn.execute(
        "SELECT value FROM settings WHERE key = 'temp_category'"
    ).fetchone()
    conn.close()
    return render_template('temp_channels.html', temp_category=temp_category)

# ====== صفحة الألوان ======
@app.route('/colors')
def colors():
    return render_template('colors.html')

# ====== صفحة سجل الإدارة ======
@app.route('/mod_actions')
def mod_actions():
    conn = get_db_connection()
    filter_type = request.args.get('filter', 'all')
    
    if filter_type == 'all':
        actions = conn.execute('SELECT * FROM mod_actions ORDER BY id DESC LIMIT 50').fetchall()
    else:
        actions = conn.execute(
            'SELECT * FROM mod_actions WHERE action = ? ORDER BY id DESC LIMIT 50',
            (filter_type,)
        ).fetchall()
    
    conn.close()
    return render_template('mod_actions.html', 
        mod_actions=actions,
        filter_type=filter_type
    )

# ====== APIs للتحكم ======
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
    app.run(host='0.0.0.0', port=5000, debug=True)
