"""Spec tests for step 11 — Advanced Analytics (GET /analytics).

Seed rows are dated days 1–20 of the *current* month, so most can be in the
future. Page tests therefore use a fresh user, fixed past dates and explicit
?from=&to=; only the default-range test is relative to today.
tests/test_analytics.py keeps the auth, navbar and CSS checks.
"""
import re
from datetime import date, timedelta

import pytest

import database.db as db
from app import (
    bar_percent,
    build_trend_rows,
    build_weekday_rows,
    busiest_weekday,
    compare_totals,
    day_count,
    period_bounds,
    previous_period,
    resolve_analytics_range,
)
from tests.conftest import add_expense_row, login, register_user

TODAY = date(2026, 11, 1)
INVALID_MSG = "Invalid date ignored."
REVERSED_MSG = "Start date must be on or before end date."
WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday",
        "Friday", "Saturday", "Sunday"]
# seed_db() adds 8 demo expenses on days 1–20 of the current month.
SEED_TOTAL = 250 + 120 + 1800 + 600 + 450 + 1500 + 200 + 320


def inr(amount):
    return f"₹{amount:,.2f}"


def fresh_user(client, email="analyst@example.com"):
    register_user(client, email=email)
    user_id = db.get_user_by_email(email)["id"]
    login(client, email, "password123")
    return user_id


def page(client, query=""):
    resp = client.get("/analytics" + query)
    assert resp.status_code == 200
    return resp.get_data(as_text=True)


def stat_for(html, label):
    """The value of the stat tile with this label, or None if absent."""
    match = re.search(
        r'stat-label">' + re.escape(label) +
        r'</span>\s*<span class="stat-value">\s*([^<]+?)\s*<', html)
    return match.group(1) if match else None


# ------------------------------------------------------------------ #
# Pure helpers                                                        #
# ------------------------------------------------------------------ #

def test_resolve_range_defaults_to_last_30_days():
    assert resolve_analytics_range({}, TODAY) == (
        "2026-10-03", "2026-11-01", None, False)


def test_resolve_range_blank_keys_mean_all_time():
    selected = resolve_analytics_range({"from": "", "to": ""}, TODAY)
    assert selected.all_time is True
    assert (selected.date_from, selected.date_to) == (None, None)


def test_resolve_range_invalid_date_falls_back_to_default():
    selected = resolve_analytics_range({"from": "2026-13-01"}, TODAY)
    assert (selected.date_from, selected.date_to) == (
        "2026-10-03", "2026-11-01")
    assert selected.error == INVALID_MSG
    assert selected.all_time is False


def test_resolve_range_reversed_falls_back_to_default():
    selected = resolve_analytics_range(
        {"from": "2020-02-01", "to": "2020-01-01"}, TODAY)
    assert (selected.date_from, selected.date_to) == (
        "2026-10-03", "2026-11-01")
    assert selected.error == REVERSED_MSG
    assert selected.all_time is False


def test_resolve_range_keeps_one_sided_bound():
    assert resolve_analytics_range({"from": "2020-01-05"}, TODAY) == (
        "2020-01-05", None, None, False)


def test_resolve_range_normalises_unpadded_dates():
    selected = resolve_analytics_range(
        {"from": "2020-1-5", "to": "2020-2-1"}, TODAY)
    assert (selected.date_from, selected.date_to) == (
        "2020-01-05", "2020-02-01")
    assert selected.error is None


@pytest.mark.parametrize("date_from, date_to, first, expected_days", [
    ("2026-10-02", None, None, 31),            # from-only → end is today
    (None, "2026-10-31", "2026-10-01", 31),    # to-only → start is first
    (None, None, None, 1),                     # no expenses at all
    (None, None, "2026-11-20", 1),             # first expense after today
    (None, None, "2026-10-01", 32),            # all time
    ("2026-12-01", None, None, 1),             # from-only in the future
])
def test_period_bounds_and_day_count(date_from, date_to, first,
                                     expected_days):
    start, end = period_bounds(date_from, date_to, first, TODAY)
    assert start <= end
    assert day_count(start, end) == expected_days


