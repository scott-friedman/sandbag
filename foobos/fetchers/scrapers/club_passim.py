"""
Scraper for Club Passim events.
https://www.passim.org/live-music/

Club Passim is a legendary folk music venue in Cambridge, MA.
Events are embedded as a JavaScript remEvents object in the page.
"""

from datetime import datetime, timedelta
from typing import List, Optional
import logging
import re
import json

from .base import BaseScraper
from ...models import Concert
from ...config import WEEKS_AHEAD
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)

PASSIM_URL = "https://www.passim.org/live-music/"


class ClubPassimScraper(BaseScraper):
    """Scrape events from Club Passim."""

    @property
    def source_name(self) -> str:
        return "scrape:club_passim"

    @property
    def url(self) -> str:
        return PASSIM_URL

    def fetch(self) -> List[Concert]:
        """Fetch concerts from Club Passim."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_club_passim")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []
        try:
            soup = self._get_soup(PASSIM_URL)

            # Find the remEvents JavaScript object in the page
            events_data = self._extract_rem_events(soup)
            if events_data:
                concerts = self._parse_events(events_data)

            # Cache the results
            save_cache("scrape_club_passim", [c.to_dict() for c in concerts])
            self._log_fetch_complete(len(concerts))

        except Exception as e:
            self._log_fetch_error(e)

        return concerts

    def _extract_rem_events(self, soup) -> Optional[dict]:
        """Extract the remEvents JavaScript object from the page."""
        # Find script tags that contain remEvents
        for script in soup.find_all('script'):
            if script.string and 'remEvents' in script.string:
                # Extract the JSON object using regex
                match = re.search(r'var\s+remEvents\s*=\s*(\{.*?\});', script.string, re.DOTALL)
                if match:
                    try:
                        json_str = match.group(1)
                        return json.loads(json_str)
                    except json.JSONDecodeError as e:
                        logger.debug(f"Failed to parse remEvents JSON: {e}")
        return None

    def _parse_events(self, events_data: dict) -> List[Concert]:
        """Parse the remEvents data into Concert objects."""
        concerts = []
        now = datetime.now()
        max_date = now + timedelta(weeks=WEEKS_AHEAD)

        for timestamp_key, event in events_data.items():
            concert = self._event_to_concert(event, now, max_date)
            if concert:
                concerts.append(concert)

        return concerts

    def _event_to_concert(self, event: dict, now: datetime, max_date: datetime) -> Optional[Concert]:
        """Convert a single event to a Concert object."""
        try:
            title = event.get('title', '').strip()
            if not title:
                return None

            # Skip closed/cancelled events
            title_lower = title.lower()
            skip_keywords = ['club closed', 'closed', 'cancelled', 'canceled', 'private event']
            if any(kw in title_lower for kw in skip_keywords):
                return None

            # Parse date from date_and_time field (format: "02/08/2026 8:00 pm")
            date_str = event.get('date_and_time', '')
            if not date_str:
                return None

            try:
                date = datetime.strptime(date_str, "%m/%d/%Y %I:%M %p")
            except ValueError:
                # Try alternate format
                try:
                    date = datetime.strptime(date_str, "%m/%d/%Y %H:%M")
                except ValueError:
                    logger.debug(f"Failed to parse date: {date_str}")
                    return None

            # Filter by date range
            if date < now.replace(hour=0, minute=0, second=0, microsecond=0):
                return None
            if date > max_date:
                return None

            # Parse time from show_string (e.g., "8PM")
            time_str = event.get('show_string', '8pm')
            time_str = self._normalize_time(time_str)

            # Parse price
            cost = event.get('cost', '')
            cost_member = event.get('cost_member', '')
            price_advance, price_door = self._parse_price_info(cost, cost_member)

            # Get event URL
            source_url = event.get('permalink', PASSIM_URL)

            # Parse bands from title
            bands = self._parse_bands(title)

            # Check for sold out
            flags = []
            if event.get('sold_out', False):
                flags.append('SOLD OUT')

            return Concert(
                date=date,
                venue_id="passim",
                venue_name="Club Passim",
                venue_location="Cambridge",
                bands=bands,
                age_requirement="a/a",
                price_advance=price_advance,
                price_door=price_door,
                time=time_str,
                flags=flags,
                source=self.source_name,
                source_url=source_url,
                genre_tags=["folk", "acoustic"]
            )

        except Exception as e:
            logger.debug(f"Error converting event to concert: {e}")
            return None

    def _normalize_time(self, time_str: str) -> str:
        """Normalize time string to format like '8pm'."""
        if not time_str:
            return "8pm"

        time_str = time_str.lower().strip()

        # Handle formats like "8PM", "8:00PM", "8:00 PM"
        match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', time_str)
        if match:
            hour = match.group(1)
            minutes = match.group(2)
            suffix = match.group(3) or 'pm'

            if minutes and minutes != '00':
                return f"{hour}:{minutes}{suffix}"
            return f"{hour}{suffix}"

        return "8pm"

    def _parse_price_info(self, cost: str, cost_member: str) -> tuple:
        """Parse price information."""
        try:
            if not cost or cost == '0':
                return (0, 0)  # Free event

            # cost is usually just the number like "33"
            price = int(float(cost))
            return (price, price)
        except (ValueError, TypeError):
            return (None, None)

    def _parse_bands(self, title: str) -> List[str]:
        """Parse band names from event title."""
        # Clean up the title
        title = title.strip()

        # Remove common suffixes/prefixes
        title = re.sub(r'\s*-\s*Seated Show.*$', '', title, flags=re.I)
        title = re.sub(r'\s*-\s*Standing Show.*$', '', title, flags=re.I)
        title = re.sub(r'^An Evening with\s*', '', title, flags=re.I)
        title = re.sub(r'^Live:\s*', '', title, flags=re.I)

        # Split on common separators
        title = re.sub(r'\s+w/\s+', ' / ', title, flags=re.I)
        title = re.sub(r'\s+with\s+', ' / ', title, flags=re.I)
        title = re.sub(r'\s+&\s+', ' / ', title)
        title = re.sub(r'\s+and\s+', ' / ', title, flags=re.I)
        title = re.sub(r'\s+ft\.?\s+', ' / ', title, flags=re.I)
        title = re.sub(r'\s+featuring\s+', ' / ', title, flags=re.I)

        if ' / ' in title:
            bands = [b.strip() for b in title.split(' / ')]
        elif ', ' in title and title.count(',') <= 3:
            # Only split on comma if there aren't too many (might be a band name with comma)
            bands = [b.strip() for b in title.split(', ')]
        else:
            bands = [title.strip()]

        # Filter out empty strings
        bands = [b for b in bands if b and len(b) > 1]

        return bands if bands else [title]
