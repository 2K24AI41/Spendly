import re
from datetime import date

import pytest
from flask.testing import FlaskClient

import database.db as db
from tests.conftest import (
    add_expense_row, fetch_users, login, register_user,
)

CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]
TOKEN_RE = re.compile(r'name="csrf_token" value="([0-9a-f]+)"')
MARKER = "Original marker"


class CsrfClient(FlaskClient):
    """Test client that adds a valid CSRF token to POSTs to an edit form."""

    auto_csrf = True

    def post(self, *args, **kwargs):
        data = kwargs.get("data")
        if (self.auto_csrf and args and args[0].endswith("/edit")
                and isinstance(data, dict) and "csrf_token" not in data):
            page = self.get(args[0]).get_data(as_text=True)
            match = TOKEN_RE.search(page)
            if match:
                kwargs["data"] = {**data, "csrf_token": match.group(1)}
        return super().post(*args, **kwargs)


@pytest.fixture
def client(app, monkeypatch):
    monkeypatch.setattr(app, "test_client_class", CsrfClient)
    return app.test_client()


@pytest.fixture
def expense_id(app):
    """An expense owned by the demo user."""
    demo_id = fetch_users("demo@spendly.com")[0]["id"]
    add_expense_row(demo_id, 250.0, "Food", "2025-05-10", MARKER)
    return fetch_by_description(MARKER)["id"]


def edit_url(expense_id):
    return f"/expenses/{expense_id}/edit"


def valid_form(**overrides):
    data = {
        "amount": "399.75",
        "category": "Bills",
        "date": "2025-06-15",
        "description": "Edited marker",
    }
    data.update(overrides)
    return data


def fetch_expense(expense_id):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    finally:
        conn.close()


def fetch_by_description(description):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE description = ?", (description,)
        ).fetchone()
    finally:
        conn.close()


def count_expenses():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    finally:
        conn.close()


def assert_unchanged(expense_id, original):
    row = fetch_expense(expense_id)
    assert tuple(row) == tuple(original)


def assert_rejected(client, expense_id, **overrides):
    original = fetch_expense(expense_id)
    resp = client.post(edit_url(expense_id), data=valid_form(**overrides))
    assert resp.status_code == 200, "Invalid input must re-render with 200"
    html = resp.get_data(as_text=True)
    assert "auth-error" in html
    assert_unchanged(expense_id, original)
    return html


# ---------------------------------------------------------------- auth guard

def test_get_signed_out_redirects_to_login(client, expense_id):
    resp = client.get(edit_url(expense_id))
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_post_signed_out_redirects_to_login(client, expense_id):
    original = fetch_expense(expense_id)
    resp = client.post(edit_url(expense_id), data=valid_form())
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    assert_unchanged(expense_id, original)


def test_signed_out_missing_id_still_redirects(client):
    resp = client.get(edit_url(99999))
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


# ------------------------------------------------------------------ GET form

def test_get_prefills_form(client, expense_id):
    login(client)
    resp = client.get(edit_url(expense_id))
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert 'value="250.00"' in html
    assert 'value="2025-05-10"' in html
    assert f'value="{MARKER}"' in html
    assert re.search(r'<option value="Food"\s+selected>', html)
    for category in CATEGORIES:
        assert f'<option value="{category}"' in html
    assert f'action="{edit_url(expense_id)}"' in html
    assert "$" not in html


def test_get_null_description_renders_empty(client, app):
    demo_id = fetch_users("demo@spendly.com")[0]["id"]
    add_expense_row(demo_id, 10.0, "Other", "2025-05-11", None)
    conn = db.get_db()
    try:
        row_id = conn.execute(
            "SELECT id FROM expenses WHERE description IS NULL"
        ).fetchone()["id"]
    finally:
        conn.close()
    login(client)
    html = client.get(edit_url(row_id)).get_data(as_text=True)
    assert 'value="None"' not in html


# ------------------------------------------------------------ 404 / ownership

def test_missing_id_returns_404(client, app):
    login(client)
    assert client.get(edit_url(99999)).status_code == 404
    assert client.post(edit_url(99999), data=valid_form()).status_code == 404


def test_other_users_expense_returns_404(client, expense_id):
    register_user(client, email="other@example.com")
    login(client, email="other@example.com", password="password123")
    original = fetch_expense(expense_id)
    assert client.get(edit_url(expense_id)).status_code == 404
    resp = client.post(edit_url(expense_id), data=valid_form())
    assert resp.status_code == 404
    assert_unchanged(expense_id, original)


# ----------------------------------------------------------------- happy path

def test_valid_edit_updates_row_and_redirects(client, expense_id):
    login(client)
    before = count_expenses()
    original = fetch_expense(expense_id)
    resp = client.post(edit_url(expense_id), data=valid_form())
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile/transactions")

    row = fetch_expense(expense_id)
    assert row["amount"] == 399.75
    assert row["category"] == "Bills"
    assert row["date"] == "2025-06-15"
    assert row["description"] == "Edited marker"
    assert row["id"] == original["id"]
    assert row["user_id"] == original["user_id"]
    assert count_expenses() == before


def test_edit_shows_on_transactions_with_rupee(client, expense_id):
    login(client)
    client.post(edit_url(expense_id), data=valid_form())
    html = client.get("/profile/transactions").get_data(as_text=True)
    assert "₹399.75" in html
    assert "Edited marker" in html
    assert MARKER not in html


