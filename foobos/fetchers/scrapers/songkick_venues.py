"""
Scraper for venues that have pages on Songkick.
Currently supports: Deep Cuts, Groton Hill Music Center, City Winery,
Club Passim, The Lilypad, ONCE venues, The 4th Wall, Warehouse XI

Uses Playwright when available to handle JavaScript-driven "Load More" pagination.
Falls back to static scraping if Playwright unavailable.
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

# Try to import Playwright - it may not be available in all environments
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.info("Playwright not available - Songkick will use static scraping (limited events)")


# Venues with Songkick pages
# Each venue has a songkick_id which is the numeric venue ID
SONGKICK_VENUES = [
    {
        "name": "Deep Cuts",
        "id": "deepcuts",
        "location": "Medford",
        "songkick_id": "4503147",
        "age": "21+",
    },
    {
        "name": "Groton Hill Music Center",
        "id": "grotonhill",
        "location": "Groton",
        "songkick_id": "4447493",
        "age": "a/a",
    },
    {
        "name": "City Winery Boston",
        "id": "citywinery",
        "location": "Boston",
        "songkick_id": "3548799",
        "age": "21+",
    },
    {
        "name": "Club Passim",
        "id": "clubpassim",
        "location": "Cambridge",
        "songkick_id": "10659",
        "age": "a/a",
    },
    {
        "name": "The Lilypad",
        "id": "lilypad",
        "location": "Cambridge",
        "songkick_id": "71389",
        "age": "a/a",
    },
    {
        "name": "ONCE Somerville",
        "id": "once_somerville",
        "location": "Somerville",
        "songkick_id": "3078734",
        "age": "18+",
    },
    {
        "name": "ONCE at Boynton Yards",
        "id": "once_boynton",
        "location": "Somerville",
        "songkick_id": "4409048",
        "age": "18+",
    },
    {
        "name": "The 4th Wall",
        "id": "4thwall",
        "location": "Arlington",
        "songkick_id": "4541042",
        "age": "a/a",
    },
    {
        "name": "Warehouse XI",
        "id": "warehousexi",
        "location": "Somerville",
        "songkick_id": "3118614",
        "age": "a/a",
    },
    {
        "name": "Arts at the Armory",
        "id": "armory",
        "location": "Somerville",
        "songkick_id": "359916",
        "age": "a/a",
    },
    {
        "name": "Faces Brewing Co",
        "id": "facesbrewing",
        "location": "Malden",
        "songkick_id": "4422088",
        "age": "21+",
    },
]


class SongkickVenuesScraper(BaseScraper):
    """Scrape events from venues with Songkick pages."""

    @property
    def source_name(self) -> str:
        return "scrape:songkick"

    @property
    def url(self) -> str:
        return "https://www.songkick.com/"

    def fetch(self) -> List[Concert]:
        """Fetch concerts from all Songkick venues."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_songkick_venues")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        all_concerts = []

        for venue in SONGKICK_VENUES:
            try:
                concerts = self._fetch_venue_events(venue)
                logger.info(f"[{self.source_name}] {venue['name']}: {len(concerts)} events")
                all_concerts.extend(concerts)
            except Exception as e:
                logger.warning(f"[{self.source_name}] Error fetching {venue['name']}: {e}")

        # Cache the results
        save_cache("scrape_songkick_venues", [c.to_dict() for c in all_concerts])
        self._log_fetch_complete(len(all_concerts))

        return all_concerts

    def _fetch_venue_events(self, venue: dict) -> List[Concert]:
        """Fetch events from a Songkick venue calendar page."""
        # Use Playwright if available for full event loading
        if PLAYWRIGHT_AVAILABLE:
            return self._fetch_venue_with_playwright(venue)
        else:
            return self._fetch_venue_static(venue)

    def _fetch_venue_with_playwright(self, venue: dict) -> List[Concert]:
        """Fetch venue events using Playwright for JavaScript pagination."""
        concerts = []
        seen_events = set()
        venue_url = f"https://www.songkick.com/venues/{venue['songkick_id']}/calendar"

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Navigate and wait for content
                page.goto(venue_url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Click "Load more" button repeatedly to get all events
                max_clicks = 20  # Safety limit
                clicks = 0
                while clicks < max_clicks:
                    try:
                        load_more = page.locator('button:has-text("Load more"), a:has-text("Load more")')
                        if load_more.count() > 0 and load_more.first.is_visible():
                            load_more.first.click()
                            page.wait_for_timeout(1500)
                            clicks += 1
                        else:
                            break
                    except Exception:
                        break

                # Get final page content
                content = page.content()
                browser.close()

                # Parse with BeautifulSoup
                soup = BeautifulSoup(content, 'lxml')
                concerts = self._parse_venue_events(soup, venue, seen_events)

        except Exception as e:
            logger.warning(f"[{self.source_name}] Playwright failed for {venue['name']}: {e}")
            # Fall back to static scraping
            return self._fetch_venue_static(venue)

        return concerts

    def _fetch_venue_static(self, venue: dict) -> List[Concert]:
        """Fetch venue events using static HTTP request (limited events)."""
        concerts = []
        seen_events = set()
        venue_url = f"https://www.songkick.com/venues/{venue['songkick_id']}/calendar"

        try:
            soup = self._get_soup(venue_url)
            concerts = self._parse_venue_events(soup, venue, seen_events)
        except Exception as e:
            logger.error(f"Error fetching Songkick venue {venue['name']}: {e}")

        return concerts

    def _parse_venue_events(self, soup, venue: dict, seen_events: set) -> List[Concert]:
        """Parse events from Songkick venue page HTML."""
        concerts = []

        # Find the upcoming concerts section (avoid past concerts)
        upcoming_section = soup.select_one('#calendar-summary')
        if not upcoming_section:
            # Try finding the event listings ul directly
            upcoming_section = soup

        # Find event listings - look for li elements with title attribute (date)
        # Structure: <li title="Saturday 31 January 2026">
        event_lists = upcoming_section.select('ul.event-listings')
        for event_list in event_lists:
            # Skip if this is the past concerts section
            parent_header = event_list.find_previous('h2')
            if parent_header and 'past' in parent_header.get_text().lower():
                continue

            for event in event_list.select('li[title]'):
                try:
                    concert = self._parse_event(event, venue)
                    if concert:
                        # Deduplicate within this venue (same date + headliner)
                        event_key = (concert.date.strftime('%Y-%m-%d'),
                                    concert.bands[0].lower() if concert.bands else '')
                        if event_key not in seen_events:
                            seen_events.add(event_key)
                            concerts.append(concert)
                except Exception as e:
                    logger.debug(f"Error parsing Songkick event: {e}")

        return concerts

    def _parse_event(self, event_elem, venue: dict) -> Optional[Concert]:
        """Parse a single event element into a Concert."""
        # Extract date
        date = self._extract_date(event_elem)
        if not date:
            return None

        # Only include future events within configured lookahead
        now = datetime.now()
        if date < now or date > now + timedelta(weeks=WEEKS_AHEAD):
            return None

        # Extract artist/band name
        bands = self._extract_bands(event_elem)
        if not bands:
            return None

        # Extract time
        time_str = self._extract_time(event_elem)

        return Concert(
            date=date,
            venue_id=venue["id"],
            venue_name=venue["name"],
            venue_location=venue["location"],
            bands=bands,
            age_requirement=venue["age"],
            price_advance=None,
            price_door=None,
            time=time_str,
            flags=[],
            source=self.source_name,
            source_url=f"https://www.songkick.com/venues/{venue['songkick_id']}",
            genre_tags=[]
        )

    def _extract_date(self, event_elem) -> Optional[datetime]:
        """Extract date from event element."""
        # Try li title attribute first (e.g., title="Saturday 31 January 2026")
        title = event_elem.get('title', '')
        if title:
            date = self._parse_date_text(title)
            if date:
                return date

        # Try datetime attribute
        time_elem = event_elem.select_one('time[datetime]')
        if time_elem and time_elem.get('datetime'):
            try:
                dt_str = time_elem['datetime']
                # Handle ISO format: 2026-01-31T20:00:00-0500
                if 'T' in dt_str:
                    dt_str = dt_str.split('T')[0]
                return datetime.strptime(dt_str, "%Y-%m-%d")
            except ValueError:
                pass

        # Try date text patterns
        date_elem = event_elem.select_one('.date')
        if not date_elem:
            date_elem = event_elem.select_one('[class*="date"]')

        if date_elem:
            date_text = self._clean_text(date_elem.get_text())
            return self._parse_date_text(date_text)

        # Look for month/day pattern in any text
        full_text = self._clean_text(event_elem.get_text())
        return self._parse_date_text(full_text)

    def _parse_date_text(self, text: str) -> Optional[datetime]:
        """Parse date from text like 'Friday, January 31, 2026' or 'Saturday 31 January 2026'."""
        if not text:
            return None

        # Common date patterns
        patterns = [
            # Songkick format: "Saturday 31 January 2026" (day before month)
            (r'(\d{1,2})\s+(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{4})', '%d %B %Y'),
            # Full date with year: "January 31, 2026"
            (r'(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})', '%B %d %Y'),
            # Short month with year: "Jan 31, 2026"
            (r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})', '%b %d %Y'),
        ]

        for pattern, fmt in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    if fmt == '%d %B %Y':
                        # Day month year format
                        date_str = f"{match.group(1)} {match.group(2)} {match.group(3)}"
                    else:
                        # Month day year format
                        date_str = f"{match.group(1)} {match.group(2)} {match.group(3)}"
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue

        return None

    def _extract_bands(self, event_elem) -> List[str]:
        """Extract band names from event element."""
        bands = []

        # Songkick structure: <p class="artists summary"> -> <strong>Artist Name</strong>
        artists_elem = event_elem.select_one('p.artists')
        if artists_elem:
            # Get main artist from strong tag
            for strong in artists_elem.select('strong'):
                band_name = self._clean_text(strong.get_text())
                if band_name and band_name not in bands and len(band_name) > 1:
                    bands.append(band_name)

        # Try headliner/support structure
        if not bands:
            headliner = event_elem.select_one('.headliner a, [class*="headliner"] a, .artist-name a')
            if headliner:
                bands.append(self._clean_text(headliner.get_text()))

        # Try support acts
        for support in event_elem.select('.support a, [class*="support"] a'):
            band_name = self._clean_text(support.get_text())
            if band_name and band_name not in bands:
                bands.append(band_name)

        # Try generic artist links
        if not bands:
            for artist_link in event_elem.select('a[href*="/artists/"]'):
                band_name = self._clean_text(artist_link.get_text())
                if band_name and band_name not in bands and len(band_name) > 1:
                    bands.append(band_name)

        # Try concert links which have artist names
        if not bands:
            for concert_link in event_elem.select('a[href*="/concerts/"]'):
                link_text = self._clean_text(concert_link.get_text())
                if link_text and link_text not in bands and len(link_text) > 1:
                    # Avoid "Buy tickets" type links
                    if 'ticket' not in link_text.lower():
                        bands.append(link_text)

        return bands

    def _extract_time(self, event_elem) -> str:
        """Extract time from event element."""
        # Try time element
        time_elem = event_elem.select_one('.time, [class*="time"]')
        if time_elem:
            time_text = self._clean_text(time_elem.get_text())
            return self._parse_time(time_text)

        # Try to find time in full text
        full_text = self._clean_text(event_elem.get_text())
        match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))', full_text, re.IGNORECASE)
        if match:
            return self._parse_time(match.group(1))

        return "8pm"
