"""
Scraper for Sofar Sounds Boston intimate concert series.

Sofar Sounds hosts secret concerts at various venues around Boston.
The exact venue is revealed ~36 hours before the show, but the neighborhood
and venue type are listed in advance. Artist lineups are kept secret until
the show itself.
"""

from datetime import datetime, timedelta
from typing import List, Optional
import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper
from ...models import Concert
from ...config import WEEKS_AHEAD
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)

# Try to import Playwright - required for this scraper
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not available - Sofar Sounds scraper will be disabled")


class SofarSoundsScraper(BaseScraper):
    """Scrape Sofar Sounds Boston events."""

    @property
    def source_name(self) -> str:
        return "scrape:sofar"

    @property
    def url(self) -> str:
        return "https://www.sofarsounds.com/cities/boston"

    def fetch(self) -> List[Concert]:
        """Fetch Sofar Sounds Boston events."""
        self._log_fetch_start()

        if not PLAYWRIGHT_AVAILABLE:
            logger.warning(f"[{self.source_name}] Playwright required but not available")
            return []

        # Check cache first
        cached = get_cached("scrape_sofar_sounds")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []

        try:
            concerts = self._fetch_with_playwright()
        except Exception as e:
            logger.error(f"[{self.source_name}] Error fetching Sofar events: {e}")

        # Cache the results
        if concerts:
            save_cache("scrape_sofar_sounds", [c.to_dict() for c in concerts])

        self._log_fetch_complete(len(concerts))
        return concerts

    def _fetch_with_playwright(self) -> List[Concert]:
        """Fetch events using Playwright."""
        concerts = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Navigate to Boston city page
            page.goto(self.url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(4000)  # Wait for JS to render

            content = page.content()
            browser.close()

            # Parse with BeautifulSoup
            soup = BeautifulSoup(content, 'lxml')
            concerts = self._parse_events(soup)

        return concerts

    def _parse_events(self, soup: BeautifulSoup) -> List[Concert]:
        """Parse events from the Boston city page."""
        concerts = []
        now = datetime.now()
        max_date = now + timedelta(weeks=WEEKS_AHEAD)

        # Find event links - they have href like /events/63920
        event_links = soup.select('a[href^="/events/"]')

        for link in event_links:
            try:
                concert = self._parse_event_link(link, now, max_date)
                if concert:
                    concerts.append(concert)
            except Exception as e:
                logger.debug(f"[{self.source_name}] Error parsing event: {e}")

        return concerts

    def _parse_event_link(self, link, now: datetime, max_date: datetime) -> Optional[Concert]:
        """Parse a single event link into a Concert."""
        href = link.get('href', '')
        if not href.startswith('/events/'):
            return None

        # Get the link text which contains date, neighborhood, venue type, etc.
        text = link.get_text(separator='|', strip=True)
        if not text:
            return None

        # Parse the components
        parts = [p.strip() for p in text.split('|') if p.strip()]
        if len(parts) < 2:
            return None

        # First part is typically the date (e.g., "Fri Jan 30")
        date = self._parse_date(parts[0])
        if not date:
            return None

        # Check date is within range
        if date < now or date > max_date:
            return None

        # Second part is typically the neighborhood
        neighborhood = parts[1] if len(parts) > 1 else "Boston"

        # Look for venue type and special tags in remaining parts
        venue_type = None
        special_tags = []

        # Common venue types
        venue_types = ['Hotel', 'Bar', 'Creative Space', 'Community Space', 'Cocktail Lounge',
                       'Restaurant', 'Gallery', 'Rooftop', 'Loft', 'Studio']

        # Skip these as they're not useful tags
        skip_tags = ['Alcohol for purchase', 'No alcohol', 'BYOB', 'Sold out', 'Presale']

        for part in parts[2:]:
            # Check if it's a venue type
            if any(vt.lower() in part.lower() for vt in venue_types):
                venue_type = part
            # Check if it's a useful special tag
            elif part not in skip_tags and not part.startswith('Limit:'):
                # Keep interesting tags like "Indoor Rooftop!", "Valentine's Day", etc.
                if len(part) > 2 and len(part) < 50:
                    special_tags.append(part)

        # Build flags list with neighborhood and venue type
        flags = [neighborhood]
        if venue_type:
            flags.append(venue_type)
        # Add up to 2 special tags
        flags.extend(special_tags[:2])

        # Extract event URL
        event_url = f"https://www.sofarsounds.com{href}"

        return Concert(
            date=date,
            venue_id="sofar_sounds",
            venue_name="Sofar Sounds",
            venue_location="Boston",
            bands=["TBA"],  # Artists are secret
            age_requirement="a/a",  # Sofar shows are typically all ages
            price_advance=29,  # Standard Sofar price
            price_door=None,
            time="8pm",  # Typical start time
            flags=flags,
            source=self.source_name,
            source_url=event_url,
            genre_tags=["indie", "acoustic", "secret show"]
        )

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date from format like 'Fri Jan 30' or 'Sat Feb 7'."""
        if not date_str:
            return None

        # Clean the string
        date_str = date_str.strip()

        # Pattern: Day Mon DD (e.g., "Fri Jan 30")
        match = re.match(
            r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+'
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+'
            r'(\d{1,2})',
            date_str,
            re.IGNORECASE
        )

        if match:
            month_str = match.group(1)
            day = int(match.group(2))

            # Determine year - assume current year, or next year if month is in the past
            now = datetime.now()
            month_map = {
                'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
            }
            month = month_map.get(month_str.lower()[:3])
            if not month:
                return None

            year = now.year
            try:
                date = datetime(year, month, day)
                # If date is more than a month in the past, assume next year
                if date < now - timedelta(days=30):
                    date = datetime(year + 1, month, day)
                return date
            except ValueError:
                return None

        return None
