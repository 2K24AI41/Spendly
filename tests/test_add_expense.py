import re
from datetime import date

import pytest
from flask.testing import FlaskClient

import database.db as db
from tests.conftest import fetch_users, login, register_user

CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]
URL = "/expenses/add"
TOKEN_RE = re.compile(r'name="csrf_token" value="([0-9a-f]+)"')


class CsrfClient(FlaskClient):
    """Test client that adds a valid CSRF token to POSTs to the add form."""

    auto_csrf = True

    def post(self, *args, **kwargs):
        data = kwargs.get("data")
        if (self.auto_csrf and args and args[0] == URL
                and isinstance(data, dict) and "csrf_token" not in data):
            page = self.get(URL).get_data(as_text=True)
            match = TOKEN_RE.search(page)
            if match:
                kwargs["data"] = {**data, "csrf_token": match.group(1)}
        return super().post(*args, **kwargs)


@pytest.fixture
def client(app, monkeypatch):
    monkeypatch.setattr(app, "test_client_class", CsrfClient)
    return app.test_client()


def valid_form(**overrides):
    data = {
        "amount": "250.50",
        "category": "Food",
        "date": "2025-05-10",
        "description": "Unique lunch marker",
    }
    data.update(overrides)
    return data


def count_expenses():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    finally:
        conn.close()


def fetch_by_description(description):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE description = ?", (description,)
        ).fetchall()
    finally:
        conn.close()


def fetch_latest_expense():
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()


def assert_rejected(client, **overrides):
    before = count_expenses()
    resp = client.post(URL, data=valid_form(**overrides))
    assert resp.status_code == 200, "Invalid input must re-render with 200"
    assert count_expenses() == before, "Invalid input must not insert a row"
    html = resp.get_data(as_text=True)
    assert "<form" in html, "Form should be re-rendered"
    return html


# ---------------------------------------------------------------- auth guard

def test_get_redirects_to_login_when_signed_out(client):
    resp = client.get(URL)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_post_redirects_to_login_when_signed_out(client):
    before = count_expenses()
    resp = client.post(URL, data=valid_form())
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    assert count_expenses() == before, "Signed-out POST must not insert"


# ------------------------------------------------------------------ GET form

def test_get_renders_form_with_today_and_all_categories(client):
    login(client)
    resp = client.get(URL)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "<form" in html
    assert date.today().isoformat() in html, "Date should default to today"
    for name in ("amount", "category", "date", "description"):
        assert f'name="{name}"' in html, f"Missing field {name}"
    for cat in CATEGORIES:
        assert cat in html, f"Category {cat} missing from form"


def test_get_form_has_no_dollar_sign(client):
    login(client)
    html = client.get(URL).get_data(as_text=True)
    assert "$" not in html


# ------------------------------------------------------------- happy path

def test_valid_post_redirects_to_transactions(client):
    login(client)
    resp = client.post(URL, data=valid_form())
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile/transactions")


def test_valid_post_stores_expense_for_logged_in_user(client):
    login(client)
    client.post(URL, data=valid_form())
    rows = fetch_by_description("Unique lunch marker")
    assert len(rows) == 1
    row = rows[0]
    demo_id = fetch_users("demo@spendly.com")[0]["id"]
    assert row["user_id"] == demo_id
    assert row["amount"] == pytest.approx(250.50)
    assert row["category"] == "Food"
    assert row["date"] == "2025-05-10"


def test_new_expense_appears_in_transactions(client):
    login(client)
    resp = client.post(URL, data=valid_form(), follow_redirects=True)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Unique lunch marker" in html
    assert "₹250.50" in html
    assert "2025-05-10" in html or "10 May 2025" in html or "May" in html


def test_new_expense_is_listed_first_when_newest(client):
    login(client)
    client.post(URL, data=valid_form(date="2099-01-01"))
    html = client.get("/profile/transactions").get_data(as_text=True)
    tbody = html.split("<tbody>")[1].split("</tbody>")[0]
    assert tbody.find("Unique lunch marker") != -1
    other = [d for d in ("Dinner out", "Groceries") if d in tbody]
    for d in other:
        assert tbody.find("Unique lunch marker") < tbody.find(d)


def test_new_expense_changes_profile_totals(client):
    login(client)
    before = client.get("/profile").get_data(as_text=True)
    assert "₹5,240.00" in before
    assert "₹5,440.00" not in before
    client.post(URL, data=valid_form(amount="200", date="2025-05-10"))
    after = client.get("/profile").get_data(as_text=True)
    assert "₹5,440.00" in after, "Profile total should grow by 200"


