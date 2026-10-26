import re
from pathlib import Path

from tests.conftest import add_expense_row, fetch_users, login, register_user

DEMO_ORDER = ["Bills", "Shopping", "Health", "Food",
              "Entertainment", "Other", "Transport"]
CSS_PATH = (Path(__file__).resolve().parent.parent
            / "static" / "css" / "categories.css")


def get_page(client, query=""):
    return client.get("/profile/categories" + query)


def row_for(html, category):
    match = re.search(
        r"<tr>\s*<td><span class=\"category-badge\">" + category
        + r"</span></td>(.*?)</tr>",
        html, re.S,
    )
    assert match, f"no row for {category}"
    return match.group(1)


def test_redirects_to_login_when_signed_out(client):
    resp = get_page(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_deleted_session_user_is_cleared_and_redirected(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
        sess["user_name"] = "Ghost"

    resp = get_page(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    with client.session_transaction() as sess:
        assert "user_id" not in sess


def test_demo_categories_listed_highest_total_first(client):
    login(client)
    resp = get_page(client)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)

    positions = [html.index(f'category-badge">{name}<') for name in DEMO_ORDER]
    assert positions == sorted(positions)


def test_food_row_shows_count_total_and_average(client):
    login(client)
    row = row_for(get_page(client).get_data(as_text=True), "Food")
    assert re.search(r'class="amount">\s*2\s*<', row)
    assert "₹570.00" in row
    assert "₹285.00" in row


def test_bills_share_is_shown(client):
    login(client)
    row = row_for(get_page(client).get_data(as_text=True), "Bills")
    assert "34.4%" in row
    assert 'style="width: 34.4%"' in row


def test_grand_total_in_footer(client):
    login(client)
    html = get_page(client).get_data(as_text=True)
    footer = re.search(r"<tfoot>(.*?)</tfoot>", html, re.S)
    assert footer
    assert "₹5,240.00" in footer.group(1)
    assert re.search(r'class="amount">\s*8\s*<', footer.group(1))


def test_date_filter_narrows_breakdown(client):
    add_expense_row(1, 300, "Food", "2020-01-05", "Old lunch")
    add_expense_row(1, 100, "Transport", "2020-01-20", "Old bus")
    login(client)

    html = get_page(client, "?from=2020-01-01&to=2020-01-31").get_data(
        as_text=True)
    assert 'category-badge">Food<' in html
    assert 'category-badge">Transport<' in html
    assert 'category-badge">Bills<' not in html
    assert "75.0%" in row_for(html, "Food")
    footer = re.search(r"<tfoot>(.*?)</tfoot>", html, re.S).group(1)
    assert "₹400.00" in footer
    assert 'value="2020-01-01"' in html


def test_invalid_date_shows_message(client):
    login(client)
    resp = get_page(client, "?from=2026-13-45")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Invalid date" in html
    assert 'category-badge">Bills<' in html


def test_reversed_range_shows_message(client):
    login(client)
    resp = get_page(client, "?from=2026-12-31&to=2026-01-01")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Start date must be on or before end date" in html
    assert "₹5,240.00" in html


def test_users_see_only_their_own_categories(client):
    register_user(client, email="other@example.com")
    other_id = fetch_users("other@example.com")[0]["id"]
    add_expense_row(other_id, 999, "Travel", "2026-01-10", "Flight")

    login(client, "other@example.com", "password123")
    html = get_page(client).get_data(as_text=True)
    assert 'category-badge">Travel<' in html
    assert 'category-badge">Bills<' not in html
    assert "₹999.00" in html
    assert "₹5,240.00" not in html

    client.get("/logout")
    login(client)
    html = get_page(client).get_data(as_text=True)
    assert 'category-badge">Travel<' not in html
    assert "₹999.00" not in html


def test_new_user_sees_empty_state(client):
    register_user(client)
    login(client, "new@example.com", "password123")
    resp = get_page(client)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "No expenses in this period" in html
    assert "profile-empty" in html
    assert "<tfoot>" not in html


def test_no_dollar_sign_on_page(client):
    login(client)
    assert "$" not in get_page(client).get_data(as_text=True)


def test_categories_css_has_no_hex_colours():
    css = CSS_PATH.read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
