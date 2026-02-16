from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any

from flask import Flask, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "doctrack.db"

app = Flask(__name__)
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

    document_columns = {row[1] for row in cur.execute("PRAGMA table_info(documents)").fetchall()}
    if "link_path" not in document_columns:
        cur.execute("ALTER TABLE documents ADD COLUMN link_path TEXT")

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


def login_required() -> Any:
    if "user_id" not in session:
        return redirect(url_for("login"))
    return None


def get_current_user() -> sqlite3.Row | None:
    if "user_id" not in session:
        return None
    return get_db().execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()


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


@app.context_processor
def inject_globals() -> dict[str, Any]:
    return {
        "current_user": get_current_user(),
        "format_date": format_date,
        "today": date.today().isoformat(),
    }


@app.route("/")
def home() -> Any:
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login() -> Any:
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if not user or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.", "danger")
            return render_template("login.html")

        session.clear()
        session["user_id"] = user["id"]
        return redirect(url_for("dashboard"))
    return render_template("login.html")


@app.route("/logout")
def logout() -> Any:
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
def dashboard() -> Any:
    guard = login_required()
    if guard:
        return guard

    db = get_db()
    on_circulation = db.execute(
        "SELECT COUNT(*) as count FROM documents WHERE approved = 0"
    ).fetchone()["count"]
    approved_not_scanned = db.execute(
        "SELECT COUNT(*) as count FROM documents WHERE approved = 1 AND scanned = 0"
    ).fetchone()["count"]

    on_circulation_rows = db.execute(
        "SELECT id, doc_no, title, created_at FROM documents WHERE approved = 0 ORDER BY created_at ASC"
    ).fetchall()
    approved_not_scanned_rows = db.execute(
        "SELECT id, doc_no, title, approved_date FROM documents WHERE approved = 1 AND scanned = 0 ORDER BY approved_date ASC"
    ).fetchall()

    return render_template(
        "dashboard.html",
        on_circulation=on_circulation,
        approved_not_scanned=approved_not_scanned,
        on_circulation_rows=on_circulation_rows,
        approved_not_scanned_rows=approved_not_scanned_rows,
        days_since=days_since,
    )


@app.route("/documents")
def documents() -> Any:
    guard = login_required()
    if guard:
        return guard

    status_filter = request.args.get("status", "all")
    type_filter = request.args.get("type", "all")
    process_filter = request.args.get("process", "all")
    q = request.args.get("q", "").strip()
    page = request.args.get("page", "1").strip()
    try:
        page_number = max(int(page), 1)
    except ValueError:
        page_number = 1
    page_size = 6

    where_clause = " WHERE 1=1"
    params: list[Any] = []

    if status_filter == "on_circulation":
        where_clause += " AND approved = 0"
    elif status_filter == "approved_not_scanned":
        where_clause += " AND approved = 1 AND scanned = 0"
    elif status_filter == "completed":
        where_clause += " AND approved = 1 AND scanned = 1"

    if type_filter != "all":
        where_clause += " AND type = ?"
        params.append(type_filter)

    if process_filter != "all":
        where_clause += " AND process = ?"
        params.append(process_filter)

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
        status_filter=status_filter,
        type_filter=type_filter,
        process_filter=process_filter,
        q=q,
        page_number=page_number,
        total_pages=total_pages,
        page_size=page_size,
        total_docs=total_docs,
        days_since=days_since,
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

    if doc_type not in TYPE_OPTIONS or process not in PROCESS_OPTIONS or not doc_no or not title:
        flash("Please fill all mandatory fields correctly.", "danger")
        return redirect(url_for("documents"))

    user = get_current_user()
    get_db().execute(
        """
        INSERT INTO documents (type, process, doc_no, title, approved, scanned, created_at, created_by)
        VALUES (?, ?, ?, ?, 0, 0, ?, ?)
        """,
        (doc_type, process, doc_no, title, date.today().isoformat(), user["username"]),
    )
    get_db().commit()
    flash("Document added.", "success")
    return redirect(url_for("documents"))


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
        return redirect(url_for("documents"))

    db.execute(
        "UPDATE documents SET approved = 1, approved_date = ?, approved_by = ? WHERE id = ?",
        (approved_date, user["username"], doc_id),
    )
    db.commit()
    flash("Document approved.", "success")
    return redirect(url_for("documents"))


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
        return redirect(url_for("documents"))

    db.execute(
        "UPDATE documents SET scanned = 1, scanned_date = ?, scanned_by = ?, link_path = ? WHERE id = ?",
        (scanned_date, user["username"], link_path, doc_id),
    )
    db.commit()
    flash("Document marked as scanned.", "success")
    return redirect(url_for("documents"))


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


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
