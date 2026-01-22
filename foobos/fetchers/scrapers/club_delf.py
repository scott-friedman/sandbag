"""
Scraper for Club d'Elf band shows.
https://clubdelf.com/shows/

This scraper tracks a specific band (Club d'Elf) and includes all their shows,
even those outside the Boston area.
"""

from datetime import datetime
from typing import List
import logging
import re

from .base import BaseScraper
from ...models import Concert
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)

CLUB_DELF_URL = "https://clubdelf.com/shows/"

# Try to import Playwright
try:
    from playwright.sync_api import sync_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not available - Club d'Elf scraper will be skipped")


class ClubDelfScraper(BaseScraper):
    """Scraper for Club d'Elf band shows (includes all locations)."""

    source_name = "club_delf"

    @property
    def url(self) -> str:
        return CLUB_DELF_URL

    def fetch(self) -> List[Concert]:
        """Fetch Club d'Elf shows."""
        if not PLAYWRIGHT_AVAILABLE:
            logger.warning(f"[{self.source_name}] Playwright not available, skipping")
            return []

        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_club_delf")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()

                # Navigate to shows page (no custom User-Agent - it triggers bot detection)
                page.goto(CLUB_DELF_URL, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(2000)

                # Get page content
                content = page.content()

                from bs4 import BeautifulSoup
                soup = BeautifulSoup(content, 'lxml')

                concerts = self._parse_shows(soup)

                browser.close()

        except Exception as e:
            logger.error(f"[{self.source_name}] Failed to fetch: {e}")
            return []

        # Cache results
        if concerts:
            save_cache("scrape_club_delf", [c.to_dict() for c in concerts])

        self._log_fetch_complete(len(concerts))
        return concerts

    def _parse_shows(self, soup) -> List[Concert]:
        """Parse shows from the page.

        Club d'Elf uses GigPress plugin with table structure:
        - .gigpress-date: Date in MM/DD/YY format
        - .gigpress-city: City, State
        - .gigpress-venue: Venue name (linked)
        - .gigpress-country: Country
        """
        concerts = []
        current_year = datetime.now().year

        # GigPress uses table rows for events
        # Look for rows containing gigpress classes
        rows = soup.find_all('tr')

        for row in rows:
            date_cell = row.find(class_='gigpress-date')
            venue_cell = row.find(class_='gigpress-venue')
            city_cell = row.find(class_='gigpress-city')

            if date_cell and venue_cell:
                concert = self._parse_gigpress_row(date_cell, venue_cell, city_cell, current_year)
                if concert:
                    concerts.append(concert)

        # If no GigPress rows found, try legacy container-based parsing
        if not concerts:
            show_containers = soup.find_all(['article', 'div', 'li'],
                                            class_=re.compile(r'show|event|gig|tour|performance', re.I))

            for container in show_containers:
                concert = self._parse_show_container(container, current_year)
                if concert:
                    concerts.append(concert)

        # If still no events, try text-based parsing
        if not concerts:
            concerts = self._parse_from_text(soup)

        return concerts

    def _parse_gigpress_row(self, date_cell, venue_cell, city_cell, year: int) -> Concert:
        """Parse a GigPress table row."""
        # Extract date (format: MM/DD/YY)
        date_text = self._clean_text(date_cell.get_text())
        date = self._parse_date(date_text, year)
        if not date:
            return None

        # Extract venue name (may be a link)
        venue_link = venue_cell.find('a')
        if venue_link:
            venue_name = self._clean_text(venue_link.get_text())
        else:
            venue_name = self._clean_text(venue_cell.get_text())

        if not venue_name or venue_name.lower() in ['tba', 'tbd', '']:
            venue_name = "TBA"

        # Extract city/location
        venue_location = ""
        if city_cell:
            venue_location = self._clean_text(city_cell.get_text())

        # Extract time if present in the row
        time_str = "8pm"
        row_text = date_cell.parent.get_text() if date_cell.parent else ""
        time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))', row_text, re.I)
        if time_match:
            time_str = time_match.group(1).lower().replace(' ', '')

        # Generate venue ID
        venue_id = re.sub(r'[^a-z0-9]', '', venue_name.lower())[:20] or "clubdelf_venue"

        return Concert(
            date=date,
            venue_id=venue_id,
            venue_name=venue_name,
            venue_location=venue_location,
            bands=["Club d'Elf"],
            age_requirement="a/a",
            price_advance=None,
            price_door=None,
            time=time_str,
            flags=["featured_band"],
            source=self.source_name,
            source_url=CLUB_DELF_URL,
            genre_tags=["jazz", "world", "experimental"]
        )

    def _parse_show_container(self, container, year: int) -> Concert:
        """Parse a single show container."""
        text = container.get_text(separator=' ')

        # Extract date
        date = self._parse_date(text, year)
        if not date:
            return None

        # Extract venue
        venue_name = "Unknown Venue"
        venue_location = ""

        # Look for venue info - common patterns
        venue_elem = container.find(class_=re.compile(r'venue|location|place', re.I))
        if venue_elem:
            venue_text = venue_elem.get_text().strip()
            venue_name, venue_location = self._parse_venue(venue_text)
        else:
            # Try to find venue from links or text
            links = container.find_all('a')
            for link in links:
                href = link.get('href', '')
                link_text = link.get_text().strip()
                # Skip social media links
                if any(x in href.lower() for x in ['facebook', 'twitter', 'instagram', 'bandcamp']):
                    continue
                if link_text and len(link_text) > 3:
                    venue_name = link_text
                    break

        # Look for location separately
        loc_elem = container.find(class_=re.compile(r'city|location|address', re.I))
        if loc_elem and not venue_location:
            venue_location = loc_elem.get_text().strip()

        # Extract time
        time_str = "8pm"
        time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))', text, re.I)
        if time_match:
            time_str = time_match.group(1).lower().replace(' ', '')

        # Generate venue ID
        venue_id = re.sub(r'[^a-z0-9]', '', venue_name.lower())[:20] or "clubdelf_venue"

        return Concert(
            date=date,
            venue_id=venue_id,
            venue_name=venue_name,
            venue_location=venue_location,
            bands=["Club d'Elf"],
            age_requirement="a/a",
            price_advance=None,
            price_door=None,
            time=time_str,
            flags=["featured_band"],
            source=self.source_name,
            source_url=CLUB_DELF_URL,
            genre_tags=["jazz", "world", "experimental"]
        )

    def _parse_from_text(self, soup) -> List[Concert]:
        """Parse shows from page text."""
        concerts = []
        current_year = datetime.now().year

        # Get all text
        text = soup.get_text(separator='\n')
        lines = [l.strip() for l in text.split('\n') if l.strip()]

        i = 0
        while i < len(lines):
            line = lines[i]

            # Look for date patterns
            date = self._parse_date(line, current_year)
            if date:
                # Collect context around date for venue info
                context_lines = lines[max(0, i-1):min(len(lines), i+4)]
                context = ' '.join(context_lines)

                venue_name, venue_location = self._extract_venue_from_context(context, line)

                if venue_name and venue_name != line:
                    # Extract time if present
                    time_str = "8pm"
                    time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))', context, re.I)
                    if time_match:
                        time_str = time_match.group(1).lower().replace(' ', '')

                    venue_id = re.sub(r'[^a-z0-9]', '', venue_name.lower())[:20] or "clubdelf_venue"

                    concert = Concert(
                        date=date,
                        venue_id=venue_id,
                        venue_name=venue_name,
                        venue_location=venue_location,
                        bands=["Club d'Elf"],
                        age_requirement="a/a",
                        price_advance=None,
                        price_door=None,
                        time=time_str,
                        flags=["featured_band"],
                        source=self.source_name,
                        source_url=CLUB_DELF_URL,
                        genre_tags=["jazz", "world", "experimental"]
                    )
                    concerts.append(concert)
            i += 1

        return concerts

    def _extract_venue_from_context(self, context: str, date_line: str) -> tuple:
        """Extract venue name and location from context around a date."""
        # Common venue patterns
        venue_patterns = [
            r'(?:at|@)\s+([^,\n]+?)(?:,\s*([A-Za-z\s]+(?:,\s*[A-Z]{2})?))?',
            r'([A-Z][a-zA-Z\s\'-]+(?:Hall|Lounge|Center|Club|Theatre|Theater|Room|Bar|Cafe|House))',
        ]

        for pattern in venue_patterns:
            match = re.search(pattern, context)
            if match:
                venue_name = match.group(1).strip()
                venue_location = match.group(2).strip() if match.lastindex >= 2 and match.group(2) else ""
                return venue_name, venue_location

        # Try to find non-date lines
        lines = context.split('\n')
        for line in lines:
            line = line.strip()
            if line and line != date_line and not self._is_date_line(line):
                # Skip generic words
                if not re.match(r'^(Buy|Tickets|More|Info|Details|Show|Shows|ft\.|featuring)', line, re.I):
                    return line[:50], ""

        return "Unknown Venue", ""

    def _is_date_line(self, line: str) -> bool:
        """Check if a line is primarily a date."""
        months = r'(January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)'
        if re.match(rf'^{months}\s+\d', line, re.I):
            return True
        if re.match(r'^\d{1,2}/\d{1,2}', line):
            return True
        return False

    def _parse_venue(self, venue_text: str) -> tuple:
        """Parse venue name and location from text."""
        # Try to split on comma for location
        if ',' in venue_text:
            parts = venue_text.split(',', 1)
            return parts[0].strip(), parts[1].strip()
        return venue_text.strip(), ""

    def _parse_date(self, date_str: str, year: int) -> datetime:
        """Parse various date formats."""
        if not date_str:
            return None

        # "January 25" or "January 25, 2026" or "Jan 25"
        match = re.search(
            r'(January|February|March|April|May|June|July|August|September|October|November|December|'
            r'Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+'
            r'(\d{1,2})(?:st|nd|rd|th)?(?:,?\s*(\d{4}))?',
            date_str, re.I
        )

        if match:
            month_name = match.group(1).lower()
            day = int(match.group(2))
            event_year = int(match.group(3)) if match.group(3) else year

            months = {
                'january': 1, 'jan': 1,
                'february': 2, 'feb': 2,
                'march': 3, 'mar': 3,
                'april': 4, 'apr': 4,
                'may': 5,
                'june': 6, 'jun': 6,
                'july': 7, 'jul': 7,
                'august': 8, 'aug': 8,
                'september': 9, 'sep': 9,
                'october': 10, 'oct': 10,
                'november': 11, 'nov': 11,
                'december': 12, 'dec': 12
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
