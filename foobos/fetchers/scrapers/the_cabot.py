"""
Scraper for The Cabot theater events.
https://thecabot.org/events/
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

CABOT_URL = "https://thecabot.org/events/"

# Browser-like headers to avoid blocking
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}


class TheCabotScraper(BaseScraper):
    """Scraper for The Cabot in Beverly."""

    source_name = "the_cabot"

    @property
    def url(self) -> str:
        return CABOT_URL

    def fetch(self) -> List[Concert]:
        """Fetch concerts from The Cabot with pagination support."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_the_cabot")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []
        max_pages = 10  # Safety limit

        try:
            for page_num in range(1, max_pages + 1):
                if page_num == 1:
                    page_url = CABOT_URL
                else:
                    page_url = f"{CABOT_URL}page/{page_num}/"

                response = requests.get(page_url, headers=HEADERS, timeout=30)

                # Stop if we get an error (likely no more pages)
                if response.status_code != 200:
                    break

                soup = BeautifulSoup(response.text, 'lxml')
                page_concerts = self._parse_events(soup)

                if not page_concerts:
                    # No more events
                    break

                concerts.extend(page_concerts)
                logger.debug(f"[{self.source_name}] Page {page_num}: {len(page_concerts)} events")

                # If fewer than 10 events, probably last page
                if len(page_concerts) < 10:
                    break

        except Exception as e:
            logger.error(f"Failed to fetch The Cabot events: {e}")

        # Cache the results
        if concerts:
            save_cache("scrape_the_cabot", [c.to_dict() for c in concerts])
        self._log_fetch_complete(len(concerts))

        return concerts

    def _parse_events(self, soup) -> List[Concert]:
        """Parse events from the events page."""
        concerts = []
        current_year = datetime.now().year

        # Find all event items
        event_items = soup.find_all('div', class_='event_item')

        for item in event_items:
            try:
                concert = self._parse_event_item(item, current_year)
                if concert:
                    concerts.append(concert)
            except Exception as e:
                logger.warning(f"Failed to parse event item: {e}")
                continue

        return concerts

    def _parse_event_item(self, item, year: int) -> Concert:
        """Parse a single event item."""
        # Get event URL
        link = item.find('a', href=True)
        event_url = link.get('href', '') if link else CABOT_URL

        # Get date info
        date_div = item.find('div', class_='event_date')
        if not date_div:
            return None

        # Date is in format: <span>20</span> Jan <div class="time">7:00pm</div>
        # Or: <span class="smaller">21 - 22</span> Jan (for multi-day events)
        day_span = date_div.find('span')
        if not day_span:
            return None

        day_text = day_span.get_text().strip()
        # Handle date ranges like "21 - 22" - take first day
        day_match = re.match(r'(\d{1,2})', day_text)
        if not day_match:
            return None
        day = int(day_match.group(1))

        # Get month from text after span
        date_text = date_div.get_text()
        month_match = re.search(
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)',
            date_text, re.I
        )
        if not month_match:
            return None

        month_name = month_match.group(1).lower()
        months = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        month = months.get(month_name)
        if not month:
            return None

        # Determine year - if month is before current month, assume next year
        current_month = datetime.now().month
        event_year = year
        if month < current_month:
            event_year = year + 1

        try:
            date = datetime(event_year, month, day)
        except ValueError:
            return None

        # Get time
        time_div = date_div.find('div', class_='time')
        time_str = "8pm"
        if time_div:
            time_str = self._parse_time(time_div.get_text())

        # Get event info
        event_text = item.find('div', class_='event_text')
        if not event_text:
            return None

        # Get genres
        genres = []
        genre_divs = event_text.find_all('div', class_='genre')
        for g in genre_divs:
            genres.append(g.get_text().strip())

        # Get title
        title_elem = event_text.find('p', class_='h4')
        if not title_elem:
            return None
        title = self._clean_text(title_elem.get_text())

        if not title:
            return None

        # Get venue location (if Off Cabot)
        location = "Beverly"
        venue_name = "The Cabot"
        venue_id = "cabot"

        location_elem = event_text.find('p', class_='h5')
        if location_elem:
            loc_text = location_elem.get_text()
            if 'off cabot' in loc_text.lower():
                venue_name = "Off Cabot"
                venue_id = "offcabot"

        # Check for off_cabot_logo
        if item.find('img', class_='off_cabot_logo'):
            venue_name = "Off Cabot"
            venue_id = "offcabot"

        # Filter: only include music events
        is_music = any('music' in g.lower() for g in genres)
        # But also include events that don't have genre tags (might be music)
        if genres and not is_music:
            # Skip comedy, films, etc. unless it's likely a music event
            non_music_genres = ['comedy', 'film', 'films', 'podcast', 'talk', 'lecture']
            if any(g.lower() in non_music_genres for g in genres):
                return None

        # Split title into bands
        bands = self._split_bands(title)
        if not bands:
            bands = [title]

        concert = Concert(
            date=date,
            venue_id=venue_id,
            venue_name=venue_name,
            venue_location=location,
            bands=bands,
            age_requirement="a/a",
            price_advance=None,
            price_door=None,
            time=time_str,
            flags=[],
            source=self.source_name,
            source_url=event_url,
            genre_tags=[g.lower() for g in genres]
        )

        return concert
