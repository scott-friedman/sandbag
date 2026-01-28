"""
Base class for recurring event generators.

These generators programmatically create events for venues with regular schedules,
rather than scraping web pages.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import List, Dict, Any
import logging

from ..models import Concert

logger = logging.getLogger(__name__)


class RecurringEventGenerator(ABC):
    """
    Abstract base class for recurring event generators.

    Subclasses define a schedule of recurring events (days, times, genres)
    and this base class handles generating Concert objects for each
    matching day in the lookahead period.
    """

    def __init__(self):
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the source name for event attribution (e.g., 'recurring:wallys_cafe')."""
        pass

    @property
    @abstractmethod
    def schedule(self) -> List[Dict[str, Any]]:
        """
        Return the schedule of recurring events.

        Each entry should be a dict with:
            - days: List of day names (e.g., ['monday', 'tuesday'])
            - time: Time string (e.g., '7pm')
            - bands: List of band/event names (e.g., ["Wally's Early Set"])
            - genre_tags: List of genre tags (e.g., ['jazz', 'improvised'])
        """
        pass

    @abstractmethod
    def get_venue_info(self) -> Dict[str, str]:
        """
        Return venue information.

        Should return a dict with:
            - id: Venue ID slug
            - name: Display name
            - location: City/neighborhood
        """
        pass

    @property
    def weeks_ahead(self) -> int:
        """Number of weeks to generate events for. Default: 4 weeks."""
        return 4

    def generate(self) -> List[Concert]:
        """
        Generate Concert objects for all scheduled events in the lookahead period.

        Returns:
            List of Concert objects
        """
        logger.info(f"[{self.source_name}] Generating recurring events...")

        concerts = []
        venue = self.get_venue_info()

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = today + timedelta(weeks=self.weeks_ahead)

        # Map day names to weekday numbers (Monday=0, Sunday=6)
        day_to_num = {
            'monday': 0,
            'tuesday': 1,
            'wednesday': 2,
            'thursday': 3,
            'friday': 4,
            'saturday': 5,
            'sunday': 6,
        }

        for schedule_entry in self.schedule:
            days = schedule_entry.get('days', [])
            time_str = schedule_entry.get('time', '8pm')
            bands = schedule_entry.get('bands', [])
            genre_tags = schedule_entry.get('genre_tags', [])

            # Convert day names to numbers
            target_weekdays = [day_to_num[d.lower()] for d in days if d.lower() in day_to_num]

            # Iterate through each day in the lookahead period
            current = today
            while current < end_date:
                if current.weekday() in target_weekdays:
                    # Parse time to set on the date
                    event_datetime = self._parse_time_to_datetime(current, time_str)

                    concert = Concert(
                        date=event_datetime,
                        venue_id=venue['id'],
                        venue_name=venue['name'],
                        venue_location=venue['location'],
                        bands=list(bands),  # Copy the list
                        time=time_str,
                        genre_tags=list(genre_tags),  # Copy the list
                        source=self.source_name,
                        age_requirement="21+",  # Most bar venues
                    )
                    concerts.append(concert)

                current += timedelta(days=1)

        logger.info(f"[{self.source_name}] Generated {len(concerts)} concerts")
        return concerts

    def _parse_time_to_datetime(self, date: datetime, time_str: str) -> datetime:
        """
        Parse a time string and combine with a date.

        Args:
            date: The date to use
            time_str: Time string like '7pm', '10pm', '8:30pm'

        Returns:
            datetime with the time set
        """
        import re

        time_str = time_str.lower().strip()

        # Extract hour and optional minutes
        match = re.match(r'(\d+)(?::(\d+))?\s*(am|pm)?', time_str)
        if not match:
            # Default to 8pm if parsing fails
            return date.replace(hour=20, minute=0)

        hour = int(match.group(1))
        minutes = int(match.group(2)) if match.group(2) else 0
        period = match.group(3) or 'pm'  # Default to PM for shows

        # Convert to 24-hour
        if period == 'pm' and hour < 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0

        return date.replace(hour=hour, minute=minutes, second=0, microsecond=0)