def test_edit_reflected_in_profile_and_categories(client, expense_id):
    login(client)
    before = client.get("/profile/categories").get_data(as_text=True)
    client.post(edit_url(expense_id), data=valid_form())
    after = client.get("/profile/categories").get_data(as_text=True)
    assert before != after
    # Seeded Bills (₹1,800.00) plus the edited expense.
    assert "₹2,199.75" in after
    assert "₹2,199.75" in client.get("/profile").get_data(as_text=True)


def test_empty_description_saved_as_null(client, expense_id):
    login(client)
    resp = client.post(edit_url(expense_id), data=valid_form(description="  "))
    assert resp.status_code == 302
    assert fetch_expense(expense_id)["description"] is None


# ----------------------------------------------------------------- validation

@pytest.mark.parametrize("amount", [
    "", "0", "-5", "abc", "10000001", "1.234", "nan", "inf", "1" * 25,
])
def test_invalid_amount_rejected(client, expense_id, amount):
    login(client)
    assert_rejected(client, expense_id, amount=amount)


@pytest.mark.parametrize("category", ["", "Nonsense", "food"])
def test_invalid_category_rejected(client, expense_id, category):
    login(client)
    assert_rejected(client, expense_id, category=category)


@pytest.mark.parametrize("value", ["", "not-a-date", "2025-13-40", "10/05/2025"])
def test_invalid_date_rejected(client, expense_id, value):
    login(client)
    assert_rejected(client, expense_id, date=value)


def test_description_too_long_rejected(client, expense_id):
    login(client)
    assert_rejected(client, expense_id, description="x" * 201)


def test_description_at_limit_accepted(client, expense_id):
    login(client)
    resp = client.post(edit_url(expense_id),
                       data=valid_form(description="x" * 200))
    assert resp.status_code == 302


def test_form_keeps_entered_values_after_error(client, expense_id):
    login(client)
    html = assert_rejected(client, expense_id, amount="-5",
                           description="Kept text", category="Health")
    assert 'value="-5"' in html
    assert 'value="Kept text"' in html
    assert re.search(r'<option value="Health"\s+selected>', html)


# ----------------------------------------------------------------------- CSRF

def test_missing_csrf_token_returns_400(app, expense_id):
    client = app.test_client()
    login(client)
    original = fetch_expense(expense_id)
    resp = client.post(edit_url(expense_id), data=valid_form())
    assert resp.status_code == 400
    assert_unchanged(expense_id, original)


def test_wrong_csrf_token_returns_400(app, expense_id):
    client = app.test_client()
    login(client)
    original = fetch_expense(expense_id)
    resp = client.post(edit_url(expense_id),
                       data=valid_form(csrf_token="deadbeef"))
    assert resp.status_code == 400
    assert_unchanged(expense_id, original)


# ------------------------------------------------------------------ tampering

def test_forged_user_id_and_id_ignored(client, expense_id):
    register_user(client, email="other@example.com")
    other_id = fetch_users("other@example.com")[0]["id"]
    login(client)
    original = fetch_expense(expense_id)
    resp = client.post(edit_url(expense_id),
                       data=valid_form(user_id=str(other_id), id="9999"))
    assert resp.status_code == 302
    row = fetch_expense(expense_id)
    assert row["user_id"] == original["user_id"]
    assert row["id"] == expense_id
    assert row["amount"] == 399.75


def test_sql_injection_in_description_stored_literally(client, expense_id):
    login(client)
    payload = "x'); DROP TABLE expenses;--"
    resp = client.post(edit_url(expense_id),
                       data=valid_form(description=payload))
    assert resp.status_code == 302
    assert fetch_expense(expense_id)["description"] == payload


# ---------------------------------------------------------------- edit links

def test_edit_links_on_transactions_and_profile(client, expense_id):
    login(client)
    # /profile only lists the 5 most recent expenses, so make this one recent.
    owner = fetch_expense(expense_id)["user_id"]
    db.update_expense(expense_id, owner, "250.00", "Food",
                      date.today().isoformat(), MARKER)
    link = f'href="{edit_url(expense_id)}"'
    assert link in client.get("/profile/transactions").get_data(as_text=True)
    assert link in client.get("/profile").get_data(as_text=True)


def test_edit_link_opens_form(client, expense_id):
    login(client)
    assert client.get(edit_url(expense_id)).status_code == 200


# ---------------------------------------------------------------- db helpers

def test_get_expense_scoped_to_user(app, expense_id):
    owner = fetch_expense(expense_id)["user_id"]
    assert db.get_expense(expense_id, owner) is not None
    assert db.get_expense(expense_id, owner + 1000) is None
    assert db.get_expense(99999, owner) is None


def test_update_expense_returns_false_for_wrong_user_or_id(app, expense_id):
    owner = fetch_expense(expense_id)["user_id"]
    args = ("1.00", "Food", "2025-01-01", None)
    assert db.update_expense(expense_id, owner + 1000, *args) is False
    assert db.update_expense(99999, owner, *args) is False
    assert fetch_expense(expense_id)["description"] == MARKER
    assert db.update_expense(expense_id, owner, *args) is True
