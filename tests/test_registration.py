from pathlib import Path

import pytest
from werkzeug.security import check_password_hash

from tests.conftest import fetch_users

TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "register.html"


def register(client, name="Priya Nair", email="priya.nair@gmail.com",
             password="password123", confirm_password=None):
    if confirm_password is None:
        confirm_password = password
    return client.post("/register", data={
        "name": name, "email": email, "password": password,
        "confirm_password": confirm_password,
    })


def test_get_register_shows_form(client):
    resp = client.get("/register")
    assert resp.status_code == 200
    assert b'<form method="POST" action="/register">' in resp.data
    assert "url_for('register')" in TEMPLATE.read_text(encoding="utf-8")


def test_valid_signup_redirects_to_login(client):
    resp = register(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_password_is_hashed(client):
    register(client)
    [user] = fetch_users("priya.nair@gmail.com")
    assert user["password_hash"].startswith(("scrypt:", "pbkdf2:"))
    assert user["password_hash"] != "password123"
    assert check_password_hash(user["password_hash"], "password123")


def test_email_and_name_are_normalised(client):
    register(client, name="  Priya Nair ", email="  Priya.Nair@Gmail.com ")
    [user] = fetch_users("priya.nair@gmail.com")
    assert user["name"] == "Priya Nair"


@pytest.mark.parametrize("email", ["demo@spendly.com", " DEMO@Spendly.com "])
def test_duplicate_email_rejected(client, email):
    before = len(fetch_users())
    resp = register(client, email=email)
    assert resp.status_code == 200
    assert b"An account with this email already exists." in resp.data
    assert len(fetch_users()) == before


@pytest.mark.parametrize("field, value", [
    ("name", ""), ("name", "   "),
    ("email", ""), ("email", "   "),
    ("password", ""),
    ("confirm_password", ""),
])
def test_blank_fields_rejected(client, field, value):
    before = len(fetch_users())
    resp = register(client, **{field: value})
    assert resp.status_code == 200
    assert b"All fields are required." in resp.data
    assert len(fetch_users()) == before


@pytest.mark.parametrize("email", ["priya", "priya@gmail", "@gmail.com",
                                   "priya@", "priya@.com", "priya@gmail."])
def test_invalid_email_rejected(client, email):
    resp = register(client, email=email)
    assert resp.status_code == 200
    assert b"Please enter a valid email address." in resp.data
    assert fetch_users("priya.nair@gmail.com") == []


def test_short_password_rejected(client):
    resp = register(client, password="abcdefg")
    assert resp.status_code == 200
    assert b"Password must be at least 8 characters." in resp.data
    assert fetch_users("priya.nair@gmail.com") == []


def test_mismatched_passwords_rejected(client):
    resp = register(client, password="password123",
                    confirm_password="password321")
    assert resp.status_code == 200
    assert b"Passwords do not match." in resp.data
    assert fetch_users("priya.nair@gmail.com") == []


def test_form_has_confirm_password_field(client):
    resp = client.get("/register")
    assert b'name="confirm_password"' in resp.data


def test_eight_char_password_accepted(client):
    resp = register(client, password="abcdefgh")
    assert resp.status_code == 302


def test_form_keeps_values_after_error(client):
    resp = register(client, password="secret7")
    assert b'value="Priya Nair"' in resp.data
    assert b'value="priya.nair@gmail.com"' in resp.data
    assert b"secret7" not in resp.data


@pytest.mark.parametrize("path", ["/", "/login", "/terms", "/privacy"])
def test_existing_pages_still_render(client, path):
    assert client.get(path).status_code == 200
