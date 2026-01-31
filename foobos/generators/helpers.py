"""
Helper functions for HTML generation.
"""

import json
from html import escape
from typing import Optional, Dict, Any

from ..models import Concert
from ..config import GA4_MEASUREMENT_ID, ANALYTICS_ENABLED, SITE_URL, DEFAULT_OG_IMAGE, SITE_NAME


def html_header(
    title: str,
    description: Optional[str] = None,
    canonical_url: Optional[str] = None,
    og_type: str = "website",
    og_image: Optional[str] = None,
    structured_data: Optional[Dict[str, Any]] = None
) -> str:
    """Generate HTML header with retro styling, SEO meta tags, and optional analytics.

    Args:
        title: Page title
        description: Meta description for SEO
        canonical_url: Canonical URL for the page
        og_type: Open Graph type (default: "website")
        og_image: Open Graph image URL (defaults to DEFAULT_OG_IMAGE)
        structured_data: JSON-LD structured data dict for schema.org
    """
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
</script>'''

    # SEO meta tags
    meta_tags = '<meta charset="UTF-8">\n'
    meta_tags += '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'

    if description:
        meta_tags += f'<meta name="description" content="{escape(description)}">\n'

    if canonical_url:
        meta_tags += f'<link rel="canonical" href="{canonical_url}">\n'

    # Open Graph tags
    og_image_url = og_image or DEFAULT_OG_IMAGE
    og_url = canonical_url or SITE_URL
    og_desc = description or ""

    meta_tags += f'<meta property="og:title" content="{escape(title)}">\n'
    if og_desc:
        meta_tags += f'<meta property="og:description" content="{escape(og_desc)}">\n'
    meta_tags += f'<meta property="og:type" content="{og_type}">\n'
    meta_tags += f'<meta property="og:url" content="{og_url}">\n'
    meta_tags += f'<meta property="og:site_name" content="{SITE_NAME}">\n'
    meta_tags += f'<meta property="og:image" content="{og_image_url}">\n'

    # Twitter Card tags
    meta_tags += '<meta name="twitter:card" content="summary_large_image">\n'
    meta_tags += f'<meta name="twitter:title" content="{escape(title)}">\n'
    if og_desc:
        meta_tags += f'<meta name="twitter:description" content="{escape(og_desc)}">\n'
    meta_tags += f'<meta name="twitter:image" content="{og_image_url}">\n'

    # JSON-LD structured data
    json_ld = ""
    if structured_data:
        json_ld = f'\n<script type="application/ld+json">\n{json.dumps(structured_data, indent=2)}\n</script>\n'

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
{meta_tags}<title>{title}</title>{analytics_script}{json_ld}
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
