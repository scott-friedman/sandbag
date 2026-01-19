"""
Helper functions for HTML generation.
"""

from ..models import Concert


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
    anchor = anchor.replace(" ", "_").replace("'", "").replace(".", "").replace(",", "")
    anchor = anchor.replace("&", "and").replace("$", "s")
    # Remove other special characters except underscores
    anchor = ''.join(c for c in anchor if c.isalnum() or c == '_')
    return anchor[:40]


def _band_to_page(band: str) -> str:
    """Determine which by-band page a band belongs on."""
    # All bands are on a single by-band.html page
    return "by-band.html"
