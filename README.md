# Spendly

A lightweight personal expense tracker built with Flask and SQLite. Amounts are in INR (₹).

**Live demo:** https://kumarkishor.pythonanywhere.com/

## Run locally

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py                     # http://127.0.0.1:5001
```

Run the tests with `pytest`.

## Deployment

The live site runs on PythonAnywhere's free tier from the `main` branch. To ship an update:

1. Push to `main` on GitHub.
2. In a PythonAnywhere Bash console: `cd ~/Spendly && git pull` (and `pip install -r requirements.txt` if dependencies changed).
3. Click **Reload** on the Web tab.

Free web apps must be extended every 3 months from the Web tab ("Run until 3 months from today").
