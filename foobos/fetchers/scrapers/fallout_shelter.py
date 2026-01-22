"""
Scraper for The Fallout Shelter venue in Norwood, MA.
https://www.extendedplaysessions.com/

Uses Playwright to handle the Wix-based dynamic content loading.
"""

from datetime import datetime
from typing import List
import logging
import re

from .base import BaseScraper
from ...models import Concert
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)

FALLOUT_SHELTER_URL = "https://www.extendedplaysessions.com/"

# Try to import Playwright
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not available - Fallout Shelter scraper will be skipped")


class FalloutShelterScraper(BaseScraper):
    """Scraper for The Fallout Shelter venue using Playwright."""

    source_name = "fallout_shelter"

    @property
    def url(self) -> str:
        return FALLOUT_SHELTER_URL

    def fetch(self) -> List[Concert]:
        """Fetch concerts from The Fallout Shelter."""
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning(f"[{self.source_name}] Playwright not available, skipping")
            return []

        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_fallout_shelter")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Set viewport to ensure content loads
                page.set_viewport_size({"width": 1920, "height": 1080})

                # Navigate and wait for initial load
                logger.info(f"[{self.source_name}] Loading page...")
                page.goto(FALLOUT_SHELTER_URL, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                # Scroll down to load dynamic content (Wix lazy-loads)
                logger.info(f"[{self.source_name}] Scrolling to load events...")
                for _ in range(5):
                    page.evaluate("window.scrollBy(0, window.innerHeight)")
                    page.wait_for_timeout(1000)

                # Scroll back to top
                page.evaluate("window.scrollTo(0, 0)")
                page.wait_for_timeout(500)

                # Get page content
                content = page.content()

                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, 'lxml')

                concerts = self._parse_events(soup)

                browser.close()

        except Exception as e:
            logger.error(f"[{self.source_name}] Failed to fetch: {e}")
            return []

        # Cache results
        if concerts:
            save_cache("scrape_fallout_shelter", [c.to_dict() for c in concerts])

        self._log_fetch_complete(len(concerts))
        return concerts

    def _parse_events(self, soup) -> List[Concert]:
        """Parse events from the rendered Wix page."""
        concerts = []
        current_year = datetime.now().year

        # Wix event widgets often use data attributes or specific patterns
        # Look for event-related text patterns in the page

        # Find all text elements that might contain event info
        # Wix uses various div structures - look for date patterns
        all_text = soup.get_text(separator='\n')
        lines = [l.strip() for l in all_text.split('\n') if l.strip()]

        # Look for date patterns followed by event info
        i = 0
        seen_events = set()

        while i < len(lines):
            line = lines[i]

            # Look for date patterns like "Jan 24", "January 24", "1/24"
            date = self._parse_date(line, current_year)

            if date:
                # Collect nearby lines for context
                context_start = max(0, i - 2)
                context_end = min(len(lines), i + 6)
                context_lines = lines[context_start:context_end]

                event_info = self._extract_event_from_context(context_lines, date, line)
                if event_info:
                    # Deduplicate by date + band
                    event_key = (date.strftime("%Y-%m-%d"), event_info['band'])
                    if event_key not in seen_events:
                        seen_events.add(event_key)

                        concert = Concert(
                            date=date,
                            venue_id="falloutshelter",
                            venue_name="The Fallout Shelter",
                            venue_location="Norwood",
                            bands=[event_info['band']],
                            age_requirement="a/a",
                            price_advance=event_info.get('price'),
                            price_door=None,
                            time=event_info.get('time', '7pm'),
                            flags=[],
                            source=self.source_name,
                            source_url=FALLOUT_SHELTER_URL,
                            genre_tags=[]
                        )
                        concerts.append(concert)
            i += 1

        return concerts

    def _extract_event_from_context(self, context_lines: List[str], date: datetime, date_line: str) -> dict:
        """Extract event info from lines around a date."""
        # Skip common non-event words
        skip_words = ['menu', 'contact', 'about', 'home', 'tickets', 'buy', 'more',
                      'info', 'subscribe', 'email', 'phone', 'address', 'hours',
                      'parking', 'directions', 'facebook', 'instagram', 'twitter',
                      'copyright', 'privacy', 'terms', 'sitemap', 'powered by']

        event_info = {'band': None, 'time': '7pm', 'price': None}

        for line in context_lines:
            line_lower = line.lower()

            # Skip the date line itself
            if line == date_line:
                continue

            # Skip navigation/UI text
            if any(skip in line_lower for skip in skip_words):
                continue

            # Skip very short or very long lines
            if len(line) < 4 or len(line) > 150:
                continue

            # Skip lines that are just dates
            if self._is_date_only(line):
                continue

            # Look for time patterns
            time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))', line, re.I)
            if time_match:
                event_info['time'] = self._parse_time(time_match.group(1))

            # Look for price patterns
            price_match = re.search(r'\$(\d+)', line)
            if price_match:
                event_info['price'] = int(price_match.group(1))

            # If this line looks like a band/event name, capture it
            # Band names typically: start with caps, don't have common UI words
            if not event_info['band']:
                # Check if line looks like a title/band name
                if (line[0].isupper() and
                    not any(skip in line_lower for skip in skip_words) and
                    not re.match(r'^\d', line) and
                    not line_lower.startswith('doors')):
                    event_info['band'] = line

        return event_info if event_info['band'] else None

    def _is_date_only(self, line: str) -> bool:
        """Check if a line contains only date information."""
        # Patterns that are just dates
        date_only_patterns = [
            r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s*$',
            r'^(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)\s*$',
            r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{1,2}\s*$',
            r'^\d{1,2}/\d{1,2}\s*$',
            r'^\d{1,2}\s*$',
        ]
        for pattern in date_only_patterns:
            if re.match(pattern, line, re.I):
                return True
        return False

    def _parse_date(self, date_str: str, year: int) -> datetime:
        """Parse various date formats."""
        if not date_str:
            return None

        # Skip very long strings (unlikely to be just a date)
        if len(date_str) > 50:
            return None

        # "January 25" or "January 25, 2026" or "Jan 25"
        match = re.search(
            r'(January|February|March|April|May|June|July|August|September|October|November|December|'
            r'Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+'
            r'(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(\d{4}))?',
            date_str, re.I
        )

        if match:
            month_name = match.group(1).lower()
            day = int(match.group(2))
            event_year = int(match.group(3)) if match.group(3) else year

            months = {
                'january': 1, 'jan': 1,
                'february': 2, 'feb': 2,
                'march': 3, 'mar': 3,
                'april': 4, 'apr': 4,
                'may': 5,
                'june': 6, 'jun': 6,
                'july': 7, 'jul': 7,
                'august': 8, 'aug': 8,
                'september': 9, 'sep': 9,
                'october': 10, 'oct': 10,
                'november': 11, 'nov': 11,
                'december': 12, 'dec': 12
            }
            month = months.get(month_name)

            if month:
                # Handle year rollover
                if month < datetime.now().month and event_year == year:
                    event_year += 1

                try:
                    return datetime(event_year, month, day)
                except ValueError:
                    pass

        # Try "1/25" or "1/25/26" or "01/25/2026"
        match = re.search(r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?', date_str)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            if match.group(3):
                event_year = int(match.group(3))
                if event_year < 100:
                    event_year += 2000
            else:
                event_year = year

            # Handle year rollover
            if month < datetime.now().month and event_year == year:
                event_year += 1

            try:
                return datetime(event_year, month, day)
            except ValueError:
                pass

        return None
