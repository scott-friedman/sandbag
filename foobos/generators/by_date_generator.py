"""
Generate by-date.X.html pages - concerts organized by week.
"""

from datetime import datetime, timedelta
from typing import List, Dict
import logging
from pathlib import Path
from collections import defaultdict

from ..models import Concert
from ..config import OUTPUT_DIR, WEEKS_AHEAD
from ..utils.date_utils import get_week_range, get_week_label, get_week_number, get_adjusted_week_label
from .helpers import format_concert_line

logger = logging.getLogger(__name__)


def generate_by_date_pages(concerts: List[Concert]) -> None:
    """Generate all by-date.X.html pages."""
    today = datetime.now()

    # Group concerts by week number
    by_week: Dict[int, List[Concert]] = defaultdict(list)

    for concert in concerts:
        week_num = get_week_number(concert.date, today)
        if 0 <= week_num < WEEKS_AHEAD:
            by_week[week_num].append(concert)

    # Generate a page for each week
    for week_num in range(WEEKS_AHEAD):
        week_concerts = by_week.get(week_num, [])
        _generate_week_page(week_num, week_concerts, today)

    logger.info(f"Generated {WEEKS_AHEAD} by-date pages")


def _generate_date_shortcuts(current_week: int, reference_date: datetime) -> str:
    """Generate date range shortcuts like foopee format.

    Format: [ Jan 12 - Jan 18 | Jan 19 - Jan 25 | ... ]
    Current week is shown in bold without a link.
    Links wrap naturally across multiple lines.

    For the current week (week 0), the start date is adjusted to today
    to avoid showing past dates in the range.
    """
    from ..config import WEEKS_AHEAD

    today = reference_date  # reference_date is today when called from generate_by_date_pages
    parts = []
    for week_num in range(WEEKS_AHEAD):
        week_start = reference_date + timedelta(weeks=week_num)
        week_start, week_end = get_week_range(week_start)
        # Format as "Jan 12 - Jan 18" with adjusted start for current week
        label = get_adjusted_week_label(week_start, week_end, today)

        if week_num == current_week:
            # Current week - bold, no link
            parts.append(f"<b>{label}</b>")
        else:
            parts.append(f'<a href="by-date.{week_num}.html">{label}</a>')

    return "[ " + " | ".join(parts) + " ]"


def _generate_week_page(week_num: int, concerts: List[Concert], reference_date: datetime) -> None:
    """Generate a single by-date.X.html page.

    For the current week (week 0), the start date in the label is adjusted to today
    to avoid showing past dates in the range.
    """
    # Calculate week range
    today = reference_date  # reference_date is today when called from generate_by_date_pages
    week_start = reference_date + timedelta(weeks=week_num)
    week_start, week_end = get_week_range(week_start)
    week_label = get_adjusted_week_label(week_start, week_end, today)

    # Group concerts by day
    by_day: Dict[str, List[Concert]] = defaultdict(list)
    for concert in sorted(concerts, key=lambda c: c.date):
        day_key = concert.date.strftime("%Y-%m-%d")
        by_day[day_key].append(concert)

    # Generate HTML
    html = f'''<!DOCTYPE html>
<html>
<head>
<title>Listing By Date - {week_label}</title>
</head>
<body bgcolor="#FFFFFF" text="#000000" link="#0000FF" vlink="#800080">

<h2><i>Listing By Date</i></h2>

<h3>{week_label}</h3>

<ul>
'''

    # Generate entries for each day
    current_date = week_start
    while current_date <= week_end:
        day_key = current_date.strftime("%Y-%m-%d")
        day_concerts = by_day.get(day_key, [])

        if day_concerts:
            day_label = current_date.strftime("%a %b %-d")
            html += f'<li><b>{day_label}</b>\n<ul>\n'

            # Sort by venue name alphabetically
            sorted_concerts = sorted(day_concerts, key=lambda c: (c.venue_name or "").lower())
            for concert in sorted_concerts:
                line = format_concert_line(concert)
                html += f'<li>{line}</li>\n'

            html += '</ul>\n</li>\n\n'

        current_date += timedelta(days=1)

    # Generate date shortcuts
    date_shortcuts = _generate_date_shortcuts(week_num, reference_date)

    html += f'''</ul>

<hr>
<p>{date_shortcuts}</p>

<p>[ <a href="list.html">Back</a> | <a href="mailto:sf@scottfriedman.ooo">Email Me</a> ]</p>

</body>
</html>
'''

    # Write file
    output_path = Path(OUTPUT_DIR) / f"by-date.{week_num}.html"
    with open(output_path, "w") as f:
        f.write(html)
