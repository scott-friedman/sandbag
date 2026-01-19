"""
Scraper for Safe In A Crowd - Massachusetts hardcore/punk show listings.
https://safeinacrowd.com/

This is the most important scraper for DIY/hardcore shows that don't appear
on ticketing platforms.
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


class SafeInACrowdScraper(BaseScraper):
    """Scrape Safe In A Crowd for MA hardcore/punk shows."""

    @property
    def source_name(self) -> str:
        return "scrape:safe_in_a_crowd"

    @property
    def url(self) -> str:
        return "https://safeinacrowd.com/"

    def fetch(self) -> List[Concert]:
        """Fetch concerts from Safe In A Crowd."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_safe_in_a_crowd")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []
        try:
            soup = self._get_soup()
            concerts = self._parse_listings(soup)

            # Cache the results
            save_cache("scrape_safe_in_a_crowd", [c.to_dict() for c in concerts])
            self._log_fetch_complete(len(concerts))

        except Exception as e:
            self._log_fetch_error(e)

        return concerts

    def _parse_listings(self, soup: BeautifulSoup) -> List[Concert]:
        """Parse show listings from the page."""
        concerts = []
        current_year = datetime.now().year

        # Safe In A Crowd typically has a simple text-based format
        # Look for the main content area
        content = soup.find("div", class_="content") or soup.find("main") or soup.body

        if not content:
            logger.warning("Could not find content area")
            return concerts

        # Get all text and try to parse show listings
        # Format is typically: DATE - VENUE - BANDS - PRICE/TIME/AGE
        text = content.get_text(separator="\n")
        lines = [line.strip() for line in text.split("\n") if line.strip()]

        current_date = None

        for line in lines:
            # Try to detect date lines
            date_match = re.match(
                r'^(?:(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)[a-z]*,?\s+)?'
                r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2})',
                line,
                re.IGNORECASE
            )

            if date_match:
                date_str = date_match.group(1)
                current_date = parse_date(date_str, default_year=current_year)
                continue

            # Try to parse as a show listing
            if current_date and self._looks_like_show(line):
                concert = self._parse_show_line(line, current_date)
                if concert:
                    concerts.append(concert)

        return concerts

    def _looks_like_show(self, line: str) -> bool:
        """Check if a line looks like a show listing."""
        # Shows typically have venue indicators or price indicators
        indicators = ["@", "$", "pm", "all ages", "21+", "18+", "a/a"]
        line_lower = line.lower()
        return any(ind in line_lower for ind in indicators)

    def _parse_show_line(self, line: str, date: datetime) -> Optional[Concert]:
        """Parse a single show listing line."""
        try:
            # Common format: "BANDS @ VENUE $PRICE TIME AGE"
            # Or: "VENUE: BANDS - $PRICE TIME"

            # Try to extract venue (often after @ or before :)
            venue_name = "Unknown Venue"
            venue_location = "Boston"
            bands_str = line

            if "@" in line:
                parts = line.split("@", 1)
                bands_str = parts[0].strip()
                venue_part = parts[1].strip()
                # Venue name is usually first part before price/time
                venue_match = re.match(r'^([^$\d]+)', venue_part)
                if venue_match:
                    venue_name = self._clean_text(venue_match.group(1))

            elif ":" in line and not re.match(r'^\d+:', line):
                parts = line.split(":", 1)
                venue_name = self._clean_text(parts[0])
                bands_str = parts[1].strip()

            # Extract price
            price_match = re.search(r'\$\d+(?:\s*/\s*\$?\d+)?', line)
            price_str = price_match.group(0) if price_match else ""
            price_advance, price_door = self._parse_price(price_str)

            # Extract time
            time_match = re.search(r'\d{1,2}(?::\d{2})?\s*(?:am|pm)', line, re.IGNORECASE)
            time = self._parse_time(time_match.group(0)) if time_match else "8pm"

            # Extract age
            age = "a/a"  # Default for hardcore shows
            if "21+" in line or "21 and over" in line.lower():
                age = "21+"
            elif "18+" in line or "18 and over" in line.lower():
                age = "18+"

            # Clean bands string (remove price/time/age info)
            bands_str = re.sub(r'\$\d+(?:\s*/\s*\$?\d+)?', '', bands_str)
            bands_str = re.sub(r'\d{1,2}(?::\d{2})?\s*(?:am|pm)', '', bands_str, flags=re.IGNORECASE)
            bands_str = re.sub(r'(?:all ages|21\+|18\+|a/a)', '', bands_str, flags=re.IGNORECASE)

            bands = self._split_bands(bands_str)
            if not bands:
                return None

            # Generate venue ID from name
            venue_id = self._generate_venue_id(venue_name)

            return Concert(
                date=date,
                venue_id=venue_id,
                venue_name=venue_name,
                venue_location=venue_location,
                bands=bands,
                age_requirement=age,
                price_advance=price_advance,
                price_door=price_door,
                time=time,
                flags=["@"],  # Assume mosh for hardcore shows
                source=self.source_name,
                source_url=self.url,
                genre_tags=["hardcore", "punk"]
            )

        except Exception as e:
            logger.debug(f"Error parsing line '{line}': {e}")
            return None

    def _generate_venue_id(self, venue_name: str) -> str:
        """Generate a venue ID slug from name."""
        # Map common venue names
        name_lower = venue_name.lower()

        venue_map = {
            "middle east": "middleeast",
            "paradise": "paradise",
            "sinclair": "sinclair",
            "great scott": "greatscott",
            "brighton music": "brighton",
            "house of blues": "hob",
            "royale": "royale",
            "elks": "elks",
            "vfw": "vfw",
            "american legion": "legion",
            "midway": "midway",
            "o'brien": "obriens",
        }

        for pattern, slug in venue_map.items():
            if pattern in name_lower:
                return slug

        # Fall back to slugifying
        slug = name_lower.replace("'", "").replace(".", "").replace(",", "")
        slug = "_".join(slug.split())
        return slug[:30]
