# Volunteer Reconciliation & Review Register (2025–2026 Moving Window)

**Author:** Development Agent / Approved by Project Owner  
**Date:** 2026-11-24  
**Policy Baseline:** Moving 2-Year Window (2025–2026) for Volunteer Resolution  

---

## 1. Operating Policy & Purpose

Per project owner decision on 2026-11-24:
1. **Moving 2-Year Window Focus**: Staff operational focus and volunteer profile management is prioritized for the current and prior calendar year (**2025 through 2026**).
2. **Pre-2025 Records**: Any historical volunteer names prior to 2025 that do not have an exact or unambiguous match are retained with `volunteer_id = NULL` and full text stored in `recorded_name`. No staff effort is wasted attempting to deduplicate historical records from 2021–2024.
3. **Automated Aliases**: Obvious name abbreviations (e.g., `David Tovey` $\rightarrow$ `David T`, `Donn Schmidt` $\rightarrow$ `Donn S`) are mapped automatically.
4. **2025–2026 Full Names**: Clean two-word person names active in 2025–2026 are auto-provisioned as volunteer records with appropriate activity status (`is_active = 1` if active within 180 days, `0` otherwise).
5. **Staff Review Checklist**: This register tracks the remaining ambiguous entries (mononyms, nicknames, corporate groups) for staff review.

---

## 2. Automated Alias Mappings Applied

The following high-confidence name variations have been mapped to their corresponding registered volunteer profiles in `volunteers`:

| Entered Name in Finished Bikes | Canonical Target | Target `volunteer_id` | Rationale |
|---|---|---|---|
| `David Tovey` | `David T` | 13 | Registered time-clock profile |
| `Donn Schmidt` | `Donn S` | 14 | Registered time-clock profile |
| `Ann Neumann` | `Ann N` | 84 | Registered time-clock profile |
| `Rich Gonzales` / `Richard Gonzales` | `Richard G` | 27 | Registered time-clock profile |
| `Ben Gottschall` | `Ben G` | 15 | Registered time-clock profile |
| `Tom Woodcock` | `Tom W` | 2 | Registered time-clock profile |
| `Stu G-J` / `Stew G-J` | `Stu G` | 1 | Registered time-clock profile |
| `Charlie Miller` / `Charlse Miller` | `Charles Miller` | 81 | Registered time-clock profile |
| `Marty H` | `Marty Heyne` | 1 | Registered time-clock profile |

---

## 3. High-Volume Volunteers Auto-Provisioned (2025–2026 Active Window)

The migration auto-provisions **167 clean individual volunteer profiles** active in 2025–2026. Top contributors include:

1. **Joe Maneiro**: 107 bikes in 2025–2026 (418 lifetime across Bentonville & Rogers).
2. **Thomas S**: 11 bikes in 2026.
3. **Kevin Richter**: 7 bikes in 2025.
4. **Brayden McMurtrey**: 7 bikes in 2025–2026.
5. **Anthony Miller**: 6 bikes in 2025.
6. **Daniel Xiong**: 5 bikes in 2025.
7. **Will Frank**: 5 bikes in 2025.
8. **James Li**: 5 bikes in 2026.
9. **Daniel Rock**: 4 bikes in 2025.
10. **Chrystal Thomas**: 4 bikes in 2025.
11. **Owen Zimmerman**: 4 bikes in 2025.
12. **Josh Goseland**: 4 bikes in 2025.
13. **Sharon Bense**: 4 bikes in 2025.

---

## 4. Staff Review Checklist (Ambiguous 2025–2026 Entries)

The following entries occurred in the 2025–2026 window and were retained with `volunteer_id = NULL` and the raw text in `recorded_name`. Staff can review this list to determine if any should be rolled up into specific registered volunteers:

### 4.1 Potential Nicknames & Single Names

- [ ] **Kenny** (87 bikes) — Potential candidate: `Kenny W` (Volunteer ID 45) or new profile?
- [ ] **Justin** (45 bikes) — Single name; frequent contributor across Bentonville and Springdale.
- [ ] **Joef** / **Joefeagin** (16 bikes combined) — Probable match to `Joe Feagin` (Volunteer ID 384).
- [ ] **RC** (20 bikes) — Mononym / initials.
- [ ] **Cory** (16 bikes) — Single name.
- [ ] **John** (15 bikes) — Multiple Johns in database; requires staff disambiguation.
- [ ] **Asher** (13 bikes) — Single name at Bentonville.
- [ ] **Isaac** (11 bikes) — Single name.
- [ ] **Rob** (11 bikes) — Potential candidate: `Rob M` (Volunteer ID 17) or `Rob W` (Volunteer ID 48).
- [ ] **Charlie** (8 bikes) — Probable match to `Charles Miller` (Volunteer ID 81) or `Charlie Grant` (Volunteer ID 489).
- [ ] **Chris** (7 bikes) — Multiple Chrises in database.
- [ ] **Missy** (7 bikes) — Single name.
- [ ] **Sam** (5 bikes) — Single name.
- [ ] **Thomas** (5 bikes) — Probable match to `Thomas S` or `Thomas Barnard` (Volunteer ID 197).
- [ ] **Dalton** (5 bikes) — Single name.
- [ ] **Hunter** (5 bikes) — Single name.

### 4.2 Corporate / Group Volunteer Entries (Confirmed Non-Person)

These entries represent visiting teams or groups and should **remain unlinked** (`volunteer_id = NULL`) to avoid creating artificial volunteer accounts:

- [x] **Staff** (17 bikes) — Generic staff logging.
- [x] **Walmart** (10 bikes) — Corporate volunteer group.
- [x] **7L** (9 bikes) — Group code / team identifier.
- [x] **Sam’s Club** (2 bikes) — Corporate volunteer group.

---

## 5. Pre-2025 Historical Records Status

In accordance with the moving 2-year window rule:
* **2,710 contributions** recorded prior to January 1, 2025 that did not match existing profiles remain unlinked (`volunteer_id = NULL`).
* Their full raw text is preserved in `bike_contributions.recorded_name`.
* No staff review or data-cleaning effort is required for these historical entries.
