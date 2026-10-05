import os
from dotenv import load_dotenv

# Loads variables from the .env file into the environment
load_dotenv()

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY')
    DB_PATH = os.environ.get('DB_PATH')
    
    # Email configuration
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', MAIL_USERNAME)

    # Safe by default: neither credentials nor test settings enable real delivery.
    EMAIL_MODE = os.environ.get('EMAIL_MODE', 'preview').strip().lower()
    EMAIL_PREVIEW_DIR = os.environ.get('EMAIL_PREVIEW_DIR', 'data/email_previews')
    MAIL_TEST_RECIPIENT = os.environ.get('MAIL_TEST_RECIPIENT')
    EMAIL_LIVE_ENABLED = os.environ.get('EMAIL_LIVE_ENABLED', '').lower() == 'true'
    EMAIL_REMINDERS_ENABLED = os.environ.get('EMAIL_REMINDERS_ENABLED', '').lower() == 'true'
