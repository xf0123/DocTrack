from __future__ import annotations

import sqlite3
import csv
from io import StringIO
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from flask import Flask, Response, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "doctrack.db"

app = Flask(__name__)

@app.template_filter('format_date')
def format_date(value):
    if not value: return ""
    try:
        return datetime.strptime(value.split('T')[0], '%Y-%m-%d').strftime('%d-%b-%Y')
    except:
        return value

@app.template_filter('format_datetime')
def format_datetime(value):
    if not value: return ""
    try:
        return datetime.fromisoformat(value).strftime('%d-%b-%Y %H:%M')
    except:
        return value

@app.context_processor
def inject_now():
    return {'datetime': datetime, 'now': datetime.now()}

app.config["SECRET_KEY"] = "change-this-secret-key"


TYPE_OPTIONS = ["Protocol", "Report", "CRF", "Dev", "QRA", "Other"]
PROCESS_OPTIONS = ["Cal", "Qual", "PV", "CV", "APS", "TV", "CSV", "Other"]


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(_: Any) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            process TEXT NOT NULL,
            doc_no TEXT NOT NULL,
            title TEXT NOT NULL,
            remarks TEXT,
            approved INTEGER NOT NULL DEFAULT 0,
            scanned INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            created_by TEXT NOT NULL,
            approved_date TEXT,
            approved_by TEXT,
            scanned_date TEXT,
            scanned_by TEXT,
            link_path TEXT
        );
        """
    )

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS executions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            activity TEXT NOT NULL,
            protocol TEXT,
            date_start TEXT NOT NULL,
            date_end TEXT,
            status TEXT NOT NULL, 
            progress_note TEXT,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS samples (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sample_name TEXT NOT NULL,
            handover_date TEXT NOT NULL,
            expected_result_date TEXT,
            status TEXT NOT NULL,
            progress_note TEXT,
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task TEXT NOT NULL,
            description TEXT,
            due_date TEXT,
            status TEXT NOT NULL, 
            progress_note TEXT,
            reminder_active INTEGER DEFAULT 0,
            reminder_time TEXT,
            basket TEXT DEFAULT 'planned',
            created_by TEXT,
            created_at TEXT,
            updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS personnel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            initial TEXT UNIQUE NOT NULL,
            is_active INTEGER DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            personnel_id INTEGER NOT NULL,
            purpose TEXT NOT NULL,
            date_start TEXT NOT NULL,
            date_end TEXT,
            note TEXT,
            FOREIGN KEY(personnel_id) REFERENCES personnel(id)
        );
        """
    )



    document_columns = {row[1] for row in cur.execute("PRAGMA table_info(documents)").fetchall()}
    if "link_path" not in document_columns:
        cur.execute("ALTER TABLE documents ADD COLUMN link_path TEXT")
        cur.execute("ALTER TABLE executions ADD COLUMN updated_at TEXT;")
        cur.execute("ALTER TABLE samples ADD COLUMN updated_at TEXT;")
    if "remarks" not in document_columns:
        cur.execute("ALTER TABLE documents ADD COLUMN remarks TEXT")

    admin = cur.execute("SELECT id FROM users WHERE username = ?", ("admin",)).fetchone()
    if not admin:
        cur.execute(
            "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (
                "admin",
                generate_password_hash("admin123"),
                "admin",
                date.today().isoformat(),
            ),
        )
    conn.commit()
    conn.close()


def backup_database_if_needed() -> None:
    backup_dir = DATA_DIR / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)

    backup_filename = f"DocTract_{date.today().strftime('%d-%b-%Y')}.db"
    backup_path = backup_dir / backup_filename
    if backup_path.exists() or not DB_PATH.exists():
        return

    source_conn = sqlite3.connect(DB_PATH)
    backup_conn = sqlite3.connect(backup_path)
    try:
        source_conn.backup(backup_conn)
    finally:
        backup_conn.close()
        source_conn.close()


def login_required() -> Any:
    if "user_id" not in session:
        return redirect(url_for("login"))
    return None


def get_current_user() -> sqlite3.Row | None:
    if "user_id" not in session:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()


