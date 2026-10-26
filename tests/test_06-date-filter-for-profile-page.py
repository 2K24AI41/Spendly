"""Tests for spec 06: date filter (?from=&to=) on GET /profile."""
import html
import re
from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

import database.db as db
from tests.conftest import add_expense_row, login, register_user

INVALID_MSG = "Invalid date ignored."
REVERSED_MSG = "Start date must be on or before end date."

# Demo seed: 8 expenses in the current month on days 1,3,5,8,11,14,17,20.
SEED_BY_DAY = {
    1: 250.0, 3: 120.0, 5: 1800.0, 8: 600.0,
    11: 450.0, 14: 1500.0, 17: 200.0, 20: 320.0,
}


def inr(amount):
    return f"₹{amount:,.2f}"


def seed_day(day):
    return f"{date.today():%Y-%m}-{day:02d}"


def get_page(client, **params):
    response = client.get("/profile", query_string=params)
    return response, response.get_data(as_text=True)


def hrefs(page):
    return [html.unescape(h) for h in re.findall(r'href="([^"]*)"', page)]


def hrefs_for_path(page, path):
    return [h for h in hrefs(page) if urlparse(h).path == path]


def demo_user_id():
    return db.get_user_by_email("demo@spendly.com")["id"]


def other_user_id():
    return db.get_user_by_email("other@example.com")["id"]


@pytest.fixture
def demo_client(client):
    login(client)
    return client


# ------------------------------------------------------------------ #
# Auth guard                                                          #
# ------------------------------------------------------------------ #

class TestAuthGuard:
    @pytest.mark.parametrize("query", [
        "", "?from=2020-01-01&to=2020-12-31", "?from=bad", "?from=2020-02-01&to=2020-01-01",
    ])
    def test_signed_out_redirects_to_login(self, client, query):
        response = client.get("/profile" + query)
        assert response.status_code == 302, "Signed-out request must redirect"
        assert urlparse(response.headers["Location"]).path == "/login"


# ------------------------------------------------------------------ #
# Unfiltered page unchanged                                           #
# ------------------------------------------------------------------ #

class TestUnfiltered:
    def test_unfiltered_shows_all_eight_expenses_and_total(self, demo_client):
        response, page = get_page(demo_client)
        assert response.status_code == 200
        assert "₹5,240.00" in page, "Unfiltered total should be ₹5,240.00"
        assert re.search(r"Expenses</span>\s*<span[^>]*>\s*8\s*<", page), \
            "Unfiltered expense count should be 8"

    def test_unfiltered_has_no_error_or_range_banner(self, demo_client):
        _, page = get_page(demo_client)
        assert INVALID_MSG not in page
        assert REVERSED_MSG not in page
        assert "Showing" not in page, "No active-range text without a filter"
        assert "No expenses in this range" not in page

    def test_empty_params_behave_as_unfiltered(self, demo_client):
        response, page = get_page(demo_client, **{"from": "", "to": ""})
        assert response.status_code == 200
        assert "₹5,240.00" in page
        assert INVALID_MSG not in page

    def test_unfiltered_recent_expenses_limited_to_most_recent(self, demo_client):
        _, page = get_page(demo_client)
        assert "Dinner out" in page, "Most recent expense should be listed"
        for outside in ("Groceries", "Metro card recharge", "Electricity bill"):
            assert outside not in page, f"{outside} falls outside the recent 5"


# ------------------------------------------------------------------ #
# Happy path / bounds                                                 #
# ------------------------------------------------------------------ #

