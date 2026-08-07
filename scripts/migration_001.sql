-- 1. Rename your current broken table so we don't lose the data
ALTER TABLE orders RENAME TO orders_old;

-- 2. Create the new table with the STRICT Auto-Incrementing Primary Key
CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    linked_order_id INTEGER,
    contact_id INTEGER,
    recipient_id INTEGER,
    shop_name TEXT,
    pedal_partner_id INTEGER,
    
    order_date TEXT,
    order_type TEXT,
    order_status TEXT DEFAULT 'Open',
    last_status TEXT,
    last_updated_date TEXT,
    pickup_date TEXT,
    
    -- Legacy columns (kept just in case you still need them here)
    age TEXT,
    height TEXT,
    bike_style_preference TEXT,
    bike_type_first_choice TEXT,
    bike_type_second_choice TEXT,
    bike_tag REAL,
    notes TEXT
);

'''
current order table
CREATE TABLE IF NOT EXISTS "orders" (
  - "order_date" TEXT,
  - "pickup_date" TEXT,
  - "bike_style_preference" TEXT,
  - "age" REAL,
  - "height" TEXT,
  - "bike_type_first_choice" TEXT,
  - "bike_type_second_choice" TEXT,
  - "bike_tag" REAL,
  - "shop_name" TEXT,
  - "notes" TEXT,
  - "order_type" TEXT,
  - "contact_id" INTEGER,
  - "pedal_partner_id" INTEGER,
  - "recipient_id" REAL,
  - "order_id" INTEGER,
  - "linked_order_id" REAL,
  "handled_by" TEXT,
  - "status" TEXT
, handled_on TEXT);
'''

-- 3. Copy everything from the old table into the new one 
-- (SQLite will automatically generate the missing order_ids during this copy!)
INSERT INTO orders (
    contact_id, linked_order_id, recipient_id, shop_name, pedal_partner_id, 
    order_date, order_type, order_status, last_status, last_updated_date, pickup_date, 
    age, height, bike_style_preference, bike_type_first_choice, bike_type_second_choice, bike_tag, notes
)
SELECT 
    contact_id, 
    linked_order_id, 
    recipient_id, 
    shop_name, 
    pedal_partner_id, 
    order_date, 
    order_type, 
    status, 
    NULL as last_status, 
    COALESCE(pickup_date, order_date) as last_updated_date, 
    pickup_date, 
    age, 
    height, 
    bike_style_preference, 
    bike_type_first_choice, 
    bike_type_second_choice, 
    bike_tag, 
    notes
FROM orders_old;

-- 4. Drop the old table to clean up
DROP TABLE orders_old;

-- 5. Add Updated By
ALTER TABLE orders ADD COLUMN last_updated_by TEXT DEFAULT 'System';