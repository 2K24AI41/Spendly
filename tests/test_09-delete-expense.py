"""Tests for Step 9 - Delete Expense (spec: .claude/specs/09-delete-expense.md)."""
import re
from pathlib import Path

import pytest

import database.db as db
from tests.conftest import add_expense_row, fetch_users, login, register_user

ADD_URL = "/expenses/add"
TOKEN_RE = re.compile(r'name="csrf_token" value="([0-9a-f]+)"')
MARKER = "Delete marker"
OTHER_EMAIL = "other@example.com"
OTHER_PW = "password123"
STATIC = Path(__file__).resolve().parent.parent / "static" / "css"


# ------------------------------------------------------------------ helpers

def delete_url(expense_id):
    return f"/expenses/{expense_id}/delete"


def get_token(client):
    """Session-wide CSRF token, read from the add-expense form."""
    page = client.get(ADD_URL).get_data(as_text=True)
    match = TOKEN_RE.search(page)
    assert match, "Expected a csrf_token hidden field on the add form"
    return match.group(1)


def demo_id():
    return fetch_users("demo@spendly.com")[0]["id"]


def make_expense(user_id=None, amount=777.0, category="Other",
                 date="2099-01-01", description=MARKER):
    add_expense_row(user_id or demo_id(), amount, category, date, description)
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT id FROM expenses ORDER BY id DESC LIMIT 1"
        ).fetchone()["id"]
    finally:
        conn.close()


def fetch_row(expense_id):
    conn = db.get_db()
    try:
        return conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
    finally:
        conn.close()


def count_expenses():
    conn = db.get_db()
    try:
        return conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    finally:
        conn.close()


def post_delete(client, expense_id, token=None, **extra):
    data = {"csrf_token": get_token(client) if token is None else token}
    data.update(extra)
    return client.post(delete_url(expense_id), data=data)


def logged_in_with_expense(client, **kwargs):
    login(client)
    return make_expense(**kwargs)


def login_as_other(client):
    client.get("/logout")
    register_user(client, email=OTHER_EMAIL, password=OTHER_PW)
    login(client, email=OTHER_EMAIL, password=OTHER_PW)


# ---------------------------------------------------------------- auth guard

def test_get_signed_out_redirects_to_login(client):
    eid = make_expense()
    resp = client.get(delete_url(eid))
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_post_signed_out_redirects_and_keeps_row(client):
    eid = make_expense()
    resp = client.post(delete_url(eid), data={"csrf_token": "x"})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    assert fetch_row(eid) is not None


# ----------------------------------------------------- confirmation page (GET)

def test_get_shows_expense_details_and_keeps_row(client):
    eid = logged_in_with_expense(client, amount=1234.5, category="Health",
                                 date="2099-03-04")
    resp = client.get(delete_url(eid))
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "₹1,234.50" in html
    assert "Health" in html
    assert "04 Mar 2099" in html
    assert MARKER in html
    assert 'class="btn-danger"' in html
    assert f'action="{delete_url(eid)}"' in html
    assert 'href="/profile/transactions"' in html
    assert "$" not in html
    assert fetch_row(eid) is not None


def test_get_null_description_shows_dash(client):
    login(client)
    eid = make_expense(description=None)
    html = client.get(delete_url(eid)).get_data(as_text=True)
    assert "None" not in html
    assert "—" in html


def test_get_form_has_csrf_token(client):
    eid = logged_in_with_expense(client)
    html = client.get(delete_url(eid)).get_data(as_text=True)
    assert TOKEN_RE.search(html)


def test_get_and_head_never_delete(client):
    eid = logged_in_with_expense(client)
    before = count_expenses()
    client.get(delete_url(eid))
    client.get(delete_url(eid))
    assert client.head(delete_url(eid)).status_code == 200
    assert count_expenses() == before
    assert fetch_row(eid) is not None


# ------------------------------------------------------------ 404 / ownership

def test_missing_id_returns_404(client):
    login(client)
    assert client.get(delete_url(999999)).status_code == 404
    assert post_delete(client, 999999).status_code == 404


def test_other_users_expense_returns_404_and_survives(client):
    eid = make_expense()
    login_as_other(client)
    assert client.get(delete_url(eid)).status_code == 404
    assert post_delete(client, eid).status_code == 404
    assert fetch_row(eid) is not None


# ------------------------------------------------------------ deleting (POST)

def test_valid_post_deletes_and_redirects(client):
    eid = logged_in_with_expense(client)
    resp = post_delete(client, eid)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile/transactions")
    assert fetch_row(eid) is None
    html = client.get("/profile/transactions").get_data(as_text=True)
    assert MARKER not in html


