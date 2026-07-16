"""
New Program Process Evaluation (NPE) Application
多用户版 - Flask + SQLite
逐工序添加模式：工程师从预定义清单逐个添加工序，填写投资和人数
"""
import os
import sys
import time
import uuid
import sqlite3
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from collections import OrderedDict

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

BASE_DIR = get_base_dir()
app = Flask(__name__)
DB_PATH = os.path.join(BASE_DIR, 'npe.db')

# Session secret key
SECRET_KEY_PATH = os.path.join(BASE_DIR, '.secret_key')
if os.path.exists(SECRET_KEY_PATH):
    with open(SECRET_KEY_PATH, 'r') as f:
        app.secret_key = f.read().strip()
else:
    app.secret_key = os.urandom(24).hex()
    with open(SECRET_KEY_PATH, 'w') as f:
        f.write(app.secret_key)

# ==================== Predefined Process Lines ====================

# Shared process lists
SMT_PURE_SMD = [
    {"name": "PCB Load", "tools": []},
    {"name": "Soldering Print", "tools": ["Knife", "Stencil"]},
    {"name": "SPI", "tools": []},
    {"name": "Placement _20R", "tools": ["Feeders 8mm", "Feeders 10mm", "Feeders 12mm"]},
    {"name": "Placement _40R", "tools": ["Feeders 8mm", "Feeders 10mm", "Feeders 12mm"]},
    {"name": "Placement _Relay", "tools": ["Customized Feeders"]},
    {"name": "Reflow", "tools": ["Profile Monitor"]},
    {"name": "AOI_3D", "tools": []},
    {"name": "ICT in line", "tools": ["ICT Fixture in line", "ICT Program in line", "Flash Module in line"]},
    {"name": "Visual Check", "tools": []},
]

SMT_TERMINAL = [
    {"name": "PCB Load", "tools": []},
    {"name": "Soldering Print", "tools": ["Knife", "Stencil"]},
    {"name": "SPI", "tools": []},
    {"name": "Terminal Insertion _Eberhand", "tools": ["Cut/Pusher", "Plate", "Die"]},
    {"name": "Terminal Insertion _Sunil", "tools": ["Cut/Pusher", "Plate", "Gripper"]},
    {"name": "Placement _20R", "tools": ["Feeders 8mm", "Feeders 10mm", "Feeders 12mm"]},
    {"name": "Placement _40R", "tools": ["Feeders 8mm", "Feeders 10mm", "Feeders 12mm"]},
    {"name": "Placement _Relay", "tools": ["Customized Feeders"]},
    {"name": "Reflow", "tools": ["Profile Monitor"]},
    {"name": "AOI_3D", "tools": []},
    {"name": "Visual Check", "tools": []},
    {"name": "FCT", "tools": ["FCT Fixture", "FCT Test Program"]},
]

# ===== Coating 产线（各产线独立定义，来自Excel） =====

COATING2 = [
    {"name": "Coating Dispense", "tools": ["Coating Fixture", "Coating program"]},
    {"name": "Coating Curing Oven", "tools": []},
]

COATING3 = [
    {"name": "Coating Dispense", "tools": ["Coating Fixture", "Coating program"]},
    {"name": "Coating Curing Oven", "tools": []},
]

COATING4 = [
    {"name": "Coating Dispense", "tools": ["Coating Fixture"]},
    {"name": "Coating Curing Oven", "tools": []},
]

COATING5 = [
    {"name": "Coating Dispense", "tools": ["Coating program", "Coating Fixture"]},
    {"name": "Coating Curing Oven", "tools": []},
]

# ===== SWS 产线（2 chambers 和 4 chambers 独立定义） =====

SWS_2 = [
    {"name": "Wave Soldering", "tools": ["Fixtures", "Program"]},
    {"name": "Assembly", "tools": []},
    {"name": "Inspection", "tools": []},
    {"name": "AOI", "tools": []},
    {"name": "Glue Dispense", "tools": ["Fixtures", "Program"]},
    {"name": "Unload", "tools": []},
]

