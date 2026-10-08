# Order workflow and existing validation

Reviewed 2026-10-08 against the application worktree and a read-only inspection of
the current database. These are existing rules, not newly introduced requirements.
Data migration and historical-data finalization remain separate work.

## Orders can operate without workshop data

Creating, contacting, cancelling, restoring and completing orders do not require
Finished Bike Inventory, volunteers, contributions or hours. Pickup accepts a new
numeric bike tag without looking it up in inventory. The current orders table has
no foreign key, trigger or unique tag constraint linking it to inventory.

Inventory tags are intended to identify unique bikes across shops and years. That
does not currently prevent the same tag being recorded on multiple order lines.
Any proposed rule against reuse must be discussed before implementation.

## Supported transitions

| Starting state | Action | Result | Existing requirement |
| --- | --- | --- | --- |
| New submission | Save | Open | Valid intake fields |
| Open | Contact | Contacted | Staff login and valid form token |
| Open | Cancel | Cancelled | Confirm cancellation |
| Contacted | Pickup | Completed | Pickup date and positive whole-number tag |
| Contacted | Cancel | Cancelled | Confirm cancellation |
| Cancelled | Restore | Open | Always restores to Open, regardless of prior state |

Completed records have no further status transition through the standard Order
Desk controls. Invalid or stale transitions are rejected instead of silently
overwriting a changed order. Repeated status actions do not repeat updates; an
identical pickup retry is accepted without applying completion twice.

Actions operate on individual recipient/order lines. A submission for multiple
bikes creates one line per recipient, each initially Open. Completing one line
does not complete all lines in the submission.

## Required intake data

- Staff login and a valid form token for the staff New Order page.
- Contact name, existing shop, valid order date and order category.
- At least one recipient name; up to 100 recipients per submission.
- Pedal Partner name when that category is selected. A new typed partner name
  can be created; a populated partner directory is not a prerequisite.
- Email and phone are independently optional. Supplied values are validated;
  phone accepts a US ten-digit number with optional country prefix 1.
- Optional age must be a whole number from 1 to 80 (requested during the New Order
  review on 2026-10-08). Supplied height, style and
  bike choices must match the supported options. Names have a 150-character
  limit and notes a 2,000-character limit.

Contact and recipient records are created as part of intake. All lines save in
one transaction. Retry protection prevents the same form submission from being
created twice. Email setup is not a prerequisite for saving or changing status;
delivery failures do not roll back the saved order action.

## Pickup assumptions and limitations to discuss

- A valid calendar pickup date and positive integer bike tag are required.
- Letters, decimal tags and blank tags are currently rejected. Inventory supports
  a wider tag format, so an alphanumeric inventory tag cannot currently be used
  in the order pickup form. No change was made to that rule in this review.
- Leading zeros collapse: 00123 is stored as the same numeric value as 123.
- The legacy orders column is REAL. Very long tags can lose precision; tag-format
  and storage changes should be agreed before introducing a new restriction or
  migrating this column.
- Pickup does not currently enforce inventory existence, inventory availability,
  uniqueness across orders, volunteer attribution, a nonfuture date or a date
  after the order date.

## Separate workshop requirements

Workshop forms have their own requirements. Finished Bike submissions need a
volunteer, tag and shop; an existing inventory tag requires confirmation and
preserves its original details. Hours require a volunteer, date and positive
duration, with a maximum daily total of 24 hours. Public forms select active
volunteers created by staff. These requirements do not apply to order pickup.

## Verification and preview

Automated workflow coverage now creates an order with blank phone and email,
checks that it appears in Open, exercises both cancellation paths and restoration,
then completes it with a tag absent from inventory. All four workshop tables stay
empty. Separate coverage exercises the pipeline with no inventory table present.
Validation: all 139 Python tests and all 3 existing Node order-action tests pass.

The local review website is http://127.0.0.1:5004/ and uses a separate SQLite copy
under the primary checkout's ignored `data/previews/order-review-20261008-a770c3/`.
Its `run.py` starts the development worktree with email and scheduler disabled.
Only that copy received the existing maintenance schema initialization. The
active database and source spreadsheets were not changed. Existing staff login
credentials are retained; no test account or authentication bypass was added.

Start the page-by-page review with New Order, then Order Desk: Open, Contacted,
Cancelled/Restore and Completed. Discuss any proposed new business validation and
its assumptions before enforcing it.
