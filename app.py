import hmac
import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import NamedTuple

from flask import (
    Flask, abort, redirect, render_template, request, session, url_for,
)
from werkzeug.security import check_password_hash

from database.db import (
    EXPENSE_CATEGORIES,
    create_expense,
    create_user,
    delete_expense as remove_expense,
    get_category_breakdown,
    get_category_totals,
    get_expense,
    get_expense_summary,
    get_expenses,
    get_first_expense_date,
    get_largest_expense,
    get_monthly_summary,
    get_recent_expenses,
    get_spending_stats,
    get_top_expenses,
    get_user_by_email,
    get_user_by_id,
    get_user_categories,
    get_weekday_totals,
    init_db,
    seed_db,
    update_expense,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    if os.environ.get("FLASK_ENV") == "production":
        raise RuntimeError("SECRET_KEY must be set in production.")
    app.secret_key = "dev-secret-change-me"

app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024

MAX_AMOUNT = 10_000_000
MAX_AMOUNT_INPUT_LENGTH = 20
MAX_DESCRIPTION_LENGTH = 200
EXPENSE_FIELDS = ("amount", "category", "date", "description")

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


def validate_expense(amount, category, expense_date, description):
    """Return (cleaned_fields, None) on success or (None, error_message)."""
    if len(amount) > MAX_AMOUNT_INPUT_LENGTH:
        return None, "Please enter a valid amount."
    try:
        parsed_amount = Decimal(amount)
    except InvalidOperation:
        return None, "Please enter a valid amount."

    if not parsed_amount.is_finite() or parsed_amount <= 0:
        return None, "Amount must be greater than zero."
    if parsed_amount.as_tuple().exponent < -2:
        return None, "Amount can have at most 2 decimal places."
    if parsed_amount > MAX_AMOUNT:
        return None, f"Amount must not exceed {format_inr(MAX_AMOUNT)}."

    if category not in EXPENSE_CATEGORIES:
        return None, "Please choose a category."

    try:
        parsed_date = datetime.strptime(expense_date, "%Y-%m-%d").date()
    except ValueError:
        return None, "Please enter a valid date."

    if len(description) > MAX_DESCRIPTION_LENGTH:
        return None, (f"Description must be {MAX_DESCRIPTION_LENGTH}"
                      " characters or fewer.")

    return {
        "amount": parsed_amount,
        "category": category,
        "expense_date": parsed_date.isoformat(),
        "description": description or None,
    }, None


def read_expense_form(source):
    return {key: source.get(key, "").strip() for key in EXPENSE_FIELDS}


def expense_to_form(expense):
    return {
        # <input type="number"> needs a plain decimal string, e.g. "250.00".
        "amount": f"{float(expense['amount']):.2f}",
        "category": expense["category"],
        "date": expense["date"],
        "description": expense["description"] or "",
    }


def get_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_hex(16)
        session["csrf_token"] = token
    return token


def csrf_token_is_valid():
    expected = session.get("csrf_token", "")
    submitted = request.form.get("csrf_token", "")
    return bool(expected) and hmac.compare_digest(
        submitted.encode(), expected.encode())


@app.context_processor
def inject_csrf_token():
    return {"csrf_token": get_csrf_token}


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
            # Normalise: strptime also accepts "2026-1-1", but SQL string
            # comparison and date.fromisoformat need canonical YYYY-MM-DD.
            dates.append(
                datetime.strptime(value, "%Y-%m-%d").date().isoformat())
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


# ---- Analytics helpers ---- #

WEEKDAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday",
                 "Friday", "Saturday", "Sunday")
TREND_MONTHS = 12
TOP_EXPENSES_LIMIT = 5


class AnalyticsRange(NamedTuple):
    date_from: str | None
    date_to: str | None
    error: str | None
    all_time: bool


def build_analytics_presets(today=None):
    """Presets for _date_filter.html with "All time" as ("", "").

    A plain /analytics means "last 30 days", so "All time" needs its own
    URL. url_for drops None query args but keeps "", so blank values give
    the All-time preset the link /analytics?from=&to=, and the partial's
    `preset_from == date_from` check still highlights it.
    """
    return [(label, start or "", end or "")
            for label, start, end in build_date_presets(today)]


