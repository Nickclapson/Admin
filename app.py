from __future__ import annotations

import datetime as dt
import html
import sqlite3
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).parent
DB_PATH = ROOT / "tasks.db"

STATUSES = [
    "planned",
    "doing",
    "to_review",
    "reviewing",
    "published",
]


def init_db() -> None:
    DB_PATH.touch(exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client TEXT NOT NULL,
                title TEXT NOT NULL,
                planned_month TEXT NOT NULL,
                scheduled_date TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                published_month TEXT
            )
            """
        )


def fetch_tasks() -> list[sqlite3.Row]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, client, title, planned_month, scheduled_date, status, created_at, published_month
            FROM tasks
            ORDER BY planned_month DESC, created_at DESC
            """
        ).fetchall()
    return rows


def fetch_billing(month: str) -> list[sqlite3.Row]:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, client, title, planned_month, scheduled_date, status, created_at, published_month
            FROM tasks
            WHERE published_month = ?
            ORDER BY created_at DESC
            """,
            (month,),
        ).fetchall()
    return rows


def insert_task(client: str, title: str, planned_month: str, scheduled_date: str | None) -> None:
    created_at = dt.datetime.utcnow().isoformat()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO tasks (client, title, planned_month, scheduled_date, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (client, title, planned_month, scheduled_date, "planned", created_at),
        )


def update_status(task_id: int, new_status: str) -> None:
    if new_status not in STATUSES:
        return
    published_month = None
    if new_status == "published":
        published_month = dt.date.today().strftime("%Y-%m")
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE tasks
            SET status = ?, published_month = COALESCE(?, published_month)
            WHERE id = ?
            """,
            (new_status, published_month, task_id),
        )


class TaskHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/":
            return self.render_index()
        if parsed.path == "/billing":
            return self.render_billing(parsed)
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path == "/tasks/create":
            return self.handle_create()
        if parsed.path == "/tasks/status":
            return self.handle_status()
        self.send_error(404, "Not Found")

    def render_index(self):
        tasks = fetch_tasks()
        grouped = {}
        for row in tasks:
            grouped.setdefault(row["planned_month"], []).append(row)
        body = self.render_header("Task planner")
        body += self.render_nav()
        body += self.render_create_form()
        if not tasks:
            body += "<p class='muted'>No tasks yet. Add one using the form above.</p>"
        for month, items in sorted(grouped.items(), reverse=True):
            body += f"<section class='card'><h2>Planned for {html.escape(month)}</h2>"
            body += "<ul class='task-list'>"
            for row in items:
                body += self.render_task_row(row)
            body += "</ul></section>"
        body += self.render_footer()
        self.respond_html(body)

    def render_billing(self, parsed):
        params = parse_qs(parsed.query)
        current_month = dt.date.today().strftime("%Y-%m")
        month = params.get("month", [current_month])[0]
        rows = fetch_billing(month)
        body = self.render_header("Billing")
        body += self.render_nav()
        body += "<section class='card'>"
        body += "<h2>Billing month</h2>"
        body += "<form class='inline' method='get'>"
        body += f"<label for='month'>Month (YYYY-MM)</label><input type='month' name='month' id='month' value='{html.escape(month)}'>"
        body += "<button type='submit'>Filter</button></form>"
        if rows:
            body += "<ul class='task-list'>"
            for row in rows:
                body += self.render_task_row(row, include_status=False)
            body += "</ul>"
        else:
            body += "<p class='muted'>No published tasks in this month yet.</p>"
        body += "</section>"
        body += self.render_footer()
        self.respond_html(body)

    def handle_create(self):
        data = self.read_form()
        client = data.get("client", [""])[0].strip()
        title = data.get("title", [""])[0].strip()
        planned_month = data.get("planned_month", [""])[0].strip()
        scheduled_date = data.get("scheduled_date", [""])[0].strip() or None
        if client and title and planned_month:
            insert_task(client, title, planned_month, scheduled_date)
        self.redirect("/")

    def handle_status(self):
        data = self.read_form()
        task_id = data.get("task_id", [None])[0]
        status = data.get("new_status", [None])[0]
        try:
            task_id_int = int(task_id) if task_id is not None else None
        except ValueError:
            task_id_int = None
        if task_id_int is not None and status:
            update_status(task_id_int, status)
        self.redirect("/")

    def render_task_row(self, row: sqlite3.Row, include_status: bool = True) -> str:
        status_display = html.escape(row["status"]).replace("_", " ")
        meta = [f"Client: {html.escape(row['client'])}"]
        if row["scheduled_date"]:
            meta.append(f"Scheduled: {html.escape(row['scheduled_date'])}")
        meta.append(f"Planned: {html.escape(row['planned_month'])}")
        meta_html = " • ".join(meta)
        body = "<li class='task'>"
        body += f"<div><h3>{html.escape(row['title'])}</h3><p class='meta'>{meta_html}</p></div>"
        if include_status:
            body += f"<span class='status pill {html.escape(row['status'])}'>{status_display}</span>"
            body += "<form class='inline' method='post' action='/tasks/status'>"
            body += f"<input type='hidden' name='task_id' value='{row['id']}'>"
            body += "<label for='new_status'>Move to</label><select name='new_status'>"
            for s in STATUSES:
                selected = " selected" if s == row["status"] else ""
                body += f"<option value='{s}'{selected}>{s.replace('_', ' ')}</option>"
            body += "</select><button type='submit'>Update</button></form>"
        body += "</li>"
        return body

    def render_header(self, title: str) -> str:
        return (
            "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            f"<title>{html.escape(title)}</title>"
            "<link rel='stylesheet' href='/static/style.css'></head><body>"
            f"<header><h1>{html.escape(title)}</h1></header>"
        )

    def render_nav(self) -> str:
        return "<nav class='nav'><a href='/'>Tasks</a><a href='/billing'>Billing</a></nav>"

    def render_create_form(self) -> str:
        today = dt.date.today()
        default_month = today.strftime("%Y-%m")
        return (
            "<section class='card'><h2>Add a task</h2>"
            "<form method='post' action='/tasks/create' class='grid'>"
            "<label for='client'>Client</label><input required name='client' id='client' placeholder='Client name'>"
            "<label for='title'>Task</label><input required name='title' id='title' placeholder='Describe the work'>"
            f"<label for='planned_month'>Planned month</label><input required type='month' name='planned_month' id='planned_month' value='{default_month}'>"
            f"<label for='scheduled_date'>Scheduled date</label><input type='date' name='scheduled_date' id='scheduled_date' min='{default_month}-01'>"
            "<button type='submit'>Save task</button>"
            "</form></section>"
        )

    def render_footer(self) -> str:
        year = dt.date.today().year
        return f"<footer><p>Client task manager · {year}</p></footer></body></html>"

    def read_form(self) -> dict[str, list[str]]:
        length = int(self.headers.get("Content-Length", 0))
        payload = self.rfile.read(length).decode("utf-8")
        return parse_qs(payload)

    def respond_html(self, body: str):
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def redirect(self, location: str):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()


if __name__ == "__main__":
    init_db()
    server = HTTPServer(("0.0.0.0", 5000), TaskHandler)
    print("Server running at http://0.0.0.0:5000")
    server.serve_forever()
