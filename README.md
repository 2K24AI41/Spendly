# Spendly

A personal expense tracking application built with **Flask** and **SQLite**. Users create an account, record expenses in Indian Rupees (₹), and review their spending through transaction history, category breakdowns, summaries and analytics, with filtering by date range.

![Python](https://img.shields.io/badge/Python_3.10%2B-0B1A2E?style=flat-square&logo=python&logoColor=38BDF8)
![Flask](https://img.shields.io/badge/Flask-0B1A2E?style=flat-square&logo=flask&logoColor=38BDF8)
![SQLite](https://img.shields.io/badge/SQLite-0B1A2E?style=flat-square&logo=sqlite&logoColor=38BDF8)
![pytest](https://img.shields.io/badge/pytest-0B1A2E?style=flat-square&logo=pytest&logoColor=38BDF8)

## Features

- **Accounts:** registration, login and logout, with passwords hashed using Werkzeug
- **Expenses:** add, edit and delete expenses, with a confirmation step before deleting
- **Profile views:** transactions, summary and category breakdown
- **Analytics:** a dedicated page for spending insights
- **Date filtering:** narrow profile views to a chosen period
- **Security basics:** CSRF tokens on forms, parameterised SQL queries, and a request size limit
- **Error pages:** branded pages for 400, 404, 405, 413 and 500 errors

## Tech Stack

| Layer | Tools |
| :--- | :--- |
| Backend | Python 3.10+, Flask, Werkzeug |
| Database | SQLite (Python's built-in `sqlite3`) |
| Frontend | Jinja2 templates, HTML, CSS, vanilla JavaScript |
| Testing | pytest, pytest-flask |

## Project Structure

```
Spendly/
├── app.py              # Flask app and all routes
├── database/db.py      # SQLite schema, seed data and queries
├── templates/          # Jinja2 templates (all extend base.html)
├── static/             # CSS and JavaScript
├── tests/              # pytest suite
├── CLAUDE.md           # project conventions used during development
└── .claude/            # feature specs, agents and commands
```

## Getting Started

**Requirements:** Python 3.10 or newer, and Git.

```bash
git clone https://github.com/2K24AI41/Spendly.git
cd Spendly

python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

pip install -r requirements.txt
python app.py
```

Open **http://127.0.0.1:5001** in your browser.

On first run the app creates `expense_tracker.db` in the project folder and adds a demo account with sample expenses. You can sign in with it straight away:

| Email | Password |
| :--- | :--- |
| `demo@spendly.com` | `demo123` |

### Configuration

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `SECRET_KEY` | built-in development key | Signs session cookies. **Required** when `FLASK_ENV=production`, otherwise the app refuses to start. |
| `FLASK_ENV` | not set | Set to `production` to require a real `SECRET_KEY`. |
| `FLASK_DEBUG` | `1` | Set to `0` to turn off Flask's debug mode. |

For local development no configuration is needed. Outside local development, set your own key:

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
```

## Running Tests

```bash
pytest
```

Each test runs against its own temporary database.

## Development Approach

Spendly was built feature by feature. Each feature started as a written spec in `.claude/specs/`, from database setup through error pages, and was then implemented and covered by tests. Development used an AI-assisted workflow with Claude Code, including custom agents for writing tests, running tests, quality review and security review.

## Author

**Kishor Kumar**, BS Artificial Intelligence student, University of Sindh, Jamshoro
[GitHub](https://github.com/2K24AI41) · [Email](mailto:kishormenghwar4120@gmail.com)
