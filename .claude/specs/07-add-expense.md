# Spec: Add Expense

## Overview
Steps 4–6 gave logged-in users a profile with summary, transactions and category views, but the only way expenses get into the database is the demo seed. This step turns the `/expenses/add` stub into a working form so users can record their own expenses (amount, category, date, optional description). On success the user lands on their transaction history, where the new expense appears at the top. This is the first write path for the `expenses` table and is the base for edit (Step 8) and delete (Step 9).

## Depends on
- **Step 1 — Database setup:** `expenses` table with `user_id` foreign key
- **Step 3 — Login and Logout:** session guard via `get_current_user()`
- **Step 4 — Profile page design:** shared look and feel, `profile.css` tokens
- **Step 5 — Profile backend routes:** `/profile/transactions` as the post-save destination

## Routes
- `GET /expenses/add` — render the empty add-expense form, date pre-filled with today — logged-in
- `POST /expenses/add` — validate the form, insert the expense for the current user, redirect to `/profile/transactions` on success; re-render the form with an error and the entered values on failure — logged-in

Behaviour:
- Signed out (GET or POST): redirect to `/login`.
- Invalid input never causes a 500. The form re-renders with status 200 and one clear error message.
- The expense is always saved against `session` user, never against a `user_id` supplied by the client.

Validation rules:
- `amount`: required, a finite number greater than 0, at most 2 decimal places, at most 10,000,000
- `category`: required, one of the fixed list (Food, Transport, Bills, Health, Entertainment, Shopping, Other)
- `date`: required, valid `YYYY-MM-DD`
- `description`: optional, trimmed, at most 200 characters; empty is stored as `NULL`

## Database changes
No schema changes. The existing `expenses` table already has every needed column.

In `database/db.py`, add:
- `EXPENSE_CATEGORIES`: the fixed category list, matching the seeded categories
- `create_expense(user_id, amount, category, date, description)`: parameterised `INSERT`, commits, returns the new row id

Verified against `database/db.py`: no existing helper inserts into `expenses`, and `PRAGMA foreign_keys = ON` is already set in `get_db()`.

## Templates
- **Create:**
  - `templates/add_expense.html` — the form (amount, category select, date, description), error banner, Cancel link back to transactions
- **Modify:**
  - `templates/transactions.html` — add an "Add expense" button linking to `url_for('add_expense')`
  - `templates/profile.html` — add an "Add expense" link in the recent-expenses section header, and in its empty state

## Files to change
- `app.py` — replace the `add_expense` stub with a `GET`/`POST` route; add a `validate_expense()` helper next to `validate_registration()`
- `database/db.py` — `EXPENSE_CATEGORIES` and `create_expense()`
- `templates/transactions.html`
- `templates/profile.html`
- `CLAUDE.md` — update the `/expenses/add` rows in the routes table to Implemented

## Files to create
- `templates/add_expense.html`
- `static/css/add_expense.css` — page-specific styles, no inline `<style>`
- `tests/test_add_expense.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only, never f-strings or `%` formatting in SQL
- Passwords hashed with werkzeug; `password_hash` is never selected
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- All DB logic lives in `database/db.py`; the route only guards the session, validates, calls the helper and redirects or renders
- Use `abort()` for HTTP errors, never bare error strings; do not leave the `"coming in Step 7"` string return
- Do not implement Edit (Step 8) or Delete (Step 9); leave those stubs untouched
- Every internal link and redirect uses `url_for()`
- Currency is `₹` only; never `$`
- Vanilla approach: HTML5 form attributes (`required`, `min`, `step`) are fine, but server-side validation is authoritative; no JavaScript is required
- Category must be checked against `EXPENSE_CATEGORIES` server-side, not trusted from the form
- Store the amount as a float rounded to 2 decimals

## Definition of done
- [ ] Signed out, `GET /expenses/add` and `POST /expenses/add` redirect to `/login`
- [ ] Signed in, `GET /expenses/add` shows the form with today's date pre-filled and all 7 categories in the select
- [ ] Submitting valid data creates the expense and redirects to `/profile/transactions`, where it appears first in the list with the right amount (`₹` formatted), category, date and description
- [ ] The new expense is counted in `/profile` totals and `/profile/categories`
- [ ] A missing amount, zero, negative, non-numeric, or over-limit amount re-renders the form with an error and status 200
- [ ] An unknown category, missing category, or invalid/missing date re-renders with an error and status 200
- [ ] A description over 200 characters is rejected; an empty description is accepted
- [ ] After a validation error the form keeps the values the user entered
- [ ] A forged `user_id` field in the POST body is ignored; the expense belongs to the signed-in user
- [ ] Another user never sees the new expense
- [ ] "Add expense" links on `/profile` and `/profile/transactions` open the form
- [ ] No `$` on the page, and no hex colours in `add_expense.css`
- [ ] The form renders at phone width without horizontal scroll
- [ ] `pytest` passes in full
- [ ] `python app.py` still starts on port 5001