SWS_4 = [
    {"name": "Wave Soldering", "tools": []},
    {"name": "Fixtures", "tools": []},
    {"name": "Program", "tools": []},
    {"name": "Assembly", "tools": []},
    {"name": "Inspection", "tools": []},
    {"name": "AOI", "tools": []},
    {"name": "Glue Dispense", "tools": []},
    {"name": "Unload", "tools": []},
]

# ===== 其他产线 =====

ELECTRONICS_ASSEMBLY = [
    {"name": "Screwing", "tools": ["Torque Screw Drivers", "Fixture"]},
    {"name": "Press", "tools": ["Press Fixture"]},
    {"name": "EOL", "tools": ["Test Fixture", "Test Program", "Assembly Manual", "Tool", "Fixture"]},
]

POTTING = [
    {"name": "Potting Machine", "tools": ["Potting Fixture", "Potting Program"]},
    {"name": "Potting Curing Oven", "tools": []},
]

ICT_OFFLINE = [
    {"name": "ICT Machines", "tools": ["ICT Fixture off line", "ICT Program off line", "Flash Module off line"]},
]

PREDEFINED_LINES = {
    "SMT1":  {"hint": "Pure SMD", "processes": SMT_PURE_SMD},
    "SMT2":  {"hint": "Terminal & Busbar", "processes": SMT_TERMINAL},
    "SMT3":  {"hint": "Terminal & Busbar", "processes": SMT_TERMINAL},
    "SMT4":  {"hint": "Terminal & Busbar", "processes": SMT_TERMINAL},
    "SMT5":  {"hint": "Terminal & Busbar", "processes": SMT_TERMINAL},
    "SMT6":  {"hint": "Terminal & Busbar", "processes": SMT_TERMINAL},
    "SMT7":  {"hint": "Pure SMD", "processes": SMT_PURE_SMD},
    "SMT8":  {"hint": "Terminal & Busbar", "processes": SMT_TERMINAL},
    "Wave soldering": {"hint": "Wave soldering", "processes": [
        {"name": "Wave Soldering", "tools": ["Fixtures", "Program"]},
        {"name": "Assembly", "tools": []},
        {"name": "AOI", "tools": ["Program"]},
        {"name": "Inspection", "tools": []},
        {"name": "Unload", "tools": []},
    ]},
    "Coating2": {"hint": "Silicon Coating", "processes": COATING2},
    "Coating3": {"hint": "UV Coating", "processes": COATING3},
    "Coating4": {"hint": "Silicon Coating", "processes": COATING4},
    "Coating5": {"hint": "Silicon Coating", "processes": COATING5},
    "SWS 2 Chambers": {"hint": "Selective Wave Soldering", "processes": SWS_2},
    "SWS 4 Chambers": {"hint": "Selective Wave Soldering", "processes": SWS_4},
    "Electronics Assembly": {"hint": "", "processes": ELECTRONICS_ASSEMBLY},
    "Potting": {"hint": "", "processes": POTTING},
    "ICT Off Line": {"hint": "", "processes": ICT_OFFLINE},
}

# 项目阶段映射：简称 -> 全称，来自Excel"项目阶段"tab
PROJECT_PHASES = {
    "PI":  "Project Initiation",
    "PL":  "Project Launch",
    "SBA": "Sanctioning Body Aproval",
    "CD":  "Concept Direction",
    "CA":  "Concept Approval",
    "FA":  "Final Approval",
    "PA":  "Production Approval",
    "CT":  "Close out/Transfer",
}
PHASE_ORDER = list(PROJECT_PHASES.keys())
PHASE_ORDER_INDEX = {phase: idx for idx, phase in enumerate(PHASE_ORDER)}

