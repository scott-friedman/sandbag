"""
Generate by-band.html page - all concerts organized by band in one master list.
Matches foopee.com format: band header with bulleted shows underneath.
"""

from html import escape
from typing import List, Dict, Tuple
import logging
from pathlib import Path
from collections import defaultdict

from ..models import Concert
from ..config import OUTPUT_DIR, SITE_URL
from .helpers import html_header, html_footer

logger = logging.getLogger(__name__)


def _normalize_band_key(band: str) -> str:
    """Normalize band name for grouping (case-insensitive, no punctuation)."""
    key = band.lower().strip()
    key = key.replace("'", "").replace("'", "").replace(".", "").replace(",", "")
    return key


def generate_by_band_pages(concerts: List[Concert]) -> Tuple[int, Dict[str, Tuple[str, int]]]:
    """Generate the single by-band.html page.

    Returns:
        Tuple of (page_count, band_info_dict)
        band_info_dict maps band_name -> (anchor, page_num) where page_num is always 0
    """
    # Group concerts by normalized band key for deduplication
    by_band_key: Dict[str, List[Concert]] = defaultdict(list)
    # Track the preferred display name for each normalized key (most common or first seen)
    band_display_names: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for concert in concerts:
        for band in concert.bands:
            if band and len(band) > 1:  # Skip single characters
                key = _normalize_band_key(band)
                by_band_key[key].append(concert)
                band_display_names[key][band] += 1

    # Convert to display name keyed dict, using most frequent name variant
    by_band: Dict[str, List[Concert]] = {}
    key_to_display: Dict[str, str] = {}
    for key, concerts_list in by_band_key.items():
        # Choose the most common display name
        display_name = max(band_display_names[key].items(), key=lambda x: x[1])[0]
        by_band[display_name] = concerts_list
        key_to_display[key] = display_name

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


def _venue_to_anchor(venue_id: str) -> str:
    """Convert venue ID to HTML anchor (must match by_club_generator)."""
    anchor = venue_id.lower()
    anchor = anchor.replace(" ", "_").replace("'", "").replace(".", "").replace(",", "")
    return anchor[:30]


def _generate_band_page(bands: Dict[str, List[Concert]]) -> None:
    """Generate the single by-band.html page in foopee format."""
    band_count = len(bands)
    description = f"All {band_count} bands with upcoming Boston area concerts."

    html = html_header(
        title="Listing By Band",
        description=description,
        canonical_url=f"{SITE_URL}/by-band.html"
    )
    html += '''
<h2><i>Listing By Band</i></h2>

<p><a href="list.html">Back to The List</a></p>

<hr>

'''

    for band, concerts in sorted(bands.items(), key=lambda x: x[0].lower()):
        if not concerts:
            continue

        anchor = _band_to_anchor(band)
        # Escape band name to prevent XSS
        band_escaped = escape(band)

        # Sort concerts by date
        concerts = sorted(concerts, key=lambda c: c.date)

        # Band header (bold) with anchor
        html += f'<ul>\n'
        html += f'<li><a name="{anchor}"><b>{band_escaped}</b></a>\n'
        html += '<ul>\n'

        for concert in concerts:
            date_str = concert.date.strftime("%b %-d")
            # Escape venue info and create link with anchor
            venue_str = f"{escape(concert.venue_name)}, {escape(concert.venue_location)}"
            venue_anchor = _venue_to_anchor(concert.venue_id)

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

            line = f'<li><b>{date_str}</b> <a href="by-club.html#{venue_anchor}">{venue_str}</a> {details}'
            if flags_str:
                line += f" {flags_str}"
            # Event link - subtle arrow to source/ticket page
            if concert.source_url:
                line += f'&nbsp;<a href="{escape(concert.source_url)}" title="Event info" style="text-decoration:none;padding:8px 12px;margin:-8px -4px">→</a>'
            line += '</li>\n'

            html += line

        html += '</ul>\n'
        html += '</li>\n'
        html += '</ul>\n\n'

    html += '''<hr>

<p><a href="list.html">Back to The List</a></p>

'''
    html += html_footer()

    output_path = Path(OUTPUT_DIR) / "by-band.html"
    with open(output_path, "w") as f:
        f.write(html)
