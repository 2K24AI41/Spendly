# Spec: Advanced Analytics

## Overview
`GET /analytics` already exists and is linked from the navbar, but it renders a "Coming Soon" placeholder. This step replaces the placeholder with real spending analysis for the signed-in user over a chosen date range: a comparison with the previous period of the same length, a monthly spending trend chart, a day-of-week breakdown, the user's biggest expenses, and per-day averages. Steps 5–6 answer "what did I spend?" with totals and tables (Summary, Categories). This page answers "how is my spending changing, and when do I spend?" All charts are drawn on the server as HTML/CSS bars, so the page needs no JavaScript and no chart library.

## Depends on
- **Step 1 — Database setup:** `expenses` table, `get_db()`, `_date_clause()`
- **Step 3 — Login and Logout:** `get_current_user()` and the redirect for signed-out users
- **Step 5 — Profile backend routes:** `get_spending_stats`, `get_monthly_summary`, `get_category_breakdown` (reused here)
- **Step 6 — Date filter:** `parse_date_range`, `build_date_presets`, `_date_filter.html`
- **Step 10 — Error pages:** invalid input never raises; it falls back with a message instead of an error page
- Existing `/analytics` placeholder route, `analytics.html`, `analytics.css` and the navbar link in `base.html`

## Routes
No new routes.

Changed route:
- `GET /analytics` — renders real analytics instead of "Coming Soon"; accepts `?from=&to=` — logged-in (signed out → redirect to `/login`, unknown `user_id` in session → session cleared and redirect, as today)

Behaviour:
- **Default range:** with no `from`/`to`, use the **last 30 days ending today** (the "Last 30 days" preset). "All time" from the presets (empty `from`/`to`) means the whole history and has no previous-period comparison.
- Invalid dates or `from > to` behave exactly as on the Summary page: `parse_date_range` drops them and its message is shown in the filter card. When only one bound is given, the missing bound is filled with the earliest expense date (for `from`) or today (for `to`) for the comparison maths only.
- **Period comparison:** for a range of N days (`from`..`to` inclusive), the previous period is the N days immediately before `from`. Show the total for each, the difference in ₹ and the % change. If the previous total is 0, show "No spending in previous period" instead of a %. Up/down is shown with text ("▲ 12.4% more" / "▼ 8.0% less"), not only colour.
- **Daily average:** `total / N` where N is the number of days in the range (inclusive). For "All time", N runs from the first expense date to today.
- **Monthly trend:** one bar per month in range from `get_monthly_summary`, oldest to newest, showing at most the latest 12 months. Bar height/width is a percentage of the largest month. Each bar has a visible ₹ label and month name (`month_label` filter).
- **Day of week:** total and count for Monday–Sunday (always all 7 rows, zero-filled), as horizontal bars scaled to the largest day. The busiest day is called out in text.
- **Top expenses:** the 5 largest expenses in range (amount, category, description, date), each linking to its edit page via `url_for('edit_expense', expense_id=...)`.
- **Top category:** first row of `get_category_breakdown` with its share %, plus a link to `/profile/categories` for the same range.
- **Empty state:** if there are no expenses in range, show the same empty-state card style as Summary ("No expenses in this period" + Clear filter link) and hide the charts.
- The page passes `presets=build_date_presets()` so the quick-pick links appear; the `/analytics` link stays in the main navbar and is **not** added to `_profile_nav.html`.

## Database changes
No database changes. Verified against `database/db.py`: `expenses(user_id, amount, category, date, description)` has everything needed.

New read-only helpers in `database/db.py` (both use `_date_clause()` and `?` placeholders, filter on `user_id`, open/close their own connection like the existing helpers):
- `get_weekday_totals(user_id, date_from=None, date_to=None)` — `SELECT CAST(strftime('%w', date) AS INTEGER) AS weekday, SUM(amount) AS total, COUNT(*) AS count ... GROUP BY weekday`. SQLite's `%w` is 0 = Sunday; reordering to Monday-first and zero-filling missing days happens in Python, not SQL.
- `get_top_expenses(user_id, limit=5, date_from=None, date_to=None)` — `SELECT id, amount, category, date, description ... ORDER BY amount DESC, date DESC, id DESC LIMIT ?`.
- `get_first_expense_date(user_id)` — `SELECT MIN(date) ...`; returns the date string or `None`.

Reuse and do not copy: `get_spending_stats` (for the current and previous period totals), `get_monthly_summary`, `get_category_breakdown`. `get_largest_expense` stays as-is. Do not change it into `get_top_expenses`.

