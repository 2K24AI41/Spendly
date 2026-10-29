import sqlite3
from datetime import date
from pathlib import Path

from werkzeug.security import generate_password_hash

DB_PATH = Path(__file__).resolve().parent.parent / "expense_tracker.db"

EXPENSE_CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_db()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                name          TEXT NOT NULL,
                email         TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at    TEXT DEFAULT (datetime('now'))
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                amount      REAL NOT NULL,
                category    TEXT NOT NULL,
                date        TEXT NOT NULL,
                description TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def seed_db():
    conn = get_db()
    try:
        if conn.execute("SELECT 1 FROM users LIMIT 1").fetchone():
            return

        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            ("Demo User", "demo@spendly.com", generate_password_hash("demo123")),
        )
        user_id = cursor.lastrowid

        month = f"{date.today():%Y-%m}"
        samples = [
            (250.0, "Food", 1, "Groceries"),
            (120.0, "Transport", 3, "Metro card recharge"),
            (1800.0, "Bills", 5, "Electricity bill"),
            (600.0, "Health", 8, "Pharmacy"),
            (450.0, "Entertainment", 11, "Movie tickets"),
            (1500.0, "Shopping", 14, "New shoes"),
            (200.0, "Other", 17, "Miscellaneous"),
            (320.0, "Food", 20, "Dinner out"),
        ]
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            [
                (user_id, amount, category, f"{month}-{day:02d}", description)
                for amount, category, day, description in samples
            ],
        )
        conn.commit()
    finally:
        conn.close()


def get_user_by_email(email):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, name, email, password_hash, created_at"
            " FROM users WHERE email = ?",
            (email,),
        ).fetchone()
    finally:
        conn.close()


def get_user_by_id(user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, name, email, created_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


def _date_clause(date_from, date_to):
    sql, params = "", []
    if date_from:
        sql += " AND date >= ?"
        params.append(date_from)
    if date_to:
        sql += " AND date <= ?"
        params.append(date_to)
    return sql, params


def get_expense_summary(user_id, *, date_from=None, date_to=None):
    date_sql, date_params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        return conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count"
            " FROM expenses WHERE user_id = ?" + date_sql,
            (user_id, *date_params),
        ).fetchone()
    finally:
        conn.close()


def get_category_totals(user_id, *, date_from=None, date_to=None):
    date_sql, date_params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        return conn.execute(
            "SELECT category, SUM(amount) AS total FROM expenses"
            " WHERE user_id = ?" + date_sql +
            " GROUP BY category ORDER BY total DESC",
            (user_id, *date_params),
        ).fetchall()
    finally:
        conn.close()


def get_recent_expenses(user_id, limit=5, *, date_from=None, date_to=None):
    date_sql, date_params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, amount, category, date, description FROM expenses"
            " WHERE user_id = ?" + date_sql +
            " ORDER BY date DESC, id DESC LIMIT ?",
            (user_id, *date_params, limit),
        ).fetchall()
    finally:
        conn.close()


def create_user(name, email, password):
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def create_expense(user_id, amount, category, expense_date, description):
    conn = get_db()
    try:
        cursor = conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, round(float(amount), 2), category, expense_date,
             description),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_expense(expense_id, user_id):
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, amount, category, date, description FROM expenses"
            " WHERE id = ? AND user_id = ?",
            (expense_id, user_id),
        ).fetchone()
    finally:
        conn.close()


def update_expense(expense_id, user_id, amount, category, expense_date,
                   description):
    conn = get_db()
    try:
        cursor = conn.execute(
            "UPDATE expenses SET amount = ?, category = ?, date = ?,"
            " description = ? WHERE id = ? AND user_id = ?",
            (round(float(amount), 2), category, expense_date, description,
             expense_id, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


# ---- Filtered query helpers (transactions, summary, categories) ---- #

def get_expenses(user_id, date_from=None, date_to=None, category=None):
    date_sql, date_params = _date_clause(date_from, date_to)
    sql = ("SELECT id, amount, category, date, description FROM expenses"
           " WHERE user_id = ?" + date_sql)
    params = [user_id, *date_params]
    if category:
        sql += " AND category = ?"
        params.append(category)
    sql += " ORDER BY date DESC, id DESC"

    conn = get_db()
    try:
        return conn.execute(sql, params).fetchall()
    finally:
        conn.close()


def get_user_categories(user_id):
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT DISTINCT category FROM expenses"
            " WHERE user_id = ? ORDER BY category ASC",
            (user_id,),
        ).fetchall()
        return [row["category"] for row in rows]
    finally:
        conn.close()


def get_spending_stats(user_id, date_from=None, date_to=None):
    date_sql, date_params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        return conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total, COUNT(*) AS count,"
            " COALESCE(AVG(amount), 0) AS average,"
            " COALESCE(MAX(amount), 0) AS highest"
            " FROM expenses WHERE user_id = ?" + date_sql,
            (user_id, *date_params),
        ).fetchone()
    finally:
        conn.close()


def get_largest_expense(user_id, date_from=None, date_to=None):
    date_sql, date_params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        return conn.execute(
            "SELECT id, amount, category, date, description FROM expenses"
            " WHERE user_id = ?" + date_sql +
            " ORDER BY amount DESC, date DESC, id DESC LIMIT 1",
            (user_id, *date_params),
        ).fetchone()
    finally:
        conn.close()


def get_monthly_summary(user_id, date_from=None, date_to=None):
    date_sql, date_params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        return conn.execute(
            "SELECT substr(date, 1, 7) AS month, SUM(amount) AS total,"
            " COUNT(*) AS count, AVG(amount) AS average"
            " FROM expenses WHERE user_id = ?" + date_sql +
            " GROUP BY month ORDER BY month DESC",
            (user_id, *date_params),
        ).fetchall()
    finally:
        conn.close()


def get_category_breakdown(user_id, date_from=None, date_to=None):
    date_sql, date_params = _date_clause(date_from, date_to)
    conn = get_db()
    try:
        return conn.execute(
            "SELECT category, SUM(amount) AS total, COUNT(*) AS count,"
            " AVG(amount) AS average,"
            " SUM(amount) * 100.0 / SUM(SUM(amount)) OVER () AS share"
            " FROM expenses WHERE user_id = ?" + date_sql +
            " GROUP BY category ORDER BY total DESC, category ASC",
            (user_id, *date_params),
        ).fetchall()
    finally:
        conn.close()