# 批准层级映射：制表人 -> (审核人, 批准人)，来自Excel"批准层级"tab的行对应关系
APPROVAL_HIERARCHY = {
    "Grisson Zhang":  ("Grisson Zhang", "Qin Jin"),
    "Tang Zhiwei":    ("Grisson Zhang", "Qin Jin"),
    "Xianjun Zhao":   ("Grisson Zhang", "Qin Jin"),
    "Qin Jin":        ("Grisson Zhang", "Qin Jin"),
    "Yonghui Zheng":  ("Hongbo Zhao",  "Qin Jin"),
    "Zenglu Geng":    ("Hongbo Zhao",  "Qin Jin"),
    "Wanshun Wang":   ("Hongbo Zhao",  "Qin Jin"),
    "Yasheng Liu":    ("Hongbo Zhao",  "Qin Jin"),
    "Chase Hu":       ("Hongbo Zhao",  "Qin Jin"),
    "Kunpeng Wang":   ("Hongbo Zhao",  "Qin Jin"),
    "Yuanyuan Wu":    ("Hongbo Zhao",  "Qin Jin"),
    "Ketter Zhang":   ("Tom Wu",       "Qin Jin"),
    "Tom Wu":         ("Tom Wu",       "Qin Jin"),
    "Star Xu":        ("Tom Wu",       "Qin Jin"),
    "Shi Xingyong":   ("Tom Wu",       "Qin Jin"),
    "Shen Shaokun":   ("Tom Wu",       "Qin Jin"),
    "Jiming Jiang":   ("Tom Wu",       "Qin Jin"),
}
# 制表人列表（用于新建项目下拉菜单）
PREPARERS = list(APPROVAL_HIERARCHY.keys())

# 超级用户列表（硬编码，享有系统管理权限）
SUPER_USERS = {"Qin Jin"}

def is_superuser():
    return session.get('username') in SUPER_USERS


