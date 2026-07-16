import pandas as pd
import sqlite3
import os
import sys


def c2t(file_path, table_name):
    try:
        # 1. Load your CSV data
        df = pd.read_csv(file_path)

        # Ensure output directory exists
        db_path = 'data/processed/pif.db'
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        # 2. Connect to (or create) the SQLite database
        conn = sqlite3.connect(db_path)

        # 3. Write the data to a SQL table
        df.to_sql(table_name, conn, if_exists='replace', index=False)

        # 4. Close the connection
        conn.close()

        print(f"Table '{table_name}' created and data imported successfully!")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python script.py <csv_file_path> <table_name>")
        sys.exit(1)

    file_path = sys.argv[1]
    table_name = sys.argv[2]

    c2t(file_path, table_name)