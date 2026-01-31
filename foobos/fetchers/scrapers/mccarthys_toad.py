"""
Scraper for McCarthy's & Toad events via RSS feed.
https://www.mccarthystoad.com/music

Two sister venues in Somerville, MA:
- McCarthy's: bar & restaurant
- Toad: live music venue next door
"""

from datetime import datetime, timedelta
from typing import List, Optional
import logging
import re
import xml.etree.ElementTree as ET
from html import unescape

from .base import BaseScraper
from ...models import Concert
from ...config import WEEKS_AHEAD
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)

RSS_URL = "https://www.mccarthystoad.com/music?format=rss"
WEBSITE_URL = "https://www.mccarthystoad.com/music"


class McCarthysToadScraper(BaseScraper):
    """Scrape events from McCarthy's & Toad via RSS feed."""

    @property
    def source_name(self) -> str:
        return "scrape:mccarthys_toad"

    @property
    def url(self) -> str:
        return RSS_URL

    def fetch(self) -> List[Concert]:
        """Fetch concerts from McCarthy's & Toad."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_mccarthys_toad")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []
        try:
            response = self._make_request(RSS_URL)
            root = ET.fromstring(response.text)

            # Find all items in the RSS feed
            for item in root.findall('.//item'):
                concert = self._item_to_concert(item)
                if concert:
                    concerts.append(concert)

            # Cache the results
            save_cache("scrape_mccarthys_toad", [c.to_dict() for c in concerts])
            self._log_fetch_complete(len(concerts))

        except Exception as e:
            self._log_fetch_error(e)

        return concerts

    def _item_to_concert(self, item: ET.Element) -> Optional[Concert]:
        """Convert an RSS item to a Concert object."""
        try:
            title = item.findtext('title', '').strip()
            if not title:
                return None

            # Parse venue from title prefix (e.g., "Toad: Saturday Revival...")
            venue_name, venue_id, event_title = self._parse_venue_and_title(title)

            # Get description for date/time/price parsing
            description = item.findtext('description', '')
            description = unescape(description)

            # Parse date and time from description
            date, time_str = self._parse_date_time(description)
            if not date:
                return None

            # Filter by date range
            now = datetime.now()
            max_date = now + timedelta(weeks=WEEKS_AHEAD)
            if date < now.replace(hour=0, minute=0, second=0, microsecond=0):
                return None
            if date > max_date:
                return None

            # Parse price from description
            price_advance, price_door = self._parse_price(description)

            # Parse age restriction
            age = self._parse_age(description)

            # Get event URL
            source_url = item.findtext('link', WEBSITE_URL)

            # Parse bands from title
            bands = self._parse_bands(event_title)

            return Concert(
                date=date,
                venue_id=venue_id,
                venue_name=venue_name,
                venue_location="Somerville",
                bands=bands,
                age_requirement=age,
                price_advance=price_advance,
                price_door=price_door,
                time=time_str,
                flags=[],
                source=self.source_name,
                source_url=source_url,
                genre_tags=[]
            )

        except Exception as e:
            logger.debug(f"Error converting RSS item to concert: {e}")
            return None

    def _parse_venue_and_title(self, title: str) -> tuple:
        """Parse venue and event title from RSS title.

        Format examples:
        - "Toad: Saturday Revival with 'Niall Connolly'"
        - "McCarthy's: Jazz Night"
        - "Upstairs at McCarthy's: Comedy Show"
        """
        # Default to Toad
        venue_name = "Toad"
        venue_id = "toad"
        event_title = title

        if title.lower().startswith("toad:"):
            event_title = title[5:].strip()
            venue_name = "Toad"
            venue_id = "toad"
        elif title.lower().startswith("mccarthy's:"):
            event_title = title[11:].strip()
            venue_name = "McCarthy's"
            venue_id = "mccarthys"
        elif "upstairs" in title.lower():
            # Extract after colon if present
            if ':' in title:
                event_title = title.split(':', 1)[1].strip()
            venue_name = "Upstairs at McCarthy's"
            venue_id = "mccarthys"

        return venue_name, venue_id, event_title

    def _parse_date_time(self, description: str) -> tuple:
        """Parse date and time from description HTML."""
        # Look for patterns like "Friday, January 30, 2026" or "Feb 1, 2026"
        date_patterns = [
            r'(\w+day),?\s+(\w+)\s+(\d{1,2}),?\s+(\d{4})',  # "Friday, January 30, 2026"
            r'(\w+)\s+(\d{1,2}),?\s+(\d{4})',  # "January 30, 2026"
        ]

        date = None
        for pattern in date_patterns:
            match = re.search(pattern, description)
            if match:
                groups = match.groups()
                try:
                    if len(groups) == 4:
                        # Day name, Month, Day, Year
                        month_str, day, year = groups[1], groups[2], groups[3]
                    else:
                        # Month, Day, Year
                        month_str, day, year = groups[0], groups[1], groups[2]

                    date_str = f"{month_str} {day}, {year}"
                    date = datetime.strptime(date_str, "%B %d, %Y")
                    break
                except ValueError:
                    continue

        # Parse time - look for patterns like "6:00 PM" or "8 PM"
        time_str = "8pm"
        time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(AM|PM|am|pm)', description)
        if time_match:
            hour = time_match.group(1)
            minutes = time_match.group(2)
            suffix = time_match.group(3).lower()
            if minutes and minutes != '00':
                time_str = f"{hour}:{minutes}{suffix}"
            else:
                time_str = f"{hour}{suffix}"

        return date, time_str

    def _parse_price(self, description: str) -> tuple:
        """Parse price from description."""
        # Look for patterns like "$15 in advance. $20 at the door"
        # or "$15" or "Free"

        desc_lower = description.lower()
        if 'free' in desc_lower and 'free' in desc_lower.split('$')[0]:
            # "Free" mentioned before any price
            return (0, 0)

        # Look for advance/door pricing
        advance_match = re.search(r'\$(\d+)\s*(?:in advance|adv)', description, re.I)
        door_match = re.search(r'\$(\d+)\s*(?:at the door|door|dos)', description, re.I)

        if advance_match and door_match:
            return (int(advance_match.group(1)), int(door_match.group(1)))
        elif advance_match:
            price = int(advance_match.group(1))
            return (price, price)
        elif door_match:
            price = int(door_match.group(1))
            return (price, price)

        # Look for single price
        price_match = re.search(r'\$(\d+)', description)
        if price_match:
            price = int(price_match.group(1))
            return (price, price)

        return (None, None)

    def _parse_age(self, description: str) -> str:
        """Parse age restriction from description."""
        desc_lower = description.lower()
        if 'all ages' in desc_lower:
            return "a/a"
        if '21+' in desc_lower or '21 and over' in desc_lower:
            return "21+"
        if '18+' in desc_lower or '18 and over' in desc_lower:
            return "18+"
        # Default for bars
        return "21+"

    def _parse_bands(self, title: str) -> List[str]:
        """Parse band names from event title."""
        # Clean up the title
        title = title.strip()

        # Remove quotes around artist names
        title = re.sub(r"'([^']+)'", r'\1', title)
        title = re.sub(r'"([^"]+)"', r'\1', title)

        # Remove common prefixes
        title = re.sub(r'^Saturday Revival\s+(?:with\s+)?', '', title, flags=re.I)
        title = re.sub(r'^Sunday Brunch\s+(?:with\s+)?', '', title, flags=re.I)
        title = re.sub(r'^Live:\s*', '', title, flags=re.I)
        title = re.sub(r'^An Evening with\s+', '', title, flags=re.I)

        # Split on common separators
        title = re.sub(r'\s+w/\s+', ' / ', title, flags=re.I)
        title = re.sub(r'\s+with\s+', ' / ', title, flags=re.I)
        title = re.sub(r'\s+&\s+', ' / ', title)
        title = re.sub(r'\s+and\s+', ' / ', title, flags=re.I)
        title = re.sub(r'\s+\+\s+', ' / ', title)

        if ' / ' in title:
            bands = [b.strip() for b in title.split(' / ')]
        else:
            bands = [title.strip()]

        # Filter out empty strings
        bands = [b for b in bands if b and len(b) > 1]

        return bands if bands else [title]
