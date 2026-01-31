"""
Scraper for Sanctuary Maynard events.
https://www.sanctuarymaynard.com/concerts
"""

from datetime import datetime
from typing import List, Optional
import logging
import re

from .base import BaseScraper
from ...models import Concert
from ...config import WEEKS_AHEAD
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)

SANCTUARY_URL = "https://www.sanctuarymaynard.com/concerts"


class SanctuaryMaynardScraper(BaseScraper):
    """Scraper for Sanctuary Maynard concert venue."""

    source_name = "sanctuary_maynard"

    @property
    def url(self) -> str:
        return SANCTUARY_URL

    def fetch(self) -> List[Concert]:
        """Fetch concerts from Sanctuary Maynard."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_sanctuary_maynard")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []

        try:
            soup = self._get_soup()
            concerts = self._parse_events(soup)
        except Exception as e:
            logger.error(f"[{self.source_name}] Failed to fetch: {e}")

        # Cache the results
        if concerts:
            save_cache("scrape_sanctuary_maynard", [c.to_dict() for c in concerts])

        self._log_fetch_complete(len(concerts))
        return concerts

    def _parse_events(self, soup) -> List[Concert]:
        """Parse events from the concerts page."""
        concerts = []
        now = datetime.now()

        # Find all event containers
        events = soup.find_all(class_='event')

        for event in events:
            concert = self._parse_event(event, now)
            if concert:
                concerts.append(concert)

        return concerts

    def _parse_event(self, event, now: datetime) -> Optional[Concert]:
        """Parse a single event container."""
        try:
            # Get event name/artist
            name_elem = event.find(class_='event-name')
            if not name_elem:
                return None

            event_name = self._clean_text(name_elem.get_text())
            if not event_name:
                return None

            # Skip cancelled events
            if 'cancel' in event_name.lower():
                return None

            # Get event details section
            details = event.find(class_='event-details')
            if not details:
                return None

            # Parse date and time from details text
            details_text = details.get_text()
            date = self._parse_date(details_text, now.year)
            if not date:
                return None

            # Skip past events
            if date.date() < now.date():
                return None

            # Parse time
            time_str = self._extract_time(details_text)

            # Parse price
            price_advance, price_door = self._extract_price(details_text)

            # Get event URL if available
            link = event.find('a', class_='btn')
            source_url = SANCTUARY_URL
            if link and link.get('href'):
                href = link.get('href')
                if href.startswith('http'):
                    source_url = href
                elif href.startswith('/'):
                    source_url = f"https://www.sanctuarymaynard.com{href}"

            # Parse bands from event name
            bands = self._split_bands(event_name)
            if not bands:
                bands = [event_name]

            return Concert(
                date=date,
                venue_id="sanctuary",
                venue_name="Sanctuary",
                venue_location="Maynard",
                bands=bands,
                age_requirement="a/a",
                price_advance=price_advance,
                price_door=price_door,
                time=time_str,
                flags=[],
                source=self.source_name,
                source_url=source_url,
                genre_tags=[]
            )

        except Exception as e:
            logger.debug(f"Error parsing event: {e}")
            return None

    def _parse_date(self, text: str, year: int) -> Optional[datetime]:
        """Parse date from text like 'Sat, Jan 31, 2026' or 'Saturday, January 24, 2026'."""
        # Month name mapping (both short and long forms)
        months = {
            'jan': 1, 'january': 1,
            'feb': 2, 'february': 2,
            'mar': 3, 'march': 3,
            'apr': 4, 'april': 4,
            'may': 5,
            'jun': 6, 'june': 6,
            'jul': 7, 'july': 7,
            'aug': 8, 'august': 8,
            'sep': 9, 'sept': 9, 'september': 9,
            'oct': 10, 'october': 10,
            'nov': 11, 'november': 11,
            'dec': 12, 'december': 12
        }

        # Match "Day, Mon DD, YYYY" format (short or long month names)
        match = re.search(
            r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun|Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+'
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec|'
            r'January|February|March|April|June|July|August|September|October|November|December)\s+'
            r'(\d{1,2}),?\s*(\d{4})?',
            text, re.I
        )

        if match:
            month_name = match.group(1).lower()
            day = int(match.group(2))
            event_year = int(match.group(3)) if match.group(3) else year

            month = months.get(month_name)

            if month:
                # Handle year rollover
                if month < datetime.now().month and event_year == year:
                    event_year += 1

                try:
                    return datetime(event_year, month, day)
                except ValueError:
                    pass

        return None

    def _extract_time(self, text: str) -> str:
        """Extract time from text like '7:00 PM start'."""
        match = re.search(r'(\d{1,2}):?(\d{2})?\s*(AM|PM)', text, re.I)
        if match:
            hour = match.group(1)
            minutes = match.group(2) or "00"
            ampm = match.group(3).lower()
            if minutes == "00":
                return f"{hour}{ampm}"
            return f"{hour}:{minutes}{ampm}"
        return "7pm"

    def _extract_price(self, text: str) -> tuple:
        """Extract price from text like '$24–$34 online$26–$36 in-person' or 'Free Event'."""
        if self._is_free_text(text):
            return (0, 0)

        # Look for "online" and "in-person" prices: $XX online$YY in-person
        # or $XX–$XX online$YY–$YY in-person (range format)
        online_match = re.search(r'\$(\d+)(?:[–\-]\$?(\d+))?\s*online', text, re.I)
        inperson_match = re.search(r'\$(\d+)(?:[–\-]\$?(\d+))?\s*in-?person', text, re.I)

        if online_match:
            price_advance = int(online_match.group(1))
            price_door = int(inperson_match.group(1)) if inperson_match else price_advance
            return (price_advance, price_door)

        # Fallback: look for any price pattern
        match = re.search(r'\$(\d+)(?:[–\-]\$?(\d+))?', text)
        if match:
            price1 = int(match.group(1))
            price2 = int(match.group(2)) if match.group(2) else price1
            return (price1, price2)

        return (None, None)
