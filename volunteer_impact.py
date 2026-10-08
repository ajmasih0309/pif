"""Read-only volunteer totals, shared by authorized views."""
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


def yearly_impact(conn, volunteer_id, through):
    """Calendar-year totals across shops; no names, notes or individual logs."""
    start, last = date(through.year, 1, 1), date(through.year, 12, 31)
    first_monday = start - timedelta(days=start.weekday())
    active, bikes, minutes = set(), set(), 0
    for row in conn.execute('''SELECT work_date,minutes FROM volunteer_hours
            WHERE volunteer_id=? AND voided_at IS NULL AND work_date BETWEEN ? AND ?''',
            (volunteer_id, start.isoformat(), through.isoformat())):
        try:
            day = date.fromisoformat(row['work_date'])
        except (ValueError, TypeError):
            continue
        if start <= day <= through:
            minutes += row['minutes']
            active.add((day - first_monday).days // 7)
    for row in conn.execute('''SELECT inventory_id,recorded_at FROM bike_contributions
            WHERE volunteer_id=?''', (volunteer_id,)):
        try:
            timestamp = datetime.fromisoformat(row['recorded_at'])
            # Historical timestamps without offsets use shop-local wall time.
            day = (timestamp.astimezone(ZoneInfo('America/Chicago')).date()
                   if timestamp.tzinfo else timestamp.date())
        except (ValueError, TypeError):
            continue
        if start <= day <= through:
            bikes.add(row['inventory_id'])
            active.add((day - first_monday).days // 7)
    weeks = []
    for index in range((last - first_monday).days // 7 + 1):
        monday = first_monday + timedelta(weeks=index)
        week_start, week_end = max(start, monday), min(last, monday + timedelta(days=6))
        state = 'active' if index in active else 'future' if week_start > through else 'empty'
        weeks.append({'state': state, 'label': f"{week_start:%b %d}–{week_end:%b %d}: " +
                      {'active': 'activity logged', 'future': 'upcoming', 'empty': 'no activity logged'}[state]})
    return {'year': through.year, 'minutes': minutes, 'bikes': len(bikes),
            'active_weeks': len(active), 'weeks': weeks}
