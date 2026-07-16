import sqlite3
import pandas as pd
import os

# --- CONFIGURATION ---
DB_FILE = "data/processed/pif.db"               # Name of the SQLite database to be created
SCHEMA_FILE = "scripts/schema.sql"              # Your provided schema file
EXCEL_FILE = "data/raw/PIF2025.xlsx"            # Your source Excel file
SHEET_NAME = [0, 1, 3]                          # 0 reads the first sheet. Or use a string like 'Sheet1'
TARGET_TABLE = {                                # The exact table name defined in your schema.sql
    "Bikes": "bikes",
    "Orders": "orders",
    "Shops": "shops",
    "Pedal_Partners": "pedal_partners",
    "Contacts": "contacts",
    "Recipients": "recipients",
    "Volunteers": "volunteers"
    }

def setup_database():
    """Connects to SQLite and executes the schema.sql file."""
    print(f"Initializing database: {DB_FILE}...")
    
    # Connect to the DB (this creates the file if it doesn't exist)
    with sqlite3.connect(DB_FILE) as conn:
        with open(SCHEMA_FILE, 'r') as file:
            schema_script = file.read()
        
        # Executes the entire SQL script
        conn.executescript(schema_script)
        
    print("✓ Schema applied successfully.")

def migrate_data():
    """Reads Excel, processes the data, and writes to SQLite."""
    print(f"Reading data from {EXCEL_FILE}...")
    
    # Load the Excel sheet into a pandas DataFrame
    df_orders = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME[0])
    df_orders_sp = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME[1])
    df_inventory = pd.read_excel(EXCEL_FILE, sheet_name=SHEET_NAME[3])

    print("Processing data...")
    # ==========================================
    # --- START OF YOUR DATA PROCESSING CODE ---
    # ==========================================
    
    # 1. Rename columns to exactly match your SQLite schema columns
    # df.rename(columns={'Excel Column A': 'db_col_a', 'Excel Column B': 'db_col_b'}, inplace=True)
    
    # 2. Handle missing values
    # df.fillna('', inplace=True) # Replaces NaNs with empty strings
    
    # 3. Add or modify columns
    # df['created_at'] = pd.Timestamp.now()
    
    # 4. Filter out rows you don't want
    # df = df[df['status'] == 'Active']
    
    # ==========================================
    # --- END OF YOUR DATA PROCESSING CODE ---
    # ==========================================
    
    print(f"Inserting processed data into '{TARGET_TABLE}'...")
    
    with sqlite3.connect(DB_FILE) as conn:
        # Write the DataFrame to the SQLite table. 
        # if_exists='append' ensures we add to the table your schema created.
        # index=False prevents pandas from writing its row numbers as a database column.
        df.to_sql(TARGET_TABLE, conn, if_exists='append', index=False)
        
    print(f"✓ Migration complete! {len(df)} rows inserted.")

if __name__ == "__main__":
    # Basic validation before running
    if not os.path.exists(SCHEMA_FILE):
        print(f"Error: Cannot find '{SCHEMA_FILE}' in the current directory.")
    elif not os.path.exists(EXCEL_FILE):
        print(f"Error: Cannot find '{EXCEL_FILE}' in the current directory.")
    else:
        # setup_database()
        migrate_data()