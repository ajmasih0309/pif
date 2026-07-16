-- 01_schema.sql
PRAGMA foreign_keys = ON;

-- =========================
-- Reference / Master tables
-- =========================

CREATE TABLE IF NOT EXISTS shops (
  shop_id     TEXT PRIMARY KEY,
  shop_name   TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS pedal_partners (
  pedal_partner_id   INTEGER PRIMARY KEY,
  pedal_partner_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS person (
  person_id           INTEGER PRIMARY KEY,
  name         TEXT NOT NULL,
  email        TEXT,
  phone_number TEXT
  gender         TEXT,            -- could later be normalized (recipient_genders)
  age            INTEGER,
  height   TEXT,
  CHECK (age IS NULL OR age >= 0),
  CHECK (height IN ('Below 3''0"', 'Above 7''0"')
    OR (
        -- Valid feet range 3–6 with any inches 0–11
        height GLOB '[3-6]''[0-9]"'
        OR
        -- Allow exactly 7'0"
        height = '7''0"'
    )
)

);

CREATE TABLE IF NOT EXISTS volunteers (
  volunteer_id           INTEGER PRIMARY KEY,
  volunteer_name         TEXT NOT NULL,
  volunteer_email        TEXT,
  volunteer_phone_number TEXT
);

-- ==========
-- Bike table
-- ==========
CREATE TABLE IF NOT EXISTS bikes (
  bike_id             INTEGER PRIMARY KEY,
  bike_tag            INTEGER NOT NULL UNIQUE,      -- "new integer tag each time bike is finished by volunteer"
  finished_timestamp  TEXT,                         -- store as ISO-8601 string (SQLite recommended)
  make                TEXT,
  model               TEXT,
  color               TEXT,
  wheel_size          TEXT,
  bike_type           TEXT NOT NULL,
  shop_id             INTEGER NOT NULL,
  volunteer_id        INTEGER,

  CHECK (bike_type IN ('A','B','C','D','E')),

  FOREIGN KEY (shop_id)      REFERENCES shops(shop_id),
  FOREIGN KEY (volunteer_id) REFERENCES volunteers(volunteer_id)
);

-- ===========
-- Orders table
-- ===========
CREATE TABLE IF NOT EXISTS orders (
  order_id                INTEGER PRIMARY KEY,
  order_number            TEXT NOT NULL,
  order_type              TEXT NOT NULL,
  order_date              TEXT NOT NULL,   -- ISO-8601 recommended
  date_picked_up          TEXT,
  bike_style_preference   TEXT,
  bike_type_first_choice  TEXT,
  bike_type_second_choice TEXT,
  notes                   TEXT,

  pedal_partner_id        INTEGER,
  shop_id                 INTEGER NOT NULL,
  contact_id              INTEGER NOT NULL,
  recipient_id            INTEGER NOT NULL,
  bike_id                 INTEGER,         -- nullable until assigned/picked-up

  CHECK (order_type IN ('Standard', 'Specialty')),
  CHECK (bike_style_preference IS NULL OR bike_style_preference IN ('Male', 'Female', 'No Preference')),
  CHECK (bike_type_first_choice  IS NULL OR bike_type_first_choice  IN ('A','B','C','D','E')),
  CHECK (bike_type_second_choice IS NULL OR bike_type_second_choice IN ('A','B','C','D','E')),
  CHECK (
    bike_type_first_choice IS NULL
    OR bike_type_second_choice IS NULL
    OR bike_type_first_choice <> bike_type_second_choice
  ),

  -- Bike can be assigned to 0..1 order:
  UNIQUE (bike_id),

  FOREIGN KEY (pedal_partner_id) REFERENCES pedal_partners(pedal_partner_id),
  FOREIGN KEY (shop_id)          REFERENCES shops(shop_id),
  FOREIGN KEY (contact_id)       REFERENCES person(person_id),
  FOREIGN KEY (recipient_id)     REFERENCES person(person_id),
  FOREIGN KEY (bike_id)          REFERENCES bikes(bike_id)
);
