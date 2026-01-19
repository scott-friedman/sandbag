"""
Generate index.html - main landing page.
"""

from datetime import datetime, timedelta
from typing import List
import logging
from pathlib import Path

from ..models import Concert
from ..config import OUTPUT_DIR, SITE_NAME, SITE_TITLE, SITE_DESCRIPTION, SITE_EMAIL, WEEKS_AHEAD
from ..utils.date_utils import get_week_range, get_week_label

logger = logging.getLogger(__name__)


def generate_index(concerts: List[Concert]) -> None:
    """Generate the main index.html page."""
    today = datetime.now()
    update_date = today.strftime("%-m/%-d/%Y")

    # Calculate week ranges for navigation
    week_links = _generate_week_links(today)
    club_links = _generate_club_links()
    band_links = _generate_band_links()

    html = f'''<!DOCTYPE html>
<html>
<head>
<title>{SITE_TITLE} (updated {update_date})</title>
</head>
<body bgcolor="#FFFFFF" text="#000000" link="#0000FF" vlink="#800080">

<h2><i>{SITE_TITLE} (updated {update_date})</i></h2>

<p>
This is a WWW version of <a href="mailto:{SITE_EMAIL}">{SITE_NAME}'s</a> excellent <a href="index.html">(Boston) Greater Boston Area concert guide</a>. All of the content is automatically aggregated from multiple sources including Ticketmaster and local venue calendars. Please <a href="mailto:{SITE_EMAIL}">send us mail</a> if you have questions or corrections related to the list content.
</p>

<p>
Here's what the symbols at the end of each listing mean:
</p>

<pre>
  *     recommendable shows                 a/a   all ages
  $     will probably sell out              @     pit warning
  ^     under 21 must buy drink tickets     #     no ins/outs
</pre>

<hr>

<p>
<b>Jan 1, 2026:</b> Welcome to {SITE_NAME}! Inspired by the legendary <a href="http://www.foopee.com/punk/the-list/">foopee.com</a> Bay Area List.<br>
<b>Jan 1, 2026:</b> Site now auto-updates daily from Ticketmaster + local venue scraping.<br>
</p>

<hr>

<p>
<b>Concerts By Date</b><br>
{week_links}
</p>

<p>
<b>Concerts By Club</b><br>
{club_links}
</p>

<p>
<b>Concerts By Band</b><br>
{band_links}
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


def _generate_club_links() -> str:
    """Generate club section links."""
    return '''&nbsp;&nbsp;&nbsp;&nbsp;<a href="by-club.0.html">Clubs starting with A-G</a><br>
&nbsp;&nbsp;&nbsp;&nbsp;<a href="by-club.1.html">Clubs starting with H-O</a><br>
&nbsp;&nbsp;&nbsp;&nbsp;<a href="by-club.2.html">Clubs starting with P-Z</a>'''


def _generate_band_links() -> str:
    """Generate band section links."""
    return '''&nbsp;&nbsp;&nbsp;&nbsp;<a href="by-band.0.html">Bands starting with #-D</a><br>
&nbsp;&nbsp;&nbsp;&nbsp;<a href="by-band.1.html">Bands starting with E-L</a><br>
&nbsp;&nbsp;&nbsp;&nbsp;<a href="by-band.2.html">Bands starting with M-R</a><br>
&nbsp;&nbsp;&nbsp;&nbsp;<a href="by-band.3.html">Bands starting with S-Z</a>'''