def test_new_expense_counted_in_categories(client):
    login(client)
    before = client.get("/profile/categories").get_data(as_text=True)
    client.post(URL, data=valid_form(amount="200", category="Other"))
    after = client.get("/profile/categories").get_data(as_text=True)
    assert before != after, "Categories page should reflect the new expense"


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_category_is_accepted(client, category):
    login(client)
    resp = client.post(URL, data=valid_form(category=category))
    assert resp.status_code == 302
    assert fetch_latest_expense()["category"] == category


@pytest.mark.parametrize("amount, expected", [
    ("100", 100.0),
    ("0.01", 0.01),
    ("12.5", 12.5),
    ("10000000", 10000000.0),
])
def test_valid_amounts_are_accepted(client, amount, expected):
    login(client)
    resp = client.post(URL, data=valid_form(amount=amount))
    assert resp.status_code == 302
    assert fetch_latest_expense()["amount"] == pytest.approx(expected)


def test_empty_description_stored_as_null(client):
    login(client)
    before = count_expenses()
    resp = client.post(URL, data=valid_form(description=""))
    assert resp.status_code == 302
    assert count_expenses() == before + 1
    assert fetch_latest_expense()["description"] is None


def test_whitespace_description_stored_as_null(client):
    login(client)
    resp = client.post(URL, data=valid_form(description="    "))
    assert resp.status_code == 302
    assert fetch_latest_expense()["description"] is None


def test_description_is_trimmed(client):
    login(client)
    client.post(URL, data=valid_form(description="  padded note  "))
    assert fetch_latest_expense()["description"] == "padded note"


def test_missing_description_field_accepted(client):
    login(client)
    data = valid_form()
    del data["description"]
    resp = client.post(URL, data=data)
    assert resp.status_code == 302
    assert fetch_latest_expense()["description"] is None


# ------------------------------------------------------- amount validation

@pytest.mark.parametrize("amount", [
    "", "0", "0.00", "-5", "-0.01", "abc", "12abc", "1.234", "10.999",
    "10000000.01", "10000001", "99999999999",
    "nan", "NaN", "inf", "-inf", "Infinity",
])
def test_invalid_amount_rejected(client, amount):
    login(client)
    html = assert_rejected(client, amount=amount)
    assert "error" in html.lower(), "An error message should be shown"


def test_missing_amount_field_rejected(client):
    login(client)
    before = count_expenses()
    data = valid_form()
    del data["amount"]
    resp = client.post(URL, data=data)
    assert resp.status_code == 200
    assert count_expenses() == before


# ----------------------------------------------------- category validation

@pytest.mark.parametrize("category", [
    "", "Travel", "food", "FOOD", "Nonsense", "<script>", "Food; DROP TABLE expenses",
])
def test_invalid_category_rejected(client, category):
    login(client)
    assert_rejected(client, category=category)


def test_missing_category_field_rejected(client):
    login(client)
    before = count_expenses()
    data = valid_form()
    del data["category"]
    resp = client.post(URL, data=data)
    assert resp.status_code == 200
    assert count_expenses() == before


# ----------------------------------------------------------- date validation

@pytest.mark.parametrize("value", [
    "", "not-a-date", "2025-13-01", "2025-02-30", "2025/05/10",
    "10-05-2025", "2025-5-1x", "20250510",
])
def test_invalid_date_rejected(client, value):
    login(client)
    assert_rejected(client, date=value)


def test_missing_date_field_rejected(client):
    login(client)
    before = count_expenses()
    data = valid_form()
    del data["date"]
    resp = client.post(URL, data=data)
    assert resp.status_code == 200
    assert count_expenses() == before


# ------------------------------------------------- description validation

def test_description_of_201_chars_rejected(client):
    login(client)
    assert_rejected(client, description="x" * 201)


def test_description_of_200_chars_accepted(client):
    login(client)
    text = "y" * 200
    resp = client.post(URL, data=valid_form(description=text))
    assert resp.status_code == 302
    assert fetch_latest_expense()["description"] == text


# ----------------------------------------------------------- sticky values

