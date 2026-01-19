"""
Generate by-band.X.html pages - concerts organized by band.
Matches foopee.com format: band header with bulleted shows underneath.
"""

from typing import List, Dict, Set, Tuple
import logging
from pathlib import Path
from collections import defaultdict

from ..models import Concert
from ..config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def generate_by_band_pages(concerts: List[Concert]) -> Tuple[int, Dict[str, Tuple[str, int]]]:
    """Generate all by-band.X.html pages.

    Returns:
        Tuple of (page_count, band_info_dict)
        band_info_dict maps band_name -> (anchor, page_num)
    """
    # Group concerts by band
    by_band: Dict[str, List[Concert]] = defaultdict(list)

    for concert in concerts:
        for band in concert.bands:
            if band and len(band) > 1:  # Skip single characters
                by_band[band].append(concert)

    # Sort bands into pages by first letter
    # Page 0: #-D, Page 1: E-L, Page 2: M-R, Page 3: S-Z
    pages: Dict[int, Dict[str, List[Concert]]] = {0: {}, 1: {}, 2: {}, 3: {}}
    band_info: Dict[str, Tuple[str, int]] = {}  # band_name -> (anchor, page_num)

    for band, band_concerts in by_band.items():
        page_num = _band_to_page_num(band)
        anchor = _band_to_anchor(band)
        pages[page_num][band] = sorted(band_concerts, key=lambda c: c.date)
        band_info[band] = (anchor, page_num)

    # Generate each page
    page_labels = ["#-D", "E-L", "M-R", "S-Z"]
    for page_num, bands in pages.items():
        _generate_band_page(page_num, page_labels[page_num], bands)

    logger.info(f"Generated 4 by-band pages")

    return 4, band_info


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
    anchor = anchor.replace(" ", "_").replace("'", "").replace(".", "").replace(",", "")
    anchor = anchor.replace("&", "and").replace("$", "s")
    # Remove other special characters
    anchor = ''.join(c for c in anchor if c.isalnum() or c == '_')
    return anchor[:40]


def _generate_band_page(page_num: int, label: str, bands: Dict[str, List[Concert]]) -> None:
    """Generate a single by-band.X.html page in foopee format."""
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

        # Band header (bold) with anchor
        html += f'<ul>\n'
        html += f'<li><a name="{anchor}"><b>{band}</b></a>\n'
        html += '<ul>\n'

        for concert in concerts:
            date_str = concert.date.strftime("%b %-d")
            venue_str = f"{concert.venue_name}, {concert.venue_location}"

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

            line = f'<li><b>{date_str}</b> <a href="by-club.0.html">{venue_str}</a> {details}'
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

    output_path = Path(OUTPUT_DIR) / f"by-band.{page_num}.html"
    with open(output_path, "w") as f:
        f.write(html)
