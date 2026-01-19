"""
Scraper for Boston Symphony Orchestra venues.
Covers Symphony Hall, Tanglewood, Boston Pops events.
"""

from datetime import datetime, timedelta
from typing import List, Optional
import logging
import re

from .base import BaseScraper
from ...models import Concert
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)


# BSO brand IDs for filtering
# 12057: BSO, 12058: Tanglewood, 12059: Boston Pops, 12060: Symphony Hall
BSO_EVENTS_URL = "https://www.bso.org/events?view=byevent&brands=12057,12058,12059,12060"


class BSOScraper(BaseScraper):
    """Scrape events from BSO (Boston Symphony Orchestra) venues."""

    @property
    def source_name(self) -> str:
        return "scrape:bso"

    @property
    def url(self) -> str:
        return BSO_EVENTS_URL

    def fetch(self) -> List[Concert]:
        """Fetch concerts from BSO events page."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_bso")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []

        try:
            soup = self._get_soup(self.url)

            # Find all event articles
            events = soup.select('article.event-tease')

            for event in events:
                try:
                    event_concerts = self._parse_event(event)
                    concerts.extend(event_concerts)
                except Exception as e:
                    logger.debug(f"Error parsing BSO event: {e}")

            logger.info(f"[{self.source_name}] Found {len(concerts)} concerts")

        except Exception as e:
            logger.error(f"Error fetching BSO events: {e}")

        # Cache the results
        save_cache("scrape_bso", [c.to_dict() for c in concerts])
        self._log_fetch_complete(len(concerts))

        return concerts

    def _parse_event(self, event_elem) -> List[Concert]:
        """Parse a BSO event element into Concert objects.

        Each event can have multiple performances (dates), so this returns a list.
        """
        concerts = []

        # Get event name
        headline = event_elem.select_one('.event-tease__headline')
        if not headline:
            return concerts
        event_name = self._clean_text(headline.get_text())
        if not event_name:
            return concerts

        # Determine venue from article class
        venue_id, venue_name, venue_location = self._get_venue_from_class(event_elem)

        # Get event link for source URL
        link_elem = event_elem.select_one('a.event-tease__link')
        event_url = link_elem.get('href', '') if link_elem else ''

        # Find all performances (each event can have multiple dates)
        performances = event_elem.select('.event-tease__performance')

        for perf in performances:
            try:
                date = self._extract_performance_date(perf)
                if not date:
                    continue

                # Only include future events within 6 months
                now = datetime.now()
                if date < now or date > now + timedelta(days=180):
                    continue

                time_str = self._extract_performance_time(perf)

                # Parse band/artist from event name
                bands = self._parse_event_name(event_name)

                concerts.append(Concert(
                    date=date,
                    venue_id=venue_id,
                    venue_name=venue_name,
                    venue_location=venue_location,
                    bands=bands,
                    age_requirement="a/a",
                    price_advance=None,
                    price_door=None,
                    time=time_str,
                    flags=[],
                    source=self.source_name,
                    source_url=event_url,
                    genre_tags=["classical", "orchestra"]
                ))

            except Exception as e:
                logger.debug(f"Error parsing BSO performance: {e}")

        return concerts

    def _get_venue_from_class(self, event_elem) -> tuple:
        """Determine venue from event article class."""
        classes = event_elem.get('class', [])
        if isinstance(classes, str):
            classes = classes.split()

        if 'symphonyhall' in classes:
            return ('symphonyhall', 'Symphony Hall', 'Boston')
        elif 'tanglewood' in classes:
            return ('tanglewood', 'Tanglewood', 'Lenox')
        elif 'pops' in classes or 'bostonpops' in classes:
            return ('symphonyhall', 'Symphony Hall', 'Boston')
        elif 'bso' in classes:
            return ('symphonyhall', 'Symphony Hall', 'Boston')
        else:
            return ('symphonyhall', 'Symphony Hall', 'Boston')

    def _extract_performance_date(self, perf_elem) -> Optional[datetime]:
        """Extract date from performance element."""
        date_elem = perf_elem.select_one('.event-tease__performance-date')
        year_elem = perf_elem.select_one('.event-tease__performance-year')

        if not date_elem:
            return None

        date_text = self._clean_text(date_elem.get_text())  # e.g., "Jan 19"
        year_text = self._clean_text(year_elem.get_text()) if year_elem else str(datetime.now().year)

        try:
            # Parse "Jan 19" + "2026"
            date_str = f"{date_text} {year_text}"
            return datetime.strptime(date_str, "%b %d %Y")
        except ValueError:
            return None

    def _extract_performance_time(self, perf_elem) -> str:
        """Extract time from performance element."""
        time_elem = perf_elem.select_one('.event-tease__performance-time')
        if not time_elem:
            return "8pm"

        time_text = self._clean_text(time_elem.get_text())  # e.g., "Mon, 4:00pm"

        # Extract time portion
        match = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm)', time_text, re.IGNORECASE)
        if match:
            hour = match.group(1)
            minute = match.group(2) or "00"
            ampm = match.group(3).lower()
            if minute == "00":
                return f"{hour}{ampm}"
            return f"{hour}:{minute}{ampm}"

        return "8pm"

    def _parse_event_name(self, event_name: str) -> List[str]:
        """Parse artist/performer names from event name.

        BSO events often have formats like:
        - "An All-John Williams Program with Emanuel Ax and Gil Shaham"
        - "Jazz at Lincoln Center Orchestra with Wynton Marsalis"
        - "23rd Annual Dr. Martin Luther King, Jr. Tribute Concert"
        """
        # Return the full event name as the "band"
        # BSO events are often concert series, not individual artists
        return [event_name]
