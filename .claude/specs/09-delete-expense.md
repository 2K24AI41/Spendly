# Spec: Delete Expense

## Overview
Users can add (Step 7) and edit (Step 8) expenses, but a wrong or duplicate entry can't be removed. This step turns the `/expenses/<id>/delete` stub into a working delete flow: a confirmation page that shows the expense, and a POST that removes it. Because deleting is destructive and irreversible, the actual deletion is POST-only and CSRF-protected, never triggered by a plain GET link. It completes the expense CRUD set and reuses the per-expense ownership pattern from Step 8.

## Depends on
- **Step 1 — Database setup:** `expenses` table with `user_id` foreign key
- **Step 3 — Login and Logout:** session guard via `get_current_user()`
- **Step 5 — Profile backend routes:** `/profile/transactions` as the post-delete destination and home of the Delete links
- **Step 8 — Edit expense:** `get_expense()` ownership lookup, CSRF helpers, the Actions column in the expense tables

## Routes
- `GET /expenses/<int:expense_id>/delete` — render a confirmation page showing the expense (amount, category, date, description) with a Delete button and a Cancel link; does NOT delete anything — logged-in
- `POST /expenses/<int:expense_id>/delete` — verify CSRF, delete the expense, redirect to `/profile/transactions` — logged-in

Behaviour:
- Signed out (GET or POST): redirect to `/login`.
- Expense does not exist, or belongs to another user: `abort(404)` (same response for both, so ids can't be probed).
- POST with a missing or invalid CSRF token: `abort(400)`.
- GET never modifies data, so links, prefetching and crawlers can't delete expenses.
- Deleting twice: the second POST finds no row and returns 404.
- Only the signed-in user's own expense can be deleted; the user id always comes from the session.

## Database changes
No schema changes.

In `database/db.py`, add:
- `delete_expense(expense_id, user_id)`: parameterised `DELETE FROM expenses WHERE id = ? AND user_id = ?`, commits, returns `True` if a row was deleted, else `False`

Verified against `database/db.py`: no existing helper deletes expenses. `get_expense(expense_id, user_id)` already exists and is reused for the ownership lookup and the confirmation page. No other table references `expenses`, so there are no cascade concerns.

## Templates
- **Create:**
  - `templates/delete_expense.html` — confirmation page: summary of the expense (amount with `₹`, category, date, description or "—"), a POST form with hidden `csrf_token` and a Delete button, and a Cancel link back to transactions
- **Modify:**
  - `templates/transactions.html` — add a "Delete" link next to "Edit" in the actions cell, to `url_for('delete_expense', expense_id=expense.id)`
  - `templates/profile.html` — same "Delete" link in the recent-expenses actions cell

## Files to change
- `app.py` — replace the `delete_expense` stub with a `GET`/`POST` route; import `delete_expense` from the db module under a non-clashing name (e.g. `from database import db` call or alias `delete_expense as remove_expense`); remove the "Placeholder routes" banner, since no stubs remain
- `database/db.py` — add `delete_expense()`
- `templates/transactions.html`
- `templates/profile.html`
- `static/css/profile.css` — style for the Delete link (destructive colour via an existing CSS variable) beside the Edit link
- `tests/test_08-edit-expense.py` — update `test_delete_stub_route_still_not_a_working_delete`, which asserts Step 9 is not implemented and will now be wrong
- `CLAUDE.md` — mark both `/expenses/<id>/delete` rows as Implemented

## Files to create
- `templates/delete_expense.html`
- `static/css/delete_expense.css` — only if the confirmation page needs styles beyond the shared `auth-*`/`profile` classes; no inline `<style>`
- `tests/test_09-delete-expense.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only, never f-strings or `%` formatting in SQL
- Passwords hashed with werkzeug; `password_hash` is never selected
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- All DB logic lives in `database/db.py`; the route only guards the session, checks ownership, verifies CSRF, calls the helper and redirects or renders
- Deletion happens only on POST with a valid CSRF token; GET must be side-effect free
- Ownership is enforced in SQL (`AND user_id = ?`) as well as in the route; the user id always comes from the session
- Use `abort()` for HTTP errors, never bare error strings; remove the `"coming in Step 9"` string return
- Name the route parameter `expense_id`, not `id`
- Every internal link and redirect uses `url_for()`
- Currency is `₹` only; never `$`
- No JavaScript required: the confirmation page is the safeguard. If a `confirm()` is added later it must be vanilla JS in `static/js/main.js`
- Do not implement undo/soft-delete or bulk delete

## Definition of done
- [ ] Signed out, `GET` and `POST /expenses/<id>/delete` redirect to `/login`
- [ ] Signed in, `GET /expenses/<id>/delete` for own expense shows the expense's amount (`₹`), category, date and description, a Delete button and a Cancel link, and the expense still exists afterwards
- [ ] `GET` and `POST` on a non-existent id return 404
- [ ] `GET` and `POST` on another user's expense return 404, and the expense still exists
- [ ] `POST` with a valid CSRF token deletes the expense and redirects to `/profile/transactions`, where it no longer appears
- [ ] Only the targeted row is removed; the user's other expenses and other users' expenses are untouched
- [ ] The deletion is reflected in `/profile` totals, `/profile/categories` and `/profile/summary`
- [ ] A second `POST` to the same URL returns 404
- [ ] `POST` with a missing, empty or wrong CSRF token returns 400 and the expense still exists
- [ ] A forged `user_id` field in the POST body is ignored
- [ ] "Delete" links on `/profile` and `/profile/transactions` open the right expense's confirmation page
- [ ] Cancel returns to `/profile/transactions` without deleting
- [ ] No `$` on the page, and no hex colours in any new CSS
- [ ] The confirmation page renders at phone width without horizontal scroll
- [ ] `pytest` passes in full, including the updated Step 8 stub test
- [ ] `python app.py` still starts on port 5001
