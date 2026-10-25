# Spec: Profile Page Design

## Overview
This step replaces the `/profile` stub with a real, designed profile page — the first page a user lands on after signing in. It shows who the user is (name, email, member-since date) and gives a snapshot of their spending: total spent in ₹, number of expenses, top category, a per-category breakdown, and their most recent expenses. Login (Step 3) already redirects to `/profile`, so this step makes that landing point useful and establishes the card / stat-tile / table visual language that the expense pages (Steps 7–9) will reuse. The page is read-only; adding, editing and deleting expenses are out of scope.

## Depends on
- **Step 1 — Database setup**: `get_db()`, the `users` and `expenses` tables, and the seeded demo user with 8 sample expenses.
- **Step 2 — Registration**: real user rows (new users have zero expenses — the page must handle the empty state).
- **Step 3 — Login and Logout**: `session["user_id"]` / `session["user_name"]`, the session-aware navbar, and the `/login` → `/profile` redirect.

## Routes
- `GET /profile` — renders `profile.html` with the signed-in user's details, spending summary, category breakdown and recent expenses — logged-in

Behaviour:
- Not signed in → `redirect(url_for("login"))`
- `session["user_id"]` points to a user that no longer exists → `session.clear()` then `redirect(url_for("login"))`

Replaces the existing stub in place. No other new routes.

## Database changes
No database changes. The existing `users` (`id`, `name`, `email`, `created_at`) and `expenses` (`user_id`, `amount`, `category`, `date`, `description`) tables already hold everything the page needs.

New read-only helpers in `database/db.py` (each opens/closes its own connection like the existing helpers):
- `get_user_by_id(user_id)` — returns `id, name, email, created_at` (never `password_hash`), or `None`
- `get_expense_summary(user_id)` — returns `total` (`COALESCE(SUM(amount), 0)`) and `count` (`COUNT(*)`)
- `get_category_totals(user_id)` — returns rows of `category, total`, ordered by `total DESC`
- `get_recent_expenses(user_id, limit=5)` — returns `id, amount, category, date, description`, ordered by `date DESC, id DESC`, limited via a `?` placeholder

All queries filter by `user_id = ?` so a user only ever sees their own data.

## Templates
- **Create:**
  - `templates/profile.html` — extends `base.html`; links `css/profile.css` via `{% block head %}`. Sections:
    1. **Profile header card** — initial-letter avatar (first letter of name), name in `--font-display`, email, "Member since <Month YYYY>"
    2. **Stat tiles row** — Total spent (`₹` + amount with thousands separators, 2 decimals), Expenses (count), Top category (or "—" when none)
    3. **Spending by category** — one row per category with name, `₹` total, and a horizontal bar whose width is that category's share of the total (width set via an inline `style="width: N%"` computed in the template — the only inline style allowed)
    4. **Recent expenses** — table with Date, Description, Category (badge), Amount (`₹`, right-aligned); description falls back to "—"
    5. **Empty state** — when `count == 0`, sections 3 and 4 are replaced by a single friendly card ("No expenses yet") with a button to `url_for('add_expense')`
- **Modify:** none (`base.html` navbar already links the user's name to `url_for('profile')`)

## Files to change
- `app.py`
  - Import the four new helpers from `database.db`
  - Replace the `profile()` stub: check session, fetch via helpers, render `profile.html` — no SQL, no aggregation logic in the route beyond passing results to the template
- `database/db.py` — add the four helpers above
- `CLAUDE.md` — routes table: `GET /profile` → Implemented

## Files to create
- `templates/profile.html`
- `static/css/profile.css` — page-specific styles (profile header, avatar, stat tiles, category bars, expense table, category badge, empty state, responsive stacking below ~720px)
- `tests/test_profile.py` — tests covering the Definition of done (reuse the `app` / `client` fixtures from `tests/conftest.py`)

## New dependencies
No new dependencies. No CDN icon libraries either — use plain text or Unicode glyphs (like the existing `◈` brand icon).

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders, including `LIMIT ?`) — never f-strings or `%` in SQL
- Passwords hashed with werkzeug — the profile page never selects, passes or displays `password_hash`
- Use CSS variables — never hardcode hex values; reuse tokens from `style.css` (`--ink*`, `--paper*`, `--accent`, `--accent-light`, `--border*`, `--radius-*`, `--font-display`, `--font-body`)
- All templates extend `base.html`
- Page-specific styles go in `static/css/profile.css` — no `<style>` tags; the only inline style is the computed bar width
- All DB logic lives in `database/db.py`; the route only checks the session, calls helpers, and renders
- Every internal link and redirect uses `url_for()`
- Currency is always `₹`, never `$`; format amounts as `₹{{ "{:,.2f}".format(amount) }}`
- Guard divide-by-zero when computing category bar widths (total of 0 → no bars, empty state shown)
- Do not implement `/expenses/add`, `/edit` or `/delete` — only link to `url_for('add_expense')` from the empty state
- Vanilla JS only, and none should be needed for this page
- Match the existing visual language (cards on `--paper-card`, soft borders, rounded corners, DM Serif Display headings) so the page feels like the landing and auth pages

## Definition of done
- [ ] Visiting `/profile` while signed out redirects to `/login`
- [ ] Signing in as `demo@spendly.com` / `demo123` lands on `/profile` and shows "Demo User", `demo@spendly.com`, and a "Member since" date
- [ ] Demo user's Total spent shows `₹5,240.00` and Expenses shows `8`
- [ ] Demo user's Top category is `Bills` (₹1,800.00)
- [ ] Spending by category lists all 7 seeded categories, highest total first, each with a proportional bar
- [ ] Recent expenses shows the 5 latest expenses, newest first, with `₹` amounts
- [ ] No `$` appears anywhere on the page, and `password_hash` is never rendered
- [ ] A freshly registered user sees `₹0.00`, `0` expenses, "—" for top category, and the "No expenses yet" empty state with a working link to the add-expense route
- [ ] One user's profile never shows another user's expenses
- [ ] If the session's `user_id` no longer exists, the session is cleared and the user is redirected to `/login`
- [ ] The page renders cleanly at phone width (stat tiles and table stack, no horizontal page scroll)
- [ ] `profile.css` contains no hardcoded hex colours
- [ ] `pytest` passes, including the new `tests/test_profile.py` and the existing registration and login/logout tests
- [ ] The app still starts with `python app.py` on port 5001 and all existing pages render
