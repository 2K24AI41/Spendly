import pytest

from tests.conftest import fetch_users


def login(client, email="demo@spendly.com", password="demo123"):
    return client.post("/login", data={"email": email, "password": password})


def test_login_page_renders_with_url_for_action(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b'action="/login"' in resp.data


def test_demo_login_redirects_to_profile_and_sets_session(client):
    [demo] = fetch_users("demo@spendly.com")
    resp = login(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")
    with client.session_transaction() as s:
        assert s["user_id"] == demo["id"]
        assert s["user_name"] == demo["name"]


def test_login_normalises_email(client):
    resp = login(client, email="  Demo@Spendly.com ")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")


def test_registered_user_can_log_in(client):
    client.post("/register", data={
        "name": "Priya Nair", "email": "priya.nair@gmail.com",
        "password": "password123", "confirm_password": "password123",
    })
    [user] = fetch_users("priya.nair@gmail.com")
    resp = login(client, email="priya.nair@gmail.com", password="password123")
    assert resp.status_code == 302
    with client.session_transaction() as s:
        assert s["user_id"] == user["id"]


@pytest.mark.parametrize("email, password", [
    ("demo@spendly.com", "wrongpass"),
    ("nobody@spendly.com", "demo123"),
])
def test_invalid_credentials_rejected(client, email, password):
    resp = login(client, email=email, password=password)
    assert resp.status_code == 200
    assert b"Invalid email or password." in resp.data
    with client.session_transaction() as s:
        assert "user_id" not in s


@pytest.mark.parametrize("email, password", [
    ("", "demo123"),
    ("demo@spendly.com", ""),
    ("", ""),
])
def test_blank_fields_rejected(client, email, password):
    resp = login(client, email=email, password=password)
    assert resp.status_code == 200
    assert b"Email and password are required." in resp.data


def test_failed_login_keeps_email_not_password(client):
    resp = login(client, password="secretwrong")
    assert b'value="demo@spendly.com"' in resp.data
    assert b"secretwrong" not in resp.data


def test_navbar_when_signed_in(client):
    login(client)
    resp = client.get("/")
    assert b"Demo User" in resp.data
    assert b"Sign out" in resp.data
    assert b'href="/logout"' in resp.data
    assert b"Sign in" not in resp.data
    assert b"Get started" not in resp.data


def test_login_page_redirects_when_signed_in(client):
    login(client)
    resp = client.get("/login")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")


def test_logout_clears_session(client):
    login(client)
    resp = client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")
    with client.session_transaction() as s:
        assert len(s) == 0
    resp = client.get("/")
    assert b"Sign in" in resp.data
    assert b"Get started" in resp.data


def test_logout_when_signed_out(client):
    resp = client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")


def test_session_holds_only_id_and_name(client):
    login(client)
    with client.session_transaction() as s:
        assert set(s.keys()) == {"user_id", "user_name"}
