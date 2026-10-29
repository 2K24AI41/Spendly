# Spec: Edit Expense

## Overview
Users can now add expenses (Step 7) and review them on `/profile` and `/profile/transactions`, but a typo in an amount, category or date can't be corrected. This step turns the `/expenses/<id>/edit` stub into a working form, pre-filled with the existing expense, so users can fix mistakes. On success the user returns to their transaction history. It is the first update path for the `expenses` table and introduces per-expense ownership checks, which Delete (Step 9) will reuse.

## Depends on
- **Step 1 — Database setup:** `expenses` table with `user_id` foreign key
- **Step 3 — Login and Logout:** session guard via `get_current_user()`
- **Step 5 — Profile backend routes:** `/profile/transactions` as the post-save destination and home of the Edit links
- **Step 7 — Add expense:** `validate_expense()`, `EXPENSE_CATEGORIES`, CSRF helpers and `add_expense.css`

## Routes
- `GET /expenses/<int:id>/edit` — render the form pre-filled with the expense's current values — logged-in
- `POST /expenses/<int:id>/edit` — validate the form, update the expense, redirect to `/profile/transactions` on success; re-render the form with an error and the entered values on failure — logged-in

Behaviour:
- Signed out (GET or POST): redirect to `/login`.
- Expense does not exist, or belongs to another user: `abort(404)` (same response for both, so ids can't be probed).
- POST with a missing or invalid CSRF token: `abort(400)`.
- Invalid input never causes a 500. The form re-renders with status 200 and one clear error message.
- Only `amount`, `category`, `date` and `description` can change. A `user_id` or `id` supplied in the POST body is ignored.

Validation rules: identical to Add Expense, by reusing `validate_expense()`:
- `amount`: required, finite, greater than 0, at most 2 decimal places, at most 10,000,000
- `category`: required, one of `EXPENSE_CATEGORIES`
- `date`: required, valid `YYYY-MM-DD`
- `description`: optional, trimmed, at most 200 characters; empty is stored as `NULL`

## Database changes
No schema changes.

In `database/db.py`, add:
- `get_expense(expense_id, user_id)`: parameterised `SELECT id, amount, category, date, description FROM expenses WHERE id = ? AND user_id = ?`; returns the row or `None`
- `update_expense(expense_id, user_id, amount, category, expense_date, description)`: parameterised `UPDATE ... WHERE id = ? AND user_id = ?`, commits, returns `True` if a row was updated, else `False`

Verified against `database/db.py`: no existing helper fetches a single expense or updates one. `get_expenses` returns lists only, and `create_expense` is insert-only. Amount is stored as `round(float(amount), 2)`, as in `create_expense`.

## Templates
- **Create:**
  - `templates/edit_expense.html` — the form (amount, category select, date, description) pre-filled, hidden `csrf_token`, error banner, Cancel link back to transactions
- **Modify:**
  - `templates/transactions.html` — add an "Edit" link per row (new actions column) to `url_for('edit_expense', id=expense.id)`
  - `templates/profile.html` — add the same "Edit" link per row in the recent-expenses table

## Files to change
- `app.py` — replace the `edit_expense` stub with a `GET`/`POST` route; import `get_expense` and `update_expense`
- `database/db.py` — `get_expense()` and `update_expense()`
- `templates/transactions.html`
- `templates/profile.html`
- `static/css/add_expense.css` — only if shared form styles need a small addition for the edit page (otherwise unchanged)
- `CLAUDE.md` — mark `/expenses/<id>/edit` as Implemented in the routes table

## Files to create
- `templates/edit_expense.html`
- `tests/test_edit_expense.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only, never f-strings or `%` formatting in SQL
- Passwords hashed with werkzeug; `password_hash` is never selected
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- All DB logic lives in `database/db.py`; the route only guards the session, checks ownership, validates, calls the helper and redirects or renders
- Reuse `validate_expense()` and `EXPENSE_CATEGORIES`; do not duplicate validation
- Ownership is enforced in SQL (`AND user_id = ?`) as well as in the route; the user id always comes from the session
- Use `abort()` for HTTP errors, never bare error strings; remove the `"coming in Step 8"` string return
- Do not implement Delete (Step 9); leave that stub untouched
- Every internal link and redirect uses `url_for()`
- Currency is `₹` only; never `$`
- Server-side validation is authoritative; no JavaScript required
- Page-specific styles go in a `.css` file, never inline `<style>`

## Definition of done
- [ ] Signed out, `GET` and `POST /expenses/<id>/edit` redirect to `/login`
- [ ] Signed in, `GET /expenses/<id>/edit` for own expense shows the form pre-filled with its amount, category, date and description, with all 7 categories in the select
- [ ] `GET` and `POST` on a non-existent id return 404
- [ ] `GET` and `POST` on another user's expense return 404, and the expense is unchanged
- [ ] Submitting valid changes updates the expense and redirects to `/profile/transactions`, where the new values appear (`₹` formatted)
- [ ] The edited expense is reflected in `/profile` totals and `/profile/categories`
- [ ] Editing does not create a new row or change the expense's id or owner
- [ ] A zero, negative, non-numeric, over-limit or missing amount re-renders with an error and status 200
- [ ] An unknown category or invalid/missing date re-renders with an error and status 200
- [ ] A description over 200 characters is rejected; clearing the description saves it as empty
- [ ] After a validation error the form keeps the values the user entered, and the database row is unchanged
- [ ] A POST without a valid CSRF token returns 400
- [ ] A forged `user_id` field in the POST body is ignored
- [ ] "Edit" links on `/profile` and `/profile/transactions` open the right expense's form
- [ ] No `$` on the page, and no hex colours in any new CSS
- [ ] The form renders at phone width without horizontal scroll
- [ ] `pytest` passes in full
- [ ] `python app.py` still starts on port 5001