def test_values_kept_after_validation_error(client):
    login(client)
    resp = client.post(URL, data=valid_form(
        amount="abc",
        category="Health",
        date="2025-07-04",
        description="Sticky note text",
    ))
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "abc" in html, "Entered amount should be kept"
    assert "2025-07-04" in html, "Entered date should be kept"
    assert "Sticky note text" in html, "Entered description should be kept"
    selected = re.search(
        r'<option[^>]*value="Health"[^>]*selected|<option[^>]*selected[^>]*value="Health"',
        html,
    )
    assert selected, "Entered category should remain selected"


def test_error_page_has_no_dollar_sign(client):
    login(client)
    html = client.post(URL, data=valid_form(amount="-1")).get_data(as_text=True)
    assert "$" not in html


# ---------------------------------------------------- ownership and safety

def test_forged_user_id_is_ignored(client):
    register_user(client, email="owner@example.com")
    login(client, email="owner@example.com", password="password123")
    owner_id = fetch_users("owner@example.com")[0]["id"]
    demo_id = fetch_users("demo@spendly.com")[0]["id"]
    assert owner_id != demo_id

    resp = client.post(URL, data=valid_form(user_id=str(demo_id)))
    assert resp.status_code == 302
    rows = fetch_by_description("Unique lunch marker")
    assert len(rows) == 1
    assert rows[0]["user_id"] == owner_id, "Expense must belong to session user"


def test_another_user_does_not_see_new_expense(client):
    login(client)
    client.post(URL, data=valid_form())
    client.get("/logout")

    register_user(client, email="other@example.com")
    login(client, email="other@example.com", password="password123")
    html = client.get("/profile/transactions").get_data(as_text=True)
    assert "Unique lunch marker" not in html
    profile = client.get("/profile").get_data(as_text=True)
    assert "Unique lunch marker" not in profile


def test_sql_injection_in_description_stored_literally(client):
    login(client)
    payload = "x'); DROP TABLE expenses; --"
    resp = client.post(URL, data=valid_form(description=payload))
    assert resp.status_code == 302
    assert len(fetch_by_description(payload)) == 1
    assert count_expenses() > 0


# --------------------------------------------------------------- entry links

def test_profile_has_add_expense_link(client):
    login(client)
    html = client.get("/profile").get_data(as_text=True)
    assert f'href="{URL}"' in html


def test_transactions_has_add_expense_link(client):
    login(client)
    html = client.get("/profile/transactions").get_data(as_text=True)
    assert f'href="{URL}"' in html


def test_profile_empty_state_has_add_expense_link(client):
    register_user(client, email="empty@example.com")
    login(client, email="empty@example.com", password="password123")
    html = client.get("/profile").get_data(as_text=True)
    assert f'href="{URL}"' in html


# ---- Review follow-ups: CSRF, date normalisation, input size ---- #

def test_form_contains_csrf_token(client):
    login(client)
    html = client.get(URL).get_data(as_text=True)
    assert TOKEN_RE.search(html)


def test_post_without_csrf_token_is_rejected(client):
    login(client)
    client.auto_csrf = False
    before = count_expenses()
    resp = client.post(URL, data=valid_form())
    assert resp.status_code == 400
    assert count_expenses() == before


def test_post_with_wrong_csrf_token_is_rejected(client):
    login(client)
    client.get(URL)
    client.auto_csrf = False
    before = count_expenses()
    resp = client.post(URL, data=valid_form(csrf_token="0" * 32))
    assert resp.status_code == 400
    assert count_expenses() == before


def test_post_with_non_ascii_csrf_token_is_rejected(client):
    login(client)
    client.get(URL)
    client.auto_csrf = False
    resp = client.post(URL, data=valid_form(csrf_token="é" * 8))
    assert resp.status_code == 400


def test_signed_out_post_redirects_before_csrf_check(client):
    client.auto_csrf = False
    resp = client.post(URL, data=valid_form())
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_non_padded_date_is_stored_normalised(client):
    login(client)
    resp = client.post(URL, data=valid_form(
        date="2026-1-5", description="Normalised date marker"))
    assert resp.status_code == 302
    row = fetch_by_description("Normalised date marker")[0]
    assert row["date"] == "2026-01-05"


def test_overlong_amount_string_is_rejected(client):
    assert_rejected(login_and(client), amount="1" * 21)


def test_oversized_request_body_is_rejected(client):
    login(client)
    before = count_expenses()
    resp = client.post(URL, data=valid_form(description="x" * 20000))
    assert resp.status_code == 413
    assert count_expenses() == before


def login_and(client):
    login(client)
    return client
