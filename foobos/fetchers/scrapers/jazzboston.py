"""
Scraper for JazzBoston calendar.
https://jazzboston.org/jazz-calendar/?view=list
"""

from datetime import datetime
from typing import List, Optional, Tuple
import logging
import re

from .base import BaseScraper
from ...models import Concert
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)

JAZZBOSTON_URL = "https://jazzboston.org/jazz-calendar/?view=list"


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

        try:
            soup = self._get_soup()
            concerts = self._parse_events(soup)
        except Exception as e:
            logger.error(f"Failed to fetch JazzBoston events: {e}")
            return []

        # Cache the results
        save_cache("scrape_jazzboston", [c.to_dict() for c in concerts])
        self._log_fetch_complete(len(concerts))

        return concerts

    def _parse_events(self, soup) -> List[Concert]:
        """Parse events from the JazzBoston calendar page.

        Structure:
        - Container: div.eli_row
        - Title: h4.eli_title a
        - Date: div.hidden or p.endate (MM-DD-YYYY)
        - Venue: span.eli_address ("Presented by X at Venue, Location")
        - Time: in "Upcoming Dates:" text ("@ X:XX pm")
        """
        concerts = []

        # Find all event rows
        event_rows = soup.select('div.eli_row')
        logger.debug(f"[{self.source_name}] Found {len(event_rows)} event rows")

        for row in event_rows:
            try:
                concert = self._parse_event_row(row)
                if concert:
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
        match = re.search(r'at\s+([^,]+),?\s*(\w+)?', address_text, re.IGNORECASE)
        if match:
            venue = match.group(1).strip()
            location = match.group(2).strip() if match.group(2) else "Boston"
            return (venue, location)

        # Try simpler pattern
        if ' at ' in address_text:
            parts = address_text.split(' at ', 1)
            if len(parts) > 1:
                venue_location = parts[1].strip()
                # Split on comma for location
                if ',' in venue_location:
                    venue, location = venue_location.rsplit(',', 1)
                    return (venue.strip(), location.strip())
                return (venue_location, "Boston")

        return ("Various", "Boston")

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
