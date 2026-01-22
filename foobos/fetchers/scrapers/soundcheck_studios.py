"""
Scraper for Soundcheck Studios events.
https://www.soundcheck-studios.com/shows
"""

from datetime import datetime
from typing import List
import logging
import re

from dateutil import parser as date_parser

from .base import BaseScraper
from ...models import Concert
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)

SOUNDCHECK_URL = "https://www.soundcheck-studios.com/shows"


class SoundcheckStudiosScraper(BaseScraper):
    """Scraper for Soundcheck Studios in Pemberton, MA."""

    source_name = "soundcheck_studios"

    def __init__(self):
        super().__init__()
        # Use standard browser User-Agent (site blocks bot-like agents)
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    @property
    def url(self) -> str:
        return SOUNDCHECK_URL

    def fetch(self) -> List[Concert]:
        """Fetch concerts from Soundcheck Studios."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_soundcheck_studios")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        try:
            soup = self._get_soup()
            concerts = self._parse_events(soup)
        except Exception as e:
            logger.error(f"Failed to fetch Soundcheck Studios events: {e}")
            return []

        # Cache the results
        save_cache("scrape_soundcheck_studios", [c.to_dict() for c in concerts])
        self._log_fetch_complete(len(concerts))

        return concerts

    def _parse_events(self, soup) -> List[Concert]:
        """Parse events from the Soundcheck Studios page.

        The page uses hidden .ec-col-item elements containing event data:
        - .title: Artist/event name
        - .start-date: Date (e.g., "April 3, 2026")
        - .webflow-link: Link to event detail page
        """
        concerts = []

        # Find all event containers
        event_items = soup.select('.ec-col-item')

        for item in event_items:
            try:
                # Extract title/artist
                title_elem = item.select_one('.title')
                if not title_elem:
                    continue
                title = self._clean_text(title_elem.get_text())
                if not title:
                    continue

                # Extract date
                date_elem = item.select_one('.start-date')
                if not date_elem:
                    continue
                date_str = self._clean_text(date_elem.get_text())
                if not date_str:
                    continue

                # Parse date (handles various formats like "April 3, 2026")
                try:
                    date = date_parser.parse(date_str)
                except (ValueError, TypeError):
                    logger.debug(f"Could not parse date: {date_str}")
                    continue

                # Extract event link if available
                link_elem = item.select_one('.webflow-link')
                event_url = None
                if link_elem and link_elem.get('href'):
                    href = link_elem.get('href')
                    if href.startswith('/'):
                        event_url = f"https://www.soundcheck-studios.com{href}"
                    elif href.startswith('http'):
                        event_url = href

                # Parse bands from title
                bands = self._parse_title(title)
                if not bands:
                    bands = [title]

                concert = Concert(
                    date=date,
                    venue_id="soundcheck_studios",
                    venue_name="Soundcheck Studios",
                    venue_location="Pemberton",
                    bands=bands,
                    age_requirement="a/a",
                    price_advance=None,
                    price_door=None,
                    time="8pm",
                    flags=[],
                    source=self.source_name,
                    source_url=event_url or SOUNDCHECK_URL,
                    genre_tags=[]
                )
                concerts.append(concert)

            except Exception as e:
                logger.debug(f"Error parsing event item: {e}")
                continue

        return concerts

    def _parse_title(self, title: str) -> List[str]:
        """Parse event title to extract band names.

        Handles various formats:
        - "Band Name" (single artist)
        - "Band A w/ Band B" (headliner with support)
        - "Artist Name (Tribute to X)" (tribute bands)
        """
        if not title:
            return []

        # Check for tribute/cover band indicators and keep as single entity
        tribute_patterns = [
            r'\(.*tribute.*\)',
            r'\(.*cover.*\)',
            r'tribute to',
            r'tribute band',
        ]
        for pattern in tribute_patterns:
            if re.search(pattern, title, re.IGNORECASE):
                return [title]

        # Use base class band splitting for standard formats
        bands = self._split_bands(title)
        return bands if bands else [title]
