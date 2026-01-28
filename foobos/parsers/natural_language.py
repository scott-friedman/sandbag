"""
Natural language parser for concert descriptions.

Parses strings like:
  "Ratboys at Wanna Hear It Records, Watertown 1/29 8pm"
  "Pile, Krill @ Deep Cuts 2/15 $15 21+"
  "Converge w/ Cave In - Roadrunner 4/1 $30"
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import logging

from ..models import Concert

logger = logging.getLogger(__name__)


@dataclass
class ParseResult:
    """Result of parsing a natural language concert description."""
    bands: List[str] = field(default_factory=list)
    venue: str = ""
    location: str = ""
    date: Optional[datetime] = None
    time: str = "8pm"
    price_advance: Optional[int] = None
    price_door: Optional[int] = None
    age_requirement: str = "a/a"
    raw_text: str = ""


class NaturalLanguageConcertParser:
    """Parser for natural language concert descriptions."""

    # Separators between band and venue
    VENUE_SEPARATORS = [" at ", " @ ", " - "]

    # Separators between bands
    BAND_SEPARATORS = [", ", " w/ ", " with ", " + ", " and ", " & "]

    # Month name patterns
    MONTH_NAMES = {
        "jan": 1, "january": 1,
        "feb": 2, "february": 2,
        "mar": 3, "march": 3,
        "apr": 4, "april": 4,
        "may": 5,
        "jun": 6, "june": 6,
        "jul": 7, "july": 7,
        "aug": 8, "august": 8,
        "sep": 9, "sept": 9, "september": 9,
        "oct": 10, "october": 10,
        "nov": 11, "november": 11,
        "dec": 12, "december": 12,
    }

    def parse(self, text: str) -> ParseResult:
        """
        Parse a natural language concert description.

        Args:
            text: Raw concert description like "Ratboys at Middle East 1/29 8pm"

        Returns:
            ParseResult with extracted fields
        """
        result = ParseResult(raw_text=text.strip())
        remaining = text.strip()

        # Extract price first (before other processing)
        remaining, result.price_advance, result.price_door = self._extract_price(remaining)

        # Extract age requirement
        remaining, result.age_requirement = self._extract_age(remaining)

        # Extract time
        remaining, result.time = self._extract_time(remaining)

        # Extract date
        remaining, result.date = self._extract_date(remaining)

        # Split into bands and venue
        bands_part, venue_part = self._split_bands_venue(remaining)

        # Parse bands
        result.bands = self._parse_bands(bands_part)

        # Parse venue and location
        result.venue, result.location = self._parse_venue_location(venue_part)

        return result

    def to_concert(self, result: ParseResult) -> Concert:
        """
        Convert a ParseResult to a Concert object.

        Args:
            result: Parsed result from parse()

        Returns:
            Concert object ready for the pipeline
        """
        venue_id = self._generate_venue_id(result.venue)

        return Concert(
            date=result.date or datetime.now(),
            venue_id=venue_id,
            venue_name=result.venue,
            venue_location=result.location or "Boston",
            bands=result.bands,
            age_requirement=result.age_requirement,
            price_advance=result.price_advance,
            price_door=result.price_door,
            time=result.time,
            source="manual",
        )

    def _extract_price(self, text: str) -> tuple[str, Optional[int], Optional[int]]:
        """Extract price from text. Returns (remaining_text, advance, door)."""
        price_advance = None
        price_door = None

        # Match $15/$20 or $15-$20 or $15
        price_pattern = r'\$(\d+)(?:[/-]\$?(\d+))?'
        match = re.search(price_pattern, text)
        if match:
            price_advance = int(match.group(1))
            if match.group(2):
                price_door = int(match.group(2))
            text = text[:match.start()] + text[match.end():]

        return text.strip(), price_advance, price_door

    def _extract_age(self, text: str) -> tuple[str, str]:
        """Extract age requirement from text. Returns (remaining_text, age)."""
        age = "a/a"

        # Match 21+, 18+, a/a, all ages
        age_patterns = [
            (r'\b21\+', "21+"),
            (r'\b18\+', "18+"),
            (r'\ba/a\b', "a/a"),
            (r'\ball\s*ages\b', "a/a"),
        ]

        for pattern, age_value in age_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                age = age_value
                text = text[:match.start()] + text[match.end():]
                break

        return text.strip(), age

    def _extract_time(self, text: str) -> tuple[str, str]:
        """Extract time from text. Returns (remaining_text, time)."""
        time = "8pm"

        # Match patterns like 8pm, 8:00pm, 8 pm, 20:00
        time_patterns = [
            r'\b(\d{1,2}):?(\d{2})?\s*(am|pm)\b',  # 8pm, 8:00pm
            r'\b(\d{1,2}):(\d{2})\b',  # 20:00 (24-hour)
        ]

        for pattern in time_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if match.lastindex >= 3:
                    # Has am/pm
                    hour = match.group(1)
                    minutes = match.group(2) or ""
                    ampm = match.group(3).lower()
                    if minutes and minutes != "00":
                        time = f"{hour}:{minutes}{ampm}"
                    else:
                        time = f"{hour}{ampm}"
                else:
                    # 24-hour format
                    hour = int(match.group(1))
                    minutes = match.group(2)
                    if hour >= 12:
                        hour = hour - 12 if hour > 12 else 12
                        ampm = "pm"
                    else:
                        ampm = "am"
                    if minutes and minutes != "00":
                        time = f"{hour}:{minutes}{ampm}"
                    else:
                        time = f"{hour}{ampm}"
                text = text[:match.start()] + text[match.end():]
                break

        return text.strip(), time

    def _extract_date(self, text: str) -> tuple[str, Optional[datetime]]:
        """Extract date from text. Returns (remaining_text, date)."""
        date = None
        now = datetime.now()

        # Pattern 1: 1/29 or 01/29
        match = re.search(r'\b(\d{1,2})/(\d{1,2})\b', text)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            year = self._determine_year(month, day)
            try:
                date = datetime(year, month, day)
                text = text[:match.start()] + text[match.end():]
                return text.strip(), date
            except ValueError:
                pass

        # Pattern 2: Jan 29, January 29
        month_pattern = '|'.join(self.MONTH_NAMES.keys())
        match = re.search(rf'\b({month_pattern})\s+(\d{{1,2}})\b', text, re.IGNORECASE)
        if match:
            month_name = match.group(1).lower()
            month = self.MONTH_NAMES[month_name]
            day = int(match.group(2))
            year = self._determine_year(month, day)
            try:
                date = datetime(year, month, day)
                text = text[:match.start()] + text[match.end():]
                return text.strip(), date
            except ValueError:
                pass

        return text.strip(), date

    def _determine_year(self, month: int, day: int) -> int:
        """Determine year for a date, handling year rollover."""
        now = datetime.now()
        current_year = now.year

        # Create date for this year
        try:
            this_year_date = datetime(current_year, month, day)
        except ValueError:
            # Invalid date (e.g., Feb 30)
            return current_year

        # If date is more than 2 weeks in the past, assume next year
        days_ago = (now - this_year_date).days
        if days_ago > 14:
            return current_year + 1
        return current_year

    def _split_bands_venue(self, text: str) -> tuple[str, str]:
        """Split text into bands and venue parts."""
        text = text.strip()

        # Try each separator
        for sep in self.VENUE_SEPARATORS:
            sep_lower = sep.lower()
            text_lower = text.lower()
            idx = text_lower.find(sep_lower)
            if idx != -1:
                bands_part = text[:idx].strip()
                venue_part = text[idx + len(sep):].strip()
                return bands_part, venue_part

        # No separator found - assume it's all venue
        return "", text

    def _parse_bands(self, bands_text: str) -> List[str]:
        """Parse band names from text."""
        if not bands_text:
            return []

        bands = [bands_text]

        # Split on band separators (try each one)
        for sep in self.BAND_SEPARATORS:
            new_bands = []
            for band in bands:
                # Case-insensitive split
                parts = re.split(re.escape(sep), band, flags=re.IGNORECASE)
                new_bands.extend(parts)
            bands = new_bands

        # Clean up band names
        bands = [b.strip() for b in bands if b.strip()]
        return bands

    def _parse_venue_location(self, venue_text: str) -> tuple[str, str]:
        """Parse venue and location from text."""
        venue_text = venue_text.strip()
        location = ""

        # Check for comma-separated location (e.g., "Middle East, Cambridge")
        if "," in venue_text:
            parts = venue_text.rsplit(",", 1)
            venue = parts[0].strip()
            location = parts[1].strip()

            # Remove state abbreviation if present
            location = re.sub(r'\s+MA$', '', location, flags=re.IGNORECASE).strip()
            return venue, location

        # No comma - just venue name
        return venue_text, location

    def _generate_venue_id(self, venue_name: str) -> str:
        """Generate a venue ID from venue name."""
        if not venue_name:
            return "unknown"

        # Known venue mappings (common names to IDs)
        known_venues = {
            "middle east": "middleeast",
            "middle east downstairs": "middleeast_down",
            "middle east upstairs": "middleeast_up",
            "paradise": "paradise",
            "paradise rock club": "paradise",
            "the sinclair": "sinclair",
            "sinclair": "sinclair",
            "roadrunner": "roadrunner",
            "royale": "royale",
            "house of blues": "hob_boston",
            "hob": "hob_boston",
            "great scott": "greatscott",
            "brighton music hall": "brighton",
            "o'brien's": "obriens",
            "o'brien's pub": "obriens",
            "obriens": "obriens",
            "sally o'brien's": "sallyobriens",
            "midway": "midway",
            "midway cafe": "midway",
            "jungle": "jungle",
            "crystal ballroom": "crystal",
            "lizard lounge": "lizardlounge",
            "the rockwell": "rockwell",
            "rockwell": "rockwell",
            "deep cuts": "deepcuts",
            "groton hill": "grotonhill",
            "groton hill music center": "grotonhill",
            "wanna hear it records": "wanna_hear_it",
            "plough and stars": "ploughandstars",
            "the plough and stars": "ploughandstars",
        }

        venue_lower = venue_name.lower().strip()
        if venue_lower in known_venues:
            return known_venues[venue_lower]

        # Generate slug from name
        slug = venue_name.lower()
        slug = re.sub(r'[^\w\s]', '', slug)  # Remove punctuation
        slug = re.sub(r'\s+', '_', slug)  # Spaces to underscores
        return slug