# ==================== Database ====================

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_name TEXT NOT NULL,
        project_number TEXT,
        customer TEXT,
        created_by TEXT,
        line_type TEXT,
        reason TEXT,
        project_phase TEXT,
        version INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS project_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        line_type TEXT,
        item_type TEXT NOT NULL DEFAULT 'process',
        item_name TEXT NOT NULL,
        parent_process TEXT,
        investment_usd REAL DEFAULT 0,
        cycle_time_sec REAL DEFAULT 0,
        operator_count REAL DEFAULT 0,
        sort_order INTEGER DEFAULT 0,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS item_versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id INTEGER NOT NULL,
        line_type TEXT,
        save_batch TEXT NOT NULL,
        item_name TEXT NOT NULL,
        item_type TEXT NOT NULL DEFAULT 'process',
        parent_process TEXT,
        investment_usd REAL DEFAULT 0,
        cycle_time_sec REAL DEFAULT 0,
        operator_count REAL DEFAULT 0,
        updated_by TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        comment TEXT,
        project_phase TEXT,
        FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
    )''')
    conn.commit()
    conn.close()


def migrate_db():
    """兼容旧数据库：添加新字段"""
    conn = get_db()
    c = conn.cursor()

    # projects 表
    c.execute("PRAGMA table_info(projects)")
    proj_cols = {row[1] for row in c.fetchall()}
    if 'reason' not in proj_cols:
        c.execute("ALTER TABLE projects ADD COLUMN reason TEXT")
    if 'project_phase' not in proj_cols:
        c.execute("ALTER TABLE projects ADD COLUMN project_phase TEXT")
    if 'version' not in proj_cols:
        c.execute("ALTER TABLE projects ADD COLUMN version INTEGER DEFAULT 1")

    # project_items 表
    c.execute("PRAGMA table_info(project_items)")
    item_cols = {row[1] for row in c.fetchall()}
    if 'line_type' not in item_cols:
        c.execute("ALTER TABLE project_items ADD COLUMN line_type TEXT")

    conn.commit()
    conn.close()


# ==================== Auth ====================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('username'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def superuser_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_superuser():
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
        conn.close()
        if user and check_password_hash(user['password_hash'], password):
            session['username'] = username
            return redirect(url_for('index'))
        return render_template('login.html', preparers=PREPARERS, error='用户名或密码错误')
    # GET: check if any users exist
    conn = get_db()
    count = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    conn.close()
    if count == 0:
        return redirect(url_for('setup'))
    return render_template('login.html', preparers=PREPARERS, error=None)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/setup', methods=['GET', 'POST'])
def setup():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        if not username:
            return render_template('setup.html', preparers=PREPARERS, error='请选择用户名')
        if not password:
            return render_template('setup.html', preparers=PREPARERS, error='请输入密码')
        if password != confirm:
            return render_template('setup.html', preparers=PREPARERS, error='两次密码不一致')
        conn = get_db()
        try:
            conn.execute('INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)',
                        (username, generate_password_hash(password), datetime.now().strftime('%Y-%m-%d %H:%M')))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.close()
            return render_template('setup.html', preparers=PREPARERS, error='该用户已设置过密码')
        conn.close()
        return redirect(url_for('login'))
    return render_template('setup.html', preparers=PREPARERS, error=None)


# ==================== Routes ====================

@app.route('/')
@login_required
def index():
    conn = get_db()
    projects = conn.execute('''
        SELECT p.*,
               COALESCE((SELECT GROUP_CONCAT(DISTINCT COALESCE(line_type, '-'))
                         FROM project_items WHERE project_id = p.id), '') as used_lines
        FROM projects p
        ORDER BY p.created_at DESC
    ''').fetchall()
    conn.close()
    return render_template('index.html', projects=projects, lines=PREDEFINED_LINES,
                           current_user=session.get('username', ''),
                           is_superuser=is_superuser())


@app.route('/project/new', methods=['GET', 'POST'])
@login_required
def create_project():
    if request.method == 'POST':
        conn = get_db()
        now = datetime.now().strftime('%Y-%m-%d %H:%M')
        cur = conn.execute('''INSERT INTO projects
            (project_name, project_number, customer, created_by, line_type, reason, project_phase, version, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)''',
            (
                request.form.get('project_name', ''),
                request.form.get('project_number', ''),
                request.form.get('customer', ''),
                session.get('username', ''),
                '',  # line_type 创建时不选
                request.form.get('reason', ''),
                request.form.get('project_phase', ''),
                now
            ))
        conn.commit()
        pid = cur.lastrowid
        conn.close()
        return redirect(url_for('edit_project', project_id=pid))
    return render_template('project_form.html', lines=PREDEFINED_LINES, project_phases=PROJECT_PHASES,
                           current_user=session.get('username', ''))


@app.route('/project/<int:project_id>')
@login_required
def view_project(project_id):
    return _load_project_page(project_id, view_only=True)


@app.route('/project/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_project(project_id):
    if request.method == 'POST':
        conn = get_db()
        d = request.get_json() if request.is_json else request.form
        version = int(d.get('version', 1))
        cur = conn.execute('''UPDATE projects SET
            project_name=?, project_number=?, customer=?,
            created_by=?, line_type=?, reason=?, project_phase=?, version=version+1
            WHERE id=? AND version=?''',
            (
                d.get('project_name', ''),
                d.get('project_number', ''),
                d.get('customer', ''),
                d.get('created_by', ''),
                d.get('line_type', ''),
                d.get('reason', ''),
                d.get('project_phase', ''),
                project_id,
                version
            ))
        conn.commit()
        conn.close()
        if cur.rowcount == 0:
            return jsonify({'error': 'conflict', 'msg': '数据已被其他人修改'}), 409
        return jsonify({'ok': True})
    return _load_project_page(project_id, view_only=False)


def _load_project_page(project_id, view_only=False):
    conn = get_db()
    project = conn.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
    if not project:
        conn.close()
        return redirect(url_for('index'))
    items = conn.execute(
        'SELECT * FROM project_items WHERE project_id=? ORDER BY sort_order, id',
        (project_id,)).fetchall()
    conn.close()
    # Convert sqlite3.Row to plain dict for JSON serialization in templates
    items = [dict(row) for row in items]
    project = dict(project)

    # Permission check: creator or superuser can edit
    current_user = session.get('username', '')
    is_owner = (project.get('created_by') == current_user)
    is_super = is_superuser()
    if not is_owner and not is_super and not view_only:
        view_only = True  # non-owner, non-superuser forced to read-only

    template = 'project_view.html' if view_only else 'project_edit.html'
    return render_template(template,
        project=project, items=items,
        lines=PREDEFINED_LINES, view_only=view_only, project_phases=PROJECT_PHASES,
        is_owner=is_owner, is_superuser=is_super, current_user=current_user)


# ==================== Save Items ====================

@app.route('/project/<int:project_id>/save-items', methods=['POST'])
@login_required
def save_items(project_id):
    data = request.get_json()
    items = data.get('items', [])
    conn = get_db()
    conn.execute('DELETE FROM project_items WHERE project_id=?', (project_id,))
    for i, item in enumerate(items):
        conn.execute('''INSERT INTO project_items
            (project_id, line_type, item_type, item_name, parent_process,
             investment_usd, cycle_time_sec, operator_count, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (
                project_id,
                item.get('line_type', ''),
                item.get('item_type', 'process'),
                item.get('item_name', ''),
                item.get('parent_process'),
                float(item.get('investment_usd') or 0),
                float(item.get('cycle_time_sec') or 0),
                float(item.get('operator_count') or 0),
                i
            ))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/project/<int:project_id>/save-line-items', methods=['POST'])
