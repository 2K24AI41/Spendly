"""Tests for Step 8 - Edit Expense (spec: .claude/specs/08-edit-expense.md)."""
import re

import pytest

import database.db as db
from tests.conftest import add_expense_row, fetch_users, login, register_user

CATEGORIES = [
    "Food", "Transport", "Bills", "Health",
    "Entertainment", "Shopping", "Other",
]
ADD_URL = "/expenses/add"
TOKEN_RE = re.compile(r'name="csrf_token" value="([0-9a-f]+)"')
ORIG_DESC = "Original edit marker"
OTHER_EMAIL = "other@example.com"
OTHER_PW = "password123"


# ------------------------------------------------------------------ helpers

def edit_url(expense_id):
    return f"/expenses/{expense_id}/edit"


def get_token(client):
    """Session-wide CSRF token, read from the add-expense form."""
    page = client.get(ADD_URL).get_data(as_text=True)
    match = TOKEN_RE.search(page)
    assert match, "Expected a csrf_token hidden field on the add form"
    return match.group(1)


def demo_id():
    return fetch_users("demo@spendly.com")[0]["id"]


def make_expense(user_id=None, amount=100.0, category="Food",
                 date="2099-01-01", description=ORIG_DESC):
    """Insert an expense and return its id (found via the newest row)."""
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


def valid_form(**overrides):
    data = {
        "amount": "300.75",
        "category": "Transport",
        "date": "2025-06-15",
        "description": "Edited note",
    }
    data.update(overrides)
    return data


def post_edit(client, expense_id, token=None, **overrides):
    """POST to the edit form with a valid token unless one is supplied."""
    data = valid_form(**overrides)
    data["csrf_token"] = get_token(client) if token is None else token
    return client.post(edit_url(expense_id), data=data)


def snapshot(expense_id):
    return tuple(fetch_row(expense_id))


def logged_in_with_expense(client, **kwargs):
    login(client)
    return make_expense(**kwargs)


def login_as_other(client):
    client.get("/logout")
    register_user(client, email=OTHER_EMAIL, password=OTHER_PW)
    login(client, email=OTHER_EMAIL, password=OTHER_PW)


# ---------------------------------------------------------------- auth guard
# DoD: signed out, GET and POST redirect to /login

def test_get_redirects_to_login_when_signed_out(client):
    eid = make_expense()
    resp = client.get(edit_url(eid))
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_post_redirects_to_login_when_signed_out_and_row_unchanged(client):
    eid = make_expense()
    before = snapshot(eid)
    resp = client.post(edit_url(eid), data=valid_form())
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    assert snapshot(eid) == before, "Signed-out POST must not modify the row"


def test_signed_out_get_for_missing_id_redirects_not_404(client):
    resp = client.get(edit_url(999999))
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


# ------------------------------------------------------------------ GET form
# DoD: pre-filled form, all 7 categories

def test_get_own_expense_renders_prefilled_form(client):
    eid = logged_in_with_expense(
        client, amount=250.5, category="Health",
        date="2025-03-04", description="Prefill marker")
    resp = client.get(edit_url(eid))
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "<form" in html
    for name in ("amount", "category", "date", "description"):
        assert f'name="{name}"' in html, f"Missing field {name}"
    assert 'value="250.5' in html, "Amount should be pre-filled"
    assert 'value="2025-03-04"' in html, "Date should be pre-filled"
    assert "Prefill marker" in html, "Description should be pre-filled"
    assert re.search(
        r'<option[^>]*value="Health"[^>]*selected|'
        r'<option[^>]*selected[^>]*value="Health"', html
    ), "Stored category should be selected"


def test_get_form_lists_all_seven_categories(client):
    eid = logged_in_with_expense(client)
    html = client.get(edit_url(eid)).get_data(as_text=True)
    for cat in CATEGORIES:
        assert f'value="{cat}"' in html, f"Category {cat} missing from select"


def test_get_form_contains_csrf_token(client):
    eid = logged_in_with_expense(client)
    html = client.get(edit_url(eid)).get_data(as_text=True)
    assert TOKEN_RE.search(html), "Hidden csrf_token field expected"


def test_get_form_has_cancel_link_to_transactions(client):
    eid = logged_in_with_expense(client)
    html = client.get(edit_url(eid)).get_data(as_text=True)
    assert 'href="/profile/transactions"' in html


