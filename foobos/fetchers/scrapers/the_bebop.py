"""
Scraper for The Bebop Boston events.
https://www.thebebopboston.com/new-events
"""

from datetime import datetime
from typing import List
import logging
import re

from .base import BaseScraper
from ...models import Concert
from ...config import WEEKS_AHEAD
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)

BEBOP_URL = "https://www.thebebopboston.com/new-events"


class TheBebopScraper(BaseScraper):
    """Scraper for The Bebop in Boston's South End."""

    source_name = "the_bebop"

    @property
    def url(self) -> str:
        return BEBOP_URL

    def fetch(self) -> List[Concert]:
        """Fetch concerts from The Bebop."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_the_bebop")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        all_concerts = []

        # Fetch multiple months based on WEEKS_AHEAD config
        now = datetime.now()
        months_ahead = (WEEKS_AHEAD // 4) + 1

        for month_offset in range(months_ahead):
            target_month = now.month + month_offset
            target_year = now.year
            while target_month > 12:
                target_month -= 12
                target_year += 1

            try:
                url = f"{BEBOP_URL}?view=calendar&month={target_month:02d}-{target_year}"
                soup = self._get_soup(url)
                concerts = self._parse_events(soup)
                all_concerts.extend(concerts)
            except Exception as e:
                logger.warning(f"[{self.source_name}] Error fetching {target_month:02d}-{target_year}: {e}")

        # Deduplicate by date + bands
        seen = set()
        unique_concerts = []
        for c in all_concerts:
            key = f"{c.date.strftime('%Y-%m-%d')}-{'-'.join(c.bands)}"
            if key not in seen:
                seen.add(key)
                unique_concerts.append(c)

        # Cache the results
        save_cache("scrape_the_bebop", [c.to_dict() for c in unique_concerts])
        self._log_fetch_complete(len(unique_concerts))

        return unique_concerts

    def _parse_events(self, soup) -> List[Concert]:
        """Parse events from the Squarespace events page."""
        concerts = []

        # Get all text with separator to preserve structure
        all_text = soup.get_text(separator='\n', strip=True)
        lines = [l.strip() for l in all_text.split('\n') if l.strip()]

        # Skip patterns for venue info - these are exact matches or line starts
        skip_exact = ['the bebop', 'google maps', 'view map', 'add to calendar']
        skip_contains = ['boylston', 'boston, ma', 'united states']

        i = 0
        while i < len(lines):
            line = lines[i]

            # Look for date patterns like "Saturday, January 31, 2026, 10:30 PM – 11:59 PM"
            date_match = re.match(
                r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),\s+'
                r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),\s+(\d{4})',
                line
            )

            if date_match:
                month = date_match.group(2)
                day = int(date_match.group(3))
                year = int(date_match.group(4))

                # Extract time from the same line
                time_match = re.search(r'(\d{1,2}:\d{2})\s*(AM|PM)', line, re.I)
                time_str = "10pm"
                if time_match:
                    hour_min = time_match.group(1)
                    ampm = time_match.group(2).lower()
                    time_str = f"{hour_min}{ampm}"

                # Parse the date
                try:
                    months = {
                        'january': 1, 'february': 2, 'march': 3, 'april': 4,
                        'may': 5, 'june': 6, 'july': 7, 'august': 8,
                        'september': 9, 'october': 10, 'november': 11, 'december': 12
                    }
                    month_num = months.get(month.lower())
                    if month_num:
                        date = datetime(year, month_num, day)
                    else:
                        i += 1
                        continue
                except ValueError:
                    i += 1
                    continue

                # Look for event title in PRECEDING lines (title comes before date on this site)
                title = None
                j = i - 1
                while j >= 0 and j > i - 5:
                    candidate = lines[j].strip()
                    candidate_lower = candidate.lower()

                    # Skip empty lines
                    if not candidate:
                        j -= 1
                        continue

                    # Skip exact venue info matches (e.g., "The Bebop" by itself)
                    if candidate_lower in skip_exact:
                        j -= 1
                        continue

                    # Skip lines containing address/location info
                    if any(p in candidate_lower for p in skip_contains):
                        j -= 1
                        continue

                    # Skip if it looks like another date/time line
                    if re.match(r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),', candidate):
                        break

                    # Skip pure numbers (like addresses) or short strings
                    if re.match(r'^\d+$', candidate) or len(candidate) <= 2:
                        j -= 1
                        continue

                    # This is likely the title
                    title = candidate
                    break

                if title and len(title) > 2:
                    # Clean up title - remove common suffixes
                    title = re.sub(r'\s*-\s*Tickets?\s*$', '', title, flags=re.I)
                    title = re.sub(r'\s*\|\s*The Bebop\s*$', '', title, flags=re.I)
                    title = re.sub(r'\s+at The Bebop!?\s*$', '', title, flags=re.I)

                    bands = self._split_bands(title)
                    if not bands:
                        bands = [title]

                    concert = Concert(
                        date=date,
                        venue_id="bebop",
                        venue_name="The Bebop",
                        venue_location="Boston",
                        bands=bands,
                        age_requirement="21+",
                        price_advance=None,
                        price_door=None,
                        time=time_str,
                        flags=[],
                        source=self.source_name,
                        source_url=BEBOP_URL,
                        genre_tags=["jazz", "soul", "funk"]
                    )
                    concerts.append(concert)

            i += 1

        return concerts
