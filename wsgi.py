"""Production WSGI entry point for PIF Portal (TASK-201, TASK-203, TASK-205).

Run with e.g.:
    PIF_ENV=production .venv/bin/gunicorn -w 2 -b 127.0.0.1:8000 wsgi:application
"""
import os

os.environ.setdefault('PIF_ENV', 'production')

from app import app, check_startup_readiness  # noqa: E402

app.debug = False
if os.getenv('PIF_SKIP_STARTUP_CHECK', '').lower() != 'true':
    check_startup_readiness(require_secret=True)

application = app
