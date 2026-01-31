"""
Scraper for venues that provide iCal feeds.
Currently supports: Lizard Lounge, The Rockwell, Firehouse Center
"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple
import logging
import re
import requests

from .base import BaseScraper
from ...models import Concert
from ...config import WEEKS_AHEAD
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)


# Venues with iCal feeds
# For monthly_url venues, we iterate over multiple months to get all events
# skip_patterns: regex patterns to filter out non-music events
ICAL_VENUES = [
    {
        "name": "Lizard Lounge",
        "id": "lizardlounge",
        "location": "Cambridge",
        "url": "https://lizardloungeclub.com/events/?ical=1",
        "monthly_url": "https://lizardloungeclub.com/events/month/{year}-{month:02d}/?ical=1",
        "age": "21+",
    },
    {
        "name": "The Rockwell",
        "id": "rockwell",
        "location": "Somerville",
        "url": "https://therockwell.org/calendar/?ical=1",
        "age": "a/a",
    },
    {
        "name": "Firehouse Center for the Arts",
        "id": "firehouse",
        "location": "Newburyport",
        "state": "MA",
        "url": "https://firehouse.org/events/?ical=1",
        "age": "a/a",
        # Filter out non-music events (theater, film, dance, etc.)
        "skip_patterns": [
            r"film series",
            r"murder mystery",
            r"junie b",
            r"kids? show",
            r"children'?s",
            r"story ?time",
            r"book club",
            r"art exhibit",
            r"gallery",
            r"workshop",
            r"class\b",
            r"lecture",
            r"talk\b",
            r"dance company",
            r"ballet",
        ],
    },
]


class ICalVenuesScraper(BaseScraper):
    """Scrape events from venues with iCal feeds."""

    @property
    def source_name(self) -> str:
        return "scrape:ical_venues"

    @property
    def url(self) -> str:
        return "https://lizardloungeclub.com/"  # Primary source

    def fetch(self) -> List[Concert]:
        """Fetch concerts from all iCal venues."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_ical_venues")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        all_concerts = []

        for venue in ICAL_VENUES:
            try:
                concerts = self._fetch_venue_ical(venue)
                logger.info(f"[{self.source_name}] {venue['name']}: {len(concerts)} events")
                all_concerts.extend(concerts)
            except Exception as e:
                logger.warning(f"[{self.source_name}] Error fetching {venue['name']}: {e}")

        # Cache the results
        save_cache("scrape_ical_venues", [c.to_dict() for c in all_concerts])
        self._log_fetch_complete(len(all_concerts))

        return all_concerts

    def _fetch_venue_ical(self, venue: dict) -> List[Concert]:
        """Fetch and parse iCal data for a venue."""
        concerts = []
        seen_events = set()  # Track seen events to avoid duplicates

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        # Determine URLs to fetch
        urls_to_fetch = []

        if "monthly_url" in venue:
            # Fetch multiple months based on WEEKS_AHEAD config
            now = datetime.now()
            months_ahead = (WEEKS_AHEAD // 4) + 1
            for month_offset in range(months_ahead):
                target_date = now + timedelta(days=month_offset * 30)
                url = venue["monthly_url"].format(
                    year=target_date.year,
                    month=target_date.month
                )
                urls_to_fetch.append(url)
        else:
            # Just fetch the single URL
            urls_to_fetch.append(venue["url"])

        for url in urls_to_fetch:
            try:
                response = requests.get(url, timeout=30, headers=headers)
                response.raise_for_status()
                ical_text = response.text

                events = self._parse_ical(ical_text)

                for event in events:
                    # Skip non-music events or placeholder events
                    if self._should_skip_event(event, venue):
                        continue

                    # Create unique key to avoid duplicates across months
                    event_key = f"{event.get('DTSTART', '')}-{event.get('SUMMARY', '')}"
                    if event_key in seen_events:
                        continue
                    seen_events.add(event_key)

                    concert = self._event_to_concert(event, venue)
                    if concert:
                        concerts.append(concert)

            except Exception as e:
                logger.debug(f"Error fetching iCal from {url}: {e}")

        return concerts

    def _parse_ical(self, ical_text: str) -> List[dict]:
        """Parse iCal text into a list of event dictionaries."""
        events = []
        current_event = None

        lines = ical_text.replace('\r\n ', '').replace('\r\n\t', '').split('\r\n')
        if len(lines) == 1:
            lines = ical_text.replace('\n ', '').replace('\n\t', '').split('\n')

        for line in lines:
            line = line.strip()

            if line == 'BEGIN:VEVENT':
                current_event = {}
            elif line == 'END:VEVENT':
                if current_event:
                    events.append(current_event)
                current_event = None
            elif current_event is not None and ':' in line:
                # Parse key:value, handling properties with parameters
                if ';' in line.split(':')[0]:
                    key = line.split(';')[0]
                else:
                    key = line.split(':')[0]
                value = ':'.join(line.split(':')[1:])
                current_event[key] = value

        return events

    def _should_skip_event(self, event: dict, venue: dict) -> bool:
        """Check if an event should be skipped."""
        summary = event.get('SUMMARY', '').lower()

        # Skip placeholder events
        skip_phrases = [
            'no event',
            'private event',
            'closed',
            'no show',
            'cancelled',
            'canceled',
        ]

        for phrase in skip_phrases:
            if phrase in summary:
                return True

        # Check venue-specific skip patterns (for filtering non-music events)
        skip_patterns = venue.get('skip_patterns', [])
        for pattern in skip_patterns:
            if re.search(pattern, summary, re.IGNORECASE):
                logger.debug(f"Skipping non-music event: {summary}")
                return True

        return False

    def _event_to_concert(self, event: dict, venue: dict) -> Optional[Concert]:
        """Convert an iCal event to a Concert object."""
        try:
            summary = event.get('SUMMARY', '')
            if not summary:
                return None

            # Parse date
            dtstart = event.get('DTSTART', '')
            date = self._parse_ical_date(dtstart)
            if not date:
                return None

            # Only include future events within configured lookahead
            now = datetime.now()
            if date < now or date > now + timedelta(weeks=WEEKS_AHEAD):
                return None

            # Parse time
            time_str = self._extract_time_from_date(dtstart)

            # Parse bands from summary
            # Summary format is usually just the event name/artist(s)
            bands = self._parse_bands_from_summary(summary)

            # Get description for additional info
            description = event.get('DESCRIPTION', '')
            description = self._unescape_ical(description)

            # Try to extract price from description
            price_advance, price_door = self._extract_price(description)

            return Concert(
                date=date,
                venue_id=venue["id"],
                venue_name=venue["name"],
                venue_location=venue["location"],
                bands=bands,
                age_requirement=venue["age"],
                price_advance=price_advance,
                price_door=price_door,
                time=time_str,
                flags=[],
                source=self.source_name,
                source_url=event.get('URL', venue["url"]),
                genre_tags=[]
            )

        except Exception as e:
            logger.debug(f"Error converting event to concert: {e}")
            return None

    def _parse_ical_date(self, dtstart: str) -> Optional[datetime]:
        """Parse iCal date string."""
        try:
            # Handle different formats:
            # DTSTART;TZID=America/New_York:20260118T190000
            # DTSTART;VALUE=DATE:20260119
            # DTSTART:20260118T190000Z

            # Extract date portion
            if 'T' in dtstart:
                # DateTime format
                date_part = dtstart.split('T')[0][-8:]
                time_part = dtstart.split('T')[1][:6]
                return datetime.strptime(f"{date_part}{time_part}", "%Y%m%d%H%M%S")
            else:
                # Date-only format
                date_part = dtstart[-8:]
                return datetime.strptime(date_part, "%Y%m%d")

        except Exception as e:
            logger.debug(f"Error parsing date '{dtstart}': {e}")
            return None

    def _extract_time_from_date(self, dtstart: str) -> str:
        """Extract time string from iCal date."""
        try:
            if 'T' in dtstart:
                time_part = dtstart.split('T')[1][:4]
                hour = int(time_part[:2])
                minute = time_part[2:4]

                if hour >= 12:
                    if hour > 12:
                        hour -= 12
                    suffix = 'pm'
                else:
                    if hour == 0:
                        hour = 12
                    suffix = 'am'

                if minute == '00':
                    return f"{hour}{suffix}"
                else:
                    return f"{hour}:{minute}{suffix}"
            else:
                return "8pm"  # Default for date-only events
        except:
            return "8pm"

    def _parse_bands_from_summary(self, summary: str) -> List[str]:
        """Parse band names from event summary."""
        # Clean the summary
        summary = self._unescape_ical(summary)

        # Try common separators
        # "Band A / Band B / Band C"
        # "Band A, Band B, Band C"
        # "Band A w/ Band B"
        # "Band A with Band B"

        # First, replace common "with" variants
        summary = re.sub(r'\s+w/\s+', ' / ', summary, flags=re.IGNORECASE)
        summary = re.sub(r'\s+with\s+', ' / ', summary, flags=re.IGNORECASE)
        summary = re.sub(r'\s+&\s+', ' / ', summary)
        summary = re.sub(r'\s+and\s+', ' / ', summary, flags=re.IGNORECASE)

        # Split by / or ,
        if ' / ' in summary:
            bands = [b.strip() for b in summary.split(' / ')]
        elif ',' in summary:
            bands = [b.strip() for b in summary.split(',')]
        else:
            bands = [summary.strip()]

        # Filter out empty strings and clean up
        bands = [b for b in bands if b and len(b) > 1]

        return bands if bands else [summary]

    def _unescape_ical(self, text: str) -> str:
        """Unescape iCal special characters."""
        text = text.replace('\\n', '\n')
        text = text.replace('\\,', ',')
        text = text.replace('\\;', ';')
        text = text.replace('\\:', ':')
        text = text.replace('\\\\', '\\')
        return text

    def _extract_price(self, description: str) -> Tuple[Optional[int], Optional[int]]:
        """Extract price from description."""
        # Look for patterns like "$15" or "$10/$15"
        price_match = re.search(r'\$(\d+)(?:\s*/\s*\$?(\d+))?', description)
        if price_match:
            advance = int(price_match.group(1))
            door = int(price_match.group(2)) if price_match.group(2) else advance
            return advance, door

        return None, None
