import streamlit as st
import pandas as pd
import sqlite3
import os

DB_FILE = 'data/processed/pif.db'

# 1. Load Data from SQLite
def load_data():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM orders_50", conn)
    conn.close()
    return df

# --- Streamlit App UI ---
st.set_page_config(page_title="SQL Spreadsheet Viewer", layout="wide")
st.title("🚴‍♂️ PIF Orders")
st.write("You can edit cells, or add/delete rows using the empty row at the bottom.")

# 2. Setup the database and load the data
df = load_data()

# 3. Display the interactive data editor
# Setting num_rows="dynamic" is what allows users to add or delete rows
edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

# 4. Save Changes Button
if st.button("Save Changes to Database"):
    try:
        conn = sqlite3.connect(DB_FILE)
        # For a quick prototype, we replace the existing table with the new dataframe
        edited_df.to_sql('inventory', conn, if_exists='replace', index=False)
        conn.close()
        st.success("Database successfully updated! 🎉")
    except Exception as e:
        st.error(f"An error occurred: {e}")