def resolve_analytics_range(args, today=None):
    """Work out the range for /analytics.

    No from/to keys -> last 30 days. Keys present but blank -> all time.
    Invalid or reversed input -> last 30 days plus the parse error.
    """
    today = today or date.today()
    date_from, date_to, error = parse_date_range(args)
    if date_from or date_to:
        return AnalyticsRange(date_from, date_to, error, False)
    if ("from" in args or "to" in args) and error is None:
        return AnalyticsRange(None, None, None, True)
    return AnalyticsRange((today - timedelta(days=29)).isoformat(),
                          today.isoformat(), error, False)


def period_bounds(date_from, date_to, first_expense_date, today):
    """Fill missing bounds so the period has a definite length.

    A missing `to` means today and a missing `from` means the first expense.
    Both are clamped so start <= end even when `from` is in the future or
    the first expense is dated after today, keeping the length >= 1 day.
    """
    end = date.fromisoformat(date_to) if date_to else today
    if date_from:
        start = date.fromisoformat(date_from)
    elif first_expense_date:
        start = min(date.fromisoformat(first_expense_date), end)
    else:
        start = end
    if not date_to:
        end = max(end, start)
    return start, end


def day_count(start, end):
    return (end - start).days + 1


def previous_period(start, days):
    """The `days` days just before `start`, or None if before year 1."""
    try:
        return ((start - timedelta(days=days)).isoformat(),
                (start - timedelta(days=1)).isoformat())
    except OverflowError:
        return None


def compare_totals(current, previous):
    """Change from the previous period, with display-ready sign and label."""
    diff = round(current - previous, 2)
    pct = None if previous <= 0 else round(abs(diff) * 100 / previous, 1)
    if diff > 0:
        direction, sign = "up", "+"
    elif diff < 0:
        direction, sign = "down", "−"
    else:
        direction, sign = "same", ""

    if pct is None:
        label = "No spending in previous period"
    elif direction == "up":
        label = f"▲ {pct:.1f}% more"
    elif direction == "down":
        label = f"▼ {pct:.1f}% less"
    else:
        label = "No change"
    return {"current": current, "previous": previous, "diff_abs": abs(diff),
            "pct": pct, "direction": direction, "sign": sign, "label": label}


def bar_percent(value, max_value):
    if not max_value or max_value <= 0:
        return 0.0
    return round(value * 100 / max_value, 1)


def build_weekday_rows(rows):
    """Monday-first, zero-filled; SQLite %w numbers Sunday as 0."""
    by_day = {row["weekday"]: row for row in rows}
    result = []
    for index, name in enumerate(WEEKDAY_NAMES):
        row = by_day.get((index + 1) % 7)
        result.append({
            "name": name,
            "total": row["total"] if row else 0.0,
            "count": row["count"] if row else 0,
        })
    max_total = max(row["total"] for row in result)
    for row in result:
        row["bar"] = bar_percent(row["total"], max_total)
    return result


def busiest_weekday(weekday_rows):
    busiest = max(weekday_rows, key=lambda row: row["total"])
    return busiest if busiest["total"] > 0 else None


def build_trend_rows(months, limit=TREND_MONTHS):
    """Chart rows, oldest first.

    `months` must be newest first, as get_monthly_summary returns it, so
    the first `limit` rows are the latest months.
    """
    latest = list(months)[:limit][::-1]
    max_total = max((row["total"] for row in latest), default=0)
    return [
        {"month": row["month"], "total": row["total"], "count": row["count"],
         "bar": bar_percent(row["total"], max_total)}
        for row in latest
    ]


def build_comparison(user_id, start, days, current_total):
    period = previous_period(start, days)
    if period is None:
        return None
    prev_from, prev_to = period
    previous = get_spending_stats(user_id, prev_from, prev_to)
    comparison = compare_totals(current_total, previous["total"])
    comparison.update(prev_from=prev_from, prev_to=prev_to)
    return comparison


