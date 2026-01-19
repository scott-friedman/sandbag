"""
Scraper for Boston Groupie News punk/rock concert listings.

Boston Groupie News (bostongroupienews.com) is a long-running Boston
punk/rock scene blog with comprehensive show listings including:
- Middle East (Downstairs, Upstairs, Corner)
- O'Brien's Pub
- Deep Cuts
- Sonia
- Various DIY venues

Data format (HTML):
- Dates in bold: **January 24, 2026 (Saturday)**
- Band names in bold: **Band1, Band2, Band3**
- Venues after "at" or with dash: "at O'Brien's" or "- Middle East UP"
- Age/price/time info in plain text
"""

from datetime import datetime
from typing import List, Optional, Tuple
import logging
import re

from bs4 import BeautifulSoup, NavigableString

from .base import BaseScraper
from ...models import Concert
from ...utils import get_cached, save_cache, parse_date

logger = logging.getLogger(__name__)


# Map venue names to standardized IDs
VENUE_PATTERNS = {
    "middle east down": {"id": "middleeast_down", "name": "Middle East Downstairs", "location": "Cambridge"},
    "middle east up": {"id": "middleeast_up", "name": "Middle East Upstairs", "location": "Cambridge"},
    "middle east corner": {"id": "middleeast_corner", "name": "Middle East Corner", "location": "Cambridge"},
    "the middle east": {"id": "middleeast", "name": "Middle East", "location": "Cambridge"},
    "middle east": {"id": "middleeast", "name": "Middle East", "location": "Cambridge"},
    "o'brien's": {"id": "obriens", "name": "O'Brien's Pub", "location": "Allston"},
    "obriens": {"id": "obriens", "name": "O'Brien's Pub", "location": "Allston"},
    "o'briens": {"id": "obriens", "name": "O'Brien's Pub", "location": "Allston"},
    "sonia": {"id": "sonia", "name": "Sonia", "location": "Cambridge"},
    "deep cuts": {"id": "deepcuts", "name": "Deep Cuts", "location": "Medford"},
    "midway cafe": {"id": "midway", "name": "Midway Cafe", "location": "Jamaica Plain"},
    "midway": {"id": "midway", "name": "Midway Cafe", "location": "Jamaica Plain"},
    "once": {"id": "once", "name": "ONCE Ballroom", "location": "Somerville"},
    "crystal ballroom": {"id": "crystal", "name": "Crystal Ballroom", "location": "Somerville"},
    "paradise rock": {"id": "paradise", "name": "Paradise Rock Club", "location": "Boston"},
    "paradise": {"id": "paradise", "name": "Paradise Rock Club", "location": "Boston"},
    "brighton music": {"id": "brighton", "name": "Brighton Music Hall", "location": "Allston"},
    "sinclair": {"id": "sinclair", "name": "The Sinclair", "location": "Cambridge"},
    "house of blues": {"id": "hob", "name": "House of Blues", "location": "Boston"},
    "royale": {"id": "royale", "name": "Royale", "location": "Boston"},
    "roadrunner": {"id": "roadrunner", "name": "Roadrunner", "location": "Boston"},
    "big night live": {"id": "bignightlive", "name": "Big Night Live", "location": "Boston"},
    "crystal ballroom somerville": {"id": "crystal", "name": "Crystal Ballroom", "location": "Somerville"},
    "elks lodge": {"id": "elks", "name": "Elks Lodge", "location": "Cambridge"},
    "lizard lounge": {"id": "lizard", "name": "Lizard Lounge", "location": "Cambridge"},
    "ralph's diner": {"id": "ralphs", "name": "Ralph's Diner", "location": "Worcester"},
    "ralphs": {"id": "ralphs", "name": "Ralph's Diner", "location": "Worcester"},
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
        """Parse concert listings from the page using HTML structure."""
        concerts = []
        current_date = None

        # Find all bold/strong elements - these contain dates and band names
        body = soup.find("body")
        if not body:
            return concerts

        # Process elements in order to maintain context
        for element in body.descendants:
            if isinstance(element, NavigableString):
                continue

            # Check for bold elements (b, strong)
            if element.name in ["b", "strong"]:
                text = element.get_text().strip()
                if not text:
                    continue

                # Check if this is a date
                date_match = re.match(
                    r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s*(\d{4})?\s*\(?(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?\)?',
                    text,
                    re.IGNORECASE
                )
                if date_match:
                    month = date_match.group(1)
                    day = date_match.group(2)
                    year = date_match.group(3) or str(datetime.now().year)
                    current_date = parse_date(f"{month} {day}, {year}")
                    continue

                # Skip if no current date or date is in the past
                if not current_date or current_date.date() < datetime.now().date():
                    continue

                # This might be band names - get context from surrounding text
                concert = self._parse_show_element(element, text, current_date)
                if concert:
                    concerts.append(concert)

        return concerts

    def _parse_show_element(self, element, band_text: str, date: datetime) -> Optional[Concert]:
        """Parse a show from a bold element and its context."""
        # Get the full context including text after the bold element
        context = self._get_element_context(element)
        if not context:
            return None

        # Skip if this looks like a date or header
        if re.match(r'^(January|February|March|April|May|June|July|August|September|October|November|December)', band_text, re.IGNORECASE):
            return None

        # Extract venue from context
        venue_info = self._extract_venue(context)
        if not venue_info:
            return None

        # Extract bands from the bold text
        bands = self._extract_bands(band_text)
        if not bands:
            return None

        # Extract age requirement from context
        age_req = self._extract_age(context)

        # Extract price from context
        price = self._extract_price(context)

        # Extract time from context
        show_time = self._extract_time(context)

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

    def _get_element_context(self, element) -> str:
        """Get the text context around an element (including siblings)."""
        parts = [element.get_text()]

        # Get text from following siblings until next bold or line break
        for sibling in element.next_siblings:
            if isinstance(sibling, NavigableString):
                parts.append(str(sibling))
            elif sibling.name in ["b", "strong", "br", "p", "div"]:
                break
            elif sibling.name == "a":
                # Include link text but stop after
                parts.append(sibling.get_text())
            else:
                parts.append(sibling.get_text())

        return " ".join(parts)

    def _extract_venue(self, text: str) -> Optional[dict]:
        """Extract venue from text."""
        text_lower = text.lower()

        # Check for known venue patterns
        for pattern, venue_info in VENUE_PATTERNS.items():
            if pattern in text_lower:
                return venue_info

        # Check for "at [Venue]" pattern - more specific matching
        at_match = re.search(
            r'\bat\s+(?:the\s+)?([A-Z][A-Za-z\'\-\s]+?)(?:\s*[-–•]|\s+\d|\s+doors|\s+all\s+ages|\s+18\+|\s+21\+|\s*$)',
            text,
            re.IGNORECASE
        )
        if at_match:
            venue_name = at_match.group(1).strip()
            # Skip if venue name is too short or looks like metadata
            if len(venue_name) < 3 or venue_name.lower() in ["the", "a", "an"]:
                return None
            venue_id = re.sub(r'[^a-z0-9]+', '_', venue_name.lower()).strip('_')
            return {"id": venue_id, "name": venue_name, "location": "Boston"}

        # Check for "- [Venue]" pattern
        dash_match = re.search(
            r'[-–]\s*([A-Z][A-Za-z\'\-\s]+?)(?:\s*[-–]|\s+\d|\s+doors|\s+all\s+ages|\s+18\+|\s+21\+|\s*$)',
            text
        )
        if dash_match:
            venue_name = dash_match.group(1).strip()
            if len(venue_name) >= 3:
                venue_id = re.sub(r'[^a-z0-9]+', '_', venue_name.lower()).strip('_')
                return {"id": venue_id, "name": venue_name, "location": "Boston"}

        return None

    def _extract_bands(self, text: str) -> List[str]:
        """Extract band names from bold text."""
        # Remove "with" prefix if present
        text = re.sub(r'^with\s+', '', text, flags=re.IGNORECASE)

        # Split by common separators
        bands = self._split_bands(text)

        # Clean each band name
        cleaned = []
        for band in bands:
            band = band.strip()

            # Skip if too short
            if len(band) < 2:
                continue

            # Skip common words that aren't band names
            skip_words = [
                "and", "with", "feat", "featuring", "plus", "at", "the",
                "all ages", "doors", "show", "pm", "am", "tix", "tickets",
                "fb", "event", "page", "link", "more", "info"
            ]
            if band.lower() in skip_words:
                continue

            # Skip if it looks like metadata
            if re.match(r'^\d+[ap]m$', band, re.IGNORECASE):
                continue
            if re.match(r'^\$\d+', band):
                continue
            if re.match(r'^(18|21)\+$', band):
                continue

            # Skip venue-like patterns
            if re.match(r'^at\s+', band, re.IGNORECASE):
                continue

            cleaned.append(band)

        return cleaned

    def _extract_age(self, text: str) -> str:
        """Extract age requirement from text."""
        text_lower = text.lower()
        if "21+" in text_lower or "21 +" in text_lower or "21 and over" in text_lower:
            return "21+"
        elif "18+" in text_lower or "18 +" in text_lower or "18 and over" in text_lower:
            return "18+"
        elif "all ages" in text_lower:
            return "a/a"
        return "a/a"

    def _extract_price(self, text: str) -> Optional[int]:
        """Extract price from text."""
        price_match = re.search(r'\$(\d+)', text)
        return int(price_match.group(1)) if price_match else None

    def _extract_time(self, text: str) -> str:
        """Extract time from text."""
        # Look for time patterns like "7PM", "7:00 PM", "doors 8pm"
        time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm|AM|PM)', text)
        if time_match:
            hour = time_match.group(1)
            minutes = time_match.group(2) or "00"
            ampm = time_match.group(3).lower()
            if minutes == "00":
                return f"{hour}{ampm}"
            else:
                return f"{hour}:{minutes}{ampm}"
        return "8pm"
