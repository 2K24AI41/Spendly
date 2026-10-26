import re
from datetime import date

from tests.conftest import add_expense_row, fetch_users, login, register_user


def get_summary(client, query=""):
    return client.get("/profile/summary" + query)


def add_earlier_months():
    add_expense_row(1, 300.0, "Food", "2020-03-04", "March lunch")
    add_expense_row(1, 700.0, "Bills", "2020-03-18", "March rent share")
    add_expense_row(1, 450.0, "Travel", "2020-05-09", "May train")


# ---- Auth ---- #

def test_summary_redirects_to_login_when_signed_out(client):
    resp = get_summary(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_summary_missing_user_clears_session_and_redirects(client):
    with client.session_transaction() as s:
        s["user_id"] = 99999
        s["user_name"] = "Ghost"
    resp = get_summary(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    with client.session_transaction() as s:
        assert len(s) == 0


# ---- Demo figures ---- #

def test_summary_shows_demo_figures(client):
    login(client)
    resp = get_summary(client)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Summary — Spendly" in html
    assert "₹5,240.00" in html
    assert re.search(r'stat-value">\s*8\s*<', html)
    assert "₹655.00" in html
    assert "₹1,800.00" in html
    assert "Electricity bill" in html
    assert "By month" in html


def test_summary_has_one_row_for_the_current_month(client):
    login(client)
    html = get_summary(client).get_data(as_text=True)
    months = re.findall(r'class="summary-month">([^<]+)<', html)
    assert months == [f"{date.today():%B %Y}"]


# ---- Filtering ---- #

def test_monthly_rows_are_newest_first_with_correct_totals(client):
    add_earlier_months()
    login(client)
    html = get_summary(client).get_data(as_text=True)
    months = re.findall(r'class="summary-month">([^<]+)<', html)
    assert months == [f"{date.today():%B %Y}", "May 2020", "March 2020"]

    tbody = html.split("<tbody>")[1].split("</tbody>")[0]
    rows = re.findall(r"<tr>(.*?)</tr>", tbody, re.S)
    assert "₹450.00" in rows[1]
    assert "₹1,000.00" in rows[2]
    assert "₹500.00" in rows[2]
    assert "₹6,690.00" in html


def test_date_filter_narrows_stats(client):
    add_earlier_months()
    login(client)
    html = get_summary(client, "?from=2020-01-01&to=2020-12-31").get_data(
        as_text=True)
    assert "₹1,450.00" in html
    assert re.search(r'stat-value">\s*3\s*<', html)
    assert "₹483.33" in html
    assert "₹700.00" in html
    assert "March rent share" in html
    assert "Electricity bill" not in html
    assert "₹5,240.00" not in html
    months = re.findall(r'class="summary-month">([^<]+)<', html)
    assert months == ["May 2020", "March 2020"]
    assert 'value="2020-01-01"' in html


def test_invalid_date_shows_message_and_all_dates(client):
    login(client)
    resp = get_summary(client, "?from=2026-13-45")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Invalid date" in html
    assert "₹5,240.00" in html


def test_reversed_range_shows_message(client):
    login(client)
    resp = get_summary(client, "?from=2026-12-31&to=2026-01-01")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Start date must be on or before end date" in html
    assert "₹5,240.00" in html


# ---- Other users ---- #

def test_new_user_sees_zero_and_empty_state(client):
    register_user(client)
    login(client, "new@example.com", "password123")
    html = get_summary(client).get_data(as_text=True)
    assert "₹0.00" in html
    assert re.search(r'stat-value">\s*0\s*<', html)
    assert "No expenses in this period" in html
    assert "<tbody>" not in html


def test_users_are_isolated(client):
    register_user(client)
    [new_user] = fetch_users("new@example.com")
    add_expense_row(new_user["id"], 999.0, "Travel", "2026-01-15",
                    "Secret trip")

    login(client)
    html = get_summary(client).get_data(as_text=True)
    assert "₹5,240.00" in html
    assert "Secret trip" not in html
    assert "₹999.00" not in html

    client.get("/logout")
    login(client, "new@example.com", "password123")
    html = get_summary(client).get_data(as_text=True)
    assert "₹999.00" in html
    assert "Secret trip" in html
    assert "Electricity bill" not in html
    assert "₹5,240.00" not in html


# ---- Hygiene ---- #

def test_summary_has_no_dollar_sign(client):
    login(client)
    html = get_summary(client).get_data(as_text=True)
    assert "$" not in html


def test_summary_css_has_no_hex_colours():
    with open("static/css/summary.css", encoding="utf-8") as f:
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", f.read())