def test_get_form_has_no_dollar_sign(client):
    eid = logged_in_with_expense(client)
    html = client.get(edit_url(eid)).get_data(as_text=True)
    assert "$" not in html


def test_get_form_has_no_inline_style_block(client):
    eid = logged_in_with_expense(client)
    html = client.get(edit_url(eid)).get_data(as_text=True)
    assert "<style" not in html, "Page styles belong in a .css file"


def test_get_does_not_modify_row(client):
    eid = logged_in_with_expense(client)
    before = snapshot(eid)
    client.get(edit_url(eid))
    assert snapshot(eid) == before


# --------------------------------------------------- 404: missing / not owned
# DoD: non-existent id -> 404; other user's expense -> 404, unchanged

def test_get_nonexistent_id_returns_404(client):
    login(client)
    assert client.get(edit_url(999999)).status_code == 404


def test_post_nonexistent_id_returns_404(client):
    login(client)
    resp = post_edit(client, 999999)
    assert resp.status_code == 404


def test_get_other_users_expense_returns_404(client):
    eid = make_expense()  # owned by demo
    login_as_other(client)
    assert client.get(edit_url(eid)).status_code == 404


def test_post_other_users_expense_returns_404_and_row_unchanged(client):
    eid = make_expense()
    before = snapshot(eid)
    login_as_other(client)
    resp = post_edit(client, eid)
    assert resp.status_code == 404
    assert snapshot(eid) == before, "Foreign expense must be untouched"


def test_other_user_and_missing_id_give_same_response(client):
    eid = make_expense()
    login_as_other(client)
    foreign = client.get(edit_url(eid))
    missing = client.get(edit_url(999999))
    assert foreign.status_code == missing.status_code == 404
    assert foreign.get_data() == missing.get_data(), (
        "404 bodies must match so ids cannot be probed")


@pytest.mark.parametrize("bad_id", ["abc", "1.5", "-1x"])
def test_non_integer_id_returns_404(client, bad_id):
    login(client)
    assert client.get(f"/expenses/{bad_id}/edit").status_code == 404


def test_post_other_users_expense_does_not_leak_data(client):
    eid = make_expense(description="Secret demo note")
    login_as_other(client)
    resp = post_edit(client, eid)
    assert b"Secret demo note" not in resp.data


# ------------------------------------------------------------- happy path
# DoD: valid changes update the row and redirect; no new row; id/owner same

def test_valid_post_redirects_to_transactions(client):
    eid = logged_in_with_expense(client)
    resp = post_edit(client, eid)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile/transactions")


def test_valid_post_updates_all_four_fields(client):
    eid = logged_in_with_expense(client)
    post_edit(client, eid)
    row = fetch_row(eid)
    assert row["amount"] == pytest.approx(300.75)
    assert row["category"] == "Transport"
    assert row["date"] == "2025-06-15"
    assert row["description"] == "Edited note"


def test_edit_does_not_create_row_or_change_id_and_owner(client):
    eid = logged_in_with_expense(client)
    before_count = count_expenses()
    post_edit(client, eid)
    assert count_expenses() == before_count, "Edit must not insert a row"
    row = fetch_row(eid)
    assert row is not None and row["id"] == eid
    assert row["user_id"] == demo_id()


def test_edit_does_not_touch_other_expenses(client):
    login(client)
    first = make_expense(description="Neighbour A", amount=11)
    target = make_expense(description="Target row", amount=22)
    neighbour_before = snapshot(first)
    post_edit(client, target)
    assert snapshot(first) == neighbour_before


