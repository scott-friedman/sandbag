"""
Scraper for Hobgoblin Bar events.
https://www.hobgoblinbar.com/events/
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

HOBGOBLIN_URL = "https://www.hobgoblinbar.com/events/"


class HobgoblinScraper(BaseScraper):
    """Scraper for Hobgoblin Bar in Boston."""

    source_name = "hobgoblin"

    @property
    def url(self) -> str:
        return HOBGOBLIN_URL

    def fetch(self) -> List[Concert]:
        """Fetch concerts from Hobgoblin Bar."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_hobgoblin")
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
            save_cache("scrape_hobgoblin", [c.to_dict() for c in concerts])

        self._log_fetch_complete(len(concerts))
        return concerts

    def _parse_events(self, soup) -> List[Concert]:
        """Parse events from the events page."""
        concerts = []
        now = datetime.now()
        current_year = now.year

        # Find all event links in list items
        event_links = soup.find_all('a', href=re.compile(r'/event/'))

        for link in event_links:
            concert = self._parse_event_link(link, current_year, now)
            if concert:
                concerts.append(concert)

        return concerts

    def _parse_event_link(self, link, year: int, now: datetime) -> Optional[Concert]:
        """Parse a single event from a link element."""
        try:
            text = self._clean_text(link.get_text())
            if not text:
                return None

            # Skip cancelled events
            if 'cancel' in text.lower():
                return None

            # Parse date from format like "1/31" or "2/5"
            date_match = re.match(r'^(\d{1,2})/(\d{1,2})\s+(.+)$', text)
            if not date_match:
                return None

            month = int(date_match.group(1))
            day = int(date_match.group(2))
            event_name = date_match.group(3).strip()

            if not event_name:
                return None

            # Determine year (handle year rollover)
            event_year = year
            if month < now.month:
                event_year = year + 1

            try:
                date = datetime(event_year, month, day)
            except ValueError:
                return None

            # Skip past events
            if date.date() < now.date():
                return None

            # Get event URL
            href = link.get('href', '')
            if href.startswith('/'):
                source_url = f"https://www.hobgoblinbar.com{href}"
            elif href.startswith('http'):
                source_url = href
            else:
                source_url = HOBGOBLIN_URL

            # Parse bands from event name
            # Clean up common suffixes like "duo", "trio", "solo piano"
            bands = self._parse_bands(event_name)

            return Concert(
                date=date,
                venue_id="hobgoblin",
                venue_name="Hobgoblin",
                venue_location="Boston",
                bands=bands,
                age_requirement="21+",
                price_advance=None,
                price_door=None,
                time="8pm",
                flags=[],
                source=self.source_name,
                source_url=source_url,
                genre_tags=["jazz"]
            )

        except Exception as e:
            logger.debug(f"Error parsing event: {e}")
            return None

    def _parse_bands(self, event_name: str) -> List[str]:
        """Parse band names from event name."""
        # Remove performance type suffixes for cleaner band names
        # but keep them as part of the name since they describe the act
        # e.g., "Mikayla Shirley duo with Kazuki Tsubakida"

        # Split on common separators
        event_name = re.sub(r'\s+with\s+', ' / ', event_name, flags=re.I)
        event_name = re.sub(r'\s+&\s+', ' / ', event_name)
        event_name = re.sub(r'\s+and\s+', ' / ', event_name, flags=re.I)

        if ' / ' in event_name:
            bands = [b.strip() for b in event_name.split(' / ')]
        else:
            bands = [event_name.strip()]

        return [b for b in bands if b and len(b) > 1]
