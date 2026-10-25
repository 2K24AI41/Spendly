# Spec: Login and Logout

## Overview
This step turns the static `/login` page into a working sign-in flow and replaces the `/logout` stub with a real sign-out. A registered user submits their email and password; the server looks the user up, verifies the password against the stored werkzeug hash, and stores the user's `id` and `name` in Flask's signed session cookie. Logging out clears the session. The shared navbar becomes session-aware so signed-in users see their name and a "Sign out" link instead of "Sign in" / "Get started". Login comes straight after registration (Step 2) because every later step — profile (Step 4) and the expense pages (Steps 7–9) — needs to know who the current user is.

## Depends on
- **Step 1 — Database setup**: `get_db()`, the `users` table, and the seeded demo user (`demo@spendly.com` / `demo123`).
- **Step 2 — Registration**: `get_user_by_email(email)` in `database/db.py`, real user rows with werkzeug password hashes, and the `/register` → `/login` redirect.

## Routes
- `GET /login` — renders the sign-in form (already exists); if the user is already signed in, redirect to `url_for('profile')` — public
- `POST /login` — validates the form, verifies credentials, sets `session["user_id"]` and `session["user_name"]`, redirects to `url_for('profile')`; on failure re-renders `login.html` with an `error` and the previously entered email — public
- `GET /logout` — clears the session and redirects to `url_for('landing')` — public (safe to hit when already signed out)

`GET` and `POST /login` are handled by the existing `login()` view by changing it to `methods=["GET", "POST"]`. `/logout` replaces the existing stub in place. No other new routes.

## Database changes
No database changes. The `users` table already has `id`, `name`, `email` and `password_hash`, and `get_user_by_email(email)` from Step 2 already returns everything needed to verify a login.

No new DB helpers are required. Password verification (`check_password_hash`) is not DB logic, so it may be called from `app.py` or wrapped in a small helper in `app.py`'s Helpers section.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html`
    - Change the hardcoded `action="/login"` to `action="{{ url_for('login') }}"`
    - Re-populate the `email` input after a failed submit (`value="{{ email or '' }}"`); never re-populate the password
  - `templates/base.html`
    - Make `.nav-links` session-aware:
      - Signed in (`session.get('user_id')`): show `{{ session['user_name'] }}` linking to `url_for('profile')` and a "Sign out" link to `url_for('logout')`
      - Signed out: keep the existing "Sign in" and "Get started" links

## Files to change
- `app.py`
  - Import `session` from `flask`, `check_password_hash` from `werkzeug.security`, and `os`
  - Set `app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")` (dev fallback only; no new packages)
  - Make `login()` accept GET and POST; call `get_user_by_email()`; no SQL in the route
  - Replace the `logout()` stub with `session.clear()` + redirect
- `templates/login.html` — changes listed above
- `templates/base.html` — changes listed above
- `CLAUDE.md` — update the routes table: `POST /login` → Implemented, `GET /logout` → Implemented

## Files to create
- `tests/test_login_logout.py` — tests covering the Definition of done below (reuse the existing `app` / `client` fixtures from `tests/conftest.py`)

## New dependencies
No new dependencies. `flask` sessions and `werkzeug.security.check_password_hash` are already available via `requirements.txt`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders) — never f-strings or `%` in SQL
- Passwords hashed with werkzeug — verify with `check_password_hash`; never compare plain passwords, never store or log the plain password
- Use CSS variables — never hardcode hex values (reuse existing `.auth-error`, `.form-input`, `.btn-submit`, `.nav-links` styles; no new CSS should be needed)
- All templates extend `base.html`
- All DB access lives in `database/db.py`; the route only reads the form, calls helpers, sets the session, and renders/redirects
- Every internal link, form action and redirect uses `url_for()`
- Validation, all server-side:
  - Strip whitespace from `email` and lowercase it before lookup (matches how Step 2 stores emails)
  - Either field blank → `"Email and password are required."`
  - Unknown email **or** wrong password → the same generic message `"Invalid email or password."` (do not reveal which one was wrong)
- On failure, respond with status 200 and the re-rendered form (not a raw string, not `abort()`)
- On success, call `session.clear()` before setting `user_id` / `user_name` (avoid session fixation), then `redirect(url_for("profile"))`
- Store only `user_id` and `user_name` in the session — never the password hash or email
- `/logout` must use `session.clear()` and redirect; it must not error when no one is signed in
- Do not implement `/profile` (still the Step 4 stub) or any other stub route; do not add a `login_required` decorator yet unless needed by a test of this step
- Use `₹`, never `$`, if any currency text appears

## Definition of done
- [ ] `GET /login` shows the form; the form's `action` is generated with `url_for`
- [ ] Signing in as `demo@spendly.com` / `demo123` redirects to `/profile` and sets `user_id` in the session
- [ ] Signing in with mixed-case/padded email (`"  Demo@Spendly.com "`) also succeeds
- [ ] A user created via `/register` can immediately sign in with the password they chose
- [ ] Wrong password shows "Invalid email or password." and no session is set
- [ ] Unknown email shows the same "Invalid email or password." message
- [ ] Submitting with email or password blank shows "Email and password are required."
- [ ] After a failed submit, the email is kept in the form; the password field is empty
- [ ] While signed in, the navbar shows the user's name and a "Sign out" link; "Sign in" / "Get started" are hidden
- [ ] While signed in, visiting `GET /login` redirects to `/profile`
- [ ] `GET /logout` clears the session and redirects to `/`; the navbar shows "Sign in" / "Get started" again
- [ ] `GET /logout` while already signed out still redirects to `/` without error
- [ ] `pytest` passes, including the new `tests/test_login_logout.py` and the existing `tests/test_registration.py`
- [ ] The app still starts with `python app.py` on port 5001 and all existing pages render