## Templates
- **Create:** none
- **Modify:**
  - `templates/analytics.html` — remove the "Coming Soon" card, badge, dots and the "We're crafting something special" note. Rebuild the page in the `profile` layout: page title "Analytics", `{% include "_date_filter.html" %}`, a row of stat tiles (total, daily average, change vs previous period, top category), then cards for monthly trend, day of week and top expenses, or the empty state. Bar widths/heights come from server-computed percentages and go in a `style="--bar: NN%"` custom property. This is the one inline style allowed, matching the existing `category-bar` pattern. Each bar has an `aria-label` or visible text with its ₹ value.

## Files to change
- `app.py` — rewrite the `analytics()` view: parse the range, apply the 30-day default, compute the previous period, call the DB helpers, and render. Put the date maths (previous-period bounds, day count, weekday zero-fill/reorder, bar percentages) in small helper functions in the Helpers section so the route stays "fetch data, render template". Import the new DB helpers.
- `database/db.py` — add `get_weekday_totals`, `get_top_expenses` and `get_first_expense_date` in the filtered query helpers section
- `templates/analytics.html` — as above
- `static/css/analytics.css` — replace the coming-soon styles with styles for the trend chart, weekday bars, comparison indicator and top-expenses list. Reuse `profile-card`, `stat-tile`, `expense-table` and the other existing classes from `profile.css` and `summary.css`; only analytics-specific rules go here. Make it responsive at 640px (the trend chart scrolls inside its card, not the page).
- `tests/test_analytics.py` — replace `test_analytics_renders_coming_soon_when_signed_in` (the placeholder is gone). Keep the auth, navbar and no-hex tests.
- `CLAUDE.md` — add `GET /analytics` to the "Implemented vs stub routes" table

## Files to create
- `tests/test_11-advanced-analytics.py` — spec-based tests: default 30-day range, previous-period comparison (including the previous total being 0), weekday zero-fill and Monday-first order, top-5 limit and order, monthly cap of 12, empty state, invalid date message, other users' expenses excluded, `₹` shown and no `$`

## New dependencies
No new dependencies. No chart libraries (Chart.js etc.) and no JS: bars are HTML/CSS.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- All SQL lives in `database/db.py`; the route only calls helpers and renders
- Every query filters by the signed-in `user_id`, so no user can see another user's data
- Reuse `get_spending_stats`, `get_monthly_summary`, `get_category_breakdown`, `parse_date_range`, `build_date_presets` and `_date_filter.html`; do not copy them
- Use `url_for()` for every link (filter form, presets, edit links, categories link)
- Currency is `₹` via the existing `inr` filter; never `$`
- Avoid dividing by zero: an empty range, a zero previous total and a zero max bar must all render without errors
- No new routes, no blueprints, no JS frameworks; `main.js` needs no changes
- No `<style>` blocks; page styles go in `analytics.css`. The only inline style is the `--bar` percentage custom property.
- Do not show exception text to users; bad input falls back with a friendly message (HTTP 200)

## Definition of done
- [ ] Signed out, `GET /analytics` redirects to `/login`; a stale `user_id` clears the session and redirects
- [ ] Signed in as the demo user, `/analytics` returns 200 and no longer contains "Coming Soon" or "We're crafting something special"
- [ ] With no query string the filter shows the last 30 days (from = today − 29, to = today) and "Last 30 days" is the active preset
- [ ] The total tile matches the Summary page total for the same `?from=&to=`
- [ ] Adding an expense in the previous 30-day window changes the "vs previous period" figure to the correct ₹ difference and %
- [ ] With nothing spent in the previous period, the tile reads "No spending in previous period" and no error occurs
- [ ] Daily average equals total ÷ number of days in the range (e.g. ₹3,000 over 30 days → ₹100.00)
- [ ] The monthly trend shows one bar per month, oldest first, at most 12; the largest month's bar is full width/height
- [ ] Day of week always lists Monday → Sunday (7 rows), days with no spending show ₹0.00, and the busiest day is named
- [ ] Top expenses lists at most 5, largest first, and each links to that expense's edit page
- [ ] Choosing "All time" shows the whole history and hides the previous-period comparison
- [ ] `?from=2026-13-01` shows "Invalid date ignored." and `?from` later than `?to` shows the start-before-end message; both return 200
- [ ] A range with no expenses shows the empty state and no chart cards
- [ ] Another user's expenses never appear in any figure, list or chart
- [ ] The navbar Analytics link is highlighted with `aria-current="page"` on this page
- [ ] No `$` on the page, no hex colours in `analytics.css`, no `<style>` tag in `analytics.html`
- [ ] At phone width (≤ 640px) the page has no horizontal scroll
- [ ] `pytest` passes, including the updated `tests/test_analytics.py`