def test_edited_values_appear_on_transactions_with_rupee(client):
    eid = logged_in_with_expense(client)
    resp = client.post(
        edit_url(eid),
        data=valid_form(csrf_token=get_token(client)),
        follow_redirects=True,
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Edited note" in html
    assert "₹300.75" in html
    assert ORIG_DESC not in html, "Old description should be gone"
    assert "$" not in html


def test_edit_reflected_in_profile_totals(client):
    eid = logged_in_with_expense(client, amount=100)
    before = client.get("/profile").get_data(as_text=True)
    assert "₹5,340.00" in before, "Seed total 5,240 + 100"
    post_edit(client, eid, amount="300")
    after = client.get("/profile").get_data(as_text=True)
    assert "₹5,540.00" in after, "Total should grow by the 200 difference"
    assert "₹5,340.00" not in after


def test_edit_reflected_in_profile_recent_list(client):
    eid = logged_in_with_expense(client)  # 2099 date -> in 5 most recent
    post_edit(client, eid, date="2099-02-02", description="Recent edited")
    html = client.get("/profile").get_data(as_text=True)
    assert "Recent edited" in html
    assert ORIG_DESC not in html


def test_edit_reflected_in_categories_page(client):
    eid = logged_in_with_expense(client, category="Food", amount=100)
    before = client.get("/profile/categories").get_data(as_text=True)
    post_edit(client, eid, category="Shopping", amount="999")
    after = client.get("/profile/categories").get_data(as_text=True)
    assert before != after, "Categories page should reflect the edit"
    # Seeded Shopping (₹1,500.00) + the edited 999; grand total 5,240 + 999.
    assert "₹2,499.00" in after, "Shopping total should include the edit"
    assert "₹6,239.00" in after, "Grand total should include the edit"


def test_edit_reflected_in_summary_page(client):
    eid = logged_in_with_expense(client, amount=100)
    before = client.get("/profile/summary").get_data(as_text=True)
    post_edit(client, eid, amount="4000")
    after = client.get("/profile/summary").get_data(as_text=True)
    assert before != after


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_category_is_accepted(client, category):
    eid = logged_in_with_expense(client, category="Food")
    resp = post_edit(client, eid, category=category)
    assert resp.status_code == 302
    assert fetch_row(eid)["category"] == category


@pytest.mark.parametrize("amount, expected", [
    ("100", 100.0),
    ("0.01", 0.01),
    ("12.5", 12.5),
    ("10000000", 10000000.0),
])
def test_valid_amounts_are_accepted(client, amount, expected):
    eid = logged_in_with_expense(client)
    resp = post_edit(client, eid, amount=amount)
    assert resp.status_code == 302
    assert fetch_row(eid)["amount"] == pytest.approx(expected)


def test_resubmitting_unchanged_values_succeeds(client):
    eid = logged_in_with_expense(
        client, amount=50.0, category="Bills",
        date="2025-01-02", description="Same")
    resp = post_edit(client, eid, amount="50", category="Bills",
                     date="2025-01-02", description="Same")
    assert resp.status_code == 302
    assert fetch_row(eid)["description"] == "Same"


# ------------------------------------------------------ description handling
# DoD: >200 rejected; clearing saves as empty (NULL)

def test_clearing_description_stores_null(client):
    eid = logged_in_with_expense(client)
    resp = post_edit(client, eid, description="")
    assert resp.status_code == 302
    assert fetch_row(eid)["description"] is None


def test_whitespace_description_stores_null(client):
    eid = logged_in_with_expense(client)
    post_edit(client, eid, description="     ")
    assert fetch_row(eid)["description"] is None


def test_missing_description_field_clears_it(client):
    eid = logged_in_with_expense(client)
    data = valid_form(csrf_token=get_token(client))
    del data["description"]
    resp = client.post(edit_url(eid), data=data)
    assert resp.status_code == 302
    assert fetch_row(eid)["description"] is None


def test_description_is_trimmed(client):
    eid = logged_in_with_expense(client)
    post_edit(client, eid, description="  padded note  ")
    assert fetch_row(eid)["description"] == "padded note"


def test_description_of_200_chars_accepted(client):
    eid = logged_in_with_expense(client)
    text = "y" * 200
    resp = post_edit(client, eid, description=text)
    assert resp.status_code == 302
    assert fetch_row(eid)["description"] == text


def test_description_of_201_chars_rejected(client):
    eid = logged_in_with_expense(client)
    before = snapshot(eid)
    resp = post_edit(client, eid, description="x" * 201)
    assert resp.status_code == 200
    assert "error" in resp.get_data(as_text=True).lower()
    assert snapshot(eid) == before


# ------------------------------------------------------------ validation
# DoD: bad amount / category / date -> 200 + error, row unchanged

def assert_rejected(client, eid, **overrides):
    before = snapshot(eid)
    count = count_expenses()
    resp = post_edit(client, eid, **overrides)
    assert resp.status_code == 200, "Invalid input must re-render with 200"
    assert snapshot(eid) == before, "Invalid input must not change the row"
    assert count_expenses() == count
    html = resp.get_data(as_text=True)
    assert "<form" in html, "Form should be re-rendered"
    assert "error" in html.lower(), "An error message should be shown"
    return html


@pytest.mark.parametrize("amount", [
    "", "0", "0.00", "-5", "-0.01", "abc", "12abc", "1.234", "10.999",
    "10000000.01", "10000001", "99999999999",
    "nan", "NaN", "inf", "-inf", "Infinity",
])
def test_invalid_amount_rejected(client, amount):
    eid = logged_in_with_expense(client)
    assert_rejected(client, eid, amount=amount)


def test_missing_amount_field_rejected(client):
    eid = logged_in_with_expense(client)
    before = snapshot(eid)
    data = valid_form(csrf_token=get_token(client))
    del data["amount"]
    resp = client.post(edit_url(eid), data=data)
    assert resp.status_code == 200
    assert snapshot(eid) == before


@pytest.mark.parametrize("category", [
    "", "Travel", "food", "FOOD", "<script>",
    "Food; DROP TABLE expenses",
])
def test_invalid_category_rejected(client, category):
    eid = logged_in_with_expense(client)
    assert_rejected(client, eid, category=category)


def test_missing_category_field_rejected(client):
    eid = logged_in_with_expense(client)
    before = snapshot(eid)
    data = valid_form(csrf_token=get_token(client))
    del data["category"]
    resp = client.post(edit_url(eid), data=data)
    assert resp.status_code == 200
    assert snapshot(eid) == before


@pytest.mark.parametrize("value", [
    "", "not-a-date", "2025-13-01", "2025-02-30", "2025/05/10",
    "10-05-2025", "20250510",
])
def test_invalid_date_rejected(client, value):
    eid = logged_in_with_expense(client)
    assert_rejected(client, eid, date=value)


def test_missing_date_field_rejected(client):
    eid = logged_in_with_expense(client)
    before = snapshot(eid)
    data = valid_form(csrf_token=get_token(client))
    del data["date"]
    resp = client.post(edit_url(eid), data=data)
    assert resp.status_code == 200
    assert snapshot(eid) == before


def test_validation_error_never_returns_500(client):
    eid = logged_in_with_expense(client)
    resp = post_edit(client, eid, amount="\x00", category="\x00", date="\x00")
    assert resp.status_code == 200


def test_error_page_has_no_dollar_sign(client):
    eid = logged_in_with_expense(client)
    html = post_edit(client, eid, amount="-1").get_data(as_text=True)
    assert "$" not in html


# ------------------------------------------------------------ sticky values
# DoD: after an error the form keeps entered values; DB row unchanged

def test_entered_values_kept_after_validation_error(client):
    eid = logged_in_with_expense(client, category="Food", amount=100)
    before = snapshot(eid)
    resp = post_edit(
        client, eid, amount="abc", category="Health",
        date="2025-07-04", description="Sticky note text")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "abc" in html, "Entered amount should be kept"
    assert "2025-07-04" in html, "Entered date should be kept"
    assert "Sticky note text" in html, "Entered description should be kept"
    assert re.search(
        r'<option[^>]*value="Health"[^>]*selected|'
        r'<option[^>]*selected[^>]*value="Health"', html
    ), "Entered category should remain selected"
    assert snapshot(eid) == before


def test_sticky_form_escapes_html_in_description(client):
    eid = logged_in_with_expense(client)
    payload = "<script>alert(1)</script>"
    html = post_edit(client, eid, amount="bad",
                     description=payload).get_data(as_text=True)
    assert payload not in html, "User input must be HTML-escaped"


# -------------------------------------------------------------------- CSRF
# DoD: missing/invalid token -> 400

def test_post_without_csrf_token_returns_400(client):
    eid = logged_in_with_expense(client)
    before = snapshot(eid)
    resp = client.post(edit_url(eid), data=valid_form())
    assert resp.status_code == 400
    assert snapshot(eid) == before


def test_post_with_wrong_csrf_token_returns_400(client):
    eid = logged_in_with_expense(client)
    before = snapshot(eid)
    client.get(edit_url(eid))
    resp = post_edit(client, eid, token="0" * 32)
    assert resp.status_code == 400
    assert snapshot(eid) == before


def test_post_with_empty_csrf_token_returns_400(client):
    eid = logged_in_with_expense(client)
    resp = client.post(edit_url(eid), data=valid_form(csrf_token=""))
    assert resp.status_code == 400


def test_post_with_non_ascii_csrf_token_returns_400(client):
    eid = logged_in_with_expense(client)
    client.get(edit_url(eid))
    resp = post_edit(client, eid, token="é" * 8)
    assert resp.status_code == 400


def test_token_from_edit_form_is_accepted(client):
    eid = logged_in_with_expense(client)
    html = client.get(edit_url(eid)).get_data(as_text=True)
    token = TOKEN_RE.search(html).group(1)
    resp = post_edit(client, eid, token=token)
    assert resp.status_code == 302


# ------------------------------------------------------------ forged fields
# DoD: forged user_id ignored; id in body ignored

def test_forged_user_id_is_ignored(client):
    register_user(client, email=OTHER_EMAIL, password=OTHER_PW)
    login(client, email=OTHER_EMAIL, password=OTHER_PW)
    owner_id = fetch_users(OTHER_EMAIL)[0]["id"]
    eid = make_expense(user_id=owner_id)
    resp = post_edit(client, eid, user_id=str(demo_id()))
    assert resp.status_code == 302
    row = fetch_row(eid)
    assert row["user_id"] == owner_id, "Owner must not change"
    assert row["amount"] == pytest.approx(300.75)


def test_forged_user_id_cannot_grant_access_to_foreign_expense(client):
    eid = make_expense()  # demo's
    login_as_other(client)
    other_id = fetch_users(OTHER_EMAIL)[0]["id"]
    before = snapshot(eid)
    resp = post_edit(client, eid, user_id=str(demo_id()))
    assert resp.status_code == 404
    assert snapshot(eid) == before
    assert fetch_row(eid)["user_id"] != other_id


def test_forged_id_in_body_is_ignored(client):
    login(client)
    target = make_expense(description="Target")
    bystander = make_expense(description="Bystander")
    bystander_before = snapshot(bystander)
    resp = post_edit(client, target, id=str(bystander))
    assert resp.status_code == 302
    assert snapshot(bystander) == bystander_before
    assert fetch_row(target)["description"] == "Edited note"
    assert fetch_row(target)["id"] == target


def test_sql_injection_in_description_stored_literally(client):
    eid = logged_in_with_expense(client)
    payload = "x'); DROP TABLE expenses; --"
    resp = post_edit(client, eid, description=payload)
    assert resp.status_code == 302
    assert fetch_row(eid)["description"] == payload
    assert count_expenses() > 0


# -------------------------------------------------------------- Edit links
# DoD: Edit links on /profile and /profile/transactions open the right form

def test_transactions_has_edit_link_for_expense(client):
    eid = logged_in_with_expense(client)
    html = client.get("/profile/transactions").get_data(as_text=True)
    assert f'href="{edit_url(eid)}"' in html


def test_profile_has_edit_link_for_recent_expense(client):
    eid = logged_in_with_expense(client)  # 2099 date -> among 5 most recent
    html = client.get("/profile").get_data(as_text=True)
    assert f'href="{edit_url(eid)}"' in html


def test_transactions_edit_link_per_row_distinct(client):
    login(client)
    a = make_expense(description="Row A")
    b = make_expense(description="Row B")
    html = client.get("/profile/transactions").get_data(as_text=True)
    assert f'href="{edit_url(a)}"' in html
    assert f'href="{edit_url(b)}"' in html


def test_edit_link_opens_form_for_that_expense(client):
    eid = logged_in_with_expense(client, description="Link target note")
    html = client.get("/profile/transactions").get_data(as_text=True)
    href = re.search(rf'href="({re.escape(edit_url(eid))})"', html).group(1)
    resp = client.get(href)
    assert resp.status_code == 200
    assert "Link target note" in resp.get_data(as_text=True)


def test_edit_links_not_shown_for_other_users_expenses(client):
    eid = make_expense()  # demo's
    login_as_other(client)
    for page in ("/profile", "/profile/transactions"):
        html = client.get(page).get_data(as_text=True)
        assert edit_url(eid) not in html, f"{page} leaked foreign edit link"


# ------------------------------------------------------- delete boundary

def test_delete_route_get_does_not_delete(client):
    eid = logged_in_with_expense(client)
    resp = client.get(f"/expenses/{eid}/delete")
    assert resp.status_code == 200
    assert fetch_row(eid) is not None, "GET on the delete URL must not delete"
