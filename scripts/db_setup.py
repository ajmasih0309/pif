import pandas as pd
import sqlite3

# 1. Load your CSV data
csv_file = 'data/processed/bikes_data.csv'
#csv_file = 'data/processed/orders_data.csv'
df = pd.read_csv(csv_file)

# 2. Connect to (or create) the SQLite database
conn = sqlite3.connect('data/processed/pif.db')

# 3. Write the data to a SQL table
# name='users' is the table name; if_exists='replace' overwrites if it exists
# df.to_sql('orders_test', conn, if_exists='replace', index=False)
df.to_sql('bikes_test', conn, if_exists='replace', index=False)

# 4. Close the connection
conn.close()
print("Table created and data imported successfully!")