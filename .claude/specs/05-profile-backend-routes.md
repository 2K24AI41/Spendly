# Spec: Backend Routes for the Profile Page

## Overview
Step 4 gave the profile page a snapshot of the user's spending: totals, the category list and the 5 latest expenses. This step adds three read-only, logged-in pages behind that snapshot, each with its own route:
- **Transaction history:** every expense, with date-range and category filters.
- **Summary stats:** totals, averages, the highest expense and a per-month table.
- **Category breakdown:** total, count, share and average per category.

Summary stats and category breakdown support the same date-range filter. The step also sets up shared building blocks that later steps will reuse:
- `get_current_user()` for the session guard
- `parse_date_range()` for safe filter parsing
- a reusable filter form partial

## Depends on
- **Step 1 — Database setup:** `get_db()`, the `users` and `expenses` tables, and the seeded demo user with 8 expenses
- **Step 2 — Registration:** real users, including new users with no expenses
- **Step 3 — Login and Logout:** `session["user_id"]` and `session["user_name"]`
- **Step 4 — Profile page design:** `profile.html`, `profile.css`, `get_user_by_id()`, and the `inr` / `short_date` filters

## Routes
- `GET /profile/transactions?from=&to=&category=`: all of the user's expenses, newest first, filtered by date range and/or category. Access: logged-in.
- `GET /profile/summary?from=&to=`: totals, average, highest expense and a per-month breakdown. Access: logged-in.
- `GET /profile/categories?from=&to=`: per-category total, count, % share and average. Access: logged-in.

Shared behaviour:
- Signed out → redirect to `/login`.
- `session["user_id"]` points to a user that no longer exists → `session.clear()`, then redirect to `/login`.
- Dates use the `YYYY-MM-DD` format, and both ends of the range are inclusive.

Bad filter input never causes a 500. The page still returns 200 with a message:
- **Invalid date:** that date is ignored. Message: "Invalid date ignored."
- **`from` later than `to`:** both dates are ignored. Message: "Start date must be on or before end date."
- **Unknown category:** the category is ignored. Message: "Unknown category — showing all categories."

## Database changes
No schema changes.

New read-only helpers go in `database/db.py`. They all filter by `user_id = ?` and use parameterised queries only:

| Helper | Returns |
|---|---|
| `_date_clause(date_from, date_to)` | `(sql_fragment, params)` |
| `get_expenses(user_id, date_from=None, date_to=None, category=None)` | rows of `id, amount, category, date, description`, ordered `date DESC, id DESC` |
| `get_user_categories(user_id)` | sorted `list[str]` |
| `get_spending_stats(user_id, date_from=None, date_to=None)` | `total, count, average, highest`; never None |
| `get_largest_expense(user_id, date_from=None, date_to=None)` | expense row or None |
| `get_monthly_summary(user_id, date_from=None, date_to=None)` | rows of `month (YYYY-MM), total, count, average`, newest first |
| `get_category_breakdown(user_id, date_from=None, date_to=None)` | rows of `category, total, count, average, share (0–100)`, ordered `total DESC, category ASC` |

## Templates
**Create:**
- `templates/transactions.html`
- `templates/summary.html`
- `templates/categories.html`
- `templates/_profile_nav.html`: a sub-nav linking the four profile pages
- `templates/_date_filter.html`: a GET filter form with from/to dates, an optional category select, and an error message

**Modify:**
- `templates/profile.html`: add links to the three new pages

## Files to change
- `app.py`:
  - new imports
  - `get_current_user()` and `parse_date_range()`
  - a `month_label` filter
  - `profile()` refactored to use `get_current_user()`
  - the three new routes, each in its own banner section
- `database/db.py`: the helpers above
- `templates/profile.html`: links to the new pages
- `static/css/profile.css`: shared sub-nav and filter-form styles
- `tests/conftest.py`: shared `login`, `register_user` and `add_expense_row` helpers
- `CLAUDE.md`: routes table

## Files to create
- **Templates:** `templates/transactions.html`, `templates/summary.html`, `templates/categories.html`, `templates/_profile_nav.html`, `templates/_date_filter.html`
- **Styles:** `static/css/transactions.css`, `static/css/summary.css`, `static/css/categories.css`
- **Tests:** `tests/test_transactions.py`, `tests/test_summary.py`, `tests/test_categories.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only, never f-strings or `%` formatting in SQL
- Passwords hashed with werkzeug, and `password_hash` is never selected for these pages
- Use CSS variables and never hardcode hex values
- All templates extend `base.html`
- All DB logic lives in `database/db.py`. Routes only do four things:
  1. guard the session
  2. parse filters
  3. call helpers
  4. render
- Every internal link uses `url_for()`
- Currency is `₹` only, formatted with the `inr` filter
- No JavaScript is needed

## Definition of done
- [ ] All three routes redirect to `/login` when signed out, and clear the session when the user no longer exists
- [ ] `/profile/transactions` shows all 8 demo expenses, newest first. The date and category filters narrow the list.
- [ ] `/profile/summary` shows these demo figures:
  - Total ₹5,240.00
  - 8 expenses
  - average ₹655.00
  - highest ₹1,800.00 (Electricity bill)
  - one row per month, newest first
- [ ] `/profile/categories` lists the 7 demo categories, highest total first, with Bills at 34.4% and Food at 2 expenses, ₹570.00
- [ ] Invalid dates, a reversed range and an unknown category each return 200 with the right message
- [ ] A new user sees ₹0.00 and an empty state on each page
- [ ] A user never sees another user's expenses
- [ ] `profile.html` links to all three pages
- [ ] No `$` on any page, and no hex colours in the new CSS
- [ ] All pages render at phone width without horizontal scroll
- [ ] `pytest` passes in full
- [ ] `python app.py` still starts on port 5001
