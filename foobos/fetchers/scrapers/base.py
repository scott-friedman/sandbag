"""
Base scraper class for web scraping concert data.
"""

from abc import abstractmethod
from typing import List
import logging
import re

from bs4 import BeautifulSoup

from ..base import BaseFetcher
from ...models import Concert

logger = logging.getLogger(__name__)


class BaseScraper(BaseFetcher):
    """Abstract base class for web scrapers."""

    @property
    @abstractmethod
    def url(self) -> str:
        """Return the URL to scrape."""
        pass

    def _get_soup(self, url: str = None) -> BeautifulSoup:
        """
        Fetch URL and return BeautifulSoup object.

        Args:
            url: URL to fetch (defaults to self.url)

        Returns:
            BeautifulSoup object
        """
        target_url = url or self.url
        response = self._make_request(target_url)
        return BeautifulSoup(response.text, "lxml")

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        if not text:
            return ""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _parse_price(self, price_str: str) -> tuple:
        """
        Parse price string into (advance, door) tuple.

        Handles formats like:
        - "$20"
        - "$15-$20"
        - "$15/$20"
        - "$15 adv / $20 door"
        - "Free"
        """
        if not price_str:
            return (None, None)

        price_str = price_str.lower().strip()

        if "free" in price_str:
            return (0, 0)

        # Find all dollar amounts
        amounts = re.findall(r'\$?(\d+(?:\.\d{2})?)', price_str)
        amounts = [int(float(a)) for a in amounts]

        if len(amounts) >= 2:
            return (amounts[0], amounts[1])
        elif len(amounts) == 1:
            return (amounts[0], amounts[0])
        return (None, None)

    def _parse_time(self, time_str: str) -> str:
        """
        Parse time string into normalized format.

        Handles formats like:
        - "8:00 PM"
        - "8pm"
        - "20:00"
        - "Doors 7pm / Show 8pm"
        """
        if not time_str:
            return "8pm"

        time_str = time_str.lower().strip()

        # Try to find time pattern
        match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', time_str)
        if match:
            hour = int(match.group(1))
            ampm = match.group(3)

            # Convert 24-hour to 12-hour if needed
            if hour > 12:
                hour -= 12
                ampm = "pm"
            elif hour == 12:
                ampm = ampm or "pm"
            elif hour == 0:
                hour = 12
                ampm = "am"
            else:
                ampm = ampm or ("pm" if hour < 7 else "pm")  # Assume PM for typical show times

            return f"{hour}{ampm}"

        return "8pm"

    def _parse_age(self, age_str: str) -> str:
        """
        Parse age requirement string.

        Handles formats like:
        - "All Ages"
        - "21+"
        - "18 and over"
        - "AA"
        """
        if not age_str:
            return "a/a"

        age_str = age_str.lower().strip()

        if "all age" in age_str or "aa" == age_str or "a/a" in age_str:
            return "a/a"
        if "21" in age_str:
            return "21+"
        if "18" in age_str:
            return "18+"

        return "a/a"

    def _is_free_text(self, text: str) -> bool:
        """Check if text indicates a free event."""
        if not text:
            return False
        text_lower = text.lower()
        return any(p in text_lower for p in ['free', 'no cover', 'donation', 'pwyc'])

    def _split_bands(self, bands_str: str) -> List[str]:
        """
        Split band string into list of band names.

        Handles formats like:
        - "Band A, Band B, Band C"
        - "Band A / Band B / Band C"
        - "Band A w/ Band B and Band C"
        - "Band A + Band B"
        """
        if not bands_str:
            return []

        # Normalize separators
        bands_str = bands_str.replace(" w/ ", ", ")
        bands_str = bands_str.replace(" with ", ", ")
        bands_str = bands_str.replace(" and ", ", ")
        bands_str = bands_str.replace(" + ", ", ")
        bands_str = bands_str.replace(" / ", ", ")
        bands_str = bands_str.replace(" | ", ", ")

        # Split and clean
        bands = [self._clean_text(b) for b in bands_str.split(",")]
        bands = [b for b in bands if b and len(b) > 1]

        return bands
