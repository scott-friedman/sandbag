"""
Scraper for The Palladium (Worcester) using Playwright for JavaScript rendering.
https://thepalladium.net/events
"""

from datetime import datetime
from typing import List, Optional
import logging
import re

from .base import BaseScraper
from ...models import Concert
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)

PALLADIUM_URL = "https://thepalladium.net/events"

# Try to import Playwright - it may not be available in all environments
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not available - Palladium scraper will be skipped")


class PalladiumScraper(BaseScraper):
    """Scraper for The Palladium in Worcester using Playwright."""

    source_name = "palladium"

    @property
    def url(self) -> str:
        return PALLADIUM_URL

    def fetch(self) -> List[Concert]:
        """Fetch concerts from The Palladium."""
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning(f"[{self.source_name}] Playwright not available, skipping")
            return []

        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_palladium")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Navigate and wait for content to load
                page.goto(PALLADIUM_URL, wait_until="networkidle", timeout=30000)

                # Wait a bit more for JS to render
                page.wait_for_timeout(2000)

                # Get the page content
                content = page.content()

                # Parse with BeautifulSoup
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, 'lxml')

                concerts = self._parse_events(soup)

                browser.close()

        except Exception as e:
            logger.error(f"[{self.source_name}] Failed to fetch: {e}")
            return []

        # Cache the results
        if concerts:
            save_cache("scrape_palladium", [c.to_dict() for c in concerts])

        self._log_fetch_complete(len(concerts))
        return concerts

    def _parse_events(self, soup) -> List[Concert]:
        """Parse events from the rendered page."""
        concerts = []

        # The Palladium uses TicketWeb integration - look for event blocks
        # Look for event containers with dates and titles
        event_blocks = soup.find_all('div', class_=re.compile(r'event', re.I))

        if not event_blocks:
            # Try alternative selectors
            event_blocks = soup.find_all('article')

        # Also try finding by text patterns
        text = soup.get_text(separator='\n')
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        # Look for date + event name patterns
        # Common format: "Jan 25" or "January 25, 2026"
        i = 0
        current_year = datetime.now().year

        while i < len(lines):
            line = lines[i]

            # Match date patterns
            date_match = re.match(
                r'(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|'
                r'Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+'
                r'(\d{1,2})(?:,?\s*(\d{4}))?',
                line, re.I
            )

            if date_match:
                month_str = date_match.group(1).lower()[:3]
                day = int(date_match.group(2))
                year = int(date_match.group(3)) if date_match.group(3) else current_year

                months = {
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                }
                month = months.get(month_str)

                if month:
                    # Adjust year if date is in the past
                    try:
                        date = datetime(year, month, day)
                        if date < datetime.now() - __import__('datetime').timedelta(days=7):
                            date = datetime(year + 1, month, day)
                    except ValueError:
                        i += 1
                        continue

                    # Look for event name in nearby lines
                    event_name = None
                    for j in range(i + 1, min(i + 5, len(lines))):
                        candidate = lines[j]
                        # Skip date lines, time lines, venue info
                        if re.match(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', candidate, re.I):
                            break
                        if re.match(r'^\d{1,2}:\d{2}', candidate):
                            continue
                        if 'doors' in candidate.lower() or 'show' in candidate.lower():
                            continue
                        if len(candidate) > 3 and not candidate.startswith('$'):
                            event_name = candidate
                            break

                    if event_name:
                        # Clean up event name
                        event_name = re.sub(r'\s*-\s*SOLD OUT.*$', '', event_name, flags=re.I)
                        event_name = re.sub(r'\s*\(.*\)$', '', event_name)

                        bands = self._split_bands(event_name)
                        if not bands:
                            bands = [event_name]

                        concert = Concert(
                            date=date,
                            venue_id="palladium",
                            venue_name="The Palladium",
                            venue_location="Worcester",
                            bands=bands,
                            age_requirement="a/a",
                            price_advance=None,
                            price_door=None,
                            time="7pm",
                            flags=[],
                            source=self.source_name,
                            source_url=PALLADIUM_URL,
                            genre_tags=[]
                        )
                        concerts.append(concert)

            i += 1

        return concerts