def redirect_to_documents_referrer() -> Any:
    return_to = request.form.get("return_to", "")
    if return_to:
        parsed_return_to = urlparse(return_to)
        if parsed_return_to.path == url_for("documents"):
            target = parsed_return_to.path
            if parsed_return_to.query:
                target = f"{target}?{parsed_return_to.query}"
            return redirect(target)

    referrer = request.referrer
    if referrer:
        parsed_referrer = urlparse(referrer)
        if parsed_referrer.path == url_for("documents"):
            return redirect(referrer)
    return redirect(url_for("documents"))


def admin_required() -> None:
    user = get_current_user()
    if not user or user["role"] != "admin":
        abort(403)


def format_date(value: str | None) -> str:
    if not value:
        return "-"
    dt = datetime.strptime(value, "%Y-%m-%d")
    return dt.strftime("%d-%b-%Y")


def days_since(value: str | None) -> int | None:
    if not value:
        return None
    dt = datetime.strptime(value, "%Y-%m-%d").date()
    return (date.today() - dt).days


def csv_date(value: str | None) -> str:
    if not value:
        return ""
    dt = datetime.strptime(value, "%Y-%m-%d")
    return dt.strftime("%d-%b-%Y")


@app.context_processor
def inject_globals() -> dict[str, Any]:
    return {
        "current_user": get_current_user(),
        "format_date": format_date,
        "today": date.today().isoformat(),
    }


@app.route("/")
@app.route("/dashboard")
def dashboard():
    guard = login_required()
    if guard: return guard
    db = get_db()
    today = date.today()
    
    # 1. Document Data
    docs = db.execute("SELECT * FROM documents ORDER BY id DESC").fetchall()
    
    on_circulation = []
    approved_not_scanned = []
    
    for d in docs:
        # Convert to a dictionary first to prevent "IndexError" crashes
        d_dict = dict(d) 
        
        # Safely look for whatever date column exists
        doc_date_str = d_dict.get('date') or d_dict.get('upload_date') or d_dict.get('created_at')
        
        if not d_dict.get('approved'):
            days = 0
            if doc_date_str:
                try:
                    d_date = datetime.strptime(doc_date_str.split('T')[0], '%Y-%m-%d').date()
                    days = (today - d_date).days
                except: pass
                
            d_dict['days'] = days
            # Ensure we have a dummy date if formatting requires it in HTML
            if not doc_date_str: d_dict['date'] = '-' 
            on_circulation.append(d_dict)
            
        elif d_dict.get('approved') and not d_dict.get('scanned'):
            days = 0
            app_date_str = d_dict.get('approved_date')
            if app_date_str:
                try:
                    a_date = datetime.strptime(app_date_str.split('T')[0], '%Y-%m-%d').date()
                    days = (today - a_date).days
                except: pass
                
            d_dict['days'] = days
            approved_not_scanned.append(d_dict)

    # 2. Execution Data
    executions_data = db.execute("SELECT * FROM executions ORDER BY date_start DESC").fetchall()
    exec_ongoing = [dict(e) for e in executions_data if e['status'] == 'progress']
    exec_total = len(exec_ongoing)
    
    exec_7d = []
    for e in exec_ongoing:
        if e.get('date_start'):
            try:
                start_date = datetime.strptime(e['date_start'].split('T')[0], '%Y-%m-%d').date()
                if (today - start_date).days > 7:
                    exec_7d.append(e)
            except: pass

    # 3. Sample Data
    samples_data = db.execute("SELECT * FROM samples ORDER BY handover_date DESC").fetchall()
    samp_ongoing = [dict(s) for s in samples_data if s['status'] == 'progress']
    sample_total = len(samp_ongoing)
    
    samp_7d, samp_14d, samp_21d, samp_30d = [], [], [], []
    for s in samp_ongoing:
        if s.get('handover_date'):
            try:
                start_date = datetime.strptime(s['handover_date'].split('T')[0], '%Y-%m-%d').date()
                days_passed = (today - start_date).days
                if days_passed > 30: samp_30d.append(s)
                elif days_passed > 21: samp_21d.append(s)
                elif days_passed > 14: samp_14d.append(s)
                elif days_passed > 7: samp_7d.append(s)
            except: pass

    return render_template(
        "dashboard.html", 
        on_circulation=on_circulation,
        approved_not_scanned=approved_not_scanned,
        exec_total=exec_total, exec_7d=exec_7d,
        sample_total=sample_total, samp_7d=samp_7d, samp_14d=samp_14d, samp_21d=samp_21d, samp_30d=samp_30d
    )