class TestFiltering:
    def test_closed_range_narrows_total_and_count(self, demo_client):
        response, page = get_page(
            demo_client, **{"from": seed_day(5), "to": seed_day(14)})
        assert response.status_code == 200
        assert inr(1800 + 600 + 450 + 1500) in page
        assert "₹5,240.00" not in page
        assert re.search(r"Expenses</span>\s*<span[^>]*>\s*4\s*<", page)

    def test_range_narrows_recent_expenses(self, demo_client):
        _, page = get_page(
            demo_client, **{"from": seed_day(5), "to": seed_day(14)})
        for present in ("Electricity bill", "Pharmacy", "Movie tickets", "New shoes"):
            assert present in page, f"{present} is inside the range"
        for absent in ("Groceries", "Metro card recharge", "Miscellaneous", "Dinner out"):
            assert absent not in page, f"{absent} is outside the range"

    def test_range_narrows_category_totals(self, demo_client):
        _, page = get_page(
            demo_client, **{"from": seed_day(5), "to": seed_day(14)})
        assert "Bills" in page and "Shopping" in page
        assert "Transport" not in page, "Transport expense is outside the range"
        assert "Other" not in page, "Other expense is outside the range"

    def test_top_category_follows_range(self, demo_client):
        _, page = get_page(
            demo_client, **{"from": seed_day(14), "to": seed_day(20)})
        # In range: Shopping 1500, Other 200, Food 320 -> Shopping on top.
        match = re.search(
            r"Top category</span>\s*<span[^>]*>\s*([^<]+?)\s*</span>", page)
        assert match and match.group(1) == "Shopping"

    def test_from_bound_is_inclusive(self, demo_client):
        _, page = get_page(
            demo_client, **{"from": seed_day(5), "to": seed_day(5)})
        assert inr(1800) in page, "Expense dated exactly on from/to is counted"
        assert "Electricity bill" in page

    def test_exact_from_date_counted(self, demo_client):
        _, page = get_page(
            demo_client, **{"from": seed_day(14), "to": seed_day(17)})
        assert inr(1500 + 200) in page

    def test_exact_to_date_counted(self, demo_client):
        _, page = get_page(
            demo_client, **{"from": seed_day(11), "to": seed_day(14)})
        assert inr(450 + 1500) in page

    def test_day_just_outside_bounds_excluded(self, demo_client):
        # The day-5 expense sits just before a 6..7 range, so it is excluded.
        _, page = get_page(
            demo_client, **{"from": seed_day(6), "to": seed_day(7)})
        assert "Electricity bill" not in page
        assert inr(0) in page

    def test_custom_expenses_on_exact_boundaries(self, demo_client):
        uid = demo_user_id()
        add_expense_row(uid, 11.0, "Food", "2020-03-01", "edge-start")
        add_expense_row(uid, 22.0, "Food", "2020-03-31", "edge-end")
        add_expense_row(uid, 99.0, "Food", "2020-02-29", "before-range")
        add_expense_row(uid, 88.0, "Food", "2020-04-01", "after-range")
        _, page = get_page(demo_client, **{"from": "2020-03-01", "to": "2020-03-31"})
        assert inr(33) in page
        assert "edge-start" in page and "edge-end" in page
        assert "before-range" not in page and "after-range" not in page

    def test_from_only_is_open_ended(self, demo_client):
        _, page = get_page(demo_client, **{"from": seed_day(14)})
        assert inr(1500 + 200 + 320) in page
        assert re.search(r"Expenses</span>\s*<span[^>]*>\s*3\s*<", page)

    def test_to_only_is_open_ended(self, demo_client):
        _, page = get_page(demo_client, **{"to": seed_day(3)})
        assert inr(250 + 120) in page
        assert re.search(r"Expenses</span>\s*<span[^>]*>\s*2\s*<", page)

    def test_full_month_range_equals_all_demo_data(self, demo_client):
        _, page = get_page(
            demo_client, **{"from": seed_day(1), "to": seed_day(20)})
        assert "₹5,240.00" in page

    def test_active_range_text_shown(self, demo_client):
        _, page = get_page(
            demo_client, **{"from": "2020-01-05", "to": "2020-01-20"})
        assert "Showing" in page
        assert "05 Jan 2020" in page and "20 Jan 2020" in page

    def test_sql_injection_in_dates_is_safe(self, demo_client):
        response, page = get_page(
            demo_client, **{"from": "2020-01-01' OR '1'='1", "to": "'; DROP TABLE expenses;--"})
        assert response.status_code == 200
        assert INVALID_MSG in page
        # Table must still exist and page unfiltered.
        _, page2 = get_page(demo_client)
        assert "₹5,240.00" in page2


# ------------------------------------------------------------------ #
# Form keeps dates                                                    #
# ------------------------------------------------------------------ #

class TestFormState:
    def test_form_keeps_selected_dates(self, demo_client):
        _, page = get_page(
            demo_client, **{"from": "2020-01-05", "to": "2020-02-10"})
        assert 'name="from"' in page and 'name="to"' in page
        assert 'value="2020-01-05"' in page
        assert 'value="2020-02-10"' in page

    def test_form_submits_to_profile_via_get(self, demo_client):
        _, page = get_page(demo_client)
        form = re.search(r"<form[^>]*>", page).group(0)
        assert 'method="get"' in form.lower()
        assert 'action="/profile"' in form

    def test_form_has_no_category_select(self, demo_client):
        _, page = get_page(demo_client)
        assert 'name="category"' not in page

    def test_unfiltered_form_dates_empty(self, demo_client):
        _, page = get_page(demo_client)
        for name in ("from", "to"):
            field = re.search(r'<input[^>]*name="%s"[^>]*>' % name, page)
            assert field, f"'{name}' input missing"
            assert 'value=""' in field.group(0), f"'{name}' should start empty"


