"""
Generate by-club.html page - all concerts organized by venue in one master list.
Matches foopee.com format: venue header with bulleted shows underneath.
"""

from html import escape
from typing import List, Dict, Tuple
import logging
from pathlib import Path
from collections import defaultdict

from ..models import Concert
from ..config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def generate_by_club_pages(concerts: List[Concert]) -> Tuple[int, Dict[str, Tuple[str, str, int]]]:
    """Generate the single by-club.html page.

    Returns:
        Tuple of (page_count, venue_info_dict)
        venue_info_dict maps venue_id -> (display_name, anchor, page_num) where page_num is always 0
    """
    # Group concerts by venue
    by_venue: Dict[str, List[Concert]] = defaultdict(list)

    for concert in concerts:
        by_venue[concert.venue_id].append(concert)

    # Build venue_info for index page links
    venue_info: Dict[str, Tuple[str, str, int]] = {}

    for venue_id, venue_concerts in by_venue.items():
        if not venue_concerts:
            continue

        # Get display name from first concert
        display_name = f"{venue_concerts[0].venue_name}, {venue_concerts[0].venue_location}"
        anchor = _venue_to_anchor(venue_id)
        venue_info[venue_id] = (display_name, anchor, 0)  # All venues on page 0 now

    # Generate single page with all venues
    _generate_club_page(by_venue)

    logger.info(f"Generated 1 by-club page with {len(by_venue)} venues")

    return 1, venue_info


def _venue_to_anchor(venue_id: str) -> str:
    """Convert venue ID to HTML anchor."""
    anchor = venue_id.lower()
    anchor = anchor.replace(" ", "_").replace("'", "").replace(".", "").replace(",", "")
    return anchor[:30]


def _band_to_anchor(band: str) -> str:
    """Convert band name to HTML anchor (must match by_band_generator)."""
    anchor = band.lower()
    anchor = anchor.replace(" ", "_").replace("'", "").replace(".", "").replace(",", "")
    anchor = anchor.replace("&", "and").replace("$", "s")
    anchor = ''.join(c for c in anchor if c.isalnum() or c == '_')
    return anchor[:40]


def _generate_club_page(venues: Dict[str, List[Concert]]) -> None:
    """Generate the single by-club.html page in foopee format."""
    html = '''<!DOCTYPE html>
<html>
<head>
<title>Listing By Club</title>
</head>
<body bgcolor="#FFFFFF" text="#000000" link="#0000FF" vlink="#800080">

<h2><i>Listing By Club</i></h2>

<p><a href="list.html">Back to The List</a></p>

<hr>

'''

    # Sort venues by display name (handling "The" prefix)
    def sort_key(item):
        venue_id, concerts = item
        if not concerts:
            return venue_id.lower()
        name = concerts[0].venue_name
        if name.lower().startswith("the "):
            return name[4:].lower()
        return name.lower()

    for venue_id, concerts in sorted(venues.items(), key=sort_key):
        if not concerts:
            continue

        # Get venue display name from first concert - escape for XSS prevention
        venue_name = escape(concerts[0].venue_name)
        venue_location = escape(concerts[0].venue_location)
        anchor = _venue_to_anchor(venue_id)

        # Sort concerts by date
        concerts = sorted(concerts, key=lambda c: c.date)

        # Venue header (bold)
        html += f'<ul>\n'
        html += f'<li><a name="{anchor}"><b>{venue_name}, {venue_location}</b></a>\n'
        html += '<ul>\n'

        for concert in concerts:
            date_str = concert.date.strftime("%b %-d")
            # Create individual band links with anchors
            band_links = []
            for band in concert.bands:
                band_escaped = escape(band)
                band_anchor = _band_to_anchor(band)
                band_links.append(f'<a href="by-band.html#{band_anchor}">{band_escaped}</a>')
            bands_str = ", ".join(band_links)

            # Build details string - escape all scraped data
            details_parts = []
            if concert.age_requirement and concert.age_requirement != "a/a":
                details_parts.append(escape(concert.age_requirement))
            else:
                details_parts.append("a/a")

            if concert.price_display:
                details_parts.append(escape(concert.price_display))

            if concert.time:
                details_parts.append(escape(concert.time))

            details = " ".join(details_parts)

            # Add flags - escape to prevent XSS
            flags_str = " ".join(escape(flag) for flag in concert.flags) if concert.flags else ""

            line = f'<li><b>{date_str}</b> {bands_str} {details}'
            if flags_str:
                line += f" {flags_str}"
            line += '</li>\n'

            html += line

        html += '</ul>\n'
        html += '</li>\n'
        html += '</ul>\n\n'

    html += '''<hr>

<p><a href="list.html">Back to The List</a></p>

</body>
</html>
'''

    output_path = Path(OUTPUT_DIR) / "by-club.html"
    with open(output_path, "w") as f:
        f.write(html)
