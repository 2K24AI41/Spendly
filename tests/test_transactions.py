import re

from tests.conftest import add_expense_row, fetch_users, login, register_user

DEMO_NEWEST_FIRST = [
    "Dinner out", "Miscellaneous", "New shoes", "Movie tickets",
    "Pharmacy", "Electricity bill", "Metro card recharge", "Groceries",
]


def descriptions(html):
    if "<tbody>" not in html:
        return []
    tbody = html.split("<tbody>")[1].split("</tbody>")[0]
    return re.findall(r"<td>([^<]+)</td>", tbody)


def get_html(client, query=""):
    resp = client.get("/profile/transactions" + query)
    assert resp.status_code == 200
    return resp.get_data(as_text=True)


def test_redirects_to_login_when_signed_out(client):
    resp = client.get("/profile/transactions")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_missing_user_clears_session_and_redirects(client):
    with client.session_transaction() as s:
        s["user_id"] = 99999
        s["user_name"] = "Ghost"
    resp = client.get("/profile/transactions")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    with client.session_transaction() as s:
        assert len(s) == 0


def test_demo_sees_all_expenses_newest_first(client):
    login(client)
    html = get_html(client)
    assert descriptions(html) == DEMO_NEWEST_FIRST
    assert "8 transactions" in html
    assert "₹1,800.00" in html


def test_date_range_filters_rows(client):
    add_expense_row(1, 100.0, "Travel", "2025-01-10", "January trip")
    add_expense_row(1, 200.0, "Travel", "2025-03-15", "March trip")
    add_expense_row(1, 300.0, "Travel", "2025-06-20", "June trip")
    login(client)

    html = get_html(client, "?from=2025-03-01&to=2025-03-31")
    assert descriptions(html) == ["March trip"]
    assert "1 transaction" in html

    # Both ends are inclusive.
    html = get_html(client, "?from=2025-03-15&to=2025-06-20")
    assert descriptions(html) == ["June trip", "March trip"]

    html = get_html(client, "?to=2025-02-01")
    assert descriptions(html) == ["January trip"]

    html = get_html(client, "?from=2025-04-01")
    rows = descriptions(html)
    assert "June trip" in rows
    assert "March trip" not in rows
    assert "January trip" not in rows
    assert len(rows) == 9


def test_category_filter(client):
    login(client)
    html = get_html(client, "?category=Food")
    assert descriptions(html) == ["Dinner out", "Groceries"]
    assert "2 transactions" in html
    assert re.search(r'<option value="Food"\s+selected>', html)


def test_invalid_date_shows_message_and_all_rows(client):
    login(client)
    html = get_html(client, "?from=2026-13-45")
    assert "Invalid date" in html
    assert descriptions(html) == DEMO_NEWEST_FIRST


def test_unknown_category_shows_message_and_all_rows(client):
    login(client)
    html = get_html(client, "?category=Nope")
    assert "Unknown category" in html
    assert descriptions(html) == DEMO_NEWEST_FIRST


def test_invalid_date_and_unknown_category_messages_combine(client):
    login(client)
    html = get_html(client, "?from=bad&category=Nope")
    assert "Invalid date ignored. Unknown category" in html


def test_reversed_range_shows_message(client):
    login(client)
    html = get_html(client, "?from=2026-05-01&to=2026-04-01")
    assert "Start date must be on or before end date" in html
    assert descriptions(html) == DEMO_NEWEST_FIRST


def test_users_only_see_own_expenses(client):
    register_user(client)
    [new_user] = fetch_users("new@example.com")
    add_expense_row(new_user["id"], 999.0, "Travel", "2026-01-15",
                    "Secret trip")

    login(client)
    html = get_html(client)
    assert "Secret trip" not in html
    assert "Travel" not in html
    assert descriptions(html) == DEMO_NEWEST_FIRST

    client.get("/logout")
    login(client, "new@example.com", "password123")
    html = get_html(client)
    assert descriptions(html) == ["Secret trip"]
    assert "Groceries" not in html
    assert "Food" not in html


def test_new_user_sees_empty_state(client):
    register_user(client)
    login(client, "new@example.com", "password123")
    html = get_html(client)
    assert "No transactions match these filters." in html
    assert "profile-empty" in html
    assert "<tbody>" not in html


def test_no_dollar_sign(client):
    login(client)
    assert "$" not in get_html(client)


def test_transactions_css_has_no_hex_colours():
    with open("static/css/transactions.css", encoding="utf-8") as f:
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", f.read())
