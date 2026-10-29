import re

from tests.conftest import login

NAV_ACTIVE = re.compile(r'<a href="/analytics" class="active"')


# ---- Auth ---- #

def test_analytics_redirects_to_login_when_signed_out(client):
    resp = client.get("/analytics")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_analytics_missing_user_clears_session_and_redirects(client):
    with client.session_transaction() as s:
        s["user_id"] = 99999
        s["user_name"] = "Ghost"
    resp = client.get("/analytics")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    with client.session_transaction() as s:
        assert len(s) == 0


# ---- Page ---- #

def test_analytics_renders_coming_soon_when_signed_in(client):
    login(client)
    resp = client.get("/analytics")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Advanced Analytics" in html
    assert "Coming Soon" in html
    assert "We're crafting something special" in html


# ---- Navbar ---- #

def test_navbar_shows_analytics_link_when_signed_in(client):
    login(client)
    html = client.get("/profile").get_data(as_text=True)
    assert 'href="/analytics"' in html
    assert not NAV_ACTIVE.search(html)


def test_navbar_hides_analytics_link_when_signed_out(client):
    for path in ("/", "/login", "/register"):
        html = client.get(path).get_data(as_text=True)
        assert "/analytics" not in html


def test_navbar_highlights_analytics_on_analytics_page(client):
    login(client)
    html = client.get("/analytics").get_data(as_text=True)
    assert NAV_ACTIVE.search(html)
    assert 'aria-current="page"' in html


# ---- Styling ---- #

def test_analytics_css_has_no_hex_colours():
    with open("static/css/analytics.css", encoding="utf-8") as f:
        assert not re.search(r"#[0-9a-fA-F]{3,8}\b", f.read())