def test_previous_period_crosses_leap_day():
    assert previous_period(date(2020, 3, 1), 30) == (
        "2020-01-31", "2020-02-29")


def test_previous_period_before_year_one_is_none():
    assert previous_period(date(1, 1, 1), 10) is None


def test_compare_totals_up():
    result = compare_totals(1500, 700)
    assert result["direction"] == "up"
    assert result["diff_abs"] == 800
    assert result["pct"] == 114.3
    assert result["sign"] == "+"
    assert result["label"] == "▲ 114.3% more"


def test_compare_totals_down():
    result = compare_totals(500, 1000)
    assert result["direction"] == "down"
    assert result["pct"] == 50.0
    assert result["sign"] == "−"
    assert result["label"] == "▼ 50.0% less"


def test_compare_totals_same():
    result = compare_totals(400, 400)
    assert result["direction"] == "same"
    assert result["sign"] == ""
    assert result["label"] == "No change"


def test_compare_totals_previous_zero_has_no_percent():
    assert compare_totals(100, 0)["pct"] is None
    result = compare_totals(0, 0)
    assert result["pct"] is None
    assert result["direction"] == "same"
    assert result["label"] == "No spending in previous period"


def test_bar_percent_handles_zero_max():
    assert bar_percent(0, 0) == 0.0
    assert bar_percent(5, 10) == 50.0


def test_weekday_rows_are_monday_first_and_zero_filled():
    rows = build_weekday_rows([{"weekday": 0, "total": 90.0, "count": 2}])
    assert [row["name"] for row in rows] == WEEK
    assert rows[-1] == {"name": "Sunday", "total": 90.0, "count": 2,
                        "bar": 100.0}
    assert all(row["total"] == 0 and row["bar"] == 0.0 for row in rows[:-1])
    assert busiest_weekday(rows)["name"] == "Sunday"


def test_busiest_weekday_is_none_without_spending():
    assert busiest_weekday(build_weekday_rows([])) is None


def test_trend_rows_cap_at_12_oldest_first():
    months = [{"month": f"2020-{m:02d}", "total": float(m), "count": 1}
              for m in range(1, 13)]
    months += [{"month": "2021-01", "total": 50.0, "count": 1},
               {"month": "2021-02", "total": 1.0, "count": 1}]
    months.reverse()                           # DB returns newest first
    rows = build_trend_rows(months)
    assert len(rows) == 12
    assert rows[0]["month"] == "2020-03"
    assert rows[-1]["month"] == "2021-02"
    assert max(row["bar"] for row in rows) == 100.0


# ------------------------------------------------------------------ #
# Page                                                                #
# ------------------------------------------------------------------ #

def test_default_range_is_last_30_days_with_comparison(client):
    today = date.today()
    user_id = fresh_user(client)
    add_expense_row(user_id, 1000, "Food", today.isoformat(), "Today")
    add_expense_row(user_id, 500, "Bills",
                    (today - timedelta(days=29)).isoformat(), "Edge")
    add_expense_row(user_id, 700, "Food",
                    (today - timedelta(days=30)).isoformat(), "Previous")
    add_expense_row(user_id, 9999, "Food",
                    (today - timedelta(days=60)).isoformat(), "Too old")

    html = page(client)
    assert f'value="{(today - timedelta(days=29)).isoformat()}"' in html
    assert f'value="{today.isoformat()}"' in html
    assert re.search(r'class="filter-preset active">\s*Last 30 days\s*<',
                     html)
    assert stat_for(html, "Total spent") == inr(1500)
    assert stat_for(html, "Daily average") == inr(50)
    assert stat_for(html, "vs previous period") == "+" + inr(800)
    assert "▲ 114.3% more" in html
    assert f"Previous: {inr(700)}" in html
    assert inr(9999) not in html


