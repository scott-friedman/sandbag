"""
Main HTML generation orchestrator.
"""

from datetime import datetime
from typing import List
import logging
import json
from pathlib import Path

from ..models import Concert
from ..config import OUTPUT_DIR, DATA_DIR, SITE_NAME, WEEKS_AHEAD
from .index_generator import generate_index
from .by_date_generator import generate_by_date_pages
from .by_club_generator import generate_by_club_pages
from .by_band_generator import generate_by_band_pages
from .clubs_generator import generate_clubs_page

logger = logging.getLogger(__name__)


def generate_all_html(concerts: List[Concert]) -> None:
    """
    Generate all HTML files from concert data.

    Args:
        concerts: List of Concert objects to generate pages from
    """
    logger.info(f"Generating HTML for {len(concerts)} concerts...")

    # Sort concerts by date
    concerts = sorted(concerts, key=lambda c: c.date)

    # Generate each section
    generate_index(concerts)
    generate_by_date_pages(concerts)
    generate_by_club_pages(concerts)
    generate_by_band_pages(concerts)
    generate_clubs_page()

    # Save concert data as JSON for reference
    _save_concerts_json(concerts)

    logger.info("HTML generation complete!")


def _save_concerts_json(concerts: List[Concert]) -> None:
    """Save concerts to JSON file."""
    data_path = Path(DATA_DIR)
    data_path.mkdir(parents=True, exist_ok=True)

    output = {
        "meta": {
            "last_updated": datetime.now().isoformat(),
            "total_concerts": len(concerts),
            "generated_by": SITE_NAME,
        },
        "concerts": [c.to_dict() for c in concerts]
    }

    with open(data_path / "concerts.json", "w") as f:
        json.dump(output, f, indent=2)

    logger.info(f"Saved {len(concerts)} concerts to concerts.json")


# HTML template helpers

def html_header(title: str) -> str:
    """Generate HTML header with retro styling."""
    return f'''<!DOCTYPE html>
<html>
<head>
<title>{title}</title>
</head>
<body bgcolor="#FFFFFF" text="#000000" link="#0000FF" vlink="#800080">
'''


def html_footer() -> str:
    """Generate HTML footer."""
    return '''
</body>
</html>
'''


def html_nav_links(current: str = "") -> str:
    """Generate navigation links."""
    links = [
        ("index.html", "Home"),
        ("by-date.0.html", "by Date"),
        ("by-club.0.html", "by Venue"),
        ("by-band.0.html", "by Band"),
        ("clubs.html", "Club Directory"),
    ]

    parts = []
    for href, label in links:
        if current == href:
            parts.append(f"<b>{label}</b>")
        else:
            parts.append(f'<a href="{href}">{label}</a>')

    return "[" + "] [".join(parts) + "]"


def html_back_link() -> str:
    """Generate back to index link."""
    return '<p><a href="index.html">Back to The List</a></p>'


def format_concert_line(concert: Concert, link_venue: bool = True, link_bands: bool = True) -> str:
    """
    Format a single concert as an HTML line.

    Format: <a href="clubs.html#venue"><b>Venue, City</b></a> Band1, Band2 age price time flags
    """
    parts = []

    # Venue
    if link_venue:
        venue_link = f'<a href="clubs.html#{concert.venue_id}"><b>{concert.venue_name}, {concert.venue_location}</b></a>'
    else:
        venue_link = f"<b>{concert.venue_name}, {concert.venue_location}</b>"
    parts.append(venue_link)

    # Bands
    if link_bands and concert.bands:
        band_links = []
        for band in concert.bands:
            anchor = _band_to_anchor(band)
            page = _band_to_page(band)
            band_links.append(f'<a href="{page}#{anchor}">{band}</a>')
        parts.append(", ".join(band_links))
    elif concert.bands:
        parts.append(", ".join(concert.bands))

    # Age, price, time
    details = []
    details.append(concert.age_requirement)
    if concert.price_display:
        details.append(concert.price_display)
    details.append(concert.time)

    parts.append(" ".join(details))

    # Flags
    if concert.flags:
        parts.append(" ".join(concert.flags))

    return " ".join(parts)


def _band_to_anchor(band: str) -> str:
    """Convert band name to HTML anchor."""
    anchor = band.lower()
    anchor = anchor.replace(" ", "").replace("'", "").replace(".", "").replace(",", "")
    anchor = anchor.replace("&", "and").replace("$", "s")
    return anchor[:30]


def _band_to_page(band: str) -> str:
    """Determine which by-band page a band belongs on."""
    if not band:
        return "by-band.0.html"

    first_char = band[0].upper()

    if first_char.isdigit() or first_char < "E":
        return "by-band.0.html"  # #-D
    elif first_char < "M":
        return "by-band.1.html"  # E-L
    elif first_char < "S":
        return "by-band.2.html"  # M-R
    else:
        return "by-band.3.html"  # S-Z
