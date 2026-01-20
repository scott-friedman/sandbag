"""
Scraper for The Plough and Stars calendar.
https://calendar.ploughandstars.com/events/calendar
"""

from datetime import datetime, timedelta
from typing import List, Optional
import logging
import re

from .base import BaseScraper
from ...models import Concert
from ...config import WEEKS_AHEAD
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)

PLOUGH_CALENDAR_URL = "https://calendar.ploughandstars.com/events/calendar"


class PloughAndStarsScraper(BaseScraper):
    """Scrape events from The Plough and Stars calendar."""

    @property
    def source_name(self) -> str:
        return "scrape:plough_and_stars"

    @property
    def url(self) -> str:
        return PLOUGH_CALENDAR_URL

    def fetch(self) -> List[Concert]:
        """Fetch concerts from Plough and Stars calendar."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_plough_and_stars")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        all_concerts = []

        # Fetch multiple months based on WEEKS_AHEAD config
        now = datetime.now()
        months_ahead = (WEEKS_AHEAD // 4) + 1
        for month_offset in range(months_ahead):
            target_date = now + timedelta(days=month_offset * 30)
            month = target_date.month
            year = target_date.year

            try:
                concerts = self._fetch_month(month, year)
                all_concerts.extend(concerts)
            except Exception as e:
                logger.warning(f"[{self.source_name}] Error fetching {month}/{year}: {e}")

        # Deduplicate (some events might appear in multiple month views)
        seen = set()
        unique_concerts = []
        for c in all_concerts:
            key = f"{c.date.strftime('%Y-%m-%d')}-{'-'.join(c.bands)}"
            if key not in seen:
                seen.add(key)
                unique_concerts.append(c)

        # Cache the results
        save_cache("scrape_plough_and_stars", [c.to_dict() for c in unique_concerts])
        self._log_fetch_complete(len(unique_concerts))

        return unique_concerts

    def _fetch_month(self, month: int, year: int) -> List[Concert]:
        """Fetch events for a specific month."""
        concerts = []
        url = f"{PLOUGH_CALENDAR_URL}?month={month}&year={year}"

        try:
            soup = self._get_soup(url)

            # Find all day divs (class starts with "day")
            days = soup.find_all('div', class_=re.compile(r'^day'))

            for day in days:
                day_id = day.get('id', '')  # Format: 20260101
                if not day_id or len(day_id) != 8:
                    continue

                # Parse date from id
                try:
                    date = datetime.strptime(day_id, '%Y%m%d')
                except ValueError:
                    continue

                # Skip past dates or dates too far in future
                now = datetime.now()
                if date < now - timedelta(days=1) or date > now + timedelta(weeks=WEEKS_AHEAD):
                    continue

                # Find events in this day
                entries = day.find('div', class_='entries')
                if not entries:
                    continue

                rows = entries.find_all('div', class_='row')
                for row in rows:
                    concert = self._parse_event(row, date)
                    if concert:
                        concerts.append(concert)

        except Exception as e:
            logger.error(f"[{self.source_name}] Error fetching {url}: {e}")

        return concerts

    def _parse_event(self, row, date: datetime) -> Optional[Concert]:
        """Parse an event row into a Concert object."""
        try:
            time_elem = row.find('div', class_='flex_item_left')
            event_elem = row.find('div', class_='event')

            if not time_elem or not event_elem:
                return None

            time_str = time_elem.text.strip()
            event_link = event_elem.find('a')
            event_name = event_link.text.strip() if event_link else event_elem.text.strip()

            if not event_name:
                return None

            # Skip non-music events
            skip_events = ['trivia night', 'trivia', 'closed', 'private']
            if any(skip in event_name.lower() for skip in skip_events):
                return None

            # Parse time
            time = self._parse_time(time_str)

            # Parse bands from event name
            bands = self._parse_bands(event_name)

            return Concert(
                date=date,
                venue_id="ploughandstars",
                venue_name="The Plough and Stars",
                venue_location="Cambridge",
                bands=bands,
                age_requirement="21+",
                price_advance=None,
                price_door=None,
                time=time,
                flags=[],
                source=self.source_name,
                source_url=PLOUGH_CALENDAR_URL,
                genre_tags=["rock", "blues", "folk"]
            )

        except Exception as e:
            logger.debug(f"Error parsing event: {e}")
            return None

    def _parse_time(self, time_str: str) -> str:
        """Parse time string like '10pm' or '4-6pm'."""
        if not time_str:
            return "8pm"

        # Handle range like "4-6pm" - take start time
        if '-' in time_str:
            time_str = time_str.split('-')[0]

        # Clean up
        time_str = time_str.strip().lower()

        # Validate format
        if re.match(r'\d{1,2}(:\d{2})?\s*(am|pm)', time_str):
            return time_str

        return "8pm"

    def _parse_bands(self, event_name: str) -> List[str]:
        """Parse band names from event name."""
        # Split on common separators
        # "Band A + Band B" or "Band A w/ Band B"
        event_name = re.sub(r'\s+w/\s+', ' + ', event_name, flags=re.IGNORECASE)
        event_name = re.sub(r'\s+with\s+', ' + ', event_name, flags=re.IGNORECASE)
        event_name = re.sub(r'\s+&\s+', ' + ', event_name)

        if ' + ' in event_name:
            bands = [b.strip() for b in event_name.split(' + ')]
        else:
            bands = [event_name.strip()]

        return [b for b in bands if b and len(b) > 1]
