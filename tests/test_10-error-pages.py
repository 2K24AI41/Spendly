"""Tests for Step 10 - Error Pages (spec: .claude/specs/10-error-pages.md)."""
import re
import sys
from pathlib import Path

import pytest

import database.db as db
from tests.conftest import add_expense_row, fetch_users, login, register_user

ADD_URL = "/expenses/add"
TOKEN_RE = re.compile(r'name="csrf_token" value="([0-9a-f]+)"')
STATIC = Path(__file__).resolve().parent.parent / "static" / "css"
SECRET = "SECRET-INTERNAL-DETAIL"
WERKZEUG_404 = "The requested URL was not found on the server"


# ------------------------------------------------------------------ helpers

def page(response):
    return response.get_data(as_text=True)


def get_token(client):
    html = page(client.get(ADD_URL))
    match = TOKEN_RE.search(html)
    assert match, "Expected a csrf_token hidden field on the add form"
    return match.group(1)


def app_module():
    return sys.modules["app"]


def boom(*args, **kwargs):
    raise RuntimeError(SECRET)


@pytest.fixture
def no_propagate(app):
    """Let unhandled exceptions reach the 500 handler, then restore."""
    app.config.update(TESTING=False, PROPAGATE_EXCEPTIONS=False)
    yield app
    app.config.update(TESTING=True, PROPAGATE_EXCEPTIONS=None)


def assert_branded(response, code):
    html = page(response)
    assert response.status_code == code
    assert f'class="error-code">{code}<' in html
    assert 'class="navbar"' in html
    assert 'class="footer"' in html
    assert "css/error.css" in html
    return html


# --------------------------------------------------------------------- 404

def test_404_unknown_path_is_branded(client):
    html = assert_branded(client.get("/does-not-exist"), 404)
    assert "Page not found" in html
    assert WERKZEUG_404 not in html


def test_404_missing_expense_signed_in(client):
    login(client)
    assert_branded(client.get("/expenses/99999/edit"), 404)


def test_404_foreign_expense_delete(client):
    register_user(client, email="other@example.com")
    other_id = fetch_users("other@example.com")[0]["id"]
    add_expense_row(other_id, 10.0, "Other", "2099-01-01", "foreign")
    conn = db.get_db()
    try:
        expense_id = conn.execute(
            "SELECT id FROM expenses WHERE description = 'foreign'"
        ).fetchone()["id"]
    finally:
        conn.close()

    login(client)
    assert_branded(client.get(f"/expenses/{expense_id}/delete"), 404)


# --------------------------------------------------------------------- 400

def test_400_missing_csrf(client):
    login(client)
    assert_branded(client.post(ADD_URL, data={"amount": "10"}), 400)


def test_400_wrong_csrf(client):
    login(client)
    response = client.post(ADD_URL, data={"csrf_token": "nope"})
    assert_branded(response, 400)


# --------------------------------------------------------------------- 405

def test_405_post_to_landing(client):
    assert_branded(client.post("/"), 405)


# --------------------------------------------------------------------- 413

def test_413_oversize_body(client, app):
    big = "x" * (app.config["MAX_CONTENT_LENGTH"] + 1)
    response = client.post("/login", data={"email": big, "password": "x"})
    assert_branded(response, 413)


# --------------------------------------------------------------------- 500

def test_500_branded_and_no_leak(client, no_propagate, monkeypatch):
    login(client)
    monkeypatch.setattr(app_module(), "get_expenses", boom)
    response = client.get("/profile/transactions")
    html = assert_branded(response, 500)
    assert SECRET not in html
    assert "Traceback" not in html


def test_500_survives_get_current_user_failure(client, no_propagate,
                                               monkeypatch):
    login(client)
    monkeypatch.setattr(app_module(), "get_current_user", boom)
    response = client.get("/profile")
    html = assert_branded(response, 500)
    assert SECRET not in html


# --------------------------------------------------------------- back link

def test_back_link_signed_out_is_landing(client):
    html = page(client.get("/does-not-exist"))
    assert 'href="/" class="btn-primary"' in html


def test_back_link_signed_in_is_transactions(client):
    login(client)
    html = page(client.get("/does-not-exist"))
    assert 'href="/profile/transactions" class="btn-primary"' in html


def test_signed_out_redirect_still_wins(client):
    response = client.get("/expenses/1/edit")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


# ------------------------------------------------------------------ content

def test_error_page_has_no_dollar_sign(client):
    assert "$" not in page(client.get("/does-not-exist"))


def test_error_css_has_no_hex_colours():
    css = (STATIC / "error.css").read_text(encoding="utf-8")
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", css)