# ------------------------------------------------------------------ #
# Presets                                                             #
# ------------------------------------------------------------------ #

def preset_hrefs(page):
    """Map preset label -> parsed query dict from hrefs on the page."""
    found = {}
    for label in ("This month", "Last 30 days", "This year", "All time"):
        match = re.search(
            r'<a[^>]*href="([^"]*)"[^>]*>\s*' + re.escape(label) + r"\s*</a>", page)
        assert match, f"Preset link '{label}' missing"
        url = urlparse(html.unescape(match.group(1)))
        assert url.path == "/profile", f"{label} must link to /profile"
        found[label] = parse_qs(url.query)
    return found


class TestPresets:
    def test_all_four_presets_present(self, demo_client):
        _, page = get_page(demo_client)
        assert set(preset_hrefs(page)) == {
            "This month", "Last 30 days", "This year", "All time"}

    def test_this_month_preset_range(self, demo_client):
        _, page = get_page(demo_client)
        today = date.today()
        query = preset_hrefs(page)["This month"]
        assert query["from"] == [today.replace(day=1).isoformat()]
        assert query["to"] == [today.isoformat()]

    def test_last_30_days_preset_range(self, demo_client):
        _, page = get_page(demo_client)
        today = date.today()
        query = preset_hrefs(page)["Last 30 days"]
        assert query["from"] == [(today - timedelta(days=29)).isoformat()]
        assert query["to"] == [today.isoformat()]

    def test_this_year_preset_range(self, demo_client):
        _, page = get_page(demo_client)
        today = date.today()
        query = preset_hrefs(page)["This year"]
        assert query["from"] == [today.replace(month=1, day=1).isoformat()]
        assert query["to"] == [today.isoformat()]

    def test_all_time_preset_clears_filter(self, demo_client):
        _, page = get_page(
            demo_client, **{"from": "2020-01-01", "to": "2020-01-31"})
        assert preset_hrefs(page)["All time"] == {}, \
            "All time must link to /profile without from/to"

    def test_following_all_time_link_restores_full_data(self, demo_client):
        _, page = get_page(demo_client, **{"from": "2020-01-01", "to": "2020-01-31"})
        match = re.search(
            r'<a[^>]*href="([^"]*)"[^>]*>\s*All time\s*</a>', page)
        response = demo_client.get(html.unescape(match.group(1)))
        assert response.status_code == 200
        assert "₹5,240.00" in response.get_data(as_text=True)

    def test_following_this_month_link_returns_demo_data(self, demo_client):
        _, page = get_page(demo_client)
        match = re.search(
            r'<a[^>]*href="([^"]*)"[^>]*>\s*This month\s*</a>', page)
        response = demo_client.get(html.unescape(match.group(1)))
        body = response.get_data(as_text=True)
        assert response.status_code == 200
        today = date.today()
        expected = sum(v for d, v in SEED_BY_DAY.items() if d <= today.day)
        assert inr(expected) in body

    def test_preset_marked_active_when_selected(self, demo_client):
        today = date.today()
        _, page = get_page(
            demo_client, **{"from": today.replace(day=1).isoformat(),
                            "to": today.isoformat()})
        match = re.search(
            r'<a[^>]*class="([^"]*)"[^>]*>\s*This month\s*</a>', page)
        assert match and "active" in match.group(1).split()


# ------------------------------------------------------------------ #
# Invalid input                                                       #
# ------------------------------------------------------------------ #

