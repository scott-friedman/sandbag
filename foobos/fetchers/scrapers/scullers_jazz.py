"""
Scraper for Scullers Jazz Club using Playwright for JavaScript rendering.
https://www.scullersjazz.com/calendar/
"""

from datetime import datetime
from typing import List
import logging
import re

from .base import BaseScraper
from ...models import Concert
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)

SCULLERS_URL = "https://www.scullersjazz.com/calendar/"

# Try to import Playwright - it may not be available in all environments
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not available - Scullers Jazz scraper will be skipped")


class ScullersJazzScraper(BaseScraper):
    """Scraper for Scullers Jazz Club using Playwright."""

    source_name = "scullers_jazz"

    @property
    def url(self) -> str:
        return SCULLERS_URL

    def fetch(self) -> List[Concert]:
        """Fetch concerts from Scullers Jazz Club."""
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning(f"[{self.source_name}] Playwright not available, skipping")
            return []

        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_scullers_jazz")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Navigate and wait for content to load
                page.goto(SCULLERS_URL, wait_until="networkidle", timeout=30000)

                # Wait for dynamic content and click "Load More" if present
                page.wait_for_timeout(2000)

                # Try to load more events by clicking the button
                try:
                    for _ in range(3):  # Click up to 3 times
                        load_more = page.locator("text=Load More").first
                        if load_more.is_visible():
                            load_more.click()
                            page.wait_for_timeout(1500)
                        else:
                            break
                except Exception:
                    pass  # No load more button or already loaded all

                # Get the page content
                content = page.content()

                # Parse with BeautifulSoup
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, 'lxml')

                concerts = self._parse_events(soup)

                browser.close()

        except Exception as e:
            logger.error(f"[{self.source_name}] Failed to fetch: {e}")
            return []

        # Cache the results
        if concerts:
            save_cache("scrape_scullers_jazz", [c.to_dict() for c in concerts])

        self._log_fetch_complete(len(concerts))
        return concerts

    def _parse_events(self, soup) -> List[Concert]:
        """Parse events from the rendered page."""
        concerts = []
        current_year = datetime.now().year

        # Look for event containers
        # Scullers typically uses cards or list items for events
        event_containers = soup.find_all(class_=re.compile(r'event|show|calendar-item', re.I))

        if not event_containers:
            # Try parsing from text if no containers found
            return self._parse_from_text(soup)

        for container in event_containers:
            try:
                # Extract date
                date_elem = container.find(class_=re.compile(r'date', re.I))
                if not date_elem:
                    continue

                date_text = date_elem.get_text().strip()
                date = self._parse_date(date_text, current_year)
                if not date:
                    continue

                # Extract title/artist
                title_elem = container.find(['h2', 'h3', 'h4', 'a'], class_=re.compile(r'title|name|artist', re.I))
                if not title_elem:
                    title_elem = container.find(['h2', 'h3', 'h4'])
                if not title_elem:
                    continue

                title = self._clean_text(title_elem.get_text())
                if not title or len(title) < 2:
                    continue

                # Extract time
                time_str = "8pm"
                time_elem = container.find(class_=re.compile(r'time', re.I))
                if time_elem:
                    time_str = self._parse_time(time_elem.get_text())

                # Extract price
                price_advance = None
                price_door = None
                price_elem = container.find(class_=re.compile(r'price|ticket', re.I))
                if price_elem:
                    price_advance, price_door = self._parse_price(price_elem.get_text())

                bands = self._split_bands(title)
                if not bands:
                    bands = [title]

                concert = Concert(
                    date=date,
                    venue_id="scullers",
                    venue_name="Scullers Jazz Club",
                    venue_location="Boston",
                    bands=bands,
                    age_requirement="21+",
                    price_advance=price_advance,
                    price_door=price_door,
                    time=time_str,
                    flags=[],
                    source=self.source_name,
                    source_url=SCULLERS_URL,
                    genre_tags=["jazz"]
                )
                concerts.append(concert)

            except Exception as e:
                logger.debug(f"Error parsing event container: {e}")
                continue

        return concerts

    def _parse_from_text(self, soup) -> List[Concert]:
        """Fallback: parse events from page text."""
        concerts = []
        current_year = datetime.now().year

        text = soup.get_text(separator='\n')
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        i = 0
        while i < len(lines):
            line = lines[i]

            # Look for date patterns
            date_match = re.match(
                r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+'
                r'(\d{1,2})(?:,?\s*(\d{4}))?',
                line, re.I
            )

            if date_match:
                month_name = date_match.group(1).lower()
                day = int(date_match.group(2))
                year = int(date_match.group(3)) if date_match.group(3) else current_year

                months = {
                    'january': 1, 'february': 2, 'march': 3, 'april': 4,
                    'may': 5, 'june': 6, 'july': 7, 'august': 8,
                    'september': 9, 'october': 10, 'november': 11, 'december': 12
                }
                month = months.get(month_name)

                if month:
                    try:
                        date = datetime(year, month, day)
                    except ValueError:
                        i += 1
                        continue

                    # Look for artist name in next line
                    if i + 1 < len(lines):
                        artist = lines[i + 1]
                        # Skip if it looks like another date or time
                        if not re.match(r'^(January|February|March|April|May|June|July|August|September|October|November|December|\d)', artist, re.I):
                            if len(artist) > 2:
                                bands = self._split_bands(artist)
                                if not bands:
                                    bands = [artist]

                                concert = Concert(
                                    date=date,
                                    venue_id="scullers",
                                    venue_name="Scullers Jazz Club",
                                    venue_location="Boston",
                                    bands=bands,
                                    age_requirement="21+",
                                    price_advance=None,
                                    price_door=None,
                                    time="8pm",
                                    flags=[],
                                    source=self.source_name,
                                    source_url=SCULLERS_URL,
                                    genre_tags=["jazz"]
                                )
                                concerts.append(concert)

            i += 1

        return concerts

    def _parse_date(self, date_str: str, year: int) -> datetime:
        """Parse various date formats."""
        if not date_str:
            return None

        # Try "January 25" or "January 25, 2026"
        match = re.search(
            r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+'
            r'(\d{1,2})(?:,?\s*(\d{4}))?',
            date_str, re.I
        )

        if match:
            month_name = match.group(1).lower()
            day = int(match.group(2))
            event_year = int(match.group(3)) if match.group(3) else year

            months = {
                'january': 1, 'february': 2, 'march': 3, 'april': 4,
                'may': 5, 'june': 6, 'july': 7, 'august': 8,
                'september': 9, 'october': 10, 'november': 11, 'december': 12
            }
            month = months.get(month_name)

            if month:
                try:
                    return datetime(event_year, month, day)
                except ValueError:
                    pass

        return None
