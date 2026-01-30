"""
Scraper for City Winery Boston.
https://citywinery.com/pages/events/boston

Uses Playwright to handle JavaScript-driven event loading.
"""

from datetime import datetime
from typing import List, Optional
import logging
import re

from .base import BaseScraper
from ...models import Concert
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)

CITY_WINERY_URL = "https://citywinery.com/pages/events/boston"

# Try to import Playwright
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not available - City Winery scraper will be skipped")


class CityWineryScraper(BaseScraper):
    """Scraper for City Winery Boston using Playwright."""

    source_name = "city_winery"

    @property
    def url(self) -> str:
        return CITY_WINERY_URL

    def fetch(self) -> List[Concert]:
        """Fetch concerts from City Winery Boston."""
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning(f"[{self.source_name}] Playwright not available, skipping")
            return []

        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_city_winery")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Set viewport
                page.set_viewport_size({"width": 1920, "height": 1080})

                # Navigate and wait for content
                logger.info(f"[{self.source_name}] Loading page...")
                page.goto(CITY_WINERY_URL, wait_until="networkidle", timeout=45000)
                page.wait_for_timeout(3000)

                # Click "Load More" repeatedly to get all events
                max_clicks = 30
                clicks = 0
                while clicks < max_clicks:
                    try:
                        load_more = page.locator('button:has-text("Load More"), a:has-text("Load More"), [class*="load-more"]')
                        if load_more.count() > 0 and load_more.first.is_visible():
                            load_more.first.click()
                            page.wait_for_timeout(2000)
                            clicks += 1
                            logger.debug(f"[{self.source_name}] Clicked Load More ({clicks})")
                        else:
                            break
                    except Exception:
                        break

                # Also scroll to ensure all content loads
                for _ in range(3):
                    page.evaluate("window.scrollBy(0, window.innerHeight)")
                    page.wait_for_timeout(500)

                # Get page content
                content = page.content()
                browser.close()

                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, 'lxml')

                concerts = self._parse_events(soup)

        except Exception as e:
            logger.error(f"[{self.source_name}] Failed to fetch: {e}")
            return []

        # Cache results
        if concerts:
            save_cache("scrape_city_winery", [c.to_dict() for c in concerts])

        self._log_fetch_complete(len(concerts))
        return concerts

    def _parse_events(self, soup) -> List[Concert]:
        """Parse events from the City Winery page."""
        concerts = []
        seen_events = set()
        current_year = datetime.now().year

        # Find ticket links - each links to a unique event
        ticket_links = soup.select('a[href*="tickets.citywinery.com/event/"]')
        logger.debug(f"[{self.source_name}] Found {len(ticket_links)} ticket links")

        seen_urls = set()
        for link in ticket_links:
            href = link.get('href', '')
            if href in seen_urls:
                continue
            seen_urls.add(href)

            concert = self._parse_ticket_link(link, href, current_year, seen_events)
            if concert:
                concerts.append(concert)

        return concerts

    def _parse_ticket_link(self, link, href: str, year: int, seen_events: set) -> Optional[Concert]:
        """Parse event from a ticket link and its container."""
        try:
            # Go up to find the event container with date/time info
            container = link
            for _ in range(8):
                if container.parent:
                    container = container.parent
                # Stop if we find a container with date info
                text = container.get_text()
                if re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', text):
                    break

            # Extract info from container
            text = container.get_text(separator=' ')
            text = re.sub(r'\s+', ' ', text).strip()

            # Find date pattern
            date = self._extract_date_from_text(text, year)
            if not date:
                return None

            # Skip past events
            if date < datetime.now():
                return None

            # Find time
            time_str = self._extract_time_from_text(text)

            # Find title - look for event-title class in container
            title_elem = container.select_one('.event-title, [class*="title"]')
            title = title_elem.get_text().strip() if title_elem else None

            if not title:
                # Extract from URL as fallback
                url_match = re.search(r'/event/([^/?]+)', href)
                if url_match:
                    title = url_match.group(1).replace('-', ' ').title()
                    # Clean up random suffixes
                    title = re.sub(r'\s+[a-z0-9]{6}$', '', title, flags=re.I)

            if not title:
                return None

            # Create event key for deduplication (include time for multi-show days)
            event_key = (date.strftime('%Y-%m-%d'), time_str, title.lower()[:30])
            if event_key in seen_events:
                return None
            seen_events.add(event_key)

            return Concert(
                date=date,
                venue_id="city_winery",
                venue_name="City Winery Boston",
                venue_location="Boston",
                bands=[title],
                age_requirement="21+",
                price_advance=None,
                price_door=None,
                time=time_str,
                flags=[],
                source=self.source_name,
                source_url=href,
                genre_tags=[]
            )

        except Exception as e:
            logger.debug(f"Error parsing ticket link: {e}")
            return None

    def _extract_date_from_text(self, text: str, year: int) -> Optional[datetime]:
        """Extract date from text."""
        # Find date pattern
        match = re.search(
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(\d{4}))?',
            text, re.I
        )
        if not match:
            return None

        months = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }

        month = months.get(match.group(1).lower()[:3])
        day = int(match.group(2))
        event_year = int(match.group(3)) if match.group(3) else year

        # Handle year rollover
        if event_year == year and month < datetime.now().month:
            event_year += 1

        try:
            return datetime(event_year, month, day)
        except ValueError:
            return None

    def _extract_time_from_text(self, text: str) -> str:
        """Extract time from text."""
        match = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)', text)
        if match:
            hour = match.group(1)
            mins = match.group(2)
            ampm = match.group(3).lower()
            if mins == '00':
                return f"{hour}{ampm}"
            return f"{hour}:{mins}{ampm}"
        return "8pm"
