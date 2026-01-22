"""
Scraper for Narrows Center for the Arts using Playwright.
https://narrowscenter.showare.com/
"""

from datetime import datetime
from typing import List
import logging
import re

from .base import BaseScraper
from ...models import Concert
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)

NARROWS_URL = "https://narrowscenter.showare.com/?category=39"

# Try to import Playwright
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not available - Narrows Center scraper will be skipped")


class NarrowsCenterScraper(BaseScraper):
    """Scraper for Narrows Center for the Arts using Playwright."""

    source_name = "narrows_center"

    @property
    def url(self) -> str:
        return NARROWS_URL

    def fetch(self) -> List[Concert]:
        """Fetch concerts from Narrows Center."""
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning(f"[{self.source_name}] Playwright not available, skipping")
            return []

        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_narrows_center")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Navigate and wait for content
                page.goto(NARROWS_URL, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(3000)

                # ShoWare systems typically load events into the page
                # Try clicking on future months to get more events
                try:
                    for _ in range(3):
                        next_btn = page.locator(".ui-datepicker-next, .next-month, [title*='Next']").first
                        if next_btn.is_visible():
                            next_btn.click()
                            page.wait_for_timeout(1500)
                except Exception:
                    pass

                # Get page content
                content = page.content()

                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, 'lxml')

                concerts = self._parse_events(soup, page)

                browser.close()

        except Exception as e:
            logger.error(f"[{self.source_name}] Failed to fetch: {e}")
            return []

        # Cache results
        if concerts:
            save_cache("scrape_narrows_center", [c.to_dict() for c in concerts])

        self._log_fetch_complete(len(concerts))
        return concerts

    def _parse_events(self, soup, page) -> List[Concert]:
        """Parse events from the rendered page."""
        concerts = []
        current_year = datetime.now().year

        # ShoWare typically has event containers with performance info
        # Look for common patterns in ShoWare sites
        event_containers = soup.find_all(class_=re.compile(r'event|performance|show-item|calendar-event', re.I))

        if not event_containers:
            # Try looking for links with event info
            event_links = soup.find_all('a', href=re.compile(r'eventperformances|ordertickets', re.I))
            for link in event_links:
                concert = self._parse_event_link(link, current_year)
                if concert:
                    concerts.append(concert)

        for container in event_containers:
            try:
                concert = self._parse_event_container(container, current_year)
                if concert:
                    concerts.append(concert)
            except Exception as e:
                logger.debug(f"Error parsing event: {e}")
                continue

        # If no events found via containers, try text-based parsing
        if not concerts:
            concerts = self._parse_from_text(soup)

        # Dedupe by (date, title)
        seen = set()
        unique_concerts = []
        for c in concerts:
            key = (c.date.strftime("%Y-%m-%d"), c.bands[0] if c.bands else "")
            if key not in seen:
                seen.add(key)
                unique_concerts.append(c)

        return unique_concerts

    def _parse_event_container(self, container, year: int) -> Concert:
        """Parse a single event container."""
        # Extract title
        title_elem = container.find(['h2', 'h3', 'h4', 'a', 'span'],
                                    class_=re.compile(r'title|name|perf', re.I))
        if not title_elem:
            title_elem = container.find(['h2', 'h3', 'h4', 'a'])

        if not title_elem:
            return None

        title = self._clean_text(title_elem.get_text())
        if not title or len(title) < 3:
            return None

        # Extract date
        date = None
        date_elem = container.find(class_=re.compile(r'date', re.I))
        if date_elem:
            date = self._parse_date(date_elem.get_text(), year)

        if not date:
            # Look for date in any text
            text = container.get_text()
            date = self._parse_date(text, year)

        if not date:
            return None

        # Extract time
        time_str = "7:30pm"
        time_elem = container.find(class_=re.compile(r'time', re.I))
        if time_elem:
            time_str = self._parse_time(time_elem.get_text())

        # Extract price
        price_advance = None
        price_elem = container.find(class_=re.compile(r'price', re.I))
        if price_elem:
            price_advance, _ = self._parse_price(price_elem.get_text())

        bands = self._split_bands(title)
        if not bands:
            bands = [title]

        return Concert(
            date=date,
            venue_id="narrowscenter",
            venue_name="Narrows Center for the Arts",
            venue_location="Fall River",
            bands=bands,
            age_requirement="a/a",
            price_advance=price_advance,
            price_door=None,
            time=time_str,
            flags=[],
            source=self.source_name,
            source_url=NARROWS_URL,
            genre_tags=[]
        )

    def _parse_event_link(self, link, year: int) -> Concert:
        """Parse event from a link element."""
        title = self._clean_text(link.get_text())
        if not title or len(title) < 3:
            return None

        # Try to find date near the link
        parent = link.find_parent(['div', 'li', 'tr'])
        date = None
        if parent:
            date = self._parse_date(parent.get_text(), year)

        if not date:
            return None

        bands = self._split_bands(title)
        if not bands:
            bands = [title]

        return Concert(
            date=date,
            venue_id="narrowscenter",
            venue_name="Narrows Center for the Arts",
            venue_location="Fall River",
            bands=bands,
            age_requirement="a/a",
            price_advance=None,
            price_door=None,
            time="7:30pm",
            flags=[],
            source=self.source_name,
            source_url=NARROWS_URL,
            genre_tags=[]
        )

    def _parse_from_text(self, soup) -> List[Concert]:
        """Fallback text-based parsing."""
        concerts = []
        current_year = datetime.now().year

        text = soup.get_text(separator='\n')
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        i = 0
        while i < len(lines):
            line = lines[i]

            # Look for date patterns
            date = self._parse_date(line, current_year)
            if date:
                # Look ahead for title
                if i + 1 < len(lines):
                    potential_title = lines[i + 1]
                    # Skip if looks like time/price/date
                    if not re.match(r'^(\d|January|February|March|April|May|June|July|August|September|October|November|December|AM|PM|\$)',
                                   potential_title, re.I):
                        if len(potential_title) > 3:
                            bands = self._split_bands(potential_title)
                            if not bands:
                                bands = [potential_title]

                            concert = Concert(
                                date=date,
                                venue_id="narrowscenter",
                                venue_name="Narrows Center for the Arts",
                                venue_location="Fall River",
                                bands=bands,
                                age_requirement="a/a",
                                price_advance=None,
                                price_door=None,
                                time="7:30pm",
                                flags=[],
                                source=self.source_name,
                                source_url=NARROWS_URL,
                                genre_tags=[]
                            )
                            concerts.append(concert)
            i += 1

        return concerts

    def _parse_date(self, date_str: str, year: int) -> datetime:
        """Parse various date formats."""
        if not date_str:
            return None

        # "January 25" or "January 25, 2026"
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
                # Handle year rollover
                if month < datetime.now().month and event_year == year:
                    event_year += 1

                try:
                    return datetime(event_year, month, day)
                except ValueError:
                    pass

        # Try "1/25/26" or "01/25/2026"
        match = re.search(r'(\d{1,2})/(\d{1,2})/(\d{2,4})', date_str)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            event_year = int(match.group(3))
            if event_year < 100:
                event_year += 2000

            try:
                return datetime(event_year, month, day)
            except ValueError:
                pass

        return None
