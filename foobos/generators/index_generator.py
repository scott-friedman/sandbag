"""
Generate index.html - main landing page.
Matches foopee.com format with alphabetical band/venue listings.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Tuple
import logging
from pathlib import Path

from ..models import Concert
from ..config import OUTPUT_DIR, SITE_NAME, SITE_TITLE, SITE_DESCRIPTION, SITE_EMAIL, WEEKS_AHEAD
from ..utils.date_utils import get_week_range, get_week_label

logger = logging.getLogger(__name__)


def generate_index(
    concerts: List[Concert],
    band_info: Dict[str, Tuple[str, int]] = None,
    venue_info: Dict[str, Tuple[str, str, int]] = None
) -> None:
    """Generate the main index.html page.

    Args:
        concerts: List of concerts
        band_info: Dict mapping band_name -> (anchor, page_num)
        venue_info: Dict mapping venue_id -> (display_name, anchor, page_num)
    """
    today = datetime.now()
    update_date = today.strftime("%-m/%-d/%Y")

    # Calculate week ranges for navigation
    week_links = _generate_week_links(today)

    # Generate alphabetical lists
    bands_list = _generate_bands_list(band_info) if band_info else ""
    venues_list = _generate_venues_list(venue_info) if venue_info else ""

    html = f'''<!DOCTYPE html>
<html>
<head>
<title>The List (updated {update_date})</title>
</head>
<body bgcolor="#FFFFFF" text="#000000" link="#0000FF" vlink="#800080">

<h2><i>The List (updated {update_date})</i></h2>

<p>
This is a Boston version of the legendary <a href="http://www.foopee.com/punk/the-list/">foopee concert list</a>. This was all foopee's idea, I've tried to clone it for Boston. Please <a href="mailto:s_friedman+foobos@outlook.com">send me mail</a> if you have questions or corrections related to the list content.
</p>

<p>
Here's what the symbols at the end of each listing might mean:
</p>

<pre>
  *     recommendable shows                 a/a   all ages
  $     will probably sell out              @     pit warning
  ^     under 21 must buy drink tickets     #     no ins/outs
</pre>

<hr>

<p>
<b>Jan 19, 2026</b> Auto-updates daily from Ticketmaster, venue calendars, and other aggregators.<br>
<b>Jan 19, 2026</b> The List has gone live! Boston's own version of the legendary <a href="http://www.foopee.com/punk/the-list/">foopee concert list</a>.<br>
</p>

<hr>

<p>
<b>Concerts By Date</b><br>
{week_links}
</p>

<p>
<b>Concerts By Band</b><br>
{bands_list}
</p>

<p>
<b>Concerts By Venue</b><br>
{venues_list}
</p>

<p>
<b>Club Listing</b><br>
&nbsp;&nbsp;&nbsp;&nbsp;<a href="clubs.html">Club addresses and info</a>
</p>

</body>
</html>
'''

    output_path = Path(OUTPUT_DIR) / "index.html"
    with open(output_path, "w") as f:
        f.write(html)

    logger.info(f"Generated index.html")


def _generate_week_links(start_date: datetime) -> str:
    """Generate week range links for Concerts By Date section."""
    lines = []

    for week_num in range(WEEKS_AHEAD):
        week_start = start_date + timedelta(weeks=week_num)
        week_start, week_end = get_week_range(week_start)
        label = get_week_label(week_start, week_end)
        lines.append(f'&nbsp;&nbsp;&nbsp;&nbsp;<a href="by-date.{week_num}.html">{label}</a><br>')

    return "\n".join(lines)


def _generate_bands_list(band_info: Dict[str, Tuple[str, int]]) -> str:
    """Generate alphabetical band list with hyperlinks, separated by asterisks.

    Format: * Band1 * Band2 * Band3 *
    Each band links to its anchor on the single by-band.html page.
    """
    if not band_info:
        return ""

    # Sort bands alphabetically (case-insensitive)
    sorted_bands = sorted(band_info.keys(), key=lambda x: x.lower())

    links = []
    for band in sorted_bands:
        anchor, _ = band_info[band]
        link = f'<a href="by-band.html#{anchor}">{band}</a>'
        links.append(link)

    # Join with asterisks
    return "* " + " * ".join(links) + " *"


def _generate_venues_list(venue_info: Dict[str, Tuple[str, str, int]]) -> str:
    """Generate alphabetical venue list with hyperlinks, separated by asterisks.

    Format: * Venue1, City * Venue2, City *
    Each venue links to its anchor on the single by-club.html page.
    """
    if not venue_info:
        return ""

    # Sort venues alphabetically by display name (case-insensitive)
    # Handle "The " prefix for sorting
    def sort_key(item):
        venue_id, (display_name, anchor, page_num) = item
        name = display_name
        if name.lower().startswith("the "):
            return name[4:].lower()
        return name.lower()

    sorted_venues = sorted(venue_info.items(), key=sort_key)

    links = []
    for venue_id, (display_name, anchor, _) in sorted_venues:
        link = f'<a href="by-club.html#{anchor}">{display_name}</a>'
        links.append(link)

    # Join with asterisks
    return "* " + " * ".join(links) + " *"
