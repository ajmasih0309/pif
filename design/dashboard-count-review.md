# Dashboard count review — 2026-10-05

Read-only review of the current July-era database and the local design preview.
Their 2025 aggregates agree. No source records, status mappings, shop assignments,
or migration rules were changed. Data preparation remains paused.

## What the dashboard measures

Each recipient added by intake creates one record in `orders` with one bike's
details. The dashboard counts records with `order_status = 'Completed'`, using
`pickup_date` for the selected year and months and `shop_name` for the shops.
It does not collapse a multi-bike order to one, count open/cancelled bikes in a
partially completed order, or count distinct bike tags. There is no additional
quantity field to multiply. The old `bikes` table is empty and is not the source.

For 2025, Jan–Dec, B/R/S selected:

| Shop | Completed bike records |
| --- | ---: |
| Bentonville | 1,872 |
| Rogers | 743 |
| Springdale | 781 |
| Total displayed | 3,396 |

The same records form 1,342 groups using Order Desk's contact/date/shop/type key.
Summing the bikes in those groups independently reproduces 3,396. This grouping
is a display convention, not an authoritative historical order identity.

Monthly totals: Jan 182, Feb 205, Mar 242, Apr 324, May 310, Jun 380, Jul 368,
Aug 200, Sep 271, Oct 288, Nov 173, Dec 453. The rendered dashboard matches this
independent tally. All seven dashboard regression tests pass, including multiple
completed bikes in one order and exclusion of its uncompleted bikes.

## Differences to reconcile with the organization's report

- Another 14 completed records have a 2025 pickup date but no shop. Selecting
  B/R/S excludes these; including unknown shops would give 3,410. Do not silently
  assign these to B while historical data preparation is paused.
- Counting completed records by 2025 **order date**, with B/R/S selected, gives
  2,605 instead. Missing order dates and pickups in different years affect this.
- Of the 3,396 records, 18 lack tags. The remaining 3,378 contain 3,234 distinct
  stored tag values: 141 tag values repeat, creating 144 additional occurrences.
  These are potential reconciliation issues, not proof of duplicate deliveries.
  Do not automatically delete records or switch to distinct-tag counting.
- Across all years, seven completed records have pickup years 1936 (three) or
  2027 (four). These need source review before treating the report as reconciled.

The organization's expected number, date basis, reporting period and shop scope
have been requested. The calculation is verified against stored records; the
historical total has not been reconciled to that external report.
