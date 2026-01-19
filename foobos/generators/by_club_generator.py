"""
Generate by-club.X.html pages - concerts organized by venue.
"""

from typing import List, Dict
import logging
from pathlib import Path
from collections import defaultdict

from ..models import Concert
from ..config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def generate_by_club_pages(concerts: List[Concert]) -> None:
    """Generate all by-club.X.html pages."""
    # Group concerts by venue
    by_venue: Dict[str, List[Concert]] = defaultdict(list)

    for concert in concerts:
        by_venue[concert.venue_id].append(concert)

    # Sort venues into pages by first letter
    # Page 0: A-G, Page 1: H-O, Page 2: P-Z
    pages: Dict[int, Dict[str, List[Concert]]] = {0: {}, 1: {}, 2: {}}

    for venue_id, venue_concerts in sorted(by_venue.items()):
        page_num = _venue_to_page_num(venue_id)
        pages[page_num][venue_id] = sorted(venue_concerts, key=lambda c: c.date)

    # Generate each page
    page_labels = ["A-G", "H-O", "P-Z"]
    for page_num, venues in pages.items():
        _generate_club_page(page_num, page_labels[page_num], venues)

    logger.info(f"Generated 3 by-club pages")


def _venue_to_page_num(venue_id: str) -> int:
    """Determine which page a venue belongs on."""
    if not venue_id:
        return 0

    first_char = venue_id[0].upper()

    if first_char < "H":
        return 0  # A-G
    elif first_char < "P":
        return 1  # H-O
    else:
        return 2  # P-Z


def _generate_club_page(page_num: int, label: str, venues: Dict[str, List[Concert]]) -> None:
    """Generate a single by-club.X.html page."""
    html = f'''<!DOCTYPE html>
<html>
<head>
<title>Listing By Club - {label}</title>
</head>
<body bgcolor="#FFFFFF" text="#000000" link="#0000FF" vlink="#800080">

<h2><i>Listing By Club</i></h2>

<h3>Clubs starting with {label}</h3>

<p><a href="index.html">Back to The List</a></p>

<hr>

'''

    for venue_id, concerts in sorted(venues.items()):
        if not concerts:
            continue

        # Get venue display name from first concert
        venue_name = concerts[0].venue_name
        venue_location = concerts[0].venue_location

        html += f'<h4><a name="{venue_id}">{venue_name}, {venue_location}</a></h4>\n'
        html += '<ul>\n'

        for concert in concerts:
            date_str = concert.date.strftime("%a %b %-d")
            bands_str = ", ".join(concert.bands)
            details = f"{concert.age_requirement} {concert.price_display} {concert.time}".strip()
            flags_str = " ".join(concert.flags)

            line = f"{date_str} - {bands_str} {details}"
            if flags_str:
                line += f" {flags_str}"

            html += f'<li>{line}</li>\n'

        html += '</ul>\n\n'

    html += '''<hr>

<p><a href="index.html">Back to The List</a></p>

</body>
</html>
'''

    output_path = Path(OUTPUT_DIR) / f"by-club.{page_num}.html"
    with open(output_path, "w") as f:
        f.write(html)
