"""
Generate by-band.X.html pages - concerts organized by band.
"""

from typing import List, Dict, Set
import logging
from pathlib import Path
from collections import defaultdict

from ..models import Concert
from ..config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def generate_by_band_pages(concerts: List[Concert]) -> None:
    """Generate all by-band.X.html pages."""
    # Group concerts by band
    by_band: Dict[str, List[Concert]] = defaultdict(list)

    for concert in concerts:
        for band in concert.bands:
            if band:
                by_band[band].append(concert)

    # Sort bands into pages by first letter
    # Page 0: #-D, Page 1: E-L, Page 2: M-R, Page 3: S-Z
    pages: Dict[int, Dict[str, List[Concert]]] = {0: {}, 1: {}, 2: {}, 3: {}}

    for band, band_concerts in sorted(by_band.items(), key=lambda x: x[0].lower()):
        page_num = _band_to_page_num(band)
        pages[page_num][band] = sorted(band_concerts, key=lambda c: c.date)

    # Generate each page
    page_labels = ["#-D", "E-L", "M-R", "S-Z"]
    for page_num, bands in pages.items():
        _generate_band_page(page_num, page_labels[page_num], bands)

    logger.info(f"Generated 4 by-band pages")


def _band_to_page_num(band: str) -> int:
    """Determine which page a band belongs on."""
    if not band:
        return 0

    first_char = band[0].upper()

    if first_char.isdigit() or first_char < "E":
        return 0  # #-D
    elif first_char < "M":
        return 1  # E-L
    elif first_char < "S":
        return 2  # M-R
    else:
        return 3  # S-Z


def _band_to_anchor(band: str) -> str:
    """Convert band name to HTML anchor."""
    anchor = band.lower()
    anchor = anchor.replace(" ", "").replace("'", "").replace(".", "").replace(",", "")
    anchor = anchor.replace("&", "and").replace("$", "s")
    return anchor[:30]


def _generate_band_page(page_num: int, label: str, bands: Dict[str, List[Concert]]) -> None:
    """Generate a single by-band.X.html page."""
    html = f'''<!DOCTYPE html>
<html>
<head>
<title>Listing By Band - {label}</title>
</head>
<body bgcolor="#FFFFFF" text="#000000" link="#0000FF" vlink="#800080">

<h2><i>Listing By Band</i></h2>

<h3>Bands starting with {label}</h3>

<p><a href="index.html">Back to The List</a></p>

<hr>

'''

    for band, concerts in sorted(bands.items(), key=lambda x: x[0].lower()):
        if not concerts:
            continue

        anchor = _band_to_anchor(band)

        for concert in concerts:
            date_str = concert.date.strftime("%a %b %-d")
            venue_short = concert.venue_name.split(",")[0]  # Just venue name, no city

            # Show other bands on the bill
            other_bands = [b for b in concert.bands if b != band]
            with_str = f"w/ {', '.join(other_bands)}" if other_bands else ""

            details = f"{concert.age_requirement} {concert.price_display} {concert.time}".strip()
            flags_str = " ".join(concert.flags)

            line = f'<p><a name="{anchor}"><b>{band}</b></a> - {date_str} [{venue_short}]'
            if with_str:
                line += f" {with_str}"
            line += f" {details}"
            if flags_str:
                line += f" {flags_str}"
            line += "</p>\n"

            html += line

    html += '''
<hr>

<p><a href="index.html">Back to The List</a></p>

</body>
</html>
'''

    output_path = Path(OUTPUT_DIR) / f"by-band.{page_num}.html"
    with open(output_path, "w") as f:
        f.write(html)
