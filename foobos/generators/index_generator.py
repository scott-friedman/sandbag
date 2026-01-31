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
from ..config import OUTPUT_DIR, SITE_NAME, SITE_TITLE, SITE_DESCRIPTION, SITE_EMAIL, WEEKS_AHEAD, SITE_URL
from ..utils.date_utils import get_week_range, get_week_label, get_adjusted_week_label
from .helpers import html_header, html_footer

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

    # SEO description
    description = f"Boston concert listings - {len(concerts)} upcoming shows at local venues. Updated {update_date}."

    html = html_header(
        title=f"The List (updated {update_date})",
        description=description,
        canonical_url=f"{SITE_URL}/list.html"
    )
    html += f'''
<h2><i>The List (updated {update_date})</i></h2>

<p>
This is a Boston version of the legendary <a href="http://www.foopee.com/punk/the-list/">foopee concert list</a>. Please <a href="mailto:sf@scottfriedman.ooo">send me mail</a> if you have questions or corrections related to the list content.
</p>

<p>
Here's what the symbols at the end of each listing might mean:
</p>

<pre>
  *     recommendable shows                 a/a   all ages
  $     will probably sell out              @     pit warning
  ^     under 21 must buy drink tickets     #     no ins/outs
</pre>

<hr>

<p>
<b>Jan 18, 2026</b> The List has gone live! Boston's own version of the legendary <a href="http://www.foopee.com/punk/the-list/">foopee concert list</a>.<br>
</p>

<hr>

<p>
<label><input type="checkbox" id="hide-ln" onchange="toggleLN()"> Hide Ticketmaster Venues</label>
</p>

<p>
<b>Concerts By Date</b><br>
{week_links}
</p>

<p>
<b>Concerts By Band</b><br>
{bands_list}
</p>

<p>
<b>Concerts By Venue</b><br>
{venues_list}
</p>

<p>
<b>Club Listing</b><br>
&nbsp;&nbsp;&nbsp;&nbsp;<a href="clubs.html">Club addresses and info</a>
</p>

<hr>

<p>
<span id="visitor-count">Visitors: loading...</span>
</p>

<script>
(function() {{
  // Bot detection: check for common bot indicators
  function isBot() {{
    // Check for webdriver (headless browsers)
    if (navigator.webdriver) return true;

    // Check user agent for common bot patterns
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

    // Check for missing browser features that real browsers have
    if (!window.localStorage || !window.sessionStorage) return true;
    if (!document.addEventListener) return true;

    return false;
  }}

  // Check if already counted this session
  function alreadyCounted() {{
    try {{
      return sessionStorage.getItem('foobos_counted') === 'true';
    }} catch(e) {{
      return false;
    }}
  }}

  function markCounted() {{
    try {{
      sessionStorage.setItem('foobos_counted', 'true');
    }} catch(e) {{}}
  }}

  // Increment and display counter
  function countVisit() {{
    if (isBot() || alreadyCounted()) {{
      // Still fetch the current count to display, but don't increment
      fetch('https://api.counterapi.dev/v1/foobos-list/visits')
        .then(function(r) {{ return r.json(); }})
        .then(function(data) {{
          document.getElementById('visitor-count').textContent = 'Visitors: ' + data.count;
        }})
        .catch(function() {{
          document.getElementById('visitor-count').textContent = 'Visitors: --';
        }});
      return;
    }}

    // Real human visitor - increment the counter
    fetch('https://api.counterapi.dev/v1/foobos-list/visits/up')
      .then(function(r) {{ return r.json(); }})
      .then(function(data) {{
        document.getElementById('visitor-count').textContent = 'Visitors: ' + data.count;
        markCounted();
      }})
      .catch(function() {{
        document.getElementById('visitor-count').textContent = 'Visitors: --';
      }});
  }}

  // Wait for human interaction before counting
  var counted = false;
  function onHumanInteraction() {{
    if (counted) return;
    counted = true;
    countVisit();
    // Remove listeners after first interaction
    document.removeEventListener('scroll', onHumanInteraction);
    document.removeEventListener('mousemove', onHumanInteraction);
    document.removeEventListener('click', onHumanInteraction);
    document.removeEventListener('touchstart', onHumanInteraction);
    document.removeEventListener('keydown', onHumanInteraction);
  }}

  // Set up interaction listeners
  document.addEventListener('scroll', onHumanInteraction);
  document.addEventListener('mousemove', onHumanInteraction);
  document.addEventListener('click', onHumanInteraction);
  document.addEventListener('touchstart', onHumanInteraction);
  document.addEventListener('keydown', onHumanInteraction);

  // Fallback: count after 3 seconds if page is visible and focused
  // This catches users who read without interacting
  setTimeout(function() {{
    if (!counted && document.visibilityState === 'visible' && document.hasFocus()) {{
      onHumanInteraction();
    }}
  }}, 3000);
}})();
</script>

<script>
function toggleLN() {{
  var hide = document.getElementById('hide-ln').checked;
  sessionStorage.setItem('hideLN', hide ? 'true' : 'false');
}}

function applyLNFilter() {{
  var hide = sessionStorage.getItem('hideLN') === 'true';
  document.getElementById('hide-ln').checked = hide;
}}

document.addEventListener('DOMContentLoaded', applyLNFilter);
</script>

'''
    html += html_footer()

    output_path = Path(OUTPUT_DIR) / "list.html"
    with open(output_path, "w") as f:
        f.write(html)

    logger.info(f"Generated list.html")


def _generate_week_links(start_date: datetime) -> str:
    """Generate week range links for Concerts By Date section.

    For the current week (week 0), the start date is adjusted to today
    to avoid showing past dates in the range.
    """
    lines = []
    today = start_date  # start_date is today when called from generate_index

    for week_num in range(WEEKS_AHEAD):
        week_start = start_date + timedelta(weeks=week_num)
        week_start, week_end = get_week_range(week_start)
        label = get_adjusted_week_label(week_start, week_end, today)
        lines.append(f'&nbsp;&nbsp;&nbsp;&nbsp;<a href="by-date.{week_num}.html">{label}</a><br>')

    return "\n".join(lines)


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
