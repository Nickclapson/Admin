from __future__ import annotations

import datetime as dt
from dateutil.relativedelta import relativedelta
from flask import Flask, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///tasks.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

STATUSES = [
    ("planned", "Planned"),
    ("doing", "Doing"),
    ("to_review", "To review"),
    ("reviewing", "Reviewing"),
    ("published", "Published"),
]


class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client = db.Column(db.String(120), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="planned")
    planned_month = db.Column(db.String(7), nullable=False)  # YYYY-MM
    scheduled_for = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)

    def mark_completed_if_needed(self) -> None:
        if self.status == "published" and self.completed_at is None:
            self.completed_at = dt.datetime.utcnow()
        elif self.status != "published":
            self.completed_at = None


@app.before_request
def create_tables() -> None:
    db.create_all()


def month_options(base: dt.date | None = None) -> list[str]:
    today = base or dt.date.today()
    months = []
    for delta in range(-2, 4):
        month_date = today + relativedelta(months=delta)
        months.append(month_date.strftime("%Y-%m"))
    return months


def parse_month(value: str | None) -> str:
    if not value:
        return dt.date.today().strftime("%Y-%m")
    try:
        dt.datetime.strptime(value, "%Y-%m")
    except ValueError:
        return dt.date.today().strftime("%Y-%m")
    return value


def month_label(value: str) -> str:
    return dt.datetime.strptime(value, "%Y-%m").strftime("%B %Y")


@app.route("/")
def index():
    month = parse_month(request.args.get("month"))
    tasks = Task.query.filter_by(planned_month=month).order_by(Task.created_at.desc()).all()
    return render_template(
        "index.html",
        tasks=tasks,
        month=month,
        month_label=month_label(month),
        month_options=month_options(),
        statuses=STATUSES,
    )


@app.route("/tasks", methods=["POST"])
def create_task():
    planned_month = parse_month(request.form.get("planned_month"))
    task = Task(
        client=request.form["client"],
        title=request.form["title"],
        description=request.form.get("description"),
        status=request.form.get("status", "planned"),
        planned_month=planned_month,
    )

    scheduled_value = request.form.get("scheduled_for")
    if scheduled_value:
        task.scheduled_for = dt.datetime.strptime(scheduled_value, "%Y-%m-%d").date()

    task.mark_completed_if_needed()
    db.session.add(task)
    db.session.commit()
    return redirect(url_for("index", month=planned_month))


@app.route("/tasks/<int:task_id>/status", methods=["POST"])
def update_status(task_id: int):
    task = Task.query.get_or_404(task_id)
    task.status = request.form["status"]
    task.mark_completed_if_needed()
    db.session.commit()
    return redirect(url_for("index", month=task.planned_month))


@app.route("/billing")
def billing():
    month = parse_month(request.args.get("month"))
    month_start = dt.datetime.strptime(month, "%Y-%m")
    month_end = month_start + relativedelta(months=1)
    tasks = (
        Task.query.filter(Task.completed_at >= month_start, Task.completed_at < month_end)
        .order_by(Task.completed_at.desc())
        .all()
    )
    return render_template(
        "billing.html",
        tasks=tasks,
        month=month,
        month_label=month_label(month),
        month_options=month_options(),
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