class TestInvalidInput:
    @pytest.mark.parametrize("value", [
        "not-a-date", "2020-13-01", "2020-02-30", "01-01-2020", "2020/01/01", "abc123",
    ])
    def test_invalid_from_ignored_with_message(self, demo_client, value):
        response, page = get_page(demo_client, **{"from": value})
        assert response.status_code == 200
        assert INVALID_MSG in page
        assert "₹5,240.00" in page, "Invalid date is ignored, so no narrowing"

    @pytest.mark.parametrize("value", ["not-a-date", "2020-13-01", "2020-02-30"])
    def test_invalid_to_ignored_with_message(self, demo_client, value):
        response, page = get_page(demo_client, **{"to": value})
        assert response.status_code == 200
        assert INVALID_MSG in page
        assert "₹5,240.00" in page

    def test_invalid_from_with_valid_to_keeps_valid_one(self, demo_client):
        response, page = get_page(
            demo_client, **{"from": "garbage", "to": seed_day(3)})
        assert response.status_code == 200
        assert INVALID_MSG in page
        assert inr(250 + 120) in page, "Valid 'to' still applies"

    def test_both_invalid(self, demo_client):
        response, page = get_page(demo_client, **{"from": "x", "to": "y"})
        assert response.status_code == 200
        assert INVALID_MSG in page
        assert "₹5,240.00" in page

    def test_reversed_range_ignores_both_with_message(self, demo_client):
        response, page = get_page(
            demo_client, **{"from": seed_day(14), "to": seed_day(5)})
        assert response.status_code == 200
        assert REVERSED_MSG in page
        assert "₹5,240.00" in page, "Both dates ignored -> all-time totals"

    def test_reversed_range_form_does_not_keep_dates(self, demo_client):
        _, page = get_page(
            demo_client, **{"from": "2021-05-05", "to": "2021-01-01"})
        assert 'value="2021-05-05"' not in page
        assert 'value="2021-01-01"' not in page

    def test_valid_range_has_no_error_message(self, demo_client):
        _, page = get_page(
            demo_client, **{"from": seed_day(1), "to": seed_day(5)})
        assert INVALID_MSG not in page and REVERSED_MSG not in page

    def test_same_from_and_to_is_not_reversed(self, demo_client):
        _, page = get_page(
            demo_client, **{"from": seed_day(8), "to": seed_day(8)})
        assert REVERSED_MSG not in page
        assert inr(600) in page

    def test_very_long_value_does_not_crash(self, demo_client):
        response, page = get_page(demo_client, **{"from": "9" * 5000})
        assert response.status_code == 200
        assert INVALID_MSG in page

    def test_whitespace_only_values_treated_as_empty(self, demo_client):
        response, page = get_page(demo_client, **{"from": "   ", "to": "  "})
        assert response.status_code == 200
        assert INVALID_MSG not in page
        assert "₹5,240.00" in page


# ------------------------------------------------------------------ #
# Empty range                                                         #
# ------------------------------------------------------------------ #

class TestEmptyRange:
    def test_empty_range_shows_zero_and_empty_state(self, demo_client):
        response, page = get_page(
            demo_client, **{"from": "2001-01-01", "to": "2001-12-31"})
        assert response.status_code == 200
        assert "₹0.00" in page
        assert "No expenses in this range" in page
        assert "₹5,240.00" not in page

    def test_empty_range_count_is_zero(self, demo_client):
        _, page = get_page(
            demo_client, **{"from": "2001-01-01", "to": "2001-12-31"})
        assert re.search(r"Expenses</span>\s*<span[^>]*>\s*0\s*<", page)

    def test_empty_range_hides_expense_rows(self, demo_client):
        _, page = get_page(
            demo_client, **{"from": "2001-01-01", "to": "2001-12-31"})
        assert "Electricity bill" not in page
        assert "No expenses yet" not in page, \
            "Filtered-empty state differs from brand-new-user state"

    def test_future_open_ended_range_is_empty(self, demo_client):
        response, page = get_page(demo_client, **{"from": "2999-01-01"})
        assert response.status_code == 200
        assert "₹0.00" in page
        assert "No expenses in this range" in page

    def test_user_with_no_expenses_unfiltered_shows_no_expenses_yet(self, client):
        register_user(client, email="empty@example.com")
        login(client, email="empty@example.com", password="password123")
        response, page = get_page(client)
        assert response.status_code == 200
        assert "₹0.00" in page
        assert "No expenses yet" in page


# ------------------------------------------------------------------ #
# Links keep the range                                                #
# ------------------------------------------------------------------ #

