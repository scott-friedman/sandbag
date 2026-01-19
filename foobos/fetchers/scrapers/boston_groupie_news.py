"""
Scraper for Boston Groupie News punk/rock concert listings.

Boston Groupie News (bostongroupienews.com) is a long-running Boston
punk/rock scene blog with comprehensive show listings including:
- Middle East (Downstairs, Upstairs, Corner)
- O'Brien's Pub
- Deep Cuts
- Sonia
- Various DIY venues

Data format:
- Dates in "Month Day, Year (Day of Week)" format
- Venues as plain text
- Bands comma-separated
- Age/price/time info inline
"""

from datetime import datetime
from typing import List, Optional
import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper
from ...models import Concert
from ...utils import get_cached, save_cache, parse_date

logger = logging.getLogger(__name__)


# Map venue names to standardized IDs
VENUE_PATTERNS = {
    "middle east downstairs": {"id": "middleeast_down", "name": "Middle East Downstairs", "location": "Cambridge"},
    "middle east upstairs": {"id": "middleeast_up", "name": "Middle East Upstairs", "location": "Cambridge"},
    "middle east corner": {"id": "middleeast_corner", "name": "Middle East Corner", "location": "Cambridge"},
    "the middle east": {"id": "middleeast", "name": "Middle East", "location": "Cambridge"},
    "middle east": {"id": "middleeast", "name": "Middle East", "location": "Cambridge"},
    "o'brien's": {"id": "obriens", "name": "O'Brien's Pub", "location": "Allston"},
    "obriens": {"id": "obriens", "name": "O'Brien's Pub", "location": "Allston"},
    "o'briens": {"id": "obriens", "name": "O'Brien's Pub", "location": "Allston"},
    "sonia": {"id": "sonia", "name": "Sonia", "location": "Cambridge"},
    "sonia's": {"id": "sonia", "name": "Sonia", "location": "Cambridge"},
    "deep cuts": {"id": "deepcuts", "name": "Deep Cuts", "location": "Medford"},
    "midway cafe": {"id": "midway", "name": "Midway Cafe", "location": "Jamaica Plain"},
    "midway": {"id": "midway", "name": "Midway Cafe", "location": "Jamaica Plain"},
    "once": {"id": "once", "name": "ONCE Ballroom", "location": "Somerville"},
    "crystal ballroom": {"id": "crystal", "name": "Crystal Ballroom", "location": "Somerville"},
    "paradise": {"id": "paradise", "name": "Paradise Rock Club", "location": "Boston"},
    "paradise rock": {"id": "paradise", "name": "Paradise Rock Club", "location": "Boston"},
    "brighton music hall": {"id": "brighton", "name": "Brighton Music Hall", "location": "Allston"},
    "sinclair": {"id": "sinclair", "name": "The Sinclair", "location": "Cambridge"},
    "the sinclair": {"id": "sinclair", "name": "The Sinclair", "location": "Cambridge"},
    "house of blues": {"id": "hob", "name": "House of Blues", "location": "Boston"},
    "royale": {"id": "royale", "name": "Royale", "location": "Boston"},
    "roadrunner": {"id": "roadrunner", "name": "Roadrunner", "location": "Boston"},
}


