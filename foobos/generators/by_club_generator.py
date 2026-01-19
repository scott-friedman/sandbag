"""
Generate by-club.X.html pages - concerts organized by venue.
Matches foopee.com format: venue header with bulleted shows underneath.
"""

from typing import List, Dict, Tuple
import logging
from pathlib import Path
from collections import defaultdict

from ..models import Concert
from ..config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def generate_by_club_pages(concerts: List[Concert]) -> Tuple[int, Dict[str, Tuple[str, str, int]]]:
    """Generate all by-club.X.html pages.

    Returns:
        Tuple of (page_count, venue_info_dict)
        venue_info_dict maps venue_id -> (display_name, anchor, page_num)
    """
    # Group concerts by venue
    by_venue: Dict[str, List[Concert]] = defaultdict(list)

    for concert in concerts:
        by_venue[concert.venue_id].append(concert)

    # Sort venues into pages by first letter of venue NAME (not ID)
    # Page 0: A-G, Page 1: H-O, Page 2: P-Z
    pages: Dict[int, Dict[str, List[Concert]]] = {0: {}, 1: {}, 2: {}}
    venue_info: Dict[str, Tuple[str, str, int]] = {}  # venue_id -> (display_name, anchor, page_num)

    for venue_id, venue_concerts in by_venue.items():
        if not venue_concerts:
            continue

        # Get display name from first concert
        display_name = f"{venue_concerts[0].venue_name}, {venue_concerts[0].venue_location}"
        page_num = _name_to_page_num(venue_concerts[0].venue_name)
        anchor = _venue_to_anchor(venue_id)

        pages[page_num][venue_id] = sorted(venue_concerts, key=lambda c: c.date)
        venue_info[venue_id] = (display_name, anchor, page_num)

    # Generate each page
    page_labels = ["A-G", "H-O", "P-Z"]
    for page_num, venues in pages.items():
        _generate_club_page(page_num, page_labels[page_num], venues)

    logger.info(f"Generated 3 by-club pages")

    return 3, venue_info


def _name_to_page_num(name: str) -> int:
    """Determine which page a venue belongs on by its display name."""
    if not name:
        return 0

    # Skip leading "The " for sorting
    sort_name = name
    if sort_name.lower().startswith("the "):
        sort_name = sort_name[4:]

    first_char = sort_name[0].upper()

    if first_char.isdigit() or first_char < "H":
        return 0  # A-G (and numbers)
    elif first_char < "P":
        return 1  # H-O
    else:
        return 2  # P-Z


def _venue_to_anchor(venue_id: str) -> str:
    """Convert venue ID to HTML anchor."""
    anchor = venue_id.lower()
    anchor = anchor.replace(" ", "_").replace("'", "").replace(".", "").replace(",", "")
    return anchor[:30]


def _generate_club_page(page_num: int, label: str, venues: Dict[str, List[Concert]]) -> None:
    """Generate a single by-club.X.html page in foopee format."""
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

    # Sort venues by display name (handling "The" prefix)
    def sort_key(item):
        venue_id, concerts = item
        name = concerts[0].venue_name if concerts else venue_id
        if name.lower().startswith("the "):
            return name[4:].lower()
        return name.lower()

    for venue_id, concerts in sorted(venues.items(), key=sort_key):
        if not concerts:
            continue

        # Get venue display name from first concert
        venue_name = concerts[0].venue_name
        venue_location = concerts[0].venue_location
        anchor = _venue_to_anchor(venue_id)

        # Venue header (bold)
        html += f'<ul>\n'
        html += f'<li><a name="{anchor}"><b>{venue_name}, {venue_location}</b></a>\n'
        html += '<ul>\n'

        for concert in concerts:
            date_str = concert.date.strftime("%b %-d")
            bands_str = ", ".join(concert.bands)

            # Build details string
            details_parts = []
            if concert.age_requirement and concert.age_requirement != "a/a":
                details_parts.append(concert.age_requirement)
            else:
                details_parts.append("a/a")

            if concert.price_display:
                details_parts.append(concert.price_display)

            if concert.time:
                details_parts.append(concert.time)

            details = " ".join(details_parts)

            # Add flags
            flags_str = " ".join(concert.flags) if concert.flags else ""

            line = f'<li><b>{date_str}</b> <a href="by-date.0.html">{bands_str}</a> {details}'
            if flags_str:
                line += f" {flags_str}"
            line += '</li>\n'

            html += line

        html += '</ul>\n'
        html += '</li>\n'
        html += '</ul>\n\n'

    html += '''<hr>

<p><a href="index.html">Back to The List</a></p>

</body>
</html>
'''

    output_path = Path(OUTPUT_DIR) / f"by-club.{page_num}.html"
    with open(output_path, "w") as f:
        f.write(html)
