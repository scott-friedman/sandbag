"""
Scraper for Safe In A Crowd - Massachusetts hardcore/punk show listings.
https://safeinacrowd.com/

This is the most important scraper for DIY/hardcore shows that don't appear
on ticketing platforms.
"""

from datetime import datetime
from typing import List, Optional, Tuple
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
        """Parse show listings from the page.

        Format: <p><strong>DATE:</strong> BANDS at VENUE in LOCATION TIME/PRICE[/AGE]</p>
        Example: <strong>Friday, January 16th:</strong> Who Remembers, Goin' Ape at Pyxis in Providence, RI 7:00pm/$10
        """
        concerts = []
        current_year = datetime.now().year

        # Find the entry-content div
        content = soup.find("div", class_="entry-content")
        if not content:
            content = soup.find("main") or soup.body

        if not content:
            logger.warning("Could not find content area")
            return concerts

        # Find all paragraph tags with show listings
        for p in content.find_all("p"):
            # Look for paragraphs with a strong tag containing a date
            strong = p.find("strong")
            if not strong:
                continue

            strong_text = strong.get_text().strip()

            # Check if this looks like a date line
            # Format: "Friday, January 16th:" or "Sunday, February 8th:"
            date_match = re.match(
                r'^(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+'
                r'((?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2})(?:st|nd|rd|th)?:?',
                strong_text,
                re.IGNORECASE
            )

            if not date_match:
                continue

            # Parse the date
            date_str = date_match.group(1)
            show_date = parse_date(date_str, default_year=current_year)
            if not show_date:
                continue

            # Get the full text of the paragraph (excluding the strong tag content)
            full_text = p.get_text().strip()
            # Remove the date portion
            show_text = full_text[len(strong_text):].strip()

            if not show_text:
                continue

            # Parse the show listing
            concert = self._parse_show_text(show_text, show_date)
            if concert:
                concerts.append(concert)

        return concerts

    def _parse_show_text(self, text: str, date: datetime) -> Optional[Concert]:
        """Parse a show listing text.

        Format: BANDS at VENUE in LOCATION TIME/PRICE[/AGE]
        Example: Who Remembers, Goin' Ape, Through And Through at Pyxis in Providence, RI 7:00pm/$10
        """
        try:
            # Pattern: "BANDS at VENUE in LOCATION TIME/PRICE[/AGE][/NOTES]"
            # We need to find " at " to split bands from venue info

            at_match = re.search(r'\s+at\s+', text, re.IGNORECASE)
            if not at_match:
                return None

            bands_str = text[:at_match.start()].strip()
            venue_info = text[at_match.end():].strip()

            # Parse venue info: "VENUE in LOCATION TIME/PRICE[/AGE]"
            # Look for " in " to separate venue name from location
            in_match = re.search(r'\s+in\s+', venue_info, re.IGNORECASE)
            if not in_match:
                return None

            venue_name = venue_info[:in_match.start()].strip()
            location_info = venue_info[in_match.end():].strip()

            # Parse location info: "LOCATION TIME/PRICE[/AGE]"
            # Location is typically "City, STATE" followed by time
            # Time format: 7:00pm or 7pm
            time_match = re.search(r'(\d{1,2}(?::\d{2})?\s*(?:am|pm))', location_info, re.IGNORECASE)

            if time_match:
                location_str = location_info[:time_match.start()].strip()
                rest = location_info[time_match.start():].strip()
                time_str = time_match.group(1)
            else:
                location_str = location_info
                rest = ""
                time_str = "8pm"

            # Clean up location (remove trailing comma)
            location_str = location_str.rstrip(',').strip()

            # Extract price from rest
            price_match = re.search(r'\$(\d+)(?:\s*/\s*\$?(\d+))?', rest)
            price_advance = None
            price_door = None
            if price_match:
                price_advance = int(price_match.group(1))
                if price_match.group(2):
                    price_door = int(price_match.group(2))
                else:
                    price_door = price_advance

            # Check for FREE
            if 'FREE' in rest.upper():
                price_advance = 0
                price_door = 0

            # Check for SOLD OUT
            sold_out = 'SOLD OUT' in rest.upper()

            # Extract age requirement
            age = "a/a"  # Default all ages
            if '21+' in rest:
                age = "21+"
            elif '18+' in rest:
                age = "18+"
            elif '16+' in rest:
                age = "16+"

            # Split bands
            bands = self._split_bands(bands_str)
            if not bands:
                return None

            # Generate venue ID
            venue_id = self._generate_venue_id(venue_name)

            # Parse time
            time = self._parse_time(time_str)

            # Build flags
            flags = ["@"]  # Assume mosh for hardcore shows
            if sold_out:
                flags.append("SOLD OUT")

            return Concert(
                date=date,
                venue_id=venue_id,
                venue_name=venue_name,
                venue_location=location_str,
                bands=bands,
                age_requirement=age,
                price_advance=price_advance,
                price_door=price_door,
                time=time,
                flags=flags,
                source=self.source_name,
                source_url=self.url,
                genre_tags=["hardcore", "punk"]
            )

        except Exception as e:
            logger.debug(f"Error parsing show text '{text}': {e}")
            return None

    def _generate_venue_id(self, venue_name: str) -> str:
        """Generate a venue ID slug from name."""
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
            "sonia": "sonia",
            "roadrunner": "roadrunner",
            "big night": "bignightlive",
            "rockwell": "rockwell",
            "deep cuts": "deepcuts",
            "lizard lounge": "lizardlounge",
        }

        for pattern, slug in venue_map.items():
            if pattern in name_lower:
                return slug

        # Fall back to slugifying
        slug = name_lower.replace("'", "").replace(".", "").replace(",", "")
        slug = "_".join(slug.split())
        return slug[:30]
