"""
Helper functions for HTML generation.
"""

from html import escape

from ..models import Concert
from ..config import GA4_MEASUREMENT_ID, ANALYTICS_ENABLED


def html_header(title: str) -> str:
    """Generate HTML header with retro styling and optional analytics."""
    analytics_script = ""
    if ANALYTICS_ENABLED and GA4_MEASUREMENT_ID:
        analytics_script = f'''
<!-- Google Analytics 4 -->
<script async src="https://www.googletagmanager.com/gtag/js?id={GA4_MEASUREMENT_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{GA4_MEASUREMENT_ID}');

  // Track page load performance
  window.addEventListener('load', function() {{
    if (window.performance) {{
      var timing = performance.timing;
      var pageLoadTime = timing.loadEventEnd - timing.navigationStart;
      gtag('event', 'page_load_time', {{
        'value': pageLoadTime,
        'event_category': 'Performance'
      }});
    }}
  }});

  // Track JavaScript errors
  window.onerror = function(msg, url, lineNo, columnNo, error) {{
    gtag('event', 'exception', {{
      'description': msg + ' at ' + url + ':' + lineNo,
      'fatal': false
    }});
    return false;
  }};
</script>
'''

    return f'''<!DOCTYPE html>
<html>
<head>
<title>{title}</title>{analytics_script}
</head>
<body bgcolor="#FFFFFF" text="#000000" link="#0000FF" vlink="#800080">
'''


def html_footer() -> str:
    """Generate HTML footer."""
    return '''
</body>
</html>
'''


def _venue_to_anchor(venue_id: str) -> str:
    """Convert venue ID to HTML anchor (must match by_club_generator)."""
    anchor = venue_id.lower()
    anchor = anchor.replace(" ", "_").replace("'", "").replace(".", "").replace(",", "")
    return anchor[:30]


def format_concert_line(concert: Concert, link_venue: bool = True, link_bands: bool = True) -> str:
    """
    Format a single concert as an HTML line.

    Format: <a href="clubs.html#venue"><b>Venue, City</b></a> Band1, Band2 age price time flags

    All scraped text is HTML-escaped to prevent XSS attacks.
    """
    parts = []

    # Venue - escape scraped names to prevent XSS
    venue_name = escape(concert.venue_name)
    venue_location = escape(concert.venue_location)
    venue_anchor = _venue_to_anchor(concert.venue_id)

    if link_venue:
        venue_link = f'<a href="by-club.html#{venue_anchor}"><b>{venue_name}, {venue_location}</b></a>'
    else:
        venue_link = f"<b>{venue_name}, {venue_location}</b>"
    parts.append(venue_link)

    # Bands - escape scraped names to prevent XSS
    if link_bands and concert.bands:
        band_links = []
        for band in concert.bands:
            band_escaped = escape(band)
            anchor = _band_to_anchor(band)
            page = _band_to_page(band)
            band_links.append(f'<a href="{page}#{anchor}">{band_escaped}</a>')
        parts.append(", ".join(band_links))
    elif concert.bands:
        parts.append(", ".join(escape(band) for band in concert.bands))

    # Age, price, time - escape to prevent XSS
    details = []
    details.append(escape(concert.age_requirement))
    if concert.price_display:
        details.append(escape(concert.price_display))
    details.append(escape(concert.time))

    parts.append(" ".join(details))

    # Flags - escape to prevent XSS
    if concert.flags:
        parts.append(" ".join(escape(flag) for flag in concert.flags))

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