def test_no_spending_in_previous_period(client):
    user_id = fresh_user(client)
    add_expense_row(user_id, 3000, "Bills", "2020-03-15", "Rent")
    html = page(client, "?from=2020-03-01&to=2020-03-30")
    assert stat_for(html, "Daily average") == inr(100)   # ₹3,000 / 30 days
    assert "No spending in previous period" in html


def test_previous_period_boundaries(client):
    user_id = fresh_user(client)
    add_expense_row(user_id, 3000, "Bills", "2020-03-15", "Rent")
    add_expense_row(user_id, 400, "Food", "2020-01-31", "Inside previous")
    add_expense_row(user_id, 999, "Food", "2020-01-30", "Outside previous")
    html = page(client, "?from=2020-03-01&to=2020-03-30")
    assert f"Previous: {inr(400)}" in html
    assert "▲ 650.0% more" in html


def test_down_comparison(client):
    user_id = fresh_user(client)
    add_expense_row(user_id, 500, "Food", "2020-03-10", "Now")
    add_expense_row(user_id, 1000, "Food", "2020-02-10", "Before")
    html = page(client, "?from=2020-03-01&to=2020-03-30")
    assert stat_for(html, "vs previous period") == "−" + inr(500)
    assert "▼ 50.0% less" in html


def test_total_matches_summary_page(client):
    login(client)
    month = f"{date.today():%Y-%m}"
    query = f"?from={month}-01&to={month}-28"     # covers every seed row
    summary = client.get("/profile/summary" + query).get_data(as_text=True)
    html = page(client, query)
    assert stat_for(html, "Total spent") == inr(SEED_TOTAL)
    assert stat_for(summary, "Total spent") == inr(SEED_TOTAL)


def test_all_time_shows_everything_without_comparison(client):
    user_id = fresh_user(client)
    add_expense_row(user_id, 100, "Food", "2019-05-01", "Old")
    add_expense_row(user_id, 250, "Food", date.today().isoformat(), "New")
    html = page(client, "?from=&to=")
    assert stat_for(html, "Total spent") == inr(350)
    assert stat_for(html, "vs previous period") is None
    assert "Previous:" not in html
    assert re.search(r'class="filter-preset active">\s*All time\s*<', html)
    assert 'href="/analytics?from=&amp;to="' in html


def test_weekday_breakdown(client):
    user_id = fresh_user(client)
    add_expense_row(user_id, 300, "Food", "2020-06-03", "Wednesday")
    add_expense_row(user_id, 450, "Food", "2020-06-06", "Saturday 1")
    add_expense_row(user_id, 450, "Shopping", "2020-06-06", "Saturday 2")
    html = page(client, "?from=2020-06-01&to=2020-06-07")
    assert re.findall(r'class="weekday-name">(\w+)<', html) == WEEK
    values = re.findall(r'class="weekday-value">([^<]+)<', html)
    assert values[2] == f"{inr(300)} · 1"
    assert values[5] == f"{inr(900)} · 2"
    assert sum(v.startswith(inr(0)) for v in values) == 5
    assert re.search(r"most on <strong>Saturday</strong>", html)


def test_top_expenses_limit_order_and_edit_links(client):
    user_id = fresh_user(client)
    for day, amount in enumerate([10, 70, 30, 50, 90, 20, 60], start=1):
        add_expense_row(user_id, amount, "Food", f"2020-05-{day:02d}",
                        f"Item {amount}")
    html = page(client, "?from=2020-05-01&to=2020-05-31")
    expected = db.get_top_expenses(user_id, "2020-05-01", "2020-05-31")
    assert [row["amount"] for row in expected] == [90, 70, 60, 50, 30]
    links = re.findall(r'href="/expenses/(\d+)/edit"', html)
    assert links == [str(row["id"]) for row in expected]
    assert "Item 10" not in html
    assert "Item 20" not in html


