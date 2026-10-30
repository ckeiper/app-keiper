"""Bounded, deterministic repair of missing daily Ads snapshots."""
from datetime import date, timedelta


def missing_days_to_fetch(existing, today, initial=False, max_recent=3):
    if not isinstance(today, date):
        raise TypeError('today must be a date')
    known={str(day)[:10] for day in existing}
    if initial:
        return [(today-timedelta(days=i)).isoformat() for i in range(1,90)
                if (today-timedelta(days=i)).isoformat() not in known]
    # Repair the most recent 30 completed dates first, oldest missing day first.
    # Do not repeatedly request today's data here; it is collected separately.
    missing=[(today-timedelta(days=i)).isoformat() for i in range(30,0,-1)
             if (today-timedelta(days=i)).isoformat() not in known]
    return missing[:max(0,max_recent)]


def daily_days_to_fetch(existing, today, initial=False, max_recent=3):
    """Refresh yesterday's partial snapshot, then repair bounded missing dates.

    A row collected during the day is not its final result. Merely skipping
    existing rows would permanently retain that partial spend and revenue.
    """
    missing = missing_days_to_fetch(existing, today, initial, max_recent)
    yesterday = (today-timedelta(days=1)).isoformat()
    return [yesterday] + [day for day in missing if day != yesterday]