@login_required
def save_line_items(project_id):
    data = request.get_json()
    line_type = data.get('line_type', '')
    items = data.get('items', [])
    comment = data.get('comment', '')
    username = session.get('username', '')
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    conn = get_db()

    # Permission check: superuser can save any project
    project = conn.execute('SELECT created_by FROM projects WHERE id=?', (project_id,)).fetchone()
    if not project or (project['created_by'] != username and not is_superuser()):
        conn.close()
        return jsonify({'error': 'forbidden', 'msg': '无权限修改此项目'}), 403

    for attempt in range(3):
        try:
            conn.execute("BEGIN IMMEDIATE")

            # Snapshot old data before overwrite
            old_items = conn.execute(
                'SELECT * FROM project_items WHERE project_id=? AND line_type=?',
                (project_id, line_type)).fetchall()

            if old_items:
                save_batch = uuid.uuid4().hex[:8]
                # Get current project phase
                proj = conn.execute('SELECT project_phase FROM projects WHERE id=?', (project_id,)).fetchone()
                project_phase = proj['project_phase'] if proj else ''
                for old in old_items:
                    conn.execute('''INSERT INTO item_versions
                        (project_id, line_type, save_batch, item_name, item_type, parent_process,
                         investment_usd, cycle_time_sec, operator_count, updated_by, updated_at, comment, project_phase)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (
                            project_id, line_type, save_batch,
                            old['item_name'], old['item_type'], old['parent_process'],
                            old['investment_usd'], old['cycle_time_sec'], old['operator_count'],
                            username, now, comment, project_phase
                        ))

            # Delete old items and insert new ones
            conn.execute('DELETE FROM project_items WHERE project_id=? AND line_type=?', (project_id, line_type))
            for i, item in enumerate(items):
                conn.execute('''INSERT INTO project_items
                    (project_id, line_type, item_type, item_name, parent_process,
                     investment_usd, cycle_time_sec, operator_count, sort_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        project_id,
                        line_type,
                        item.get('item_type', 'process'),
                        item.get('item_name', ''),
                        item.get('parent_process'),
                        float(item.get('investment_usd') or 0),
                        float(item.get('cycle_time_sec') or 0),
                        float(item.get('operator_count') or 0),
                        i
                    ))

            # Bump project version
            conn.execute('UPDATE projects SET version = version + 1 WHERE id=?', (project_id,))

            conn.commit()
            break
        except sqlite3.OperationalError:
            conn.rollback()
            if attempt < 2:
                time.sleep(0.2)
            else:
                conn.close()
                return jsonify({'error': 'db_busy', 'msg': '数据库繁忙，请稍后重试'}), 503

    conn.close()
    return jsonify({'ok': True})


# ==================== Item Versions API ====================

@app.route('/project/<int:project_id>/item-versions')
@login_required
def item_versions(project_id):
    conn = get_db()
    rows = conn.execute('''
        SELECT iv.item_name, iv.item_type, iv.parent_process,
               iv.investment_usd, iv.cycle_time_sec, iv.operator_count
        FROM item_versions iv
        INNER JOIN (
            SELECT item_name, item_type, parent_process, MAX(updated_at) as max_at
            FROM item_versions
            WHERE project_id = ?
            GROUP BY item_name, item_type, parent_process
        ) latest ON iv.item_name = latest.item_name
                AND iv.item_type = latest.item_type
                AND COALESCE(iv.parent_process, '') = COALESCE(latest.parent_process, '')
                AND iv.updated_at = latest.max_at
        WHERE iv.project_id = ?
    ''', (project_id, project_id)).fetchall()
    conn.close()
    return jsonify({'items': [dict(r) for r in rows]})


