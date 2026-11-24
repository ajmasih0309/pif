#!/usr/bin/env python3
"""Reusable migration script for Finished Bike Inventory.

Imports historical finished bikes and volunteer contributions from
'PIF 2025 .xlsx' (sheet 'Finished Bike Inventory') into the active SQLite database.

Enforces:
- Global canonical tag deduplication into `bike_inventory`.
- Preserves multi-contributions and reused tags into `bike_contributions`.
- 2-Year Moving Window (2025-2026) for volunteer profile provisioning:
  * Resolves known aliases to existing registered profiles.
  * Auto-provisions new volunteer profiles for clean full person names active in 2025-2026.
  * Preserves pre-2025 and single/group names with volunteer_id=NULL and exact recorded_name.
- Filters out placeholder / test rows per design/database.md specifications.
- Safe pre-migration backup, integrity verification, and PRAGMA foreign_key_check.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
import sqlite3
import sys

try:
    import openpyxl
except ImportError:
    print("Error: openpyxl is required. Run: pip install openpyxl", file=sys.stderr)
    sys.exit(1)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "processed" / "pif.db"
DEFAULT_EXCEL_PATH = PROJECT_ROOT / "data" / "raw" / "PIF 2025 .xlsx"
SHEET_NAME = "Finished Bike Inventory"

# Known test and placeholder tags to filter out per design/database.md
PLACEHOLDER_TAGS = {"test", "test2", "test3", "need", "trailer bike"}

# Shop mapping
SHOP_MAP = {
    "bv shop": "B",
    "rac shop": "R",
    "sdale shop": "S",
}

# Wheel size normalization mapping
WHEEL_MAP = {
    "12": "12 inch",
    "12.0": "12 inch",
    "14": "14 inch",
    "14.0": "14 inch",
    "16": "16 inch",
    "16.0": "16 inch",
    "18": "18 inch",
    "18.0": "18 inch",
    "20": "20 inch",
    "20.0": "20 inch",
    "24": "24 inch",
    "24.0": "24 inch",
    "26": "26 inch",
    "26.0": "26 inch",
    "27": "27 inch",
    "27.0": "27 inch",
    "27.5": "27.5 inch",
    "29": "29 inch",
    "29.0": "29 inch",
    "700": "700C",
    "700.0": "700C",
    "650b": "650B",
    "650c": "650C",
}

TAG_KEY_SQL = (
    "CASE WHEN bike_tag <> '' AND bike_tag NOT GLOB '*[^0-9]*' "
    "THEN COALESCE(NULLIF(ltrim(bike_tag, '0'), ''), '0') ELSE bike_tag END"
)

# Known name aliases linking full names / nicknames to existing volunteer directory entries
NAME_ALIASES = {
    "david tovey": "david t",
    "donn schmidt": "donn s",
    "ann neumann": "ann n",
    "rich gonzales": "richard gonzales",
    "richard gonzales": "richard g",
    "ben gottschall": "ben g",
    "tom woodcock": "tom w",
    "stu g-j": "stu g",
    "stew g-j": "stu g",
    "charlie miller": "charles miller",
    "charlse miller": "charles miller",
    "marty h": "marty heyne",
}

ORG_WORDS = {
    "walmart",
    "trek",
    "rotary",
    "church",
    "high",
    "school",
    "team",
    "club",
    "group",
    "staff",
    "sams",
    "sam’s",
    "supply",
    "7l",
    "bomb",
    "mechanic",
}


def canonical_bike_tag(tag: str | int | float | None) -> str:
    """Normalize bike tag to canonical representation (strip leading zeroes if numeric)."""
    if tag is None:
        return ""
    if isinstance(tag, float) and tag.is_integer():
        tag = int(tag)
    s = str(tag).strip()
    if re.fullmatch(r"[0-9]+", s):
        return str(int(s))
    return s


def normalize_shop(raw_shop: str | None) -> tuple[str, str | None]:
    """Map raw shop string to standard shop_name ('B', 'R', 'S').

    Returns (shop_code, note_if_composite).
    """
    if not raw_shop:
        return "B", "Shop unspecified in source; defaulted to Bentonville"
    s = str(raw_shop).strip()
    low = s.lower()
    if low in SHOP_MAP:
        return SHOP_MAP[low], None

    # Handle composite shops (e.g. 'RAC Shop, BV Shop')
    parts = [p.strip().lower() for p in s.split(",")]
    first_part = parts[0]
    shop_code = SHOP_MAP.get(first_part, "B")
    note = f"Original composite shop: {s}"
    return shop_code, note


def normalize_wheel_size(raw_wheel: str | int | float | None) -> str | None:
    """Normalize wheel size to standard application choice."""
    if raw_wheel is None:
        return None
    s = str(raw_wheel).strip()
    if not s:
        return None
    return WHEEL_MAP.get(s.lower(), s)


def normalize_bike_type(raw_type: str | None) -> str | None:
    """Normalize bike type to A-F if valid."""
    if not raw_type:
        return None
    s = str(raw_type).strip().upper()
    return s if s in {"A", "B", "C", "D", "E", "F"} else s


def normalize_timestamp(ts: any) -> str | None:
    """Convert timestamp to ISO-8601 string."""
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts.strftime("%Y-%m-%d %H:%M:%S")
    s = str(ts).strip()
    return s if s else None


def load_volunteers(conn: sqlite3.Connection) -> tuple[dict[str, int], dict[str, int]]:
    """Load volunteer lookup dictionaries.

    Returns:
    - direct_map: lower(name) -> volunteer_id
    - initial_map: 'first last_initial' -> volunteer_id (only if unambiguous)
    """
    cur = conn.execute("SELECT volunteer_id, volunteer_name FROM volunteers")
    direct_map = {}
    fn_li_counts = Counter()
    temp_li_map = {}

    for vid, vname in cur.fetchall():
        name_clean = str(vname).strip()
        direct_map[name_clean.lower()] = vid
        parts = name_clean.split()
        if len(parts) >= 2:
            key = f"{parts[0].lower()} {parts[-1][0].lower()}"
            fn_li_counts[key] += 1
            temp_li_map[key] = vid

    # Keep only unambiguous initial mappings
    initial_map = {k: vid for k, vid in temp_li_map.items() if fn_li_counts[k] == 1}
    return direct_map, initial_map


def match_existing_volunteer(
    name: str | None,
    direct_map: dict[str, int],
    initial_map: dict[str, int],
) -> int | None:
    """Attempt to match volunteer name to existing volunteer_id via direct, alias, or initial lookup."""
    if not name:
        return None
    clean = name.strip()
    low = clean.lower()

    # 1. Direct match
    if low in direct_map:
        return direct_map[low]

    # 2. Alias match
    alias_target = NAME_ALIASES.get(low)
    if alias_target and alias_target in direct_map:
        return direct_map[alias_target]

    # 3. First Name + Last Initial match (unambiguous)
    parts = clean.split()
    if len(parts) >= 2:
        key = f"{parts[0].lower()} {parts[-1][0].lower()}"
        if key in initial_map:
            return initial_map[key]

    return None


def ensure_schema_and_indexes(conn: sqlite3.Connection) -> None:
    """Ensure bike_inventory, bike_contributions and canonical indexes exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bike_inventory (
            inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
            recorded_at TEXT,
            shop_name TEXT NOT NULL REFERENCES shops(shop_name),
            bike_tag TEXT NOT NULL UNIQUE CHECK(length(trim(bike_tag)) > 0),
            make TEXT,
            model TEXT,
            colour TEXT,
            wheel_size TEXT,
            bike_type TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS ux_inventory_canonical_tag ON bike_inventory ({TAG_KEY_SQL})"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS bike_contributions (
            contribution_id INTEGER PRIMARY KEY AUTOINCREMENT,
            inventory_id INTEGER NOT NULL REFERENCES bike_inventory(inventory_id),
            volunteer_id INTEGER REFERENCES volunteers(volunteer_id),
            recorded_name TEXT,
            recorded_at TEXT,
            source_key TEXT UNIQUE,
            source_sheet TEXT,
            source_row INTEGER,
            notes TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_bike_contributions_inventory ON bike_contributions(inventory_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS ix_bike_contributions_volunteer ON bike_contributions(volunteer_id)"
    )


def create_backup(db_path: Path) -> Path:
    """Create a timestamped backup copy of the target database."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"pif-before-bike-inventory-{timestamp}.db"
    shutil.copy2(db_path, backup_path)
    return backup_path


def identify_2025_new_volunteers(
    sheet: openpyxl.worksheet.worksheet.Worksheet,
    direct_map: dict[str, int],
    initial_map: dict[str, int],
) -> dict[str, dict[str, any]]:
    """Scan the sheet and collect new full-person volunteer candidates active in 2025-2026.

    Returns dict mapping canonical_name -> {first_seen, last_seen, count_2025, lifetime_count}.
    """
    candidates = defaultdict(
        lambda: {
            "first_seen": None,
            "last_seen": None,
            "count_2025": 0,
            "lifetime_count": 0,
        }
    )

    for row in sheet.iter_rows(min_row=2, max_col=9, values_only=True):
        if not any(row):
            continue
        ts, _, tag, _, _, _, _, _, vol = row
        if not tag or str(tag).strip() == "":
            continue
        c_tag = canonical_bike_tag(tag)
        c_tag_low = c_tag.lower()
        if (
            c_tag_low in PLACEHOLDER_TAGS
            or "test" in c_tag_low
            or c_tag_low == "0"
        ):
            continue
        if not vol:
            continue

        v_raw = str(vol).strip()
        if match_existing_volunteer(v_raw, direct_map, initial_map) is not None:
            continue

        parts = v_raw.split()
        is_org = any(w in ORG_WORDS for w in [p.lower() for p in parts]) or any(
            c.isdigit() for c in v_raw
        )
        if len(parts) >= 2 and not is_org:
            canon = " ".join(p.capitalize() for p in parts)
            dt = ts if isinstance(ts, datetime) else None
            year = dt.year if dt else 2021

            st = candidates[canon]
            st["lifetime_count"] += 1
            if dt:
                if st["first_seen"] is None or dt < st["first_seen"]:
                    st["first_seen"] = dt
                if st["last_seen"] is None or dt > st["last_seen"]:
                    st["last_seen"] = dt
            if year >= 2025:
                st["count_2025"] += 1

    # Keep only those active in the 2025-2026 moving window
    return {k: v for k, v in candidates.items() if v["count_2025"] > 0}


def run_migration(
    db_path: Path,
    excel_path: Path,
    apply: bool = False,
) -> dict[str, any]:
    """Execute the bike inventory migration implementing the moving 2-year window policy."""
    if not excel_path.is_file():
        raise FileNotFoundError(f"Workbook not found at {excel_path}")
    if not db_path.is_file():
        raise FileNotFoundError(f"Database not found at {db_path}")

    print(f"Opening workbook: {excel_path}")
    wb = openpyxl.load_workbook(excel_path, data_only=True)
    if SHEET_NAME not in wb.sheetnames:
        raise ValueError(f"Sheet '{SHEET_NAME}' not found in {excel_path}")
    sheet = wb[SHEET_NAME]

    backup_path = None
    if apply:
        backup_path = create_backup(db_path)
        print(f"Pre-migration backup created: {backup_path}")

    conn = sqlite3.connect(db_path)
    try:
        ensure_schema_and_indexes(conn)
        conn.execute("PRAGMA foreign_keys = ON")

        direct_map, initial_map = load_volunteers(conn)
        print(
            f"Loaded {len(direct_map)} existing volunteer profiles ({len(initial_map)} initial mappings)"
        )

        # 1. Identify and provision new volunteers active in the moving 2-year window (2025-2026)
        new_vols = identify_2025_new_volunteers(sheet, direct_map, initial_map)
        print(
            f"Identified {len(new_vols)} new volunteer candidates active in 2025-2026 moving window"
        )

        # Reference activity cutoff: 180 days before max date in dataset (~2026-10-03 -> ~2026-04-06)
        active_cutoff = datetime(2026, 4, 6)
        new_vol_ids: dict[str, int] = {}

        if apply:
            for name, info in new_vols.items():
                joined = (
                    info["first_seen"].strftime("%Y-%m-%d")
                    if info["first_seen"]
                    else "2025-01-01"
                )
                is_active = (
                    1
                    if info["last_seen"] and info["last_seen"] >= active_cutoff
                    else 0
                )
                cursor = conn.execute(
                    "INSERT INTO volunteers (volunteer_name, joined_on, is_active) VALUES (?, ?, ?)",
                    (name, joined, is_active),
                )
                new_vid = cursor.lastrowid
                new_vol_ids[name.lower()] = new_vid
                direct_map[name.lower()] = new_vid
            print(
                f"Provisioned {len(new_vol_ids)} new volunteer profiles into `volunteers` table."
            )
        else:
            for idx, name in enumerate(new_vols.keys(), start=1000):
                new_vol_ids[name.lower()] = idx
                direct_map[name.lower()] = idx

        # Existing inventory tag mapping: canonical_tag -> inventory_id
        existing_tags: dict[str, int] = {}
        for row in conn.execute("SELECT inventory_id, bike_tag FROM bike_inventory").fetchall():
            existing_tags[canonical_bike_tag(row[1])] = row[0]

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

        total_rows = 0
        filtered_placeholder = 0
        inserted_bikes = 0
        inserted_contributions = 0
        multi_contributions = 0
        matched_volunteer_count = 0
        unmatched_volunteer_count = 0
        unmatched_pre_2025 = 0
        unmatched_2025_single_or_org = 0

        for row_idx, row in enumerate(
            sheet.iter_rows(min_row=2, max_col=9, values_only=True), start=2
        ):
            if not any(row):
                continue
            total_rows += 1

            raw_ts, raw_shop, raw_tag, raw_make, raw_model, raw_colour, raw_wheel, raw_type, raw_vol = (
                row
            )

            # Check for missing tag
            if raw_tag is None or str(raw_tag).strip() == "":
                filtered_placeholder += 1
                continue

            # Check for placeholder/test tags
            c_tag = canonical_bike_tag(raw_tag)
            c_tag_low = c_tag.lower()
            if (
                c_tag_low in PLACEHOLDER_TAGS
                or "test" in c_tag_low
                or c_tag_low == "0"
            ):
                filtered_placeholder += 1
                continue

            shop_code, shop_note = normalize_shop(raw_shop)
            wheel_norm = normalize_wheel_size(raw_wheel)
            type_norm = normalize_bike_type(raw_type)
            ts_norm = normalize_timestamp(raw_ts) or now_utc
            dt = raw_ts if isinstance(raw_ts, datetime) else None
            year = dt.year if dt else 2021

            make_clean = str(raw_make).strip() if raw_make is not None else None
            model_clean = str(raw_model).strip() if raw_model is not None else None
            colour_clean = str(raw_colour).strip() if raw_colour is not None else None
            vol_clean = str(raw_vol).strip() if raw_vol is not None else None

            # Resolve volunteer
            vol_id = None
            if vol_clean:
                vol_id = match_existing_volunteer(vol_clean, direct_map, initial_map)
                if vol_id is None:
                    # Check if matches newly provisioned 2025 volunteer
                    parts = vol_clean.split()
                    if len(parts) >= 2:
                        canon = " ".join(p.capitalize() for p in parts).lower()
                        vol_id = new_vol_ids.get(canon)

            if vol_id is not None:
                matched_volunteer_count += 1
            else:
                unmatched_volunteer_count += 1
                if year >= 2025:
                    unmatched_2025_single_or_org += 1
                else:
                    unmatched_pre_2025 += 1

            source_key = f"finished-bike-inventory:{row_idx}"
            source_sheet = SHEET_NAME
            source_row = row_idx

            if c_tag not in existing_tags:
                # First time seeing this bike tag: insert into bike_inventory
                if apply:
                    cursor = conn.execute(
                        """
                        INSERT INTO bike_inventory (
                            bike_tag, shop_name, recorded_at, make, model, colour, wheel_size, bike_type, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            c_tag,
                            shop_code,
                            ts_norm,
                            make_clean,
                            model_clean,
                            colour_clean,
                            wheel_norm,
                            type_norm,
                            now_utc,
                        ),
                    )
                    inv_id = cursor.lastrowid
                else:
                    inv_id = -len(existing_tags) - 1

                existing_tags[c_tag] = inv_id
                inserted_bikes += 1

                # Insert primary contribution
                contrib_notes = shop_note
                if apply:
                    conn.execute(
                        """
                        INSERT INTO bike_contributions (
                            inventory_id, volunteer_id, recorded_name, recorded_at,
                            source_key, source_sheet, source_row, notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            inv_id,
                            vol_id,
                            vol_clean,
                            ts_norm,
                            source_key,
                            source_sheet,
                            source_row,
                            contrib_notes,
                        ),
                    )
                inserted_contributions += 1
            else:
                # Tag already exists: record as additional contribution in bike_contributions
                inv_id = existing_tags[c_tag]
                multi_contributions += 1

                # Formulate explanatory note if bike attributes differ
                variation_parts = []
                if shop_note:
                    variation_parts.append(shop_note)
                if make_clean or model_clean:
                    variation_parts.append(
                        f"Entry make/model: {make_clean or ''} {model_clean or ''}".strip()
                    )
                if colour_clean:
                    variation_parts.append(f"Colour: {colour_clean}")
                if raw_shop:
                    variation_parts.append(f"Shop: {raw_shop}")

                notes = (
                    "Reused tag / additional contribution. "
                    + "; ".join(variation_parts)
                    if variation_parts
                    else "Additional contribution"
                )

                if apply:
                    conn.execute(
                        """
                        INSERT INTO bike_contributions (
                            inventory_id, volunteer_id, recorded_name, recorded_at,
                            source_key, source_sheet, source_row, notes
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            inv_id,
                            vol_id,
                            vol_clean,
                            ts_norm,
                            source_key,
                            source_sheet,
                            source_row,
                            notes,
                        ),
                    )
                inserted_contributions += 1

        if apply:
            conn.commit()
            print("Changes committed successfully.")

            # Integrity checks
            fk_check = conn.execute("PRAGMA foreign_key_check").fetchall()
            integrity = conn.execute("PRAGMA integrity_check").fetchall()

            if fk_check:
                raise RuntimeError(f"Foreign key check failed: {fk_check}")
            if integrity != [("ok",)]:
                raise RuntimeError(f"Integrity check failed: {integrity}")

            print("PRAGMA foreign_key_check: clean (0 errors)")
            print("PRAGMA integrity_check: ok")

        metrics = {
            "mode": "APPLY" if apply else "DRY-RUN",
            "backup_path": str(backup_path) if backup_path else None,
            "total_rows_read": total_rows,
            "filtered_placeholders": filtered_placeholder,
            "valid_records": total_rows - filtered_placeholder,
            "unique_bikes_inserted": inserted_bikes,
            "contributions_inserted": inserted_contributions,
            "multi_contributions": multi_contributions,
            "new_volunteers_provisioned": len(new_vols),
            "matched_volunteers": matched_volunteer_count,
            "unmatched_volunteers": unmatched_volunteer_count,
            "unmatched_pre_2025_kept_null": unmatched_pre_2025,
            "unmatched_2025_plus_single_or_org": unmatched_2025_single_or_org,
            "attribution_rate_percent": round(
                (matched_volunteer_count / (total_rows - filtered_placeholder)) * 100,
                1,
            ),
        }

        print("\n=== MIGRATION SUMMARY (2-Year Moving Window Policy) ===")
        for k, v in metrics.items():
            print(f"  {k}: {v}")

        return metrics

    finally:
        conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="Migrate Finished Bike Inventory from Excel into PIF Portal database."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )
    parser.add_argument(
        "--excel-path",
        type=Path,
        default=DEFAULT_EXCEL_PATH,
        help=f"Path to raw Excel workbook (default: {DEFAULT_EXCEL_PATH})",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes to the database (defaults to dry-run)",
    )
    args = parser.parse_args()

    run_migration(args.db_path, args.excel_path, apply=args.apply)


if __name__ == "__main__":
    main()
