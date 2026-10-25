import re

import database.db as db
from tests.conftest import fetch_users


def login(client, email="demo@spendly.com", password="demo123"):
    return client.post("/login", data={"email": email, "password": password})


def register(client, name="New User", email="new@example.com",
             password="password123"):
    return client.post("/register", data={
        "name": name,
        "email": email,
        "password": password,
        "confirm_password": password,
    })


def add_expense_row(user_id, amount, category, date, description):
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
        conn.commit()
    finally:
        conn.close()


def test_profile_redirects_to_login_when_signed_out(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_demo_login_lands_on_profile_with_user_details(client):
    resp = login(client)
    assert resp.headers["Location"].endswith("/profile")

    resp = client.get("/profile")
    assert resp.status_code == 200
    assert b"Demo User" in resp.data
    assert b"demo@spendly.com" in resp.data
    assert b"Member since" in resp.data


def test_demo_summary_stats(client):
    login(client)
    html = client.get("/profile").get_data(as_text=True)
    assert "₹5,240.00" in html
    assert re.search(r'stat-value">\s*8\s*<', html)
    assert re.search(r'stat-value">\s*Bills\s*<', html)
    assert "₹1,800.00" in html


def test_category_breakdown_lists_all_categories_highest_first(client):
    login(client)
    html = client.get("/profile").get_data(as_text=True)
    names = re.findall(r'class="category-name">([^<]+)<', html)
    assert names == ["Bills", "Shopping", "Health", "Food",
                     "Entertainment", "Other", "Transport"]
    assert len(re.findall(r'class="category-bar" style="width: [\d.]+%"',
                          html)) == 7


def test_recent_expenses_shows_five_newest_first(client):
    login(client)
    html = client.get("/profile").get_data(as_text=True)
    tbody = html.split("<tbody>")[1].split("</tbody>")[0]
    descriptions = re.findall(r"<td>([^<]+)</td>", tbody)
    assert descriptions == ["Dinner out", "Miscellaneous", "New shoes",
                            "Movie tickets", "Pharmacy"]


def test_no_dollar_sign_or_password_hash(client):
    login(client)
    [demo] = fetch_users("demo@spendly.com")
    html = client.get("/profile").get_data(as_text=True)
    assert "$" not in html
    assert demo["password_hash"] not in html


def test_new_user_sees_empty_state(client):
    register(client)
    login(client, "new@example.com", "password123")
    html = client.get("/profile").get_data(as_text=True)
    assert "New User" in html
    assert "₹0.00" in html
    assert re.search(r'stat-value">\s*0\s*<', html)
    assert re.search(r'stat-value">\s*—\s*<', html)
    assert "No expenses yet" in html
    assert 'href="/expenses/add"' in html
    assert "<tbody>" not in html
    assert client.get("/expenses/add").status_code == 200


def test_profile_only_shows_own_expenses(client):
    register(client)
    [new_user] = fetch_users("new@example.com")
    add_expense_row(new_user["id"], 999.0, "Travel", "2026-01-15",
                    "Secret trip")

    login(client)
    html = client.get("/profile").get_data(as_text=True)
    assert "Secret trip" not in html
    assert "Travel" not in html
    assert "₹5,240.00" in html

    client.get("/logout")
    login(client, "new@example.com", "password123")
    html = client.get("/profile").get_data(as_text=True)
    assert "Secret trip" in html
    assert "₹999.00" in html
    assert "Groceries" not in html


def test_missing_user_clears_session_and_redirects(client):
    with client.session_transaction() as s:
        s["user_id"] = 99999
        s["user_name"] = "Ghost"
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    with client.session_transaction() as s:
        assert len(s) == 0


def test_profile_css_has_no_hex_colours():
    with open("static/css/profile.css", encoding="utf-8") as f:
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", f.read())
