import os
import sqlite3
from datetime import date, datetime, timedelta

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (
    create_user,
    get_category_breakdown,
    get_category_totals,
    get_expense_summary,
    get_expenses,
    get_largest_expense,
    get_monthly_summary,
    get_recent_expenses,
    get_spending_stats,
    get_user_by_email,
    get_user_by_id,
    get_user_categories,
    init_db,
    seed_db,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    if os.environ.get("FLASK_ENV") == "production":
        raise RuntimeError("SECRET_KEY must be set in production.")
    app.secret_key = "dev-secret-change-me"

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def validate_registration(name, email, password, confirm_password):
    if not name or not email or not password or not confirm_password:
        return "All fields are required."

    local, sep, domain = email.rpartition("@")
    if (not sep or not local or "." not in domain
            or domain.startswith(".") or domain.endswith(".")):
        return "Please enter a valid email address."

    if len(password) < 8:
        return "Password must be at least 8 characters."

    if password != confirm_password:
        return "Passwords do not match."

    return None


@app.template_filter("inr")
def format_inr(amount):
    return f"₹{amount:,.2f}"


@app.template_filter("month_year")
def format_month_year(timestamp):
    return datetime.strptime(timestamp[:10], "%Y-%m-%d").strftime("%B %Y")


@app.template_filter("short_date")
def format_short_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d %b %Y")
    except (TypeError, ValueError):
        return value


@app.template_filter("month_label")
def format_month_label(value):
    return datetime.strptime(value, "%Y-%m").strftime("%B %Y")


def authenticate(email, password):
    user = get_user_by_email(email)
    if user and check_password_hash(user["password_hash"], password):
        return user
    return None


def get_current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None

    user = get_user_by_id(user_id)
    if not user:
        session.clear()
    return user


def parse_date_range(args):
    error = None
    dates = []
    for key in ("from", "to"):
        value = args.get(key, "").strip()
        if not value:
            dates.append(None)
            continue
        try:
            datetime.strptime(value, "%Y-%m-%d")
            dates.append(value)
        except ValueError:
            dates.append(None)
            error = "Invalid date ignored."

    date_from, date_to = dates
    if date_from and date_to and date_from > date_to:
        return None, None, "Start date must be on or before end date."
    return date_from, date_to, error


def build_date_presets(today=None):
    today = today or date.today()
    end = today.isoformat()
    return [
        ("This month", today.replace(day=1).isoformat(), end),
        ("Last 30 days", (today - timedelta(days=29)).isoformat(), end),
        ("This year", today.replace(month=1, day=1).isoformat(), end),
        ("All time", None, None),
    ]


# ------------------------------------------------------------------ #
# Routes                                                            #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")
    confirm_password = request.form.get("confirm_password", "")

    error = validate_registration(name, email, password, confirm_password)
    if not error and get_user_by_email(email):
        error = "An account with this email already exists."
    if not error:
        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            error = "An account with this email already exists."

    if error:
        return render_template("register.html", error=error,
                               name=name, email=email)
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = None
    if not email or not password:
        error = "Email and password are required."
    else:
        user = authenticate(email, password)
        error = None if user else "Invalid email or password."

    if error:
        return render_template("login.html", error=error, email=email)

    session.clear()
    session["user_id"] = user["id"]
    session["user_name"] = user["name"]
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


@app.route("/profile")
def profile():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    date_from, date_to, error = parse_date_range(request.args)
    user_id = user["id"]
    return render_template(
        "profile.html",
        user=user,
        summary=get_expense_summary(
            user_id, date_from=date_from, date_to=date_to),
        category_totals=get_category_totals(
            user_id, date_from=date_from, date_to=date_to),
        recent_expenses=get_recent_expenses(
            user_id, date_from=date_from, date_to=date_to),
        date_from=date_from,
        date_to=date_to,
        error=error,
        presets=build_date_presets(),
    )


# >>> Subagent 01: transaction history routes >>>
@app.route("/profile/transactions")
def profile_transactions():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    date_from, date_to, error = parse_date_range(request.args)
    category = request.args.get("category", "").strip() or None
    categories = get_user_categories(user["id"])
    if category and category not in categories:
        category = None
        category_error = "Unknown category — showing all categories."
        error = f"{error} {category_error}" if error else category_error

    return render_template(
        "transactions.html",
        user=user,
        expenses=get_expenses(user["id"], date_from, date_to, category),
        categories=categories,
        selected_category=category,
        date_from=date_from,
        date_to=date_to,
        error=error,
    )
# <<< end Subagent 01 <<<


# >>> Subagent 02: summary stats routes >>>
@app.route("/profile/summary")
def profile_summary():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    date_from, date_to, error = parse_date_range(request.args)
    user_id = user["id"]
    return render_template(
        "summary.html",
        user=user,
        stats=get_spending_stats(user_id, date_from, date_to),
        largest=get_largest_expense(user_id, date_from, date_to),
        months=get_monthly_summary(user_id, date_from, date_to),
        date_from=date_from,
        date_to=date_to,
        error=error,
    )
# <<< end Subagent 02 <<<


# >>> Subagent 03: category breakdown routes >>>
@app.route("/profile/categories")
def profile_categories():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    date_from, date_to, error = parse_date_range(request.args)
    return render_template(
        "categories.html",
        user=user,
        breakdown=get_category_breakdown(user["id"], date_from, date_to),
        stats=get_spending_stats(user["id"], date_from, date_to),
        date_from=date_from,
        date_to=date_to,
        error=error,
    )
# <<< end Subagent 03 <<<


@app.route("/analytics")
def analytics():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))
    return render_template("analytics.html", user=user)


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1", port=5001)
