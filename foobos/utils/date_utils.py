"""
Date parsing and formatting utilities.
"""

from datetime import datetime, timedelta
from typing import Tuple, Optional
from dateutil import parser as dateparser


def parse_date(date_str: str, default_year: Optional[int] = None) -> Optional[datetime]:
    """
    Parse various date formats into datetime.

    Handles:
    - "Jan 24, 2026"
    - "1/24/2026"
    - "2026-01-24"
    - "Friday, January 24"
    - "Fri Jan 24"
    """
    if not date_str:
        return None

    try:
        # Try dateutil parser first (handles most formats)
        dt = dateparser.parse(date_str)

        # If year is missing or seems wrong, use default
        if dt and default_year and dt.year < 2020:
            dt = dt.replace(year=default_year)

        return dt
    except (ValueError, TypeError):
        return None


def format_date(dt: datetime, fmt: str = "short") -> str:
    """
    Format datetime for display.

    Formats:
    - "short": "Fri Jan 24"
    - "long": "Friday, January 24, 2026"
    - "iso": "2026-01-24"
    """
    if fmt == "short":
        return dt.strftime("%a %b %-d")
    elif fmt == "long":
        return dt.strftime("%A, %B %-d, %Y")
    elif fmt == "iso":
        return dt.strftime("%Y-%m-%d")
    return dt.strftime("%a %b %-d")


def get_week_range(dt: datetime) -> Tuple[datetime, datetime]:
    """
    Get the Sunday-Saturday week range containing the given date.

    Returns (start_date, end_date) tuple.
    """
    # Find the previous Sunday (or same day if already Sunday)
    days_since_sunday = dt.weekday() + 1  # Monday=0, so Sunday=-1+1=0... wait
    # Actually weekday(): Monday=0, Sunday=6
    # We want Sunday as start of week
    days_since_sunday = (dt.weekday() + 1) % 7
    start = dt - timedelta(days=days_since_sunday)
    end = start + timedelta(days=6)

    # Normalize to start of day
    start = start.replace(hour=0, minute=0, second=0, microsecond=0)
    end = end.replace(hour=23, minute=59, second=59, microsecond=0)

    return (start, end)


def get_week_number(dt: datetime, reference_date: Optional[datetime] = None) -> int:
    """
    Get the week number relative to a reference date.

    Week 0 is the week containing the reference date.
    Used for generating by-date.X.html page numbers.
    """
    if reference_date is None:
        reference_date = datetime.now()

    ref_start, _ = get_week_range(reference_date)
    target_start, _ = get_week_range(dt)

    # Calculate difference in weeks
    diff = (target_start - ref_start).days // 7
    return max(0, diff)


def get_week_label(start: datetime, end: datetime) -> str:
    """
    Generate week label like "Jan 19 - Jan 25".
    """
    if start.month == end.month:
        return f"{start.strftime('%b %-d')} - {end.strftime('%b %-d')}"
    else:
        return f"{start.strftime('%b %-d')} - {end.strftime('%b %-d')}"


def get_adjusted_week_label(week_start: datetime, week_end: datetime, today: datetime) -> str:
    """
    Generate week label, adjusting start date to today if today falls within the week.

    For the current week, if today is after the week start (Sunday), use today
    as the display start date. This prevents showing past dates in the range.

    Args:
        week_start: The Sunday start of the week
        week_end: The Saturday end of the week
        today: Today's date

    Returns:
        Week label like "Jan 19 - Jan 25" with adjusted start if applicable
    """
    # Normalize dates for comparison
    today_normalized = today.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start_normalized = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end_normalized = week_end.replace(hour=0, minute=0, second=0, microsecond=0)

    # If today is within this week and after the week start, use today as start
    if week_start_normalized <= today_normalized <= week_end_normalized:
        display_start = today_normalized
    else:
        display_start = week_start_normalized

    return get_week_label(display_start, week_end_normalized)
