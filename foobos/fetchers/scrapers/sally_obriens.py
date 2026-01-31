"""
Scraper for Sally O'Brien's bar music calendar.
https://www.sallyobriensbar.com/music/
"""

from datetime import datetime, timedelta
from typing import List, Optional
import logging
import re

from .base import BaseScraper
from ...models import Concert
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)

SALLY_OBRIENS_URL = "https://www.sallyobriensbar.com/music/"

# Days of week for date parsing
DAYS_OF_WEEK = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
MONTHS = ['january', 'february', 'march', 'april', 'may', 'june',
          'july', 'august', 'september', 'october', 'november', 'december']


class SallyOBriensScraper(BaseScraper):
    """Scrape events from Sally O'Brien's music calendar."""

    @property
    def source_name(self) -> str:
        return "scrape:sally_obriens"

    @property
    def url(self) -> str:
        return SALLY_OBRIENS_URL

    def fetch(self) -> List[Concert]:
        """Fetch concerts from Sally O'Brien's calendar."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_sally_obriens")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []

        try:
            soup = self._get_soup()

            # Get all the text content - the page structure is not very semantic
            # We need to parse the text looking for date patterns
            content = soup.find('main') or soup.find('body')
            if not content:
                logger.warning(f"[{self.source_name}] Could not find main content")
                return []

            # Get the text and find events
            concerts = self._parse_events(content)

        except Exception as e:
            logger.error(f"[{self.source_name}] Error fetching: {e}")

        # Cache the results
        save_cache("scrape_sally_obriens", [c.to_dict() for c in concerts])
        self._log_fetch_complete(len(concerts))

        return concerts

    def _parse_events(self, content) -> List[Concert]:
        """Parse events from the page content.

        Sally O'Brien's uses a simple structure with separate lines:
        1. Day of week (e.g., "Monday")
        2. Month and day (e.g., "January 19")
        3. Time (e.g., "730pm")
        4. Band name
        5. Price/cover info (optional)
        """
        concerts = []
        current_year = datetime.now().year

        # Get text with ||| separator to preserve structure
        all_text = content.get_text(separator='|||', strip=True)
        parts = [p.strip() for p in all_text.split('|||') if p.strip()]

        i = 0
        while i < len(parts) - 3:  # Need at least 4 parts for an event
            part = parts[i].lower()

            # Look for day of week (may be concatenated with month, e.g., "Sunday Febr")
            day_of_week = None
            for day in DAYS_OF_WEEK:
                if part.startswith(day):
                    day_of_week = day
                    break

            if day_of_week:
                # Next should be "Month Day" (e.g., "January 19")
                # But month might be split across parts (e.g., "Sunday Febr" + "uary 1")
                if i + 1 < len(parts):
                    # Check if day of week part has extra text (start of month)
                    extra = part[len(day_of_week):].strip()
                    date_part = extra + parts[i + 1] if extra else parts[i + 1]
                    date = self._parse_month_day(date_part, current_year)

                    if date:
                        # Next should be time (e.g., "730pm")
                        time_str = "8pm"
                        band_name = None
                        price = None

                        if i + 2 < len(parts):
                            time_candidate = parts[i + 2].lower()
                            time_match = re.match(r'^(\d{1,4})\s*(am|pm)$', time_candidate)
                            if time_match:
                                time_str = self._normalize_time(time_candidate)

                                # Next should be band name
                                if i + 3 < len(parts):
                                    band_name = parts[i + 3]

                                    # Check if price is embedded in band name line
                                    price_match = re.search(r'\$(\d+)', band_name)
                                    if price_match:
                                        price = int(price_match.group(1))
                                        # Remove price from band name
                                        band_name = re.sub(r'\s*\$\d+\s*', '', band_name).strip()

                                    # Check next line for price/cover info
                                    if i + 4 < len(parts):
                                        next_part = parts[i + 4]
                                        if 'free' in next_part.lower():
                                            price = 0
                                        elif 'no-cover' in next_part.lower():
                                            price = 0
                                        price_match = re.search(r'\$(\d+)', next_part)
                                        if price_match:
                                            price = int(price_match.group(1))

                        if band_name and len(band_name) > 2:
                            # Skip non-band text
                            skip_patterns = ['free show', 'no-cover', 'residency', 'followed by',
                                           'here for you', 'live music', 'follow us']
                            if not any(p in band_name.lower() for p in skip_patterns):
                                bands = self._split_bands(band_name)

                                if bands:
                                    concert = Concert(
                                        date=date,
                                        venue_id="sallyobriens",
                                        venue_name="Sally O'Brien's",
                                        venue_location="Somerville",
                                        bands=bands,
                                        age_requirement="21+",
                                        price_advance=price,
                                        price_door=price,
                                        time=time_str,
                                        flags=[],
                                        source=self.source_name,
                                        source_url=SALLY_OBRIENS_URL,
                                        genre_tags=["rock", "indie", "folk", "americana"]
                                    )
                                    concerts.append(concert)

            i += 1

        return concerts

    def _parse_month_day(self, text: str, year: int) -> Optional[datetime]:
        """Parse a 'Month Day' string like 'January 19' into a datetime."""
        text_lower = text.lower().strip()

        # Find month
        month_num = None
        for i, month in enumerate(MONTHS):
            if month in text_lower:
                month_num = i + 1
                break

        if not month_num:
            return None

        # Find day number
        day_match = re.search(r'\b(\d{1,2})\b', text)
        if not day_match:
            return None

        day_num = int(day_match.group(1))
        if day_num < 1 or day_num > 31:
            return None

        # Determine year - if date is in the past, assume next year
        try:
            current = datetime.now()
            event_year = year

            test_date = datetime(event_year, month_num, day_num)
            if test_date < current - timedelta(days=7):
                event_year += 1

            return datetime(event_year, month_num, day_num)
        except ValueError:
            return None

    def _normalize_time(self, time_str: str) -> str:
        """Normalize time string like '730pm' to '7:30pm'."""
        time_str = time_str.lower().strip()

        # Match patterns like "730pm", "930pm", "500pm"
        match = re.match(r'^(\d{1,4})\s*(am|pm)$', time_str)
        if match:
            digits = match.group(1)
            ampm = match.group(2)

            if len(digits) <= 2:
                # It's just hour like "7pm"
                return f"{digits}{ampm}"
            elif len(digits) == 3:
                # It's like "730" -> "7:30"
                hour = digits[0]
                minutes = digits[1:]
                return f"{hour}:{minutes}{ampm}"
            elif len(digits) == 4:
                # It's like "1030" -> "10:30"
                hour = digits[:2]
                minutes = digits[2:]
                return f"{int(hour)}:{minutes}{ampm}"

        return time_str
