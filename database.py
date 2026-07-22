"""
Database Connection Functionality (database.py)
-------------------------------------
Handles Database connection when app routes database related operations. 
"""

import sqlite3
from flask import current_app

# Change the below table name when ready to switch
TABLE_ORDERS = 'orders_50'
TABLE_USERS = 'users'

def get_db_connection():
    """
    Creates a fresh database connection for a request.
    We use a Row factory so we can access columns by their name (e.g., row['status']) 
    instead of their numerical index.
    """
    conn = sqlite3.connect(current_app.config['DB_PATH'])
    conn.row_factory = sqlite3.Row
    return conn