def build_analytics_context(user_id, args, today):
    """Everything analytics.html needs, apart from the user.

    range_from/range_to are the bounds applied to the queries (None means
    open-ended). date_from/date_to are what the filter form shows: "" in
    all-time mode so the All-time preset is highlighted.
    """
    selected = resolve_analytics_range(args, today)
    range_from, range_to = selected.date_from, selected.date_to
    stats = get_spending_stats(user_id, range_from, range_to)
    start, end = period_bounds(
        range_from, range_to, get_first_expense_date(user_id), today)
    days = day_count(start, end)
    breakdown = get_category_breakdown(user_id, range_from, range_to)
    weekdays = build_weekday_rows(
        get_weekday_totals(user_id, range_from, range_to))
    return {
        "stats": stats,
        "days": days,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "daily_average": round(stats["total"] / days, 2),
        "all_time": selected.all_time,
        "comparison": (None if selected.all_time else
                       build_comparison(user_id, start, days, stats["total"])),
        "top_category": breakdown[0] if breakdown else None,
        "trend": build_trend_rows(
            get_monthly_summary(user_id, range_from, range_to)),
        "weekdays": weekdays,
        "busiest": busiest_weekday(weekdays),
        "top_expenses": get_top_expenses(
            user_id, range_from, range_to, limit=TOP_EXPENSES_LIMIT),
        "range_from": range_from,
        "range_to": range_to,
        "date_from": "" if selected.all_time else range_from,
        "date_to": "" if selected.all_time else range_to,
        "error": selected.error,
        "presets": build_analytics_presets(today),
    }


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

    context = build_analytics_context(user["id"], request.args, date.today())
    return render_template("analytics.html", user=user, **context)


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    form = {"date": date.today().isoformat()}
    error = None
    if request.method == "POST":
        if not csrf_token_is_valid():
            abort(400)
        form = read_expense_form(request.form)
        cleaned, error = validate_expense(
            form["amount"], form["category"], form["date"],
            form["description"])
        if error is None:
            create_expense(user["id"], **cleaned)
            return redirect(url_for("profile_transactions"))

    return render_template(
        "add_expense.html",
        categories=EXPENSE_CATEGORIES,
        form=form,
        error=error,
    )


@app.route("/expenses/<int:expense_id>/edit", methods=["GET", "POST"])
def edit_expense(expense_id):
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    expense = get_expense(expense_id, user["id"])
    if expense is None:
        abort(404)

    error = None
    if request.method == "POST":
        if not csrf_token_is_valid():
            abort(400)
        form = read_expense_form(request.form)
        cleaned, error = validate_expense(
            form["amount"], form["category"], form["date"],
            form["description"])
        if error is None:
            # No row matched only if it was deleted since the lookup above.
            if not update_expense(expense_id, user["id"], **cleaned):
                abort(404)
            return redirect(url_for("profile_transactions"))
    else:
        form = expense_to_form(expense)

    return render_template(
        "edit_expense.html",
        categories=EXPENSE_CATEGORIES,
        form=form,
        error=error,
        expense_id=expense_id,
    )


@app.route("/expenses/<int:expense_id>/delete", methods=["GET", "POST"])
def delete_expense(expense_id):
    user = get_current_user()
    if user is None:
        return redirect(url_for("login"))

    expense = get_expense(expense_id, user["id"])
    if expense is None:
        abort(404)

    if request.method == "POST":
        if not csrf_token_is_valid():
            abort(400)
        # No row matched only if it was deleted since the lookup above.
        if not remove_expense(expense_id, user["id"]):
            abort(404)
        return redirect(url_for("profile_transactions"))

    return render_template(
        "delete_expense.html",
        expense=expense,
        expense_id=expense_id,
    )


ERROR_PAGES = {
    400: ("Bad request",
          "Something was wrong with that request. "
          "Please go back and try again."),
    404: ("Page not found",
          "We could not find what you were looking for. "
          "It may have moved or never existed."),
    405: ("Method not allowed",
          "That action is not available for this page."),
    413: ("Request too large",
          "What you sent was too large. Please shorten it and try again."),
    500: ("Something went wrong",
          "An unexpected error occurred on our side. "
          "Please try again in a moment."),
}


def render_error(error):
    code = getattr(error, "code", None)
    if code not in ERROR_PAGES:
        code = 500
    title, message = ERROR_PAGES[code]

    # Session only, no DB lookup: the fault may be DB-related.
    try:
        signed_in = bool(session.get("user_id"))
    except Exception:
        signed_in = False

    if signed_in:
        back_url = url_for("profile_transactions")
        back_label = "Back to transactions"
    else:
        back_url = url_for("landing")
        back_label = "Back to home"

    return render_template(
        "error.html",
        code=code,
        title=title,
        message=message,
        back_url=back_url,
        back_label=back_label,
    ), code


for _code in ERROR_PAGES:
    app.register_error_handler(_code, render_error)


if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG", "1") == "1", port=5001)
