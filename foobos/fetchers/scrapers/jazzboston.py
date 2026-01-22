"""
Scraper for JazzBoston calendar.
https://jazzboston.org/jazz-calendar/?view=list

Uses Playwright when available to handle JavaScript-driven pagination
(5 pages, ~21 events each, ~105 total events).
Falls back to static scraping (page 1 only) if Playwright unavailable.
"""

from datetime import datetime
from typing import List, Optional, Tuple
import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper
from ...models import Concert
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)

JAZZBOSTON_URL = "https://jazzboston.org/jazz-calendar/?view=list"

# Venue name normalization - map alternate names to canonical names
VENUE_ALIASES = {
    "the charles hotel at regattabar": ("Regattabar", "Cambridge"),
    "charles hotel at regattabar": ("Regattabar", "Cambridge"),
    "regattabar at the charles hotel": ("Regattabar", "Cambridge"),
}

# Try to import Playwright - it may not be available in all environments
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.info("Playwright not available - JazzBoston will use static scraping (page 1 only)")


class JazzBostonScraper(BaseScraper):
    """Scraper for JazzBoston jazz calendar."""

    source_name = "jazzboston"

    @property
    def url(self) -> str:
        return JAZZBOSTON_URL

    def fetch(self) -> List[Concert]:
        """Fetch concerts from JazzBoston calendar."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_jazzboston")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        # Use Playwright if available for full pagination support
        if PLAYWRIGHT_AVAILABLE:
            concerts = self._fetch_with_playwright()
        else:
            concerts = self._fetch_static()

        # Cache the results
        if concerts:
            save_cache("scrape_jazzboston", [c.to_dict() for c in concerts])

        self._log_fetch_complete(len(concerts))
        return concerts

    def _fetch_with_playwright(self) -> List[Concert]:
        """Fetch all pages using Playwright for JavaScript pagination."""
        all_concerts = []
        seen_events = set()

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Navigate and wait for content to load
                logger.info(f"[{self.source_name}] Loading page with Playwright...")
                page.goto(JAZZBOSTON_URL, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Get total pages from pagination info
                total_pages = 5  # Default based on observed behavior

                try:
                    # Try to get actual page count from pagination
                    pagination = page.locator('.eli_pagination')
                    if pagination.count() > 0:
                        page_buttons = page.locator('.eli_pagination a, .eli_pagination span.page-number')
                        if page_buttons.count() > 0:
                            # Get the last page number
                            all_nums = page_buttons.all_text_contents()
                            nums = [int(n) for n in all_nums if n.isdigit()]
                            if nums:
                                total_pages = max(nums)
                except Exception:
                    pass

                logger.info(f"[{self.source_name}] Scraping {total_pages} pages...")

                # Scrape each page
                for page_num in range(1, total_pages + 1):
                    try:
                        if page_num > 1:
                            # Click on page number
                            page_link = page.locator(f'.eli_pagination a:has-text("{page_num}")')
                            if page_link.count() > 0:
                                page_link.first.click()
                                page.wait_for_timeout(1500)
                            else:
                                # Try clicking "next" or incrementing
                                next_btn = page.locator('.eli_pagination .next, .eli_pagination a:has-text("»")')
                                if next_btn.count() > 0:
                                    next_btn.first.click()
                                    page.wait_for_timeout(1500)
                                else:
                                    break

                        # Get page content and parse
                        content = page.content()
                        soup = BeautifulSoup(content, 'lxml')
                        page_concerts = self._parse_events(soup, seen_events)
                        all_concerts.extend(page_concerts)

                        logger.debug(f"[{self.source_name}] Page {page_num}: {len(page_concerts)} events")

                    except Exception as e:
                        logger.debug(f"[{self.source_name}] Error on page {page_num}: {e}")
                        break

                browser.close()

        except Exception as e:
            logger.error(f"[{self.source_name}] Playwright fetch failed: {e}")
            # Fall back to static scraping
            logger.info(f"[{self.source_name}] Falling back to static scraping...")
            return self._fetch_static()

        return all_concerts

    def _fetch_static(self) -> List[Concert]:
        """Fetch using static HTTP request (page 1 only)."""
        try:
            soup = self._get_soup()
            seen_events = set()
            return self._parse_events(soup, seen_events)
        except Exception as e:
            logger.error(f"Failed to fetch JazzBoston events: {e}")
            return []

    def _parse_events(self, soup, seen_events: set) -> List[Concert]:
        """Parse events from the JazzBoston calendar page.

        Structure:
        - Container: div.eli_row
        - Title: h4.eli_title a
        - Date: div.hidden or p.endate (MM-DD-YYYY)
        - Venue: span.eli_address ("Presented by X at Venue, Location")
        - Time: in "Upcoming Dates:" text ("@ X:XX pm")

        Note: Each event appears twice in the HTML, so we deduplicate by
        (title, date) key using the seen_events set.
        """
        concerts = []

        # Find all event rows
        event_rows = soup.select('div.eli_row')

        for row in event_rows:
            try:
                concert = self._parse_event_row(row)
                if concert:
                    # Deduplicate by title + date
                    event_key = (concert.bands[0] if concert.bands else "", concert.date.date())
                    if event_key not in seen_events:
                        seen_events.add(event_key)
                        concerts.append(concert)
            except Exception as e:
                logger.debug(f"Error parsing JazzBoston event: {e}")
                continue

        return concerts

    def _parse_event_row(self, row) -> Optional[Concert]:
        """Parse a single event row."""
        # Extract title
        title_elem = row.select_one('h4.eli_title a, h4.eli_h4 a')
        if not title_elem:
            return None
        title = self._clean_text(title_elem.get_text())
        if not title:
            return None

        # Extract event URL
        event_url = title_elem.get('href', '')
        if event_url and not event_url.startswith('http'):
            event_url = f"https://jazzboston.org{event_url}"

        # Extract date from hidden div or endate paragraph
        date = self._extract_date(row)
        if not date:
            return None

        # Extract venue and location
        venue_name, venue_location = self._extract_venue(row)
        if not venue_name:
            venue_name = "Various"
            venue_location = "Boston"

        # Extract time
        time_str = self._extract_time(row)

        # Parse artists from title
        bands = self._parse_artists(title)

        return Concert(
            date=date,
            venue_id=self._make_venue_id(venue_name),
            venue_name=venue_name,
            venue_location=venue_location,
            bands=bands,
            age_requirement="a/a",
            price_advance=None,
            price_door=None,
            time=time_str,
            flags=[],
            source=self.source_name,
            source_url=event_url or JAZZBOSTON_URL,
            genre_tags=["jazz"]
        )

    def _extract_date(self, row) -> Optional[datetime]:
        """Extract date from event row."""
        # Try hidden div first
        hidden_date = row.select_one('h4 div.hidden')
        if hidden_date:
            date_str = self._clean_text(hidden_date.get_text())
            date = self._parse_date_str(date_str)
            if date:
                return date

        # Try endate paragraph
        endate = row.select_one('p.endate')
        if endate:
            date_str = self._clean_text(endate.get_text())
            date = self._parse_date_str(date_str)
            if date:
                return date

        # Try to find date in "Upcoming Dates:" text
        row_text = row.get_text()
        match = re.search(r'(\w{3}),\s+(\w{3})\s+(\d{1,2})\s+@', row_text)
        if match:
            try:
                # Format: "Thu, Jan 22 @"
                month_day = f"{match.group(2)} {match.group(3)}"
                # Assume current or next year
                year = datetime.now().year
                date_str = f"{month_day} {year}"
                date = datetime.strptime(date_str, "%b %d %Y")
                # If date is in past, assume next year
                if date < datetime.now():
                    date = date.replace(year=year + 1)
                return date
            except ValueError:
                pass

        return None

    def _parse_date_str(self, date_str: str) -> Optional[datetime]:
        """Parse date string in MM-DD-YYYY format."""
        if not date_str:
            return None

        # Format: 01-22-2026
        match = re.match(r'(\d{2})-(\d{2})-(\d{4})', date_str)
        if match:
            try:
                return datetime(
                    year=int(match.group(3)),
                    month=int(match.group(1)),
                    day=int(match.group(2))
                )
            except ValueError:
                pass

        return None

    def _extract_venue(self, row) -> Tuple[str, str]:
        """Extract venue name and location from address span."""
        address_elem = row.select_one('span.eli_address')
        if not address_elem:
            return ("Various", "Boston")

        address_text = self._clean_text(address_elem.get_text())

        # Format: "Presented by X at Venue, Location"
        # or just "Presented by X at Venue"
        venue = None
        location = "Boston"

        match = re.search(r'at\s+([^,]+),?\s*(\w+)?', address_text, re.IGNORECASE)
        if match:
            venue = match.group(1).strip()
            location = match.group(2).strip() if match.group(2) else "Boston"
        elif ' at ' in address_text:
            # Try simpler pattern
            parts = address_text.split(' at ', 1)
            if len(parts) > 1:
                venue_location = parts[1].strip()
                # Split on comma for location
                if ',' in venue_location:
                    venue, location = venue_location.rsplit(',', 1)
                    venue = venue.strip()
                    location = location.strip()
                else:
                    venue = venue_location

        if not venue:
            return ("Various", "Boston")

        # Check for venue aliases (normalize alternate names)
        venue_lower = venue.lower()
        if venue_lower in VENUE_ALIASES:
            return VENUE_ALIASES[venue_lower]

        return (venue, location)

    def _extract_time(self, row) -> str:
        """Extract show time from event row."""
        row_text = row.get_text()

        # Look for time pattern like "@ 7:30 pm" or "@ 6:00 pm"
        match = re.search(r'@\s*(\d{1,2}:\d{2}\s*[ap]m)', row_text, re.IGNORECASE)
        if match:
            return self._parse_time(match.group(1))

        # Look for standalone time pattern
        match = re.search(r'(\d{1,2}:\d{2}\s*[ap]m)', row_text, re.IGNORECASE)
        if match:
            return self._parse_time(match.group(1))

        return "8pm"

    def _parse_artists(self, title: str) -> List[str]:
        """Parse artist names from event title."""
        if not title:
            return []

        # Remove common prefixes
        prefixes_to_remove = [
            r'^.*?\s+presents?:?\s+',
            r'^.*?\s+concert series:?\s+',
        ]
        cleaned = title
        for prefix in prefixes_to_remove:
            cleaned = re.sub(prefix, '', cleaned, flags=re.IGNORECASE)

        # Use base class band splitting
        bands = self._split_bands(cleaned)
        return bands if bands else [title]

    def _make_venue_id(self, venue_name: str) -> str:
        """Create a venue ID from venue name."""
        # Lowercase, remove special chars, replace spaces with underscore
        venue_id = re.sub(r'[^a-z0-9\s]', '', venue_name.lower())
        venue_id = re.sub(r'\s+', '_', venue_id.strip())
        return venue_id[:30]  # Limit length
