import pytest

import database.db as db
# Importing app runs init_db()/seed_db() once against the real database.
# Both are idempotent and the file is gitignored, so this is harmless.
from app import app as flask_app


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    db.seed_db()
    flask_app.config.update(TESTING=True)
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def fetch_users(email=None):
    conn = db.get_db()
    try:
        if email is None:
            return conn.execute("SELECT * FROM users").fetchall()
        return conn.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchall()
    finally:
        conn.close()