class BostonGroupieNewsScraper(BaseScraper):
    """Scrape Boston Groupie News for punk/rock shows."""

    @property
    def source_name(self) -> str:
        return "scrape:boston_groupie_news"

    @property
    def url(self) -> str:
        return "https://www.bostongroupienews.com/BostonPunkRockConcertReport.html"

    def fetch(self) -> List[Concert]:
        """Fetch concerts from Boston Groupie News."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_boston_groupie_news")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []

        try:
            soup = self._get_soup(self.url)
            concerts = self._parse_listings(soup)
        except Exception as e:
            logger.error(f"[{self.source_name}] Failed to fetch: {e}")

        # Cache the results
        if concerts:
            save_cache("scrape_boston_groupie_news", [c.to_dict() for c in concerts])

        self._log_fetch_complete(len(concerts))
        return concerts

    def _parse_listings(self, soup: BeautifulSoup) -> List[Concert]:
        """Parse concert listings from the page."""
        concerts = []
        current_date = None

        # The page structure has dates as headers followed by show listings
        # Look for all text content and parse line by line
        body = soup.find("body")
        if not body:
            return concerts

        text = body.get_text(separator="\n")
        lines = text.split("\n")

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # Check if this is a date line: "January 24, 2026 (Saturday)"
            date_match = re.match(
                r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s*(\d{4})?\s*\(?(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?\)?',
                line,
                re.IGNORECASE
            )
            if date_match:
                month = date_match.group(1)
                day = date_match.group(2)
                year = date_match.group(3) or str(datetime.now().year)
                current_date = parse_date(f"{month} {day}, {year}")
                continue

            # Skip if we don't have a current date
            if not current_date:
                continue

            # Skip past dates
            if current_date.date() < datetime.now().date():
                continue

            # Try to parse a show listing
            concert = self._parse_show_line(line, current_date)
            if concert:
                concerts.append(concert)

        return concerts

    def _parse_show_line(self, line: str, date: datetime) -> Optional[Concert]:
        """Parse a single show listing line."""
        # Skip obvious non-show lines
        skip_patterns = [
            r'^(january|february|march|april|may|june|july|august|september|october|november|december)',
            r'^(monday|tuesday|wednesday|thursday|friday|saturday|sunday)',
            r'^(click|buy|tickets|rsvp|more info|facebook)',
            r'^(http|www\.)',
            r'^\d+$',
            r'^-+$',
        ]
        line_lower = line.lower()
        for pattern in skip_patterns:
            if re.match(pattern, line_lower):
                return None

        # Need at least some alphabetic content
        if not re.search(r'[a-zA-Z]{3,}', line):
            return None

        # Try to find venue in the line
        venue_info = self._extract_venue(line)
        if not venue_info:
            return None

        # Extract bands (everything before "at" or the venue mention)
        bands = self._extract_bands(line, venue_info["name"])
        if not bands:
            return None

        # Extract age requirement
        age_req = "a/a"
        if "21+" in line or "21 +" in line:
            age_req = "21+"
        elif "18+" in line or "18 +" in line:
            age_req = "18+"
        elif "all ages" in line.lower():
            age_req = "a/a"

        # Extract price
        price_match = re.search(r'\$(\d+)', line)
        price = int(price_match.group(1)) if price_match else None

        # Extract time
        time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm|AM|PM)', line)
        show_time = "8pm"
        if time_match:
            hour = time_match.group(1)
            minutes = time_match.group(2) or "00"
            ampm = time_match.group(3).lower()
            if minutes == "00":
                show_time = f"{hour}{ampm}"
            else:
                show_time = f"{hour}:{minutes}{ampm}"

        return Concert(
            date=date,
            venue_id=venue_info["id"],
            venue_name=venue_info["name"],
            venue_location=venue_info["location"],
            bands=bands,
            age_requirement=age_req,
            price_advance=price,
            price_door=None,
            time=show_time,
            flags=[],
            source=self.source_name,
            source_url=self.url,
            genre_tags=["punk", "rock"]
        )

    def _extract_venue(self, line: str) -> Optional[dict]:
        """Extract venue from a show listing line."""
        line_lower = line.lower()

        # Check for known venue patterns
        for pattern, venue_info in VENUE_PATTERNS.items():
            if pattern in line_lower:
                return venue_info

        # Check for "at [Venue]" pattern
        at_match = re.search(r'\bat\s+(?:the\s+)?([A-Z][A-Za-z\'\s]+?)(?:\s*,|\s+\d|\s+in\s+|\s+doors|\s*$)', line)
        if at_match:
            venue_name = at_match.group(1).strip()
            venue_id = re.sub(r'[^a-z0-9]+', '_', venue_name.lower()).strip('_')
            return {"id": venue_id, "name": venue_name, "location": "Boston"}

        return None

    def _extract_bands(self, line: str, venue_name: str) -> List[str]:
        """Extract band names from a show listing line."""
        # Remove venue and everything after it
        venue_lower = venue_name.lower()

        # Find where the venue info starts
        line_lower = line.lower()
        venue_pos = line_lower.find(venue_lower)
        at_pos = line_lower.find(" at ")

        if at_pos > 0:
            band_part = line[:at_pos]
        elif venue_pos > 0:
            band_part = line[:venue_pos]
        else:
            band_part = line

        # Clean up
        band_part = re.sub(r'\s*[-–]\s*$', '', band_part)
        band_part = re.sub(r'^\s*[-–]\s*', '', band_part)

        # Remove common prefixes
        band_part = re.sub(r'^(matinee|afternoon|evening):\s*', '', band_part, flags=re.IGNORECASE)

        # Remove metadata patterns that might be mixed in
        band_part = re.sub(r'\b(all ages|21\+|18\+|doors|showat|show at)\b.*$', '', band_part, flags=re.IGNORECASE)
        band_part = re.sub(r'\b\d{1,2}:\d{2}\s*(am|pm)\b.*$', '', band_part, flags=re.IGNORECASE)
        band_part = re.sub(r'\b\d{1,2}\s*(am|pm)\b.*$', '', band_part, flags=re.IGNORECASE)
        band_part = re.sub(r'\$\d+.*$', '', band_part)

        # Split by common separators
        bands = self._split_bands(band_part)

        # Clean each band name
        cleaned = []
        for band in bands:
            band = band.strip()
            # Skip if too short or looks like metadata
            if len(band) < 2:
                continue
            if re.match(r'^(and|with|feat|featuring|plus|\+|&|at|the)$', band, re.IGNORECASE):
                continue
            if re.search(r'^\d+[ap]m$', band, re.IGNORECASE):
                continue
            if re.search(r'^\$\d+', band):
                continue
            if re.search(r'^(all ages|doors|show)$', band, re.IGNORECASE):
                continue
            # Skip if it's just "at The" or similar
            if re.match(r'^(at\s+the|the\s+middle|middle\s+east)$', band, re.IGNORECASE):
                continue
            cleaned.append(band)

        return cleaned
