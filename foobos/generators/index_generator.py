"""
Generate index.html - main landing page.
Matches foopee.com format with alphabetical band/venue listings.
"""

from datetime import datetime, timedelta
from html import escape
from typing import List, Dict, Tuple
import logging
from pathlib import Path

from ..models import Concert
from ..config import OUTPUT_DIR, SITE_NAME, SITE_TITLE, SITE_DESCRIPTION, SITE_EMAIL, WEEKS_AHEAD
from ..utils.date_utils import get_week_range, get_week_label

logger = logging.getLogger(__name__)


def generate_index(
    concerts: List[Concert],
    band_info: Dict[str, Tuple[str, int]] = None,
    venue_info: Dict[str, Tuple[str, str, int]] = None
) -> None:
    """Generate the main index.html page.

    Args:
        concerts: List of concerts
        band_info: Dict mapping band_name -> (anchor, page_num)
        venue_info: Dict mapping venue_id -> (display_name, anchor, page_num)
    """
    today = datetime.now()
    update_date = today.strftime("%-m/%-d/%Y")

    # Calculate week ranges for navigation
    week_links = _generate_week_links(today)

    # Generate alphabetical lists
    bands_list = _generate_bands_list(band_info) if band_info else ""
    venues_list = _generate_venues_list(venue_info) if venue_info else ""

    html = f'''<!DOCTYPE html>
<html>
<head>
<title>foobos - Boston Concert List</title>
<style>
body {{
  font-family: Arial, Helvetica, sans-serif;
  background: #FFFFFF;
  color: #000000;
  text-align: center;
  padding: 40px 20px;
}}
.site-title {{
  font-size: 48px;
  font-weight: bold;
  margin-bottom: 30px;
}}
.nav-links {{
  margin: 20px 0;
}}
.nav-links a {{
  color: #4B0082;
  text-decoration: none;
  font-size: 18px;
}}
.nav-links a:hover {{
  text-decoration: underline;
}}
.content {{
  max-width: 800px;
  margin: 0 auto;
  text-align: left;
  margin-top: 40px;
}}
.section-title {{
  font-weight: bold;
  margin-top: 20px;
}}
.band-list, .venue-list {{
  font-size: 14px;
  line-height: 1.8;
}}
hr {{
  border: none;
  border-top: 1px solid #ccc;
  margin: 30px 0;
}}
.footer {{
  margin-top: 40px;
  font-size: 12px;
  color: #666;
}}
a {{
  color: #4B0082;
}}
a:visited {{
  color: #800080;
}}
</style>
</head>
<body>

<div class="site-title">foobos</div>

<div class="nav-links">
[ <a href="by-date.0.html">concerts by date</a> ]<br>
[ <a href="by-band.html">concerts by band</a> ]<br>
[ <a href="by-club.html">concerts by venue</a> ]<br>
[ <a href="clubs.html">club info</a> ]
</div>

<div class="content">

<hr>

<p style="text-align: center; font-size: 14px;">
Boston's version of the legendary <a href="http://www.foopee.com/punk/the-list/">foopee concert list</a>.<br>
Updated {update_date}. <a href="mailto:sf@scottfriedman.ooo">Contact</a>.
</p>

<hr>

<p class="section-title">Quick Links - By Date</p>
{week_links}

<p class="section-title">All Bands</p>
<div class="band-list">
{bands_list}
</div>

<p class="section-title">All Venues</p>
<div class="venue-list">
{venues_list}
</div>

<hr>

<div class="footer">
<span id="visitor-count">Visitors: loading...</span>
</div>

</div>

<script>
(function() {{
  function isBot() {{
    if (navigator.webdriver) return true;
    var ua = navigator.userAgent.toLowerCase();
    var botPatterns = [
      'bot', 'crawl', 'spider', 'slurp', 'mediapartners',
      'headless', 'phantom', 'selenium', 'puppeteer', 'playwright',
      'wget', 'curl', 'python', 'java', 'perl', 'ruby',
      'scrapy', 'httpclient', 'nutch', 'dataprovider', 'feedfetcher',
      'facebookexternalhit', 'twitterbot', 'linkedinbot', 'embedly',
      'quora link preview', 'showyoubot', 'outbrain', 'pinterest',
      'applebot', 'yandex', 'baiduspider', 'duckduckbot', 'bingbot', 'googlebot',
      'ia_archiver', 'archive.org_bot'
    ];
    for (var i = 0; i < botPatterns.length; i++) {{
      if (ua.indexOf(botPatterns[i]) !== -1) return true;
    }}
    if (!window.localStorage || !window.sessionStorage) return true;
    if (!document.addEventListener) return true;
    return false;
  }}
  function alreadyCounted() {{
    try {{ return sessionStorage.getItem('foobos_counted') === 'true'; }}
    catch(e) {{ return false; }}
  }}
  function markCounted() {{
    try {{ sessionStorage.setItem('foobos_counted', 'true'); }} catch(e) {{}}
  }}
  function countVisit() {{
    if (isBot() || alreadyCounted()) {{
      fetch('https://api.counterapi.dev/v1/foobos-list/visits')
        .then(function(r) {{ return r.json(); }})
        .then(function(data) {{
          document.getElementById('visitor-count').textContent = 'Visitors: ' + data.count;
        }})
        .catch(function() {{
          document.getElementById('visitor-count').textContent = '';
        }});
      return;
    }}
    fetch('https://api.counterapi.dev/v1/foobos-list/visits/up')
      .then(function(r) {{ return r.json(); }})
      .then(function(data) {{
        document.getElementById('visitor-count').textContent = 'Visitors: ' + data.count;
        markCounted();
      }})
      .catch(function() {{
        document.getElementById('visitor-count').textContent = '';
      }});
  }}
  var counted = false;
  function onHumanInteraction() {{
    if (counted) return;
    counted = true;
    countVisit();
    document.removeEventListener('scroll', onHumanInteraction);
    document.removeEventListener('mousemove', onHumanInteraction);
    document.removeEventListener('click', onHumanInteraction);
    document.removeEventListener('touchstart', onHumanInteraction);
    document.removeEventListener('keydown', onHumanInteraction);
  }}
  document.addEventListener('scroll', onHumanInteraction);
  document.addEventListener('mousemove', onHumanInteraction);
  document.addEventListener('click', onHumanInteraction);
  document.addEventListener('touchstart', onHumanInteraction);
  document.addEventListener('keydown', onHumanInteraction);
  setTimeout(function() {{
    if (!counted && document.visibilityState === 'visible' && document.hasFocus()) {{
      onHumanInteraction();
    }}
  }}, 3000);
}})();
</script>

</body>
</html>
'''

    output_path = Path(OUTPUT_DIR) / "list.html"
    with open(output_path, "w") as f:
        f.write(html)

    logger.info(f"Generated list.html")