class TestLinksKeepRange:
    SUBPAGES = ["/profile/transactions", "/profile/summary", "/profile/categories"]

    @pytest.mark.parametrize("path", SUBPAGES)
    def test_subpage_links_carry_range(self, demo_client, path):
        _, page = get_page(
            demo_client, **{"from": "2020-01-05", "to": "2020-02-10"})
        links = hrefs_for_path(page, path)
        assert links, f"No link to {path} found"
        for link in links:
            query = parse_qs(urlparse(link).query)
            assert query.get("from") == ["2020-01-05"], f"{link} lost 'from'"
            assert query.get("to") == ["2020-02-10"], f"{link} lost 'to'"

    @pytest.mark.parametrize("path", SUBPAGES)
    def test_subpage_links_carry_open_ended_from(self, demo_client, path):
        _, page = get_page(demo_client, **{"from": "2020-01-05"})
        for link in hrefs_for_path(page, path):
            query = parse_qs(urlparse(link).query)
            assert query.get("from") == ["2020-01-05"]
            assert "to" not in query

    @pytest.mark.parametrize("path", SUBPAGES)
    def test_subpage_links_carry_open_ended_to(self, demo_client, path):
        _, page = get_page(demo_client, **{"to": "2020-02-10"})
        for link in hrefs_for_path(page, path):
            query = parse_qs(urlparse(link).query)
            assert query.get("to") == ["2020-02-10"]
            assert "from" not in query

    @pytest.mark.parametrize("path", SUBPAGES)
    def test_subpage_links_have_no_range_when_unfiltered(self, demo_client, path):
        _, page = get_page(demo_client)
        links = hrefs_for_path(page, path)
        assert links, f"No link to {path} found"
        for link in links:
            query = parse_qs(urlparse(link).query)
            assert "from" not in query and "to" not in query

    @pytest.mark.parametrize("path", SUBPAGES)
    def test_subpage_links_drop_ignored_dates(self, demo_client, path):
        _, page = get_page(
            demo_client, **{"from": seed_day(14), "to": seed_day(5)})
        for link in hrefs_for_path(page, path):
            query = parse_qs(urlparse(link).query)
            assert "from" not in query and "to" not in query

    @pytest.mark.parametrize("path", SUBPAGES)
    def test_following_subpage_link_applies_range(self, demo_client, path):
        uid = demo_user_id()
        add_expense_row(uid, 4321.0, "Food", "2020-06-15", "range-marker")
        _, page = get_page(
            demo_client, **{"from": "2020-06-01", "to": "2020-06-30"})
        link = hrefs_for_path(page, path)[0]
        response = demo_client.get(link)
        body = response.get_data(as_text=True)
        assert response.status_code == 200
        assert "₹4,321.00" in body
        assert "₹5,240.00" not in body


# ------------------------------------------------------------------ #
# Cross-user isolation                                                #
# ------------------------------------------------------------------ #

class TestIsolation:
    def _setup_other(self, client):
        register_user(client, name="Other Person", email="other@example.com")
        uid = other_user_id()
        add_expense_row(uid, 7777.77, "Travel", "2020-06-15", "other-secret")
        return uid

    def test_demo_does_not_see_other_users_expenses_in_range(self, client):
        self._setup_other(client)
        login(client)
        response, page = get_page(
            client, **{"from": "2020-01-01", "to": "2020-12-31"})
        assert response.status_code == 200
        assert "other-secret" not in page
        assert "7,777.77" not in page
        assert "₹0.00" in page

    def test_demo_unfiltered_does_not_include_other_user(self, client):
        self._setup_other(client)
        login(client)
        _, page = get_page(client)
        assert "other-secret" not in page
        assert "₹5,240.00" in page

    def test_other_user_sees_only_own_expenses(self, client):
        self._setup_other(client)
        login(client, email="other@example.com", password="password123")
        _, page = get_page(
            client, **{"from": "2020-01-01", "to": "2020-12-31"})
        assert "other-secret" in page
        assert "₹7,777.77" in page
        assert "Electricity bill" not in page

    def test_other_user_range_over_demo_dates_is_empty(self, client):
        self._setup_other(client)
        login(client, email="other@example.com", password="password123")
        _, page = get_page(
            client, **{"from": seed_day(1), "to": seed_day(20)})
        assert "₹0.00" in page
        assert "Electricity bill" not in page
        assert "No expenses in this range" in page


# ------------------------------------------------------------------ #
# Currency and template landmarks                                     #
# ------------------------------------------------------------------ #

class TestPageContent:
    @pytest.mark.parametrize("params", [
        {},
        {"from": "2020-01-01", "to": "2020-12-31"},
        {"from": "2001-01-01", "to": "2001-02-01"},
        {"from": "bad"},
        {"from": "2021-05-05", "to": "2021-01-01"},
    ])
    def test_no_dollar_sign_on_page(self, demo_client, params):
        response, page = get_page(demo_client, **params)
        assert response.status_code == 200
        assert "$" not in page, "Currency must be INR, never $"

    def test_rupee_symbol_present(self, demo_client):
        _, page = get_page(demo_client)
        assert "₹" in page

    def test_page_extends_base_and_shows_user(self, demo_client):
        _, page = get_page(demo_client)
        assert "Demo User" in page
        assert "demo@spendly.com" in page
        assert "<html" in page.lower()

    def test_nav_links_to_subpages_exist(self, demo_client):
        _, page = get_page(demo_client)
        for path in ("/profile/transactions", "/profile/summary",
                     "/profile/categories"):
            assert hrefs_for_path(page, path), f"Missing link to {path}"

    def test_post_not_allowed(self, demo_client):
        response = demo_client.post("/profile")
        assert response.status_code == 405
