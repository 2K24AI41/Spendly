# Spec: Registration

## Overview
This step turns the static `/register` page into a working sign-up flow. A visitor submits their name, email and password; the server validates the input, rejects duplicate emails, hashes the password with werkzeug and stores a new row in the `users` table, then redirects to the sign-in page. Registration is the first user-facing feature built on the Step 1 data layer — every later step (login, profile, expenses) needs real user accounts to exist, so this comes before login/logout (Step 3).

## Depends on
- **Step 1 — Database setup**: `get_db()`, `init_db()` and the `users` table (`id`, `name`, `email UNIQUE`, `password_hash`, `created_at`) in `database/db.py`.

## Routes
- `GET /register` — renders the registration form (already exists) — public
- `POST /register` — validates the form, creates the user, redirects to `url_for('login')` on success; re-renders `register.html` with an `error` message and the previously entered name/email on failure — public

Both are handled by the existing `register()` view by changing it to `methods=["GET", "POST"]`. No other new routes.

## Database changes
No database changes. The existing `users` table already has every column needed, and `email` is already `UNIQUE`.

New helper functions in `database/db.py` (no schema change):
- `get_user_by_email(email)` — returns the matching `sqlite3.Row` or `None`
- `create_user(name, email, password)` — hashes the password with `generate_password_hash`, inserts the row with a parameterised query, commits, and returns the new user's `id`. Raises `sqlite3.IntegrityError` on a duplicate email (race-condition backstop for the pre-check).

Both helpers open a connection with `get_db()` and close it in a `finally` block, matching `init_db()` / `seed_db()`.

## Templates
- **Create:** none
- **Modify:** `templates/register.html`
  - Change the hardcoded `action="/register"` to `action="{{ url_for('register') }}"`
  - Re-populate the `name` and `email` inputs from template variables after a failed submit (`value="{{ name or '' }}"`, `value="{{ email or '' }}"`); never re-populate the password
  - Add `minlength="8"` to the password input to match server-side validation

## Files to change
- `app.py` — import `request`, `redirect`, `url_for`; make `register()` accept GET and POST; call the new DB helpers; no SQL in the route
- `database/db.py` — add `get_user_by_email()` and `create_user()`
- `templates/register.html` — changes listed above
- `CLAUDE.md` — update the routes table: `POST /register` → Implemented

## Files to create
- `tests/__init__.py` — empty, makes `tests` a package
- `tests/conftest.py` — pytest fixtures: Flask `app` configured with `TESTING=True` and pointed at a temporary SQLite file (monkeypatch `database.db.DB_PATH`), plus a `client` fixture
- `tests/test_registration.py` — tests covering the Definition of done below

## New dependencies
No new dependencies. `flask`, `werkzeug`, `pytest` and `pytest-flask` are already in `requirements.txt`.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only (`?` placeholders) — never f-strings or `%` in SQL
- Passwords hashed with werkzeug's `generate_password_hash` — never store or log the plain password
- Use CSS variables — never hardcode hex values (reuse the existing `.auth-error`, `.form-input`, `.btn-submit` classes; no new CSS should be needed)
- All templates extend `base.html`
- All DB access lives in `database/db.py`; the route only reads the form, calls helpers, and renders/redirects
- Every internal link and form action uses `url_for()`
- Validation, all server-side (client-side `required`/`minlength` is a convenience only):
  - Strip whitespace from `name` and `email`; lowercase `email` before checking or storing
  - All three fields required → `"All fields are required."`
  - Email must contain `@` and a `.` after it → `"Please enter a valid email address."`
  - Password at least 8 characters → `"Password must be at least 8 characters."`
  - `password` and `confirm_password` must be identical → `"Passwords do not match."` (vanilla JS in `static/js/main.js` also flags a mismatch before submit; the server check is authoritative)
  - Email already registered → `"An account with this email already exists."`
- On failure, respond with status 200 and the re-rendered form (not a raw string, not `abort()`)
- On success, `redirect(url_for("login"))` (POST/redirect/GET) — do not log the user in; that is Step 3
- Do not implement `/logout`, `/profile` or any other stub route
- Use `₹`, never `$`, if any currency text appears

## Definition of done
- [ ] `GET /register` shows the form; the form's `action` is generated with `url_for`
- [ ] Submitting a valid name, new email and 8+ character password redirects to `/login`
- [ ] The new user appears in the `users` table with `password_hash` starting with a werkzeug prefix (e.g. `scrypt:` / `pbkdf2:`), not the plain password
- [ ] The stored email is lowercased and trimmed (`"  Priya.Nair@Gmail.com "` → `priya.nair@gmail.com`)
- [ ] Registering with an existing email (e.g. `demo@spendly.com`) re-shows the form with "An account with this email already exists." and no second row is inserted
- [ ] Submitting with any field blank shows "All fields are required."
- [ ] An email without `@`/domain shows "Please enter a valid email address."
- [ ] A 7-character password shows "Password must be at least 8 characters."
- [ ] The form asks for the password twice; mismatched passwords show "Passwords do not match." and no user is created
- [ ] After a failed submit, name and email are kept in the form; the password field is empty
- [ ] `pytest` passes, including the new `tests/test_registration.py`
- [ ] The app still starts with `python app.py` on port 5001 and all existing pages render