def _generate_week_links(start_date: datetime) -> str:
    """Generate week range links for Concerts By Date section."""
    lines = []

    for week_num in range(WEEKS_AHEAD):
        week_start = start_date + timedelta(weeks=week_num)
        week_start, week_end = get_week_range(week_start)
        label = get_week_label(week_start, week_end)
        lines.append(f'<a href="by-date.{week_num}.html">{label}</a>')

    return " | ".join(lines)


def _generate_bands_list(band_info: Dict[str, Tuple[str, int]]) -> str:
    """Generate alphabetical band list with hyperlinks, separated by asterisks.

    Format: * Band1 * Band2 * Band3 *
    Each band links to its anchor on the single by-band.html page.
    All band names are HTML-escaped to prevent XSS attacks.
    """
    if not band_info:
        return ""

    # Sort bands alphabetically (case-insensitive)
    sorted_bands = sorted(band_info.keys(), key=lambda x: x.lower())

    links = []
    for band in sorted_bands:
        anchor, _ = band_info[band]
        # Escape band name to prevent XSS
        link = f'<a href="by-band.html#{anchor}">{escape(band)}</a>'
        links.append(link)

    # Join with asterisks
    return "* " + " * ".join(links) + " *"


def _generate_venues_list(venue_info: Dict[str, Tuple[str, str, int]]) -> str:
    """Generate alphabetical venue list with hyperlinks, separated by asterisks.

    Format: * Venue1, City * Venue2, City *
    Each venue links to its anchor on the single by-club.html page.
    All venue names are HTML-escaped to prevent XSS attacks.
    """
    if not venue_info:
        return ""

    # Sort venues alphabetically by display name (case-insensitive)
    # Handle "The " prefix for sorting
    def sort_key(item):
        venue_id, (display_name, anchor, page_num) = item
        name = display_name
        if name.lower().startswith("the "):
            return name[4:].lower()
        return name.lower()

    sorted_venues = sorted(venue_info.items(), key=sort_key)

    links = []
    for venue_id, (display_name, anchor, _) in sorted_venues:
        # Escape venue name to prevent XSS
        link = f'<a href="by-club.html#{anchor}">{escape(display_name)}</a>'
        links.append(link)

    # Join with asterisks
    return "* " + " * ".join(links) + " *"
