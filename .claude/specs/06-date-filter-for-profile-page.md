# Spec: Date Filter for Profile Page

## Overview
Step 5 added date-range filtering (`?from=&to=`) to the three sub-pages (`/profile/transactions`, `/profile/summary`, `/profile/categories`), but the main `/profile` page still shows all-time figures. This step brings the same filter to `/profile`, so the summary total, expense count, category totals and recent expenses all follow the selected range. It also adds quick-pick presets (This month, Last 30 days, This year, All time) so users do not have to type dates. The filter carries over into the profile sub-page links, so the chosen range stays active while moving between pages.

## Depends on
- **Step 1 — Database setup:** `expenses` table and the seeded demo user
- **Step 3 — Login and Logout:** session guard via `get_current_user()`
- **Step 4 — Profile page design:** `profile.html`, `profile.css`
- **Step 5 — Profile backend routes:** `parse_date_range()`, `_date_clause()`, `_date_filter.html`, `_profile_nav.html`

## Routes
- `GET /profile?from=&to=`: the existing profile page, now filtered by an inclusive `YYYY-MM-DD` date range. Access: logged-in.

No other new routes. Behaviour matches Step 5:
- Invalid date: that date is ignored, message "Invalid date ignored."
- `from` later than `to`: both dates are ignored, message "Start date must be on or before end date."
- Bad input never causes a 500. The page returns 200.
- Signed out: redirect to `/login`.

Presets are plain links to `/profile` with `from`/`to` query strings, computed server-side from today's date. No JavaScript is needed.

## Database changes
No schema changes.

In `database/db.py`, add optional `date_from=None, date_to=None` parameters to the existing helpers so their unfiltered behaviour stays unchanged:
- `get_expense_summary(user_id, date_from=None, date_to=None)`
- `get_category_totals(user_id, date_from=None, date_to=None)`
- `get_recent_expenses(user_id, limit=5, date_from=None, date_to=None)`

All three reuse `_date_clause()` and stay parameterised.

## Templates
- **Create:** none
- **Modify:**
  - `templates/profile.html`: include `_date_filter.html` (without the category select), show the active range, pass the active range into the links to the sub-pages, and show an empty state when the range has no expenses
  - `templates/_date_filter.html`: allow the form `action` to be set by the including page, and add an optional presets row
  - `templates/_profile_nav.html`: append `from`/`to` to links when a range is active

## Files to change
- `app.py`: `profile()` parses the range, passes it to the helpers and the template; add a small helper that builds preset ranges
- `database/db.py`: the three helpers above
- `templates/profile.html`
- `templates/_date_filter.html`
- `templates/_profile_nav.html`
- `static/css/profile.css`: presets row and active-range styles
- `CLAUDE.md`: update the `GET /profile` row to mention `?from=&to=`

## Files to create
- `tests/test_profile_date_filter.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only, never f-strings or `%` formatting in SQL
- Passwords hashed with werkzeug, and `password_hash` is never selected
- Use CSS variables and never hardcode hex values
- All templates extend `base.html`
- All DB logic lives in `database/db.py`. The route only guards the session, parses filters, calls helpers and renders.
- Reuse `parse_date_range()` and `_date_clause()`; do not duplicate date parsing or SQL
- Every internal link uses `url_for()`, with the filter passed as query arguments
- Currency is `₹` only, formatted with the `inr` filter
- Vanilla approach: no JavaScript, no new packages
- Existing callers of the changed helpers must keep working without the new arguments

## Definition of done
- [ ] `/profile` with no query string looks and behaves as before (all 8 demo expenses counted, total ₹5,240.00)
- [ ] `/profile?from=YYYY-MM-DD&to=YYYY-MM-DD` narrows the total, expense count, category totals and recent expenses to that inclusive range
- [ ] Both ends are inclusive: an expense dated exactly on `from` or `to` is counted
- [ ] `from` only or `to` only works as an open-ended range
- [ ] The filter form keeps the selected dates after submit
- [ ] Each preset (This month, Last 30 days, This year, All time) shows the right range, and All time clears the filter
- [ ] An invalid date and a reversed range each return 200 with the correct message
- [ ] A range with no expenses shows ₹0.00 and an empty state, not an error
- [ ] The links to Transactions, Summary and Categories keep the active range
- [ ] A user never sees another user's expenses through the filter
- [ ] Signed-out requests redirect to `/login`
- [ ] No `$` on the page, and no hex colours in the new CSS
- [ ] The page renders at phone width without horizontal scroll
- [ ] `pytest` passes in full
- [ ] `python app.py` still starts on port 5001