def test_only_target_row_is_removed(client):
    login(client)
    target = make_expense(description="Target row")
    sibling = make_expense(description="Sibling row")
    other_uid = None
    register_user(client, email=OTHER_EMAIL, password=OTHER_PW)
    other_uid = fetch_users(OTHER_EMAIL)[0]["id"]
    foreign = make_expense(user_id=other_uid, description="Foreign row")
    before = count_expenses()
    sibling_before = tuple(fetch_row(sibling))
    foreign_before = tuple(fetch_row(foreign))

    assert post_delete(client, target).status_code == 302

    assert count_expenses() == before - 1
    assert fetch_row(target) is None
    assert tuple(fetch_row(sibling)) == sibling_before
    assert tuple(fetch_row(foreign)) == foreign_before


def test_delete_reflected_in_profile_categories_and_summary(client):
    eid = logged_in_with_expense(client, amount=777.0, category="Other")
    assert "₹6,017.00" in client.get("/profile").get_data(as_text=True)
    assert "₹6,017.00" in client.get(
        "/profile/categories").get_data(as_text=True)
    assert "₹6,017.00" in client.get(
        "/profile/summary").get_data(as_text=True)

    post_delete(client, eid)

    for page in ("/profile", "/profile/categories", "/profile/summary"):
        html = client.get(page).get_data(as_text=True)
        assert "₹6,017.00" not in html, f"{page} still counts the expense"
        assert "₹5,240.00" in html, f"{page} should return to the seed total"


def test_second_post_returns_404(client):
    eid = logged_in_with_expense(client)
    token = get_token(client)
    assert post_delete(client, eid, token=token).status_code == 302
    assert post_delete(client, eid, token=token).status_code == 404


# ----------------------------------------------------------------------- CSRF

@pytest.mark.parametrize("token", ["", "deadbeef", "ünïcode"])
def test_bad_csrf_token_returns_400(client, token):
    eid = logged_in_with_expense(client)
    resp = client.post(delete_url(eid), data={"csrf_token": token})
    assert resp.status_code == 400
    assert fetch_row(eid) is not None


def test_missing_csrf_field_returns_400(client):
    eid = logged_in_with_expense(client)
    resp = client.post(delete_url(eid), data={})
    assert resp.status_code == 400
    assert fetch_row(eid) is not None


# ------------------------------------------------------------------ tampering

def test_forged_user_id_does_not_reach_foreign_expense(client):
    register_user(client, email=OTHER_EMAIL, password=OTHER_PW)
    other_uid = fetch_users(OTHER_EMAIL)[0]["id"]
    foreign = make_expense(user_id=other_uid, description="Foreign row")
    login(client)
    resp = post_delete(client, foreign, user_id=str(other_uid))
    assert resp.status_code == 404
    assert fetch_row(foreign) is not None


def test_forged_user_id_ignored_on_own_expense(client):
    register_user(client, email=OTHER_EMAIL, password=OTHER_PW)
    other_uid = fetch_users(OTHER_EMAIL)[0]["id"]
    foreign = make_expense(user_id=other_uid, description="Foreign row")
    eid = logged_in_with_expense(client)
    resp = post_delete(client, eid, user_id=str(other_uid), id=str(foreign))
    assert resp.status_code == 302
    assert fetch_row(eid) is None
    assert fetch_row(foreign) is not None


# --------------------------------------------------------------- links / UI

def test_delete_links_on_transactions_and_profile(client):
    eid = logged_in_with_expense(client)
    link = f'href="{delete_url(eid)}"'
    for page in ("/profile/transactions", "/profile"):
        html = client.get(page).get_data(as_text=True)
        assert link in html, f"{page} missing the Delete link"
        assert f"Delete {MARKER} expense of" in html


def test_delete_link_opens_confirmation(client):
    eid = logged_in_with_expense(client)
    assert client.get(delete_url(eid)).status_code == 200


def test_delete_links_not_shown_for_other_users(client):
    eid = make_expense()
    login_as_other(client)
    for page in ("/profile", "/profile/transactions"):
        html = client.get(page).get_data(as_text=True)
        assert delete_url(eid) not in html


def test_cancel_returns_to_transactions_without_deleting(client):
    eid = logged_in_with_expense(client)
    assert client.get("/profile/transactions").status_code == 200
    assert fetch_row(eid) is not None


def test_confirmation_page_has_viewport_meta(client):
    eid = logged_in_with_expense(client)
    html = client.get(delete_url(eid)).get_data(as_text=True)
    assert 'name="viewport"' in html


# ---------------------------------------------------------------------- CSS

def test_new_css_has_no_hex_colours():
    css = (STATIC / "delete_expense.css").read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)


# ---------------------------------------------------------------- db helper

def test_delete_expense_helper_scoped_to_user(app):
    eid = make_expense()
    owner = fetch_row(eid)["user_id"]
    assert db.delete_expense(eid, owner + 1000) is False
    assert fetch_row(eid) is not None
    assert db.delete_expense(99999, owner) is False
    assert db.delete_expense(eid, owner) is True
    assert fetch_row(eid) is None