@app.route("/documents")
def documents() -> Any:
    guard = login_required()
    if guard:
        return guard

    status_filters = [value for value in request.args.getlist("status") if value]
    type_filters = [value for value in request.args.getlist("type") if value]
    process_filters = [value for value in request.args.getlist("process") if value]
    q = request.args.get("q", "").strip()
    page = request.args.get("page", "1").strip()
    try:
        page_number = max(int(page), 1)
    except ValueError:
        page_number = 1
    page_size = 6

    where_clause = " WHERE 1=1"
    params: list[Any] = []

    status_conditions = {
        "on_circulation": "(approved = 0)",
        "approved_not_scanned": "(approved = 1 AND scanned = 0)",
        "completed": "(approved = 1 AND scanned = 1)",
    }
    valid_status_filters = [status for status in status_filters if status in status_conditions]
    if valid_status_filters and len(valid_status_filters) < len(status_conditions):
        where_clause += " AND (" + " OR ".join(status_conditions[status] for status in valid_status_filters) + ")"

    valid_type_filters = [doc_type for doc_type in type_filters if doc_type in TYPE_OPTIONS]
    if valid_type_filters and len(valid_type_filters) < len(TYPE_OPTIONS):
        placeholders = ", ".join("?" for _ in valid_type_filters)
        where_clause += f" AND type IN ({placeholders})"
        params.extend(valid_type_filters)

    valid_process_filters = [process for process in process_filters if process in PROCESS_OPTIONS]
    if valid_process_filters and len(valid_process_filters) < len(PROCESS_OPTIONS):
        placeholders = ", ".join("?" for _ in valid_process_filters)
        where_clause += f" AND process IN ({placeholders})"
        params.extend(valid_process_filters)

    if q:
        where_clause += " AND (doc_no LIKE ? OR title LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])

    db = get_db()
    count_query = f"SELECT COUNT(*) AS count FROM documents{where_clause}"
    total_docs = db.execute(count_query, params).fetchone()["count"]
    total_pages = max((total_docs + page_size - 1) // page_size, 1)
    page_number = min(page_number, total_pages)

    offset = (page_number - 1) * page_size
    query = f"SELECT * FROM documents{where_clause} ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?"
    docs = db.execute(query, [*params, page_size, offset]).fetchall()

    existing_doc_nos = [
        row["doc_no"]
        for row in db.execute("SELECT doc_no FROM documents").fetchall()
    ]

    return render_template(
        "documents.html",
        docs=docs,
        existing_doc_nos=existing_doc_nos,
        type_options=TYPE_OPTIONS,
        process_options=PROCESS_OPTIONS,
        status_filters=valid_status_filters,
        type_filters=valid_type_filters,
        process_filters=valid_process_filters,
        q=q,
        page_number=page_number,
        total_pages=total_pages,
        page_size=page_size,
        total_docs=total_docs,
        days_since=days_since,
    )


@app.route("/documents/export-csv")
def export_documents_csv() -> Any:
    guard = login_required()
    if guard:
        return guard

    db = get_db()
    docs = db.execute(
        """
        SELECT type, process, doc_no, title, created_at, approved_date, scanned_date
        FROM documents
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(["Type", "Process", "Doc No", "Title", "Added", "Approved", "Scanned"])

    for doc in docs:
        row = [
            doc["type"],
            doc["process"],
            doc["doc_no"],
            doc["title"],
            csv_date(doc["created_at"]),
            csv_date(doc["approved_date"]),
            csv_date(doc["scanned_date"]),
        ]
        writer.writerow(row)

    filename = f"documents_{date.today().strftime('%Y%m%d')}.csv"
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/documents/add", methods=["POST"])
def add_document() -> Any:
    guard = login_required()
    if guard:
        return guard

    form = request.form
    doc_type = form.get("type", "")
    process = form.get("process", "")
    doc_no = form.get("doc_no", "").strip()
    title = form.get("title", "").strip()
    remarks = form.get("remarks", "").strip()

    if doc_type not in TYPE_OPTIONS or process not in PROCESS_OPTIONS or not doc_no or not title:
        flash("Please fill all mandatory fields correctly.", "danger")
        return redirect_to_documents_referrer()

    user = get_current_user()
    get_db().execute(
        """
        INSERT INTO documents (type, process, doc_no, title, remarks, approved, scanned, created_at, created_by)
        VALUES (?, ?, ?, ?, ?, 0, 0, ?, ?)
        """,
        (doc_type, process, doc_no, title, remarks, date.today().isoformat(), user["username"]),
    )
    get_db().commit()
    flash("Document added.", "success")
    return redirect_to_documents_referrer()




@app.route("/documents/<int:doc_id>/update", methods=["POST"])
def update_document(doc_id: int) -> Any:
    guard = login_required()
    if guard:
        return guard

    form = request.form
    doc_type = form.get("type", "")
    process = form.get("process", "")
    doc_no = form.get("doc_no", "").strip()
    title = form.get("title", "").strip()
    remarks = form.get("remarks", "").strip()

    if doc_type not in TYPE_OPTIONS or process not in PROCESS_OPTIONS or not doc_no or not title:
        flash("Please fill all mandatory fields correctly.", "danger")
        return redirect_to_documents_referrer()

    db = get_db()
    doc = db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not doc:
        abort(404)
    if doc["scanned"]:
        flash("Scanned documents cannot be edited from this modal.", "warning")
        return redirect_to_documents_referrer()

    db.execute(
        "UPDATE documents SET type = ?, process = ?, doc_no = ?, title = ?, remarks = ? WHERE id = ?",
        (doc_type, process, doc_no, title, remarks, doc_id),
    )
    db.commit()
    flash("Document updated.", "success")
    return redirect_to_documents_referrer()

@app.route("/documents/<int:doc_id>/approve", methods=["POST"])
def approve_document(doc_id: int) -> Any:
    guard = login_required()
    if guard:
        return guard

    approved_date = request.form.get("date", "")
    if not approved_date:
        flash("Approved date is required.", "danger")
        return redirect(url_for("documents"))

    user = get_current_user()
    db = get_db()
    doc = db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not doc:
        abort(404)
    if doc["approved"]:
        flash("Document already approved.", "warning")
        return redirect_to_documents_referrer()

    db.execute(
        "UPDATE documents SET approved = 1, approved_date = ?, approved_by = ? WHERE id = ?",
        (approved_date, user["username"], doc_id),
    )
    db.commit()
    flash("Document approved.", "success")
    return redirect_to_documents_referrer()


@app.route("/documents/<int:doc_id>/scan", methods=["POST"])
def scan_document(doc_id: int) -> Any:
    guard = login_required()
    if guard:
        return guard

    scanned_date = request.form.get("date", "")
    link_path = request.form.get("link_path", "").strip()
    if link_path.startswith('"'):
        link_path = link_path[1:].strip()
    if link_path.endswith('"'):
        link_path = link_path[:-1].strip()
    if not scanned_date:
        flash("Scanned date is required.", "danger")
        return redirect(url_for("documents"))
    if not link_path:
        flash("Link path is required.", "danger")
        return redirect(url_for("documents"))

    user = get_current_user()
    db = get_db()
    doc = db.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    if not doc:
        abort(404)
    if not doc["approved"]:
        flash("Document must be approved before scan.", "danger")
        return redirect(url_for("documents"))
    if doc["scanned"]:
        flash("Document already scanned.", "warning")
        return redirect_to_documents_referrer()

    db.execute(
        "UPDATE documents SET scanned = 1, scanned_date = ?, scanned_by = ?, link_path = ? WHERE id = ?",
        (scanned_date, user["username"], link_path, doc_id),
    )
    db.commit()
    flash("Document marked as scanned.", "success")
    return redirect_to_documents_referrer()


@app.route("/setup", methods=["GET", "POST"])
def setup() -> Any:
    guard = login_required()
    if guard:
        return guard

    user = get_current_user()
    db = get_db()

    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "change_password":
            target_id = int(request.form.get("target_id", "0"))
            new_password = request.form.get("new_password", "")
            if not new_password:
                flash("Password cannot be empty.", "danger")
                return redirect(url_for("setup"))

            if user["role"] != "admin" and target_id != user["id"]:
                abort(403)

            db.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (generate_password_hash(new_password), target_id),
            )
            db.commit()
            flash("Password updated.", "success")

        elif action == "add_user":
            admin_required()
            username = request.form.get("username", "").strip()
            password = request.form.get("password", "")
            role = request.form.get("role", "user")
            if not username or not password or role not in ["admin", "user"]:
                flash("Invalid user data.", "danger")
                return redirect(url_for("setup"))
            try:
                db.execute(
                    "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                    (username, generate_password_hash(password), role, date.today().isoformat()),
                )
                db.commit()
                flash("User added.", "success")
            except sqlite3.IntegrityError:
                flash("Username already exists.", "danger")

        elif action == "delete_user":
            admin_required()
            target_id = int(request.form.get("target_id", "0"))
            if target_id == user["id"]:
                flash("You cannot delete your own account.", "danger")
                return redirect(url_for("setup"))

            db.execute("DELETE FROM users WHERE id = ?", (target_id,))
            db.commit()
            flash("User deleted.", "success")

        elif action == "change_role":
            admin_required()
            target_id = int(request.form.get("target_id", "0"))
            new_role = request.form.get("role", "user")
            if new_role not in ["admin", "user"]:
                flash("Invalid role.", "danger")
                return redirect(url_for("setup"))

            db.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, target_id))
            db.commit()
            flash("Role updated.", "success")

        return redirect(url_for("setup"))

    users = db.execute("SELECT * FROM users ORDER BY username ASC").fetchall()
    return render_template("setup.html", users=users)

@app.route("/projects", methods=["GET", "POST"])
def projects():
    guard = login_required()
    if guard: return guard
    db = get_db()
    
    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            rem_active = 1 if request.form.get("reminder_active") == 'on' else 0
            db.execute(
                "INSERT INTO projects (task, description, due_date, reminder_active, reminder_time, basket, created_by, created_at, status) VALUES (?,?,?,?,?,'parked',?,?,'')",
                (request.form.get("task"), request.form.get("description"), request.form.get("due_date"), rem_active, request.form.get("reminder_time"), get_current_user()["username"], date.today().isoformat())
            )
            flash("Project task added to Parked.", "success")
        elif action == "edit":
            rem_active = 1 if request.form.get("reminder_active") == 'on' else 0
            db.execute(
                "UPDATE projects SET task=?, description=?, due_date=?, reminder_active=?, reminder_time=? WHERE id=?",
                (request.form.get("task"), request.form.get("description"), request.form.get("due_date"), rem_active, request.form.get("reminder_time"), request.form.get("id"))
            )
        elif action == "move":
            db.execute("UPDATE projects SET basket = ? WHERE id = ?", (request.form.get("basket"), request.form.get("task_id")))
            db.commit()
            return Response("OK", status=200)
        elif action == "snooze":
            db.execute("UPDATE projects SET reminder_time = ? WHERE id = ?", (request.form.get("new_time"), request.form.get("task_id")))
            db.commit()
            return Response("OK", status=200)
            
        db.commit()
        return redirect(url_for("projects"))
        
    tasks = db.execute("SELECT * FROM projects").fetchall()
    return render_template("projects.html", tasks=tasks)


@app.route("/projects/reminders")
def get_reminders():
    db = get_db()
    now = datetime.now().isoformat()
    reminders = db.execute("SELECT id, task, reminder_time FROM projects WHERE reminder_active = 1 AND reminder_time <= ?", (now,)).fetchall()
    return {"reminders": [dict(r) for r in reminders]}

# ==========================================
# 1. EXECUTION TRACKER ROUTE
# ==========================================
@app.route("/executions", methods=["GET", "POST"])
def executions():
    guard = login_required()
    if guard: return guard
    db = get_db()
    user = get_current_user()

    if request.method == "POST":
        action = request.form.get("action")
        now_str = datetime.now().isoformat()
        
        if action == "add":
            db.execute(
                "INSERT INTO executions (activity, protocol, date_start, date_end, status, progress_note, created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (request.form.get("activity"), request.form.get("protocol"), request.form.get("date_start"), request.form.get("date_end"), request.form.get("status"), request.form.get("progress_note"), user["username"], date.today().isoformat(), now_str)
            )
            flash("Execution tracked successfully.", "success")
        elif action == "edit":
            db.execute(
                "UPDATE executions SET activity=?, protocol=?, date_start=?, date_end=?, status=?, progress_note=?, updated_at=? WHERE id=?",
                (request.form.get("activity"), request.form.get("protocol"), request.form.get("date_start"), request.form.get("date_end"), request.form.get("status"), request.form.get("progress_note"), now_str, request.form.get("id"))
            )
            flash("Execution updated.", "success")
        elif action == "delete":
            db.execute("DELETE FROM executions WHERE id=?", (request.form.get("id"),))
            flash("Execution deleted.", "success") 

        db.commit()
        return redirect(url_for("executions"))

    status_filter = request.args.get("status", "both")
    search_query = request.args.get("search", "")
    sort_by = "date_start" # Hardcoded
    
    query = "SELECT * FROM executions WHERE 1=1"
    params = []
    
    if status_filter != "both":
        query += " AND status = ?"
        params.append(status_filter)
    if search_query:
        query += " AND activity LIKE ?"
        params.append(f"%{search_query}%")
        
    query += f" ORDER BY {sort_by} DESC"
    executions_list = db.execute(query, params).fetchall()
    return render_template("executions.html", executions=executions_list, status=status_filter, search=search_query)


# ==========================================
# 2. SAMPLE TRACKER ROUTE
# ==========================================
@app.route("/samples", methods=["GET", "POST"])
def samples():
    guard = login_required()
    if guard: return guard
    db = get_db()
    user = get_current_user()

    if request.method == "POST":
        action = request.form.get("action")
        now_str = datetime.now().isoformat()
        
        if action == "add":
            db.execute(
                "INSERT INTO samples (sample_name, handover_date, expected_result_date, status, progress_note, created_by, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (request.form.get("sample_name"), request.form.get("handover_date"), request.form.get("expected_result_date"), request.form.get("status"), request.form.get("progress_note"), user["username"], date.today().isoformat(), now_str)
            )
            flash("Sample logged successfully.", "success")
        elif action == "edit":
            db.execute(
                "UPDATE samples SET sample_name=?, handover_date=?, expected_result_date=?, status=?, progress_note=?, updated_at=? WHERE id=?",
                (request.form.get("sample_name"), request.form.get("handover_date"), request.form.get("expected_result_date"), request.form.get("status"), request.form.get("progress_note"), now_str, request.form.get("id"))
            )
            flash("Sample updated.", "success")
        elif action == "delete":
            db.execute("DELETE FROM samples WHERE id=?", (request.form.get("id"),))
            flash("Sample deleted.", "success")    
        db.commit()

        return redirect(url_for("samples"))

    # GET Request: Handle Search, Filter, and Sort
    status_filter = request.args.get("status", "both")
    search_query = request.args.get("search", "")
    sort_by = request.args.get("sort", "handover_date") # Default sort
    
    query = "SELECT * FROM samples WHERE 1=1"
    params = []
    
    if status_filter != "both":
        query += " AND status = ?"
        params.append(status_filter)
    if search_query:
        query += " AND sample_name LIKE ?"
        params.append(f"%{search_query}%")
        
    # Whitelist sorting to prevent errors
    allowed_sorts = ['handover_date', 'expected_result_date']
    sort_col = sort_by if sort_by in allowed_sorts else 'handover_date'
    query += f" ORDER BY {sort_col} DESC"
    
    samples_list = db.execute(query, params).fetchall()
    return render_template("samples.html", samples=samples_list, status=status_filter, search=search_query, sort=sort_by)


# ==========================================
# 3. TEAM ATTENDANCE TRACKER ROUTE
# ==========================================
@app.route("/attendance", methods=["GET", "POST"])
def attendance():
    guard = login_required()
    if guard: return guard
    db = get_db()
    
    if request.method == "POST":
        action = request.form.get("action")
        
        if action == "add_personnel":
            initial = request.form.get("initial").upper()
            try:
                db.execute("INSERT INTO personnel (initial, is_active) VALUES (?, 1)", (initial,))
                db.commit()
            except sqlite3.IntegrityError:
                pass
            return redirect(url_for("attendance", _anchor="personnel"))
        
        elif action == "toggle_personnel":
            new_status = 0 if request.form.get("is_active") == '1' else 1
            db.execute("UPDATE personnel SET is_active = ? WHERE id = ?", (new_status, request.form.get("personnel_id")))
            db.commit()
            return redirect(url_for("attendance", _anchor="personnel"))

        elif action == "add_attendance":
            db.execute(
                "INSERT INTO attendance (personnel_id, purpose, date_start, date_end, note) VALUES (?, ?, ?, ?, ?)",
                (request.form.get("personnel_id"), request.form.get("purpose"), request.form.get("date_start"), request.form.get("date_end"), request.form.get("note", ""))
            )
            db.commit()
            return redirect(url_for("attendance"))
            
        elif action == "edit_attendance":
            db.execute(
                "UPDATE attendance SET purpose=?, date_start=?, date_end=?, note=? WHERE id=?",
                (request.form.get("purpose"), request.form.get("date_start"), request.form.get("date_end"), request.form.get("note", ""), request.form.get("id"))
            )
            db.commit()
            return redirect(url_for("attendance"))

    personnel_list = db.execute("SELECT * FROM personnel ORDER BY initial ASC").fetchall()
    
    # --- AUTOMATIC YEAR EXTRACTION LOGIC ---
    years_data = db.execute("SELECT DISTINCT strftime('%Y', date_start) as year FROM attendance WHERE date_start IS NOT NULL ORDER BY year DESC").fetchall()
    available_years = [y['year'] for y in years_data if y['year']]
    
    current_year = str(date.today().year)
    if current_year not in available_years:
        available_years.append(current_year)
        available_years.sort(reverse=True)
        
    year_filter = request.args.get("year", current_year)
    active_only = request.args.get("active_only", "0")
    initials_filter = request.args.getlist("initials") 
    
    query = "SELECT a.*, p.initial, p.is_active FROM attendance a JOIN personnel p ON a.personnel_id = p.id WHERE strftime('%Y', a.date_start) = ?"
    params = [year_filter]
    
    if active_only == "1":
        query += " AND p.is_active = 1"
    if initials_filter:
        placeholders = ','.join('?' for _ in initials_filter)
        query += f" AND p.initial IN ({placeholders})"
        params.extend(initials_filter)
        
    query += " ORDER BY a.date_start DESC"
    attendance_records = db.execute(query, params).fetchall()

    return render_template(
        "attendance.html", 
        personnel=personnel_list, 
        attendance=attendance_records,
        year_filter=year_filter,
        active_only=active_only,
        initials_filter=initials_filter,
        available_years=available_years  # Sent to HTML
    )

@app.route("/dashboard/stats")
def stats():
    # Example logic
    overdue = db.execute("SELECT count(*) FROM executions WHERE status='progress' AND date_start < date('now', '-7 days')").fetchone()[0]
    return render_template("stats.html", overdue=overdue)

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    # If your login page is called something else (like 'index'), change 'login' below to that name
    return redirect(url_for("login"))

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=4000, debug=True)
