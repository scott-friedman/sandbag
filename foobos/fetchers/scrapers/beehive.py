"""
Scraper for The Beehive via Tockify iCal feed.
webcal://tockify.com/api/feeds/ics/beehive

The Beehive is a jazz club in Boston's South End at the Boston Center for the Arts.
"""

from datetime import datetime, timedelta
from typing import List, Optional
import logging
import re
import requests

from .base import BaseScraper
from ...models import Concert
from ...config import WEEKS_AHEAD
from ...utils import get_cached, save_cache

logger = logging.getLogger(__name__)

BEEHIVE_ICAL_URL = "https://tockify.com/api/feeds/ics/beehive"


class BeehiveScraper(BaseScraper):
    """Scrape events from The Beehive via Tockify iCal feed."""

    @property
    def source_name(self) -> str:
        return "scrape:beehive"

    @property
    def url(self) -> str:
        return BEEHIVE_ICAL_URL

    def fetch(self) -> List[Concert]:
        """Fetch concerts from The Beehive."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_beehive")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []
        try:
            response = requests.get(BEEHIVE_ICAL_URL, timeout=30)
            response.raise_for_status()

            events = self._parse_ical(response.text)
            concerts = self._events_to_concerts(events)

            # Cache the results
            save_cache("scrape_beehive", [c.to_dict() for c in concerts])
            self._log_fetch_complete(len(concerts))

        except Exception as e:
            self._log_fetch_error(e)

        return concerts

    def _parse_ical(self, ical_text: str) -> List[dict]:
        """Parse iCal text into a list of event dictionaries."""
        events = []
        current_event = None

        # Handle line continuations (lines starting with space/tab are continuations)
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
                # Parse key:value, handling properties with parameters like DTSTART;VALUE=DATE:
                if ';' in line.split(':')[0]:
                    key = line.split(';')[0]
                else:
                    key = line.split(':')[0]
                value = ':'.join(line.split(':')[1:])
                current_event[key] = value

        return events

    def _events_to_concerts(self, events: List[dict]) -> List[Concert]:
        """Convert iCal events to Concert objects."""
        concerts = []
        now = datetime.now()
        max_date = now + timedelta(weeks=WEEKS_AHEAD)

        for event in events:
            concert = self._event_to_concert(event, now, max_date)
            if concert:
                concerts.append(concert)

        return concerts

    def _event_to_concert(self, event: dict, now: datetime, max_date: datetime) -> Optional[Concert]:
        """Convert a single iCal event to a Concert object."""
        try:
            summary = event.get('SUMMARY', '').strip()
            if not summary:
                return None

            # Skip non-music events
            skip_keywords = ['closed', 'private event', 'no music', 'canceled', 'cancelled']
            summary_lower = summary.lower()
            if any(kw in summary_lower for kw in skip_keywords):
                return None

            # Parse date
            dtstart = event.get('DTSTART', '')
            date, time_str = self._parse_datetime(dtstart)
            if not date:
                return None

            # Filter by date range
            if date < now.replace(hour=0, minute=0, second=0, microsecond=0):
                return None
            if date > max_date:
                return None

            # Get event URL
            source_url = event.get('URL', 'https://www.beehiveboston.com/calendar')

            # Parse bands from summary
            bands = self._parse_bands(summary)

            # Get description for additional context
            description = self._unescape_ical(event.get('DESCRIPTION', ''))

            # Extract price from description
            price_advance, price_door = self._extract_price(description)

            return Concert(
                date=date,
                venue_id="beehive",
                venue_name="The Beehive",
                venue_location="Boston",
                bands=bands,
                age_requirement="21+",
                price_advance=price_advance,
                price_door=price_door,
                time=time_str,
                flags=[],
                source=self.source_name,
                source_url=source_url,
                genre_tags=["jazz"]
            )

        except Exception as e:
            logger.debug(f"Error converting event to concert: {e}")
            return None

    def _parse_datetime(self, dtstart: str) -> tuple:
        """Parse iCal datetime string, returning (date, time_str)."""
        try:
            # Handle different formats:
            # DTSTART:20260102T030000Z (UTC)
            # DTSTART;VALUE=DATE:20260101 (date only)
            # DTSTART;TZID=America/New_York:20260118T190000

            if 'T' in dtstart:
                # DateTime format
                date_part = dtstart.split('T')[0][-8:]
                time_part = dtstart.split('T')[1][:6]

                dt = datetime.strptime(f"{date_part}{time_part}", "%Y%m%d%H%M%S")

                # If UTC (ends with Z), convert to Eastern Time
                # EST is UTC-5, EDT is UTC-4. Use -5 as simplified approximation.
                if dtstart.endswith('Z'):
                    dt = dt - timedelta(hours=5)

                # Extract date (the show date) and time separately
                show_date = dt.date()
                hour = dt.hour
                minute = dt.minute

                # Format time string
                if hour >= 12:
                    display_hour = hour - 12 if hour > 12 else 12
                    suffix = 'pm'
                else:
                    display_hour = hour if hour > 0 else 12
                    suffix = 'am'

                if minute == 0:
                    time_str = f"{display_hour}{suffix}"
                else:
                    time_str = f"{display_hour}:{minute:02d}{suffix}"

                return datetime.combine(show_date, datetime.min.time()), time_str
            else:
                # Date-only format
                date_part = dtstart[-8:]
                dt = datetime.strptime(date_part, "%Y%m%d")
                return dt, "8pm"

        except Exception as e:
            logger.debug(f"Error parsing datetime '{dtstart}': {e}")
            return None, "8pm"

    def _parse_bands(self, summary: str) -> List[str]:
        """Parse band names from event summary."""
        # Clean up the summary
        summary = summary.strip()

        # Remove common suffixes like "- Early Jazz Set", "- Organ Groove"
        summary = re.sub(r'\s*-\s*(Early Jazz Set|Late Set|Organ Groove|New Jazz|Jazz Brunch|Brunch Jazz).*$', '', summary, flags=re.I)

        # Handle "Artist/Artist/Artist" format common in Beehive listings
        if '/' in summary and ' / ' not in summary:
            # Convert "A/B/C" to "A / B / C" for splitting
            summary = re.sub(r'/', ' / ', summary)

        # Split on common separators
        summary = re.sub(r'\s+w/\s+', ' / ', summary, flags=re.I)
        summary = re.sub(r'\s+with\s+', ' / ', summary, flags=re.I)
        summary = re.sub(r'\s+&\s+', ' / ', summary)
        summary = re.sub(r'\s+and\s+', ' / ', summary, flags=re.I)
        summary = re.sub(r'\s+ft\.?\s+', ' / ', summary, flags=re.I)
        summary = re.sub(r'\s+featuring\s+', ' / ', summary, flags=re.I)

        if ' / ' in summary:
            bands = [b.strip() for b in summary.split(' / ')]
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

    def _extract_price(self, description: str) -> tuple:
        """Extract price from event description."""
        if self._is_free_text(description):
            return (0, 0)
        match = re.search(r'\$(\d+)(?:\s*/\s*\$?(\d+))?', description)
        if match:
            advance = int(match.group(1))
            door = int(match.group(2)) if match.group(2) else advance
            return (advance, door)
        return (None, None)
