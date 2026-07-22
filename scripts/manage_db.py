import sqlite3
import sys
import os

# Adjust path so we can import from the parent directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config import Config

def upgrade_schema():
    """
    One-time script to add missing columns to the database.
    Run this manually via terminal: python scripts/manage_db.py
    """
    conn = sqlite3.connect(Config.DB_PATH)
    try:
        conn.execute("ALTER TABLE orders_50 ADD COLUMN status TEXT DEFAULT 'Open'")
        conn.execute("UPDATE orders_50 SET status = 'Completed' WHERE date_picked_up IS NOT NULL AND date_picked_up != ''")
        print("Status column added and populated.")
    except sqlite3.OperationalError:
        print("Status column already exists.")

    try:
        conn.execute("ALTER TABLE orders_50 ADD COLUMN handled_by TEXT DEFAULT 'System'")
        print("Handled_by column added.")
    except sqlite3.OperationalError:
        print("Handled_by column already exists.")
        
    conn.commit()
    conn.close()

if __name__ == '__main__':
    upgrade_schema()