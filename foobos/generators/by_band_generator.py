"""
Generate by-band.html page - all concerts organized by band in one master list.
Matches foopee.com format: band header with bulleted shows underneath.
"""

from typing import List, Dict, Tuple
import logging
from pathlib import Path
from collections import defaultdict

from ..models import Concert
from ..config import OUTPUT_DIR

logger = logging.getLogger(__name__)


def generate_by_band_pages(concerts: List[Concert]) -> Tuple[int, Dict[str, Tuple[str, int]]]:
    """Generate the single by-band.html page.

    Returns:
        Tuple of (page_count, band_info_dict)
        band_info_dict maps band_name -> (anchor, page_num) where page_num is always 0
    """
    # Group concerts by band
    by_band: Dict[str, List[Concert]] = defaultdict(list)

    for concert in concerts:
        for band in concert.bands:
            if band and len(band) > 1:  # Skip single characters
                by_band[band].append(concert)

    # Build band_info for index page links
    band_info: Dict[str, Tuple[str, int]] = {}
    for band in by_band.keys():
        anchor = _band_to_anchor(band)
        band_info[band] = (anchor, 0)  # All bands on page 0 now

    # Generate single page with all bands
    _generate_band_page(by_band)

    logger.info(f"Generated 1 by-band page with {len(by_band)} bands")

    return 1, band_info


def _band_to_anchor(band: str) -> str:
    """Convert band name to HTML anchor."""
    anchor = band.lower()
    anchor = anchor.replace(" ", "_").replace("'", "").replace(".", "").replace(",", "")
    anchor = anchor.replace("&", "and").replace("$", "s")
    # Remove other special characters
    anchor = ''.join(c for c in anchor if c.isalnum() or c == '_')
    return anchor[:40]


def _generate_band_page(bands: Dict[str, List[Concert]]) -> None:
    """Generate the single by-band.html page in foopee format."""
    html = '''<!DOCTYPE html>
<html>
<head>
<title>Listing By Band</title>
</head>
<body bgcolor="#FFFFFF" text="#000000" link="#0000FF" vlink="#800080">

<h2><i>Listing By Band</i></h2>

<p><a href="index.html">Back to The List</a></p>

<hr>

'''

    for band, concerts in sorted(bands.items(), key=lambda x: x[0].lower()):
        if not concerts:
            continue

        anchor = _band_to_anchor(band)

        # Sort concerts by date
        concerts = sorted(concerts, key=lambda c: c.date)

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

            line = f'<li><b>{date_str}</b> <a href="by-club.html">{venue_str}</a> {details}'
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

    output_path = Path(OUTPUT_DIR) / "by-band.html"
    with open(output_path, "w") as f:
        f.write(html)
