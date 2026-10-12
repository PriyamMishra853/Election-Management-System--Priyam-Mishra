"""Shared constants and small helpers."""
from datetime import date, datetime

DISTRICTS = ["Nashik", "Pune", "Mumbai", "Jalgaon", "Satara"]
TS = "%Y-%m-%dT%H:%M"  # matches the HTML datetime-local format, so strings compare in time order


def now():
    return datetime.now().strftime(TS)


def election_status(e):
    """Elections move through their lifecycle purely by the clock."""
    t = now()
    if t < e["start_at"]:
        return "upcoming"
    if t < e["end_at"]:
        return "live"
    return "closed"


def age(dob):
    d = date.fromisoformat(dob)
    t = date.today()
    return t.year - d.year - ((t.month, t.day) < (d.month, d.day))


def fmt_dt(s):
    try:
        return datetime.strptime(s[:16], TS).strftime("%d %b %Y, %H:%M")
    except (ValueError, TypeError):
        return s
