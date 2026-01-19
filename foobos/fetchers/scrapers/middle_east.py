"""
Scraper for Middle East Club - Cambridge, MA.
https://www.mideastoffers.com/

The Middle East is one of the most important punk/hardcore venues in Boston.
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


class MiddleEastScraper(BaseScraper):
    """Scrape Middle East Club calendar."""

    @property
    def source_name(self) -> str:
        return "scrape:middle_east"

    @property
    def url(self) -> str:
        return "https://www.mideastoffers.com/"

    def fetch(self) -> List[Concert]:
        """Fetch concerts from Middle East."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_middle_east")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []
        try:
            soup = self._get_soup()
            concerts = self._parse_listings(soup)

            # Cache the results
            save_cache("scrape_middle_east", [c.to_dict() for c in concerts])
            self._log_fetch_complete(len(concerts))

        except Exception as e:
            self._log_fetch_error(e)

        return concerts

    def _parse_listings(self, soup: BeautifulSoup) -> List[Concert]:
        """Parse event listings from Middle East website."""
        concerts = []

        # Middle East website structure varies, try multiple selectors
        event_containers = (
            soup.find_all("div", class_=re.compile(r"event|show|listing", re.I)) or
            soup.find_all("article") or
            soup.find_all("li", class_=re.compile(r"event", re.I))
        )

        for container in event_containers:
            concert = self._parse_event(container)
            if concert:
                concerts.append(concert)

        # If no structured events found, try parsing the page text
        if not concerts:
            concerts = self._parse_text_listings(soup)

        return concerts

    def _parse_event(self, container) -> Optional[Concert]:
        """Parse a single event container."""
        try:
            # Get event text content
            text = self._clean_text(container.get_text())
            if len(text) < 10:
                return None

            # Extract title/bands
            title_elem = container.find(["h2", "h3", "h4", "a"])
            if title_elem:
                title = self._clean_text(title_elem.get_text())
            else:
                title = text[:100]

            bands = self._split_bands(title)
            if not bands:
                return None

            # Extract date - look for date patterns
            date = None
            date_elem = container.find(class_=re.compile(r"date", re.I))
            if date_elem:
                date_str = self._clean_text(date_elem.get_text())
                date = parse_date(date_str, default_year=datetime.now().year)

            if not date:
                # Try to find date in text
                date_match = re.search(
                    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2}',
                    text,
                    re.IGNORECASE
                )
                if date_match:
                    date = parse_date(date_match.group(0), default_year=datetime.now().year)

            if not date:
                return None

            # Determine room (Downstairs vs Upstairs)
            room = "Downstairs"  # Default to main room
            text_lower = text.lower()
            if "upstairs" in text_lower or "zuzu" in text_lower:
                room = "Upstairs"
            elif "corner" in text_lower:
                room = "Corner"

            venue_name = f"Middle East {room}"

            # Extract price
            price_match = re.search(r'\$\d+(?:\s*/\s*\$?\d+)?', text)
            price_str = price_match.group(0) if price_match else ""
            price_advance, price_door = self._parse_price(price_str)

            # Extract time
            time_match = re.search(r'\d{1,2}(?::\d{2})?\s*(?:am|pm)', text, re.IGNORECASE)
            time = self._parse_time(time_match.group(0)) if time_match else "8pm"

            # Extract age
            age = "18+"  # Default for Middle East
            if "all ages" in text_lower or "a/a" in text_lower:
                age = "a/a"
            elif "21+" in text or "21 and over" in text_lower:
                age = "21+"

            # Extract link
            link_elem = container.find("a", href=True)
            source_url = None
            if link_elem and link_elem["href"]:
                href = link_elem["href"]
                if href.startswith("http"):
                    source_url = href
                else:
                    source_url = f"https://www.mideastoffers.com{href}"

            return Concert(
                date=date,
                venue_id="middleeast",
                venue_name=venue_name,
                venue_location="Cambridge",
                bands=bands,
                age_requirement=age,
                price_advance=price_advance,
                price_door=price_door,
                time=time,
                flags=["@"],  # Middle East shows often have pits
                source=self.source_name,
                source_url=source_url or self.url,
                genre_tags=[]
            )

        except Exception as e:
            logger.debug(f"Error parsing Middle East event: {e}")
            return None

    def _parse_text_listings(self, soup: BeautifulSoup) -> List[Concert]:
        """Fall back to parsing page as text listings."""
        concerts = []
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        current_date = None

        for line in lines:
            # Try to detect date
            date_match = re.match(
                r'^(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+)?'
                r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2})',
                line,
                re.IGNORECASE
            )

            if date_match:
                current_date = parse_date(date_match.group(1), default_year=datetime.now().year)
                continue

            # If we have a date and the line looks like a show
            if current_date and ("$" in line or "pm" in line.lower()):
                concert = self._parse_text_line(line, current_date)
                if concert:
                    concerts.append(concert)

        return concerts

    def _parse_text_line(self, line: str, date: datetime) -> Optional[Concert]:
        """Parse a text line as a show listing."""
        try:
            # Extract price
            price_match = re.search(r'\$\d+(?:\s*/\s*\$?\d+)?', line)
            price_str = price_match.group(0) if price_match else ""
            price_advance, price_door = self._parse_price(price_str)

            # Extract time
            time_match = re.search(r'\d{1,2}(?::\d{2})?\s*(?:am|pm)', line, re.IGNORECASE)
            time = self._parse_time(time_match.group(0)) if time_match else "8pm"

            # Clean line to get bands
            bands_str = line
            bands_str = re.sub(r'\$\d+(?:\s*/\s*\$?\d+)?', '', bands_str)
            bands_str = re.sub(r'\d{1,2}(?::\d{2})?\s*(?:am|pm)', '', bands_str, flags=re.IGNORECASE)
            bands_str = re.sub(r'(?:all ages|21\+|18\+|a/a)', '', bands_str, flags=re.IGNORECASE)

            bands = self._split_bands(bands_str)
            if not bands:
                return None

            return Concert(
                date=date,
                venue_id="middleeast",
                venue_name="Middle East",
                venue_location="Cambridge",
                bands=bands,
                age_requirement="18+",
                price_advance=price_advance,
                price_door=price_door,
                time=time,
                flags=["@"],
                source=self.source_name,
                source_url=self.url,
                genre_tags=[]
            )

        except Exception as e:
            logger.debug(f"Error parsing text line: {e}")
            return None
