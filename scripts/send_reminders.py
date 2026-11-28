"""Single-owner CLI job to send due pickup reminder emails (TASK-205, TASK-702).

Intended to be invoked periodically by cron or a systemd timer (e.g. every 15 minutes):
    .venv/bin/python scripts/send_reminders.py
"""
from contextlib import closing
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402
from database import get_db_connection  # noqa: E402
from pickup_policy import send_due_reminders  # noqa: E402
from utils import send_email  # noqa: E402


def run_reminders():
    """Execute one idempotent reminder pass if enabled by environment configuration."""
    with app.app_context():
        mode = app.config.get('EMAIL_MODE', 'preview')
        if (
            not app.config.get('EMAIL_REMINDERS_ENABLED', False)
            or mode not in {'live', 'test'}
            or (mode == 'live' and app.config.get('EMAIL_LIVE_ENABLED') is not True)
        ):
            return {'ran': False, 'reason': f'disabled (mode={mode})'}
        with closing(get_db_connection()) as conn:
            send_due_reminders(conn, send_email, mode)
        return {'ran': True, 'mode': mode}


if __name__ == '__main__':
    print(run_reminders())
