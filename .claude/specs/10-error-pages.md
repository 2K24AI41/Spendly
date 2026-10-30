# Spec: Error Pages

## Overview
The app already calls `abort(400)` (bad CSRF token) and `abort(404)` (missing or foreign expense), and `MAX_CONTENT_LENGTH` can trigger 413, but every one of these currently shows Flask/Werkzeug's bare default HTML page with no navbar, styling or way back. This step adds branded error pages that extend `base.html`, registered through Flask error handlers in `app.py`, so users who hit a bad link, an expired form or a server fault see a friendly, on-brand explanation and a link back to safety. It is the polish step after the expense CRUD flow (Steps 7–9) introduced most of the `abort()` paths.

## Depends on
- **Step 1 — Database setup:** `init_db()` / `get_db()` (used by the 500 handler tests)
- **Step 3 — Login and Logout:** `session["user_id"]` decides which "go back" link is shown
- **Step 7–9 — Add / Edit / Delete expense:** the `abort(400)` and `abort(404)` calls these pages will render

## Routes
No new routes.

Error handlers (not routes) registered with `@app.errorhandler`:
- `400` — bad request (e.g. missing or invalid CSRF token) — all users
- `404` — page or expense not found (also covers another user's expense) — all users
- `405` — method not allowed — all users
- `413` — request body too large (`MAX_CONTENT_LENGTH`) — all users
- `500` — unexpected server error — all users

Behaviour:
- Each handler renders `error.html` with the correct HTTP status code in the response (never a 200).
- A single shared handler function is used for all codes; it reads `code`, `name` and a friendly message from a small mapping in `app.py`. No per-code duplicate functions.
- The `description` of the exception is never shown to the user (avoids leaking internals); only the fixed friendly message is.
- The 500 handler must not depend on the database or on `get_current_user()`, since the fault may be DB-related. It reads only `session.get("user_id")`, and the page must still render if that fails.
- The primary action link goes to `url_for("profile_transactions")` if signed in, otherwise `url_for("landing")`.
- Existing behaviour is unchanged: redirects to `/login` for signed-out users still win over 404 where they do today; status codes stay the same.

## Database changes
No database changes. Verified against `database/db.py`: nothing there is needed to render an error page.

## Templates
- **Create:**
  - `templates/error.html` — extends `base.html`; shows the status code, a short title (e.g. "Page not found"), the friendly message, and a button linking back (Dashboard/Transactions when signed in, Home otherwise)
- **Modify:**
  - None expected. `base.html` is reused as-is; the navbar and footer already work without a user lookup.

## Files to change
- `app.py` — add the error-code mapping, one shared `render_error` handler, and register it for 400, 404, 405, 413 and 500
- `CLAUDE.md` — add a short note on error handling (all HTTP errors render `error.html` through the shared handler in `app.py`)

## Files to create
- `templates/error.html`
- `static/css/error.css` — page-specific styles, loaded through `{% block head %}`; no inline `<style>`
- `tests/test_10-error-pages.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Handlers live in `app.py` only, no blueprints; there is no DB logic in them
- Keep `abort()` as the way routes raise HTTP errors; do not change existing routes
- Return `(render_template(...), code)` so the status code is preserved
- Use `url_for()` for every link, including the "back" button
- Never echo the exception's description, traceback or request data into the page
- The 500 handler must be safe when the DB or session is broken
- Do not enable `debug` behaviour changes; in debug mode Flask's interactive debugger for unhandled 500s may still appear, which is acceptable
- Vanilla JS only, and none is required for this step
- Currency is `₹` only; no `$` anywhere
- Do not add error pages for codes the app cannot produce (e.g. 401, 403, 418)

## Definition of done
- [ ] `GET /does-not-exist` returns status 404 and shows the branded page with "404", the navbar and footer
- [ ] `GET /expenses/99999/edit` (signed in) and `GET /expenses/<other user's id>/delete` return 404 with the same branded page
- [ ] `POST /expenses/add` with a missing or wrong CSRF token returns status 400 with the branded page
- [ ] `POST /` or `GET` on a POST-only path returns status 405 with the branded page
- [ ] A POST body larger than `MAX_CONTENT_LENGTH` returns status 413 with the branded page
- [ ] A forced exception in a route (tested with a temporary route or a monkeypatched helper, `TESTING`/`PROPAGATE_EXCEPTIONS` off) returns status 500 with the branded page and no traceback text
- [ ] The page text never includes the raw exception message
- [ ] Signed out, the back link goes to the landing page; signed in, it goes to `/profile/transactions`
- [ ] Every response has the correct status code, never 200
- [ ] The 500 page still renders when `get_current_user` or the DB is made to fail
- [ ] No `$` on the page and no hex colours in `error.css`
- [ ] The page renders at phone width without horizontal scroll
- [ ] Existing flows are unaffected: login redirects, add/edit/delete still behave as before
- [ ] `pytest` passes in full
- [ ] `python app.py` still starts on port 5001
