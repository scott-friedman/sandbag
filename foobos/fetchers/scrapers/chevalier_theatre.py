"""
Scraper for Chevalier Theatre calendar.
https://www.chevaliertheatre.com/calendar/
"""

from datetime import datetime
from typing import List
import logging
import re

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper
from ...models import Concert
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)

CHEVALIER_URL = "https://www.chevaliertheatre.com/calendar/"

# Browser-like headers to avoid blocking
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}


class ChevalierTheatreScraper(BaseScraper):
    """Scraper for Chevalier Theatre in Medford."""

    source_name = "chevalier_theatre"

    @property
    def url(self) -> str:
        return CHEVALIER_URL

    def fetch(self) -> List[Concert]:
        """Fetch concerts from Chevalier Theatre calendar."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_chevalier_theatre")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        try:
            # Use custom headers to avoid blocking
            response = requests.get(CHEVALIER_URL, headers=HEADERS, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'lxml')
            concerts = self._parse_calendar_page(soup)
        except Exception as e:
            logger.error(f"Failed to fetch Chevalier Theatre events: {e}")
            return []

        # Cache the results
        save_cache("scrape_chevalier_theatre", [c.to_dict() for c in concerts])
        self._log_fetch_complete(len(concerts))

        return concerts

    def _parse_calendar_page(self, soup) -> List[Concert]:
        """Parse events directly from the calendar page text."""
        concerts = []

        # Find the event-calendar div which contains the event list
        event_cal = soup.find(class_='event-calendar')
        if not event_cal:
            logger.warning("Could not find event-calendar element")
            return []

        text = event_cal.get_text()

        # Events appear in format: "Jan 24, 2026James Acaster" or "Feb 2-5, 2026Trevor Noah"
        # Use regex to extract date + event name pairs
        # Pattern: Month Day(s), Year followed by event name (until next month or end)
        pattern = r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})(?:-\d{1,2})?,\s*(\d{4})([A-Z][^J\n]+?)(?=(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d|$)'

        matches = re.findall(pattern, text)

        months = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }

        for match in matches:
            month_name, day_str, year_str, event_name = match
            month = months.get(month_name.lower())
            day = int(day_str)
            year = int(year_str)

            if not month:
                continue

            try:
                date = datetime(year, month, day)
            except ValueError:
                continue

            event_name = event_name.strip()
            if not event_name or len(event_name) < 3:
                continue

            # Skip non-event text
            skip_patterns = ['buy tickets', 'sold out', 'subscribe', 'previous', 'next']
            if any(p in event_name.lower() for p in skip_patterns):
                continue

            bands = self._split_bands(event_name)
            if not bands:
                bands = [event_name]

            concert = Concert(
                date=date,
                venue_id="chevalier",
                venue_name="Chevalier Theatre",
                venue_location="Medford",
                bands=bands,
                age_requirement="a/a",
                price_advance=None,
                price_door=None,
                time="8pm",
                flags=[],
                source=self.source_name,
                source_url=CHEVALIER_URL,
                genre_tags=[]
            )
            concerts.append(concert)

        return concerts
