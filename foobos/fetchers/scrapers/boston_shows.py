"""
Scraper for bostonshows.org - Greater Boston live music calendar.
https://bostonshows.org/

Note: This site may have connectivity issues from some networks (TLS handshake failures).
It should work in most production environments like GitHub Actions.
"""

from datetime import datetime, timedelta
from typing import List, Optional
import logging
import re

from .base import BaseScraper
from ...models import Concert
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)

BOSTON_SHOWS_URL = "https://bostonshows.org/"


class BostonShowsScraper(BaseScraper):
    """Scrape events from bostonshows.org."""

    @property
    def source_name(self) -> str:
        return "scrape:boston_shows"

    @property
    def url(self) -> str:
        return BOSTON_SHOWS_URL

    def fetch(self) -> List[Concert]:
        """Fetch concerts from bostonshows.org."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_boston_shows")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        all_concerts = []

        try:
            # Fetch main page
            soup = self._get_soup(BOSTON_SHOWS_URL)
            concerts = self._parse_main_page(soup)
            all_concerts.extend(concerts)
            logger.info(f"[{self.source_name}] Found {len(concerts)} events on main page")

        except Exception as e:
            logger.warning(f"[{self.source_name}] Error fetching main page: {e}")
            # Return empty list if site is inaccessible
            return []

        # Cache the results
        if all_concerts:
            save_cache("scrape_boston_shows", [c.to_dict() for c in all_concerts])

        self._log_fetch_complete(len(all_concerts))
        return all_concerts

    def _parse_main_page(self, soup) -> List[Concert]:
        """Parse the main page for concert listings."""
        concerts = []

        # The site appears to list shows by date
        # Look for common patterns: date headers followed by show listings

        # Try finding show entries - adapt based on actual site structure
        # Common patterns:
        # - <div class="show"> or <div class="event">
        # - <tr> table rows with date/venue/artist
        # - <li> list items with show info

        # Try table-based layout first
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            current_date = None

            for row in rows:
                # Check if this is a date header row
                date_cell = row.find(['th', 'td'], class_=re.compile(r'date|day', re.I))
                if date_cell:
                    date_text = self._clean_text(date_cell.get_text())
                    parsed_date = self._parse_date(date_text)
                    if parsed_date:
                        current_date = parsed_date
                        continue

                # Try to parse as show row
                if current_date:
                    concert = self._parse_table_row(row, current_date)
                    if concert:
                        concerts.append(concert)

        # Try div-based layout
        for show_div in soup.find_all(['div', 'article'], class_=re.compile(r'show|event|listing', re.I)):
            concert = self._parse_show_div(show_div)
            if concert:
                concerts.append(concert)

        # Try list-based layout
        for show_list in soup.find_all(['ul', 'ol'], class_=re.compile(r'show|event|listing', re.I)):
            for item in show_list.find_all('li'):
                concert = self._parse_list_item(item)
                if concert:
                    concerts.append(concert)

        # If structured parsing didn't work, try generic text parsing
        if not concerts:
            concerts = self._parse_generic(soup)

        return concerts

    def _parse_table_row(self, row, date: datetime) -> Optional[Concert]:
        """Parse a table row as a concert listing."""
        try:
            cells = row.find_all('td')
            if len(cells) < 2:
                return None

            # Try to extract venue, artist, time from cells
            venue_name = None
            bands = []
            time_str = "8pm"

            for cell in cells:
                text = self._clean_text(cell.get_text())
                links = cell.find_all('a')

                # Check for venue link
                for link in links:
                    href = link.get('href', '')
                    if '/venues/' in href:
                        venue_name = self._clean_text(link.get_text())
                    elif '/artists/' in href or '/bands/' in href:
                        bands.append(self._clean_text(link.get_text()))

                # Check for time pattern
                time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))', text, re.I)
                if time_match:
                    time_str = time_match.group(1).lower()

            if not venue_name or not bands:
                return None

            return self._create_concert(date, venue_name, bands, time_str)

        except Exception as e:
            logger.debug(f"Error parsing table row: {e}")
            return None

    def _parse_show_div(self, div) -> Optional[Concert]:
        """Parse a show div element."""
        try:
            # Look for date
            date_elem = div.find(class_=re.compile(r'date', re.I))
            date = None
            if date_elem:
                date = self._parse_date(self._clean_text(date_elem.get_text()))

            if not date:
                return None

            # Look for venue
            venue_elem = div.find(class_=re.compile(r'venue', re.I))
            venue_link = div.find('a', href=re.compile(r'/venues/'))
            venue_name = None
            if venue_elem:
                venue_name = self._clean_text(venue_elem.get_text())
            elif venue_link:
                venue_name = self._clean_text(venue_link.get_text())

            # Look for artist/band
            artist_elem = div.find(class_=re.compile(r'artist|band|act', re.I))
            artist_links = div.find_all('a', href=re.compile(r'/artists/|/bands/'))
            bands = []
            if artist_elem:
                bands = [self._clean_text(artist_elem.get_text())]
            elif artist_links:
                bands = [self._clean_text(a.get_text()) for a in artist_links]

            # Look for time
            time_elem = div.find(class_=re.compile(r'time', re.I))
            time_str = "8pm"
            if time_elem:
                time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))', time_elem.get_text(), re.I)
                if time_match:
                    time_str = time_match.group(1).lower()

            if venue_name and bands:
                return self._create_concert(date, venue_name, bands, time_str)

        except Exception as e:
            logger.debug(f"Error parsing show div: {e}")

        return None

    def _parse_list_item(self, item) -> Optional[Concert]:
        """Parse a list item as a concert."""
        try:
            text = self._clean_text(item.get_text())

            # Try to extract date
            date = self._parse_date(text)
            if not date:
                return None

            # Try to extract venue from link
            venue_link = item.find('a', href=re.compile(r'/venues/'))
            venue_name = self._clean_text(venue_link.get_text()) if venue_link else None

            # Try to extract artist
            artist_link = item.find('a', href=re.compile(r'/artists/|/bands/'))
            bands = [self._clean_text(artist_link.get_text())] if artist_link else []

            # Extract time
            time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))', text, re.I)
            time_str = time_match.group(1).lower() if time_match else "8pm"

            if venue_name and bands:
                return self._create_concert(date, venue_name, bands, time_str)

        except Exception as e:
            logger.debug(f"Error parsing list item: {e}")

        return None

    def _parse_generic(self, soup) -> List[Concert]:
        """Generic parsing when structured elements aren't found."""
        concerts = []

        # Find all links that might be shows
        for link in soup.find_all('a'):
            href = link.get('href', '')
            text = self._clean_text(link.get_text())

            # Skip navigation links
            if not text or len(text) < 3:
                continue

            # Look for date patterns in surrounding text
            parent = link.parent
            if parent:
                parent_text = self._clean_text(parent.get_text())
                date = self._parse_date(parent_text)

                if date and '/venues/' in href:
                    # This might be a venue link for a show
                    venue_name = text
                    # Look for artist in siblings
                    bands = []
                    for sibling in parent.find_all('a'):
                        sibling_href = sibling.get('href', '')
                        if sibling_href != href and '/venues/' not in sibling_href:
                            band_name = self._clean_text(sibling.get_text())
                            if band_name and len(band_name) > 2:
                                bands.append(band_name)

                    if bands:
                        time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))', parent_text, re.I)
                        time_str = time_match.group(1).lower() if time_match else "8pm"
                        concert = self._create_concert(date, venue_name, bands, time_str)
                        if concert:
                            concerts.append(concert)

        return concerts

    def _parse_date(self, text: str) -> Optional[datetime]:
        """Parse date from text."""
        if not text:
            return None

        # Common patterns
        patterns = [
            # "January 31, 2026" or "Jan 31, 2026"
            (r'(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})', '%B %d %Y'),
            # "1/31/2026" or "01/31/2026"
            (r'(\d{1,2})/(\d{1,2})/(\d{4})', '%m/%d/%Y'),
            # "2026-01-31"
            (r'(\d{4})-(\d{2})-(\d{2})', '%Y-%m-%d'),
        ]

        for pattern, fmt in patterns:
            match = re.search(pattern, text, re.I)
            if match:
                try:
                    if '%B' in fmt:
                        date_str = f"{match.group(1)} {match.group(2)} {match.group(3)}"
                    elif '%m/%d/%Y' in fmt:
                        date_str = f"{match.group(1)}/{match.group(2)}/{match.group(3)}"
                    else:
                        date_str = f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue

        return None

    def _create_concert(self, date: datetime, venue_name: str, bands: List[str], time_str: str) -> Optional[Concert]:
        """Create a Concert object."""
        # Validate date range
        now = datetime.now()
        if date < now - timedelta(days=1) or date > now + timedelta(days=180):
            return None

        # Create venue ID from name
        venue_id = venue_name.lower()
        venue_id = re.sub(r'[^a-z0-9]+', '_', venue_id)
        venue_id = venue_id.strip('_')[:30]

        return Concert(
            date=date,
            venue_id=venue_id,
            venue_name=venue_name,
            venue_location="Boston",
            bands=bands,
            age_requirement="18+",
            price_advance=None,
            price_door=None,
            time=time_str,
            flags=[],
            source=self.source_name,
            source_url=BOSTON_SHOWS_URL,
            genre_tags=[]
        )
