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

    # Generate by-club and by-band first to get anchor info for index
    _, venue_info = generate_by_club_pages(concerts)
    _, band_info = generate_by_band_pages(concerts)

    # Generate index with band/venue lists
    generate_index(concerts, band_info, venue_info)

    # Generate other pages
    generate_by_date_pages(concerts)
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
    return '<p><a href="list.html">Back to The List</a></p>'


# Re-export helpers for backwards compatibility
from .helpers import format_concert_line, _band_to_anchor, _band_to_page