def test_monthly_trend_capped_at_12(client):
    user_id = fresh_user(client)
    months = [f"2020-{m:02d}" for m in range(1, 13)] + ["2021-01", "2021-02"]
    for month in months:
        amount = 5000 if month == "2020-11" else 100
        add_expense_row(user_id, amount, "Food", f"{month}-10", month)
    html = page(client, "?from=2020-01-01&to=2021-12-31")
    labels = re.findall(r'class="trend-month">([^<]+)<', html)
    assert len(labels) == 12
    assert labels[0] == "March 2020"
    assert labels[-1] == "February 2021"
    assert "January 2020" not in labels
    assert 'style="--bar: 100.0%"' in html


def test_empty_state(client):
    fresh_user(client)
    html = page(client, "?from=2019-01-01&to=2019-01-31")
    assert "No expenses in this period" in html
    assert "trend-chart" not in html
    assert "weekday-list" not in html
    assert "Top expenses" not in html


def test_invalid_and_reversed_input_return_200_with_message(client):
    fresh_user(client)
    assert INVALID_MSG in page(client, "?from=2026-13-01")
    assert REVERSED_MSG in page(client, "?from=2020-02-01&to=2020-01-01")


@pytest.mark.parametrize("query", [
    "?from=2020-3-1", "?to=2020-3-31", "?from=2020-3-1&to=2020-3-31",
])
def test_unpadded_dates_do_not_crash(client, query):
    user_id = fresh_user(client)
    add_expense_row(user_id, 250, "Food", "2020-03-10", "Lunch")
    html = page(client, query)
    assert INVALID_MSG not in html
    assert stat_for(html, "Total spent") == inr(250)


def test_unpadded_dates_match_padded_on_summary(client):
    user_id = fresh_user(client)
    add_expense_row(user_id, 250, "Food", "2020-03-10", "In range")
    add_expense_row(user_id, 999, "Food", "2020-10-10", "Out of range")
    padded = client.get("/profile/summary?from=2020-03-01&to=2020-03-31")
    unpadded = client.get("/profile/summary?from=2020-3-1&to=2020-3-31")
    assert unpadded.status_code == 200
    assert (stat_for(unpadded.get_data(as_text=True), "Total spent")
            == stat_for(padded.get_data(as_text=True), "Total spent")
            == inr(250))


@pytest.mark.parametrize("query", [
    "?from=0001-01-01", "?from=0001-01-01&to=0001-01-10",
])
def test_earliest_dates_do_not_crash(client, query):
    fresh_user(client)
    html = page(client, query)
    assert stat_for(html, "vs previous period") is None


def test_other_users_data_is_excluded(client):
    other_id = fresh_user(client, "other@example.com")
    add_expense_row(other_id, 77777.77, "Shopping", "2020-03-10", "Theirs")
    client.get("/logout")

    user_id = fresh_user(client)
    add_expense_row(user_id, 100, "Food", "2020-03-11", "Mine")
    html = page(client, "?from=2020-03-01&to=2020-03-31")
    assert stat_for(html, "Total spent") == inr(100)
    assert inr(77777.77) not in html
    assert "Theirs" not in html
    other_ids = {str(row["id"]) for row in db.get_expenses(other_id)}
    assert not other_ids & set(re.findall(r"/expenses/(\d+)/edit", html))

    client.get("/logout")
    login(client, "other@example.com", "password123")
    html = page(client, "?from=2020-03-01&to=2020-03-31")
    assert stat_for(html, "Total spent") == inr(77777.77)
    assert "Mine" not in html


def test_currency_and_markup_hygiene(client):
    login(client)
    html = page(client, "?from=&to=")
    assert "₹" in html
    assert not re.search(r"\$\s?\d", html)      # no dollar amounts
    assert "<style" not in html
    assert "profile-subnav" not in html


def test_top_category_links_to_categories_with_range(client):
    user_id = fresh_user(client)
    add_expense_row(user_id, 300, "Bills", "2020-03-10", "Power")
    add_expense_row(user_id, 100, "Food", "2020-03-11", "Lunch")
    html = page(client, "?from=2020-03-01&to=2020-03-31")
    assert stat_for(html, "Top category") == "Bills"
    assert "75.0% of spending" in html
    assert ('href="/profile/categories?from=2020-03-01&amp;to=2020-03-31"'
            in html)
