"""
Mini School Management - Flask app (Python)
Auth, students, tasks, complaints; teacher vs student dashboards.
"""
import json
import os
import random
import sqlite3
from contextlib import contextmanager
from functools import wraps
from pathlib import Path

from flask import (
    Flask,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

# -----------------------------------------------------------------------------
# Config & DB
# -----------------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent
DATABASE = BASE_DIR / "school.db"

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-in-production")


@contextmanager
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'teacher',
                student_id TEXT
            );
            CREATE TABLE IF NOT EXISTS students (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                class_name TEXT NOT NULL,
                roll TEXT NOT NULL,
                attendance REAL NOT NULL DEFAULT 0,
                attendance_history TEXT
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                student_id TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Pending',
                created_at INTEGER,
                FOREIGN KEY (student_id) REFERENCES students(id)
            );
            CREATE TABLE IF NOT EXISTS complaints (
                id TEXT PRIMARY KEY,
                student_id TEXT NOT NULL,
                title TEXT NOT NULL,
                category TEXT,
                message TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'Open',
                reply TEXT,
                created_at INTEGER,
                replied_at INTEGER,
                FOREIGN KEY (student_id) REFERENCES students(id)
            );
        """)


def uid():
    import time
    return f"{int(time.time() * 1000)}_{random.randint(0, 0xFFFF):04x}"


# -----------------------------------------------------------------------------
# Chart rendered in Python (no JavaScript)
# -----------------------------------------------------------------------------
def render_attendance_chart_svg(points, width=600, height=260, theme="teacher"):
    """Generate attendance wave chart as SVG. theme: 'teacher' (blue) or 'student' (amber)."""
    if not points or len(points) < 2:
        return ""
    values = [max(0, min(100, float(v) if v is not None else 0)) for v in points]
    pad = 14
    base_y = height - pad - 14
    top_y = pad + 10
    usable_h = base_y - top_y
    n = len(values)
    step_x = (width - pad * 2) / (n - 1) if n > 1 else 0
    pts = []
    for i, v in enumerate(values):
        x = pad + i * step_x
        y = base_y - (v / 100) * usable_h
        pts.append((x, y, v))
    # Path for wave (smooth quadratic curve)
    path_d = f"M {pts[0][0]:.2f} {pts[0][1]:.2f}"
    for i in range(1, len(pts) - 1):
        mid_x = (pts[i][0] + pts[i + 1][0]) / 2
        mid_y = (pts[i][1] + pts[i + 1][1]) / 2
        path_d += f" Q {pts[i][0]:.2f} {pts[i][1]:.2f} {mid_x:.2f} {mid_y:.2f}"
    path_d += f" L {pts[-1][0]:.2f} {pts[-1][1]:.2f}"
    # Fill path (wave + bottom)
    fill_d = path_d + f" L {pts[-1][0]:.2f} {base_y:.2f} L {pts[0][0]:.2f} {base_y:.2f} Z"
    if theme == "student":
        fill_start = "rgba(255,183,3,.26)"
        fill_end = "rgba(255,92,122,.06)"
        stroke_color = "rgba(238,244,255,.78)"
        dot_ok = "rgba(255,183,3,.95)"
    else:
        fill_start = "rgba(78,168,255,.26)"
        fill_end = "rgba(124,92,255,.04)"
        stroke_color = "rgba(238,244,255,.78)"
        dot_ok = "rgba(78,168,255,.95)"
    dot_low = "rgba(255,92,122,.95)"
    t_y = base_y - (75 / 100) * usable_h
    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="100%" height="{height}" class="chart-svg" aria-label="Attendance chart">',
        "<defs>",
        f'<linearGradient id="chartFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="{fill_start}"/><stop offset="1" stop-color="{fill_end}"/></linearGradient>',
        "</defs>",
    ]
    for g in [25, 50, 75, 100]:
        y = base_y - (g / 100) * usable_h
        lines.append(f'<line x1="{pad}" y1="{y:.2f}" x2="{width - pad}" y2="{y:.2f}" stroke="rgba(255,255,255,.08)" stroke-width="1"/>')
    lines.append(f'<line x1="{pad}" y1="{t_y:.2f}" x2="{width - pad}" y2="{t_y:.2f}" stroke="rgba(255,204,102,.28)" stroke-width="1" stroke-dasharray="6 6"/>')
    lines.append(f'<path d="{fill_d}" fill="url(#chartFill)"/>')
    lines.append(f'<path d="{path_d}" fill="none" stroke="{stroke_color}" stroke-width="2.6"/>')
    for x, y, v in pts:
        col = dot_low if v < 75 else dot_ok
        lines.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3.4" fill="{col}" stroke="rgba(0,0,0,.35)" stroke-width="1"/>')
    lines.append("</svg>")
    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Auth
# -----------------------------------------------------------------------------
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def inner(*args, **kwargs):
            if "user_id" not in session:
                return redirect(url_for("index"))
            user = get_user_by_id(session["user_id"])
            if not user:
                session.clear()
                return redirect(url_for("index"))
            if role and user["role"] != role:
                if user["role"] == "student":
                    return redirect(url_for("student_dashboard"))
                return redirect(url_for("dashboard"))
            request.current_user = user
            return f(*args, **kwargs)
        return inner
    return decorator


def get_user_by_id(user_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, name, email, role, student_id FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    return dict(row) if row else None


def get_user_by_email(email):
    with get_db() as conn:
        row = conn.execute(
            "SELECT id, name, email, password, role, student_id FROM users WHERE LOWER(TRIM(email)) = ?",
            (email.strip().lower(),),
        ).fetchone()
    return dict(row) if row else None


# -----------------------------------------------------------------------------
# Data helpers
# -----------------------------------------------------------------------------
def get_all_students():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, name, class_name, roll, attendance, attendance_history FROM students ORDER BY class_name, roll"
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        if d.get("attendance_history"):
            try:
                d["attendance_history"] = json.loads(d["attendance_history"])
            except Exception:
                d["attendance_history"] = []
        else:
            d["attendance_history"] = []
        out.append(d)
    return out


def ensure_attendance_history(student):
    hist = student.get("attendance_history") or []
    if len(hist) >= 8:
        return student
    base = max(0, min(100, float(student.get("attendance") or 0)))
    prev = base
    for _ in range(12):
        drift = (random.random() - 0.5) * 8
        n = max(35, min(100, round(prev + drift)))
        hist.append(n)
        prev = n * 0.6 + base * 0.4
    student["attendance_history"] = hist
    with get_db() as conn:
        conn.execute(
            "UPDATE students SET attendance_history = ? WHERE id = ?",
            (json.dumps(hist), student["id"]),
        )
    return student


def get_tasks():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, title, student_id, status, created_at FROM tasks ORDER BY status, created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def get_complaints():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT id, student_id, title, category, message, status, reply, created_at, replied_at FROM complaints ORDER BY status, created_at DESC"
        ).fetchall()
    return [dict(r) for r in rows]


def seed_if_empty():
    with get_db() as conn:
        if conn.execute("SELECT 1 FROM students LIMIT 1").fetchone():
            return
    s1, s2, s3 = uid(), uid(), uid()
    hist = [92, 90, 91, 93, 92, 91, 92, 94, 93, 92, 91, 92]
    with get_db() as conn:
        conn.execute(
            "INSERT INTO students (id, name, class_name, roll, attendance, attendance_history) VALUES (?,?,?,?,?,?)",
            (s1, "Ayesha Khan", "10-A", "12", 92, json.dumps(hist)),
        )
        conn.execute(
            "INSERT INTO students (id, name, class_name, roll, attendance, attendance_history) VALUES (?,?,?,?,?,?)",
            (s2, "Hassan Ali", "10-A", "07", 68, json.dumps([68, 70, 67, 69, 68, 70, 66, 68, 69, 67, 68, 70])),
        )
        conn.execute(
            "INSERT INTO students (id, name, class_name, roll, attendance, attendance_history) VALUES (?,?,?,?,?,?)",
            (s3, "Maryam Noor", "9-B", "18", 74, json.dumps([74, 75, 73, 74, 76, 74, 73, 75, 74, 73, 74, 75])),
        )
        conn.execute(
            "INSERT INTO tasks (id, title, student_id, status, created_at) VALUES (?,?,?,?,?)",
            (uid(), "Submit Science assignment", s2, "Pending", int(__import__("time").time() * 1000)),
        )
        conn.execute(
            "INSERT INTO tasks (id, title, student_id, status, created_at) VALUES (?,?,?,?,?)",
            (uid(), "Bring parent signature", s3, "Pending", int(__import__("time").time() * 1000)),
        )


# -----------------------------------------------------------------------------
# Routes - Auth
# -----------------------------------------------------------------------------
@app.route("/")
def index():
    if "user_id" in session:
        user = get_user_by_id(session["user_id"])
        if user:
            if user["role"] == "student":
                return redirect(url_for("student_dashboard"))
            return redirect(url_for("dashboard"))
    return render_template("index.html", error=request.args.get("error"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = (request.form.get("password") or "").strip()
        user = get_user_by_email(email)
        if not user or user["password"] != password:
            return render_template("index.html", error="Invalid email or password.")
        session["user_id"] = user["id"]
        session["role"] = user["role"]
        if user["role"] == "student":
            return redirect(url_for("student_dashboard"))
        return redirect(url_for("dashboard"))
    return redirect(url_for("index"))


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        email = (request.form.get("email") or "").strip().lower()
        password = (request.form.get("password") or "").strip()
        if not name or not email or len(password) < 4:
            return render_template("signup.html", error="Name, email and password (min 4 chars) required.")
        if get_user_by_email(email):
            return render_template("signup.html", error="An account with this email already exists.")
        user_id = uid()
        with get_db() as conn:
            conn.execute(
                "INSERT INTO users (id, name, email, password, role) VALUES (?,?,?,?,?)",
                (user_id, name, email, password, "teacher"),
            )
        session["user_id"] = user_id
        session["role"] = "teacher"
        return redirect(url_for("dashboard"))
    return render_template("signup.html", error=request.args.get("error"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# -----------------------------------------------------------------------------
# Routes - Teacher dashboard
# -----------------------------------------------------------------------------
@app.route("/dashboard")
@login_required("teacher")
def dashboard():
    seed_if_empty()
    students = get_all_students()
    for s in students:
        ensure_attendance_history(s)
    students = get_all_students()
    tasks = get_tasks()
    complaints = get_complaints()
    pending_count = sum(1 for t in tasks if t["status"] != "Completed")
    low = [s for s in students if float(s.get("attendance") or 0) < 75]
    open_complaints = [c for c in complaints if c["status"] != "Replied"]
    # Attendance flow: average of all histories
    hist_len = 12
    series = [0.0] * hist_len
    with_hist = [s for s in students if s.get("attendance_history")]
    n = max(1, len(with_hist))
    for s in with_hist:
        for i in range(hist_len):
            series[i] += (s["attendance_history"][i] if i < len(s["attendance_history"]) else s.get("attendance")) or 0
    series = [round(x / n) for x in series]
    student_map = {s["id"]: s for s in students}
    attendance_chart_svg = render_attendance_chart_svg(series, width=600, height=260, theme="teacher")
    return render_template(
        "dashboard.html",
        students=students,
        tasks=tasks,
        complaints=complaints,
        student_map=student_map,
        student_count=len(students),
        pending_count=pending_count,
        low_count=len(low),
        open_complaint_count=len(open_complaints),
        attendance_chart_svg=attendance_chart_svg,
    )


@app.route("/dashboard/add_student", methods=["POST"])
@login_required("teacher")
def add_student():
    name = (request.form.get("s_name") or "").strip()
    class_name = (request.form.get("s_class") or "").strip()
    roll = (request.form.get("s_roll") or "").strip()
    try:
        att = float(request.form.get("s_att") or 0)
    except ValueError:
        att = 0
    att = max(0, min(100, att))
    if not name or not class_name or not roll:
        flash("Name, class and roll required.")
        return redirect(url_for("dashboard"))
    student_id = uid()
    hist = [att]
    prev = att
    for _ in range(11):
        prev = max(35, min(100, round(prev + (random.random() - 0.5) * 8)))
        hist.append(prev)
    with get_db() as conn:
        conn.execute(
            "INSERT INTO students (id, name, class_name, roll, attendance, attendance_history) VALUES (?,?,?,?,?,?)",
            (student_id, name, class_name, roll, att, json.dumps(hist)),
        )
    email = (request.form.get("s_email") or "").strip().lower()
    password = (request.form.get("s_pass") or "").strip()
    if email and len(password) >= 4:
        if not get_user_by_email(email):
            with get_db() as conn:
                conn.execute(
                    "INSERT INTO users (id, name, email, password, role, student_id) VALUES (?,?,?,?,?,?)",
                    (uid(), name, email, password, "student", student_id),
                )
        else:
            flash("Student login not created: email already in use.")
    return redirect(url_for("dashboard"))


@app.route("/dashboard/delete_student/<sid>", methods=["POST"])
@login_required("teacher")
def delete_student(sid):
    with get_db() as conn:
        conn.execute("DELETE FROM tasks WHERE student_id = ?", (sid,))
        conn.execute("DELETE FROM complaints WHERE student_id = ?", (sid,))
        conn.execute("DELETE FROM users WHERE student_id = ?", (sid,))
        conn.execute("DELETE FROM students WHERE id = ?", (sid,))
    return redirect(url_for("dashboard"))


@app.route("/dashboard/add_task", methods=["POST"])
@login_required("teacher")
def add_task():
    title = (request.form.get("t_title") or "").strip()
    student_id = (request.form.get("t_student") or "").strip()
    status = (request.form.get("t_status") or "Pending").strip()
    if not title or not student_id:
        flash("Title and student required.")
        return redirect(url_for("dashboard"))
    import time
    with get_db() as conn:
        conn.execute(
            "INSERT INTO tasks (id, title, student_id, status, created_at) VALUES (?,?,?,?,?)",
            (uid(), title, student_id, status, int(time.time() * 1000)),
        )
    return redirect(url_for("dashboard"))


@app.route("/dashboard/complete_task/<tid>", methods=["POST"])
@login_required("teacher")
def complete_task(tid):
    with get_db() as conn:
        conn.execute("UPDATE tasks SET status = 'Completed' WHERE id = ?", (tid,))
    return redirect(url_for("dashboard"))


@app.route("/dashboard/delete_task/<tid>", methods=["POST"])
@login_required("teacher")
def delete_task(tid):
    with get_db() as conn:
        conn.execute("DELETE FROM tasks WHERE id = ?", (tid,))
    return redirect(url_for("dashboard"))


@app.route("/dashboard/reply_complaint/<cid>", methods=["POST"])
@login_required("teacher")
def reply_complaint(cid):
    reply = (request.form.get("reply") or "").strip()
    if not reply:
        flash("Please enter a reply.")
        return redirect(url_for("dashboard"))
    import time
    with get_db() as conn:
        conn.execute(
            "UPDATE complaints SET status = 'Replied', reply = ?, replied_at = ? WHERE id = ?",
            (reply, int(time.time() * 1000), cid),
        )
    return redirect(url_for("dashboard"))


# -----------------------------------------------------------------------------
# Routes - Student dashboard
# -----------------------------------------------------------------------------
@app.route("/student")
@login_required("student")
def student_dashboard():
    user = request.current_user
    students = get_all_students()
    student = next((s for s in students if s["id"] == user.get("student_id")), None)
    if not student:
        return render_template("student.html", student=None, user=user, tasks=[], complaints=[], attendance_chart_svg="")
    ensure_attendance_history(student)
    student = next((s for s in get_all_students() if s["id"] == student["id"]), student)
    tasks = [t for t in get_tasks() if t["student_id"] == student["id"]]
    complaints = [c for c in get_complaints() if c["student_id"] == student["id"]]
    series = student.get("attendance_history") or [student.get("attendance"), student.get("attendance")]
    if len(series) < 2:
        series = [student.get("attendance"), student.get("attendance")]
    attendance_chart_svg = render_attendance_chart_svg(series, width=600, height=220, theme="student")
    return render_template(
        "student.html",
        student=student,
        user=user,
        tasks=tasks,
        complaints=complaints,
        attendance_chart_svg=attendance_chart_svg,
    )


@app.route("/student/complete_task/<tid>", methods=["POST"])
@login_required("student")
def student_complete_task(tid):
    with get_db() as conn:
        conn.execute("UPDATE tasks SET status = 'Completed' WHERE id = ?", (tid,))
    return redirect(url_for("student_dashboard"))


@app.route("/student/complaint", methods=["POST"])
@login_required("student")
def student_complaint():
    user = request.current_user
    student_id = user.get("student_id")
    if not student_id:
        flash("Your account is not linked to a student.")
        return redirect(url_for("student_dashboard"))
    title = (request.form.get("c_title") or "").strip()
    category = (request.form.get("c_category") or "Other").strip()
    message = (request.form.get("c_message") or "").strip()
    if not title or not message:
        flash("Title and details required.")
        return redirect(url_for("student_dashboard"))
    import time
    with get_db() as conn:
        conn.execute(
            "INSERT INTO complaints (id, student_id, title, category, message, status, created_at) VALUES (?,?,?,?,?,?,?)",
            (uid(), student_id, title, category, message, "Open", int(time.time() * 1000)),
        )
    return redirect(url_for("student_dashboard"))


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    init_db()
    import sys
    port = 5000
    host = "127.0.0.1"
    print("Mini School Management")
    print("Open in browser: http://{}:{}".format(host, port))
    print("Press CTRL+C to stop.")
    # use_reloader=False avoids process exit issues on Windows
    app.run(host=host, port=port, debug=True, use_reloader=False)
