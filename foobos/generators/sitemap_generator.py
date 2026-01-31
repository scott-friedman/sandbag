"""
Generate sitemap.xml for SEO.
"""

from datetime import datetime
import logging
from pathlib import Path

from ..config import OUTPUT_DIR, SITE_URL, WEEKS_AHEAD

logger = logging.getLogger(__name__)


def generate_sitemap() -> None:
    """Generate sitemap.xml with all pages and appropriate priorities."""
    today = datetime.now().strftime("%Y-%m-%d")

    # Start XML
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
    xml += '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'

    # Static pages with high priority
    static_pages = [
        ("index.html", "1.0", "weekly"),
        ("list.html", "1.0", "daily"),
        ("clubs.html", "0.8", "weekly"),
        ("by-band.html", "0.8", "daily"),
        ("by-club.html", "0.8", "daily"),
    ]

    for page, priority, changefreq in static_pages:
        xml += f'''  <url>
    <loc>{SITE_URL}/{page}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>{changefreq}</changefreq>
    <priority>{priority}</priority>
  </url>
'''

    # By-date pages with decreasing priority
    for week_num in range(WEEKS_AHEAD):
        # First few weeks are most important and change frequently
        if week_num < 4:
            priority = "0.9"
            changefreq = "daily"
        elif week_num < 12:
            priority = "0.7"
            changefreq = "weekly"
        else:
            priority = "0.5"
            changefreq = "weekly"

        xml += f'''  <url>
    <loc>{SITE_URL}/by-date.{week_num}.html</loc>
    <lastmod>{today}</lastmod>
    <changefreq>{changefreq}</changefreq>
    <priority>{priority}</priority>
  </url>
'''

    xml += '</urlset>\n'

    # Write file
    output_path = Path(OUTPUT_DIR) / "sitemap.xml"
    with open(output_path, "w") as f:
        f.write(xml)

    logger.info(f"Generated sitemap.xml with {len(static_pages) + WEEKS_AHEAD} URLs")