# ==================== Project Management (Superuser) ====================

@app.route('/project/<int:project_id>', methods=['DELETE'])
@login_required
def delete_project(project_id):
    if not is_superuser():
        return jsonify({'error': 'forbidden'}), 403
    conn = get_db()
    conn.execute('DELETE FROM projects WHERE id=?', (project_id,))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/project/<int:project_id>/clone', methods=['POST'])
@login_required
def clone_project(project_id):
    conn = get_db()
    proj = conn.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
    if not proj:
        conn.close()
        return jsonify({'error': 'not_found'}), 404

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    cur = conn.execute('''INSERT INTO projects
        (project_name, project_number, customer, created_by, line_type, reason, project_phase, version, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)''',
        (
            proj['project_name'] + ' (Clone)',
            '',
            proj['customer'],
            session.get('username', ''),
            proj['line_type'],
            proj['reason'],
            proj['project_phase'],
            now
        ))
    new_id = cur.lastrowid

    items = conn.execute('SELECT * FROM project_items WHERE project_id=?', (project_id,)).fetchall()
    for item in items:
        conn.execute('''INSERT INTO project_items
            (project_id, line_type, item_type, item_name, parent_process,
             investment_usd, cycle_time_sec, operator_count, sort_order)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (new_id, item['line_type'], item['item_type'], item['item_name'],
             item['parent_process'], item['investment_usd'], item['cycle_time_sec'],
             item['operator_count'], item['sort_order']))

    conn.commit()
    conn.close()
    return jsonify({'ok': True, 'new_id': new_id})


# ==================== Admin ====================

@app.route('/admin/users')
@login_required
@superuser_required
def admin_users():
    conn = get_db()
    users = conn.execute('SELECT id, username, created_at FROM users ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('admin_users.html', users=users, is_superuser=True)


@app.route('/admin/reset-password', methods=['POST'])
@login_required
@superuser_required
def admin_reset_password():
    user_id = request.form.get('user_id', type=int)
    new_password = request.form.get('new_password', '')
    if not user_id or not new_password:
        return jsonify({'error': 'missing_fields'}), 400
    conn = get_db()
    conn.execute('UPDATE users SET password_hash=? WHERE id=?',
                 (generate_password_hash(new_password), user_id))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})


@app.route('/admin/dashboard')
@login_required
@superuser_required
def admin_dashboard():
    conn = get_db()

    stats_by_engineer = conn.execute('''
        SELECT p.created_by,
               COUNT(DISTINCT p.id) as project_count,
               COALESCE(SUM(pi.investment_usd), 0) as total_investment
        FROM projects p
        LEFT JOIN project_items pi ON p.id = pi.project_id AND pi.item_type = 'process'
        GROUP BY p.created_by
        ORDER BY project_count DESC
    ''').fetchall()

    stats_by_phase = conn.execute('''
        SELECT project_phase, COUNT(*) as count
        FROM projects
        GROUP BY project_phase
        ORDER BY count DESC
    ''').fetchall()

    recent_projects = conn.execute('''
        SELECT p.*, COALESCE(SUM(pi.investment_usd), 0) as total_investment
        FROM projects p
        LEFT JOIN project_items pi ON p.id = pi.project_id
        GROUP BY p.id
        ORDER BY p.created_at DESC
        LIMIT 10
    ''').fetchall()

    total_projects = conn.execute('SELECT COUNT(*) FROM projects').fetchone()[0]
    total_engineers = conn.execute('SELECT COUNT(DISTINCT created_by) FROM projects').fetchone()[0]
    total_investment_all = conn.execute('SELECT COALESCE(SUM(investment_usd), 0) FROM project_items').fetchone()[0]

    conn.close()
    return render_template('admin_dashboard.html',
                           stats_by_engineer=stats_by_engineer,
                           stats_by_phase=stats_by_phase,
                           recent_projects=recent_projects,
                           total_projects=total_projects,
                           total_engineers=total_engineers,
                           total_investment_all=total_investment_all,
                           is_superuser=True)


# ==================== Phase Diff Helper ====================

def compute_batch_diff(curr_items, prev_items):
    """计算当前批次与上一批次工序数据的差异。"""
    curr_map = {}
    for it in curr_items:
        key = (it['item_name'], it.get('parent_process') or '')
        curr_map[key] = it

    prev_map = {}
    for it in prev_items:
        key = (it['item_name'], it.get('parent_process') or '')
        prev_map[key] = it

    curr_keys = set(curr_map.keys())
    prev_keys = set(prev_map.keys())

    curr_total_inv = sum(it['investment_usd'] or 0 for it in curr_items)
    prev_total_inv = sum(it['investment_usd'] or 0 for it in prev_items)
    curr_total_hc = sum(it['operator_count'] or 0 for it in curr_items)
    prev_total_hc = sum(it['operator_count'] or 0 for it in prev_items)

    added = sorted([k[0] for k in (curr_keys - prev_keys)])
    removed = sorted([k[0] for k in (prev_keys - curr_keys)])
    modified = []
    for k in curr_keys & prev_keys:
        c = curr_map[k]
        p = prev_map[k]
        if (abs((c['investment_usd'] or 0) - (p['investment_usd'] or 0)) > 0.001 or
            abs((c['cycle_time_sec'] or 0) - (p['cycle_time_sec'] or 0)) > 0.001 or
            abs((c['operator_count'] or 0) - (p['operator_count'] or 0)) > 0.001):
            modified.append(k[0])

    def fmt_num(val, prefix=''):
        if val > 0:
            return f'+{prefix}{val:,.2f}'
        elif val < 0:
            return f'-{prefix}{abs(val):,.2f}'
        return f'±0'

    def fmt_int(val):
        if val > 0:
            return f'+{val}'
        elif val < 0:
            return f'-{abs(val)}'
        return '±0'

    def truncate_names(names, limit=2):
        if not names:
            return ''
        if len(names) <= limit:
            return ', '.join(names)
        return ', '.join(names[:limit]) + f' 等{len(names)}项'

    return {
        'investment_str': fmt_num(curr_total_inv - prev_total_inv, '$'),
        'headcount_str': fmt_num(curr_total_hc - prev_total_hc),
        'item_str': fmt_int(len(curr_items) - len(prev_items)),
        'added_names': truncate_names(added),
        'removed_names': truncate_names(removed),
        'modified_names': truncate_names(modified),
        'has_changes': bool(added or removed or modified or abs(curr_total_inv - prev_total_inv) > 0.001 or abs(curr_total_hc - prev_total_hc) > 0.001)
    }


# ==================== PDF Export ====================

@app.route('/project/<int:project_id>/export')
@login_required
def export_pdf(project_id):
    conn = get_db()
    project = conn.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
    items = conn.execute(
        'SELECT * FROM project_items WHERE project_id=? ORDER BY sort_order, id',
        (project_id,)).fetchall()

    # Version history for PDF
    version_history = conn.execute('''
        SELECT save_batch, line_type, updated_by, updated_at, comment, project_phase, COUNT(*) as item_count
        FROM item_versions
        WHERE project_id = ?
        GROUP BY save_batch
        ORDER BY updated_at DESC
    ''', (project_id,)).fetchall()

    # Phase diff: fetch all version items for this project
    all_version_items = conn.execute('''
        SELECT save_batch, item_name, parent_process,
               investment_usd, cycle_time_sec, operator_count, project_phase
        FROM item_versions WHERE project_id = ?
    ''', (project_id,)).fetchall()

    # Group all items by save_batch
    items_by_batch = {}
    for it in all_version_items:
        items_by_batch.setdefault(it['save_batch'], []).append(dict(it))

    # Build a lookup: (line_type, project_phase) -> latest save_batch
    # Need updated_at per save_batch; fetch it
    batch_info = {}
    for v in version_history:
        batch_info[v['save_batch']] = {
            'line_type': v['line_type'],
            'project_phase': v['project_phase'],
            'updated_at': v['updated_at']
        }

    # For each phase+line_type combo, keep only the latest save_batch
    latest_batch_by_phase_line = {}
    for sb, info in batch_info.items():
        key = (info['line_type'], info['project_phase'])
        if key not in latest_batch_by_phase_line:
            latest_batch_by_phase_line[key] = sb
        else:
            # Compare updated_at strings (ISO format works for string compare)
            if info['updated_at'] > batch_info[latest_batch_by_phase_line[key]]['updated_at']:
                latest_batch_by_phase_line[key] = sb

    # Compute diff for each version_history row
    version_history_with_diff = []
    for v in version_history:
        v_dict = dict(v)
        curr_phase = v['project_phase']
        line_type = v['line_type']
        curr_idx = PHASE_ORDER_INDEX.get(curr_phase, -1)

        if curr_idx <= 0:
            v_dict['diff'] = None
            v_dict['diff_status'] = 'first_phase'
        else:
            prev_phase = None
            for i in range(curr_idx - 1, -1, -1):
                candidate = PHASE_ORDER[i]
                if (line_type, candidate) in latest_batch_by_phase_line:
                    prev_phase = candidate
                    break

            if prev_phase is None:
                v_dict['diff'] = None
                v_dict['diff_status'] = 'no_prev_data'
            else:
                prev_batch = latest_batch_by_phase_line[(line_type, prev_phase)]
                curr_items = items_by_batch.get(v['save_batch'], [])
                prev_items = items_by_batch.get(prev_batch, [])
                diff = compute_batch_diff(curr_items, prev_items)
                diff['prev_phase'] = prev_phase
                v_dict['diff'] = diff
                v_dict['diff_status'] = 'has_diff'

        version_history_with_diff.append(v_dict)

    conn.close()
    if not project:
        return redirect(url_for('index'))

    # Group items by line_type
    lines_data = OrderedDict()
    for it in items:
        lt = it['line_type'] or project['line_type'] or '未分类'
        if lt not in lines_data:
            lines_data[lt] = {'items': [], 'process_items': []}
        lines_data[lt]['items'].append(it)
        if it['item_type'] == 'process':
            lines_data[lt]['process_items'].append(it)

    # Calculate per-line stats
    for lt, data in lines_data.items():
        procs = data['process_items']
        data['process_count'] = len(procs)
        data['total_investment'] = sum(it['investment_usd'] or 0 for it in data['items'])
        data['total_headcount'] = sum(it['operator_count'] or 0 for it in procs)
        data['bottleneck'] = max(procs, key=lambda x: x['cycle_time_sec'] or 0) if procs else None

    # Global totals
    all_process_items = [it for it in items if it['item_type'] == 'process']
    total_investment = sum(it['investment_usd'] or 0 for it in items)
    total_headcount = sum(it['operator_count'] or 0 for it in all_process_items)
    bottleneck = max(all_process_items, key=lambda x: x['cycle_time_sec'] or 0) if all_process_items else None

    # Look up reviewer and approver based on engineer (preparer)
    created_by = project['created_by'] or ''
    reviewer_name = ''
    approver_name = ''
    if created_by in APPROVAL_HIERARCHY:
        reviewer_name, approver_name = APPROVAL_HIERARCHY[created_by]

    return render_template('pdf_template.html',
        project=project, items=items,
        lines_data=lines_data,
        total_investment=total_investment,
        total_headcount=total_headcount,
        bottleneck=bottleneck,
        process_count=len(all_process_items),
        generated_at=datetime.now().strftime('%Y-%m-%d %H:%M'),
        reviewer_name=reviewer_name,
        approver_name=approver_name,
        project_phases=PROJECT_PHASES,
        version_history=version_history_with_diff,
    )


# ==================== Launch ====================

if __name__ == '__main__':
    init_db()
    migrate_db()
    app.run(host='0.0.0.0', port=8080, debug=False)