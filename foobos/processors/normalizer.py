"""
Data normalization for concerts from multiple sources.
"""

import re
from typing import List
import logging

from ..models import Concert

logger = logging.getLogger(__name__)


def normalize_concerts(concerts: List[Concert]) -> List[Concert]:
    """
    Normalize concert data from multiple sources.

    - Standardizes band names
    - Normalizes venue names/IDs
    - Standardizes time formats
    - Normalizes price formats
    - Cleans up age requirements
    """
    normalized = []

    for concert in concerts:
        try:
            normalized_concert = _normalize_concert(concert)
            if normalized_concert:
                normalized.append(normalized_concert)
        except Exception as e:
            logger.debug(f"Error normalizing concert: {e}")
            normalized.append(concert)  # Keep original if normalization fails

    logger.info(f"Normalized {len(normalized)} concerts")
    return normalized


def _normalize_concert(concert: Concert) -> Concert:
    """Normalize a single concert."""
    # Normalize bands
    concert.bands = [_normalize_band_name(b) for b in concert.bands if b]
    concert.bands = [b for b in concert.bands if b]  # Remove empty

    if not concert.bands:
        return None

    # Normalize venue
    concert.venue_id = _normalize_venue_id(concert.venue_id)
    concert.venue_name = _normalize_venue_name(concert.venue_name)
    concert.venue_location = _normalize_location(concert.venue_location)

    # Normalize time
    concert.time = _normalize_time(concert.time)

    # Normalize age requirement
    concert.age_requirement = _normalize_age(concert.age_requirement)

    # Clean up flags (remove duplicates, sort)
    concert.flags = sorted(list(set(concert.flags)))

    return concert


def _normalize_band_name(name: str) -> str:
    """Normalize a band name."""
    if not name:
        return ""

    name = name.strip()

    # Remove common prefixes/suffixes
    name = re.sub(r'^(?:the\s+)?(.+?)(?:\s+band)?$', r'\1', name, flags=re.IGNORECASE)

    # Fix common capitalization issues
    # Keep "The" at the start
    if name.lower().startswith("the "):
        name = "The " + name[4:]

    # Handle all-caps names
    if name.isupper() and len(name) > 4:
        name = name.title()

    # Known corrections
    corrections = {
        "dropkick murphy's": "Dropkick Murphys",
        "dropkick murphys": "Dropkick Murphys",
        "mighty mighty bosstones": "The Mighty Mighty Bosstones",
        "bosstones": "The Mighty Mighty Bosstones",
        "dinosaur jr": "Dinosaur Jr.",
        "dinosaur jr.": "Dinosaur Jr.",
    }

    name_lower = name.lower()
    if name_lower in corrections:
        name = corrections[name_lower]

    return name.strip()


def _normalize_venue_id(venue_id: str) -> str:
    """Normalize venue ID to standard slug."""
    if not venue_id:
        return "unknown"

    venue_id = venue_id.lower().strip()

    # Standard mappings
    id_map = {
        "middle_east": "middleeast",
        "middle-east": "middleeast",
        "themiddleeast": "middleeast",
        "paradise_rock_club": "paradise",
        "paradise_rock": "paradise",
        "paradiserock": "paradise",
        "sinclair_cambridge": "sinclair",
        "thesinclair": "sinclair",
        "great_scott": "greatscott",
        "greatscottboston": "greatscott",
        "brighton_music_hall": "brighton",
        "brightonmusic": "brighton",
        "house_of_blues": "hob",
        "houseofblues": "hob",
        "obriens_pub": "obriens",
        "obrien": "obriens",
        "midway_cafe": "midway",
        "midwaycafe": "midway",
    }

    return id_map.get(venue_id, venue_id)


def _normalize_venue_name(name: str) -> str:
    """Normalize venue display name."""
    if not name:
        return "Unknown Venue"

    # Standard venue names
    name_map = {
        "middle east": "Middle East",
        "middle east downstairs": "Middle East Downstairs",
        "middle east upstairs": "Middle East Upstairs",
        "paradise rock club": "Paradise Rock Club",
        "paradise": "Paradise Rock Club",
        "the sinclair": "The Sinclair",
        "sinclair": "The Sinclair",
        "great scott": "Great Scott",
        "brighton music hall": "Brighton Music Hall",
        "house of blues": "House of Blues",
        "house of blues boston": "House of Blues",
        "royale": "Royale",
        "royale boston": "Royale",
        "orpheum": "Orpheum Theatre",
        "orpheum theatre": "Orpheum Theatre",
        "midway cafe": "Midway Cafe",
        "o'brien's pub": "O'Brien's Pub",
        "obriens": "O'Brien's Pub",
    }

    name_lower = name.lower().strip()
    return name_map.get(name_lower, name)


def _normalize_location(location: str) -> str:
    """Normalize city/location name."""
    if not location:
        return "Boston"

    location = location.strip()

    # Standard locations
    loc_map = {
        "boston": "Boston",
        "boston, ma": "Boston",
        "cambridge": "Cambridge",
        "cambridge, ma": "Cambridge",
        "somerville": "Somerville",
        "somerville, ma": "Somerville",
        "allston": "Allston",
        "allston, ma": "Allston",
        "jamaica plain": "Jamaica Plain",
        "jp": "Jamaica Plain",
        "brookline": "Brookline",
        "worcester": "Worcester",
        "providence": "Providence",
        "providence, ri": "Providence",
    }

    return loc_map.get(location.lower(), location)


def _normalize_time(time: str) -> str:
    """Normalize time to standard format (e.g., '8pm')."""
    if not time:
        return "8pm"

    time = time.lower().strip()

    # Remove spaces
    time = time.replace(" ", "")

    # Ensure am/pm
    if not ("am" in time or "pm" in time):
        # Assume PM for typical show times
        match = re.match(r'(\d+)', time)
        if match:
            hour = int(match.group(1))
            if hour < 12:
                time = f"{hour}pm"
            else:
                time = f"{hour - 12}pm"

    # Remove :00 for whole hours
    time = re.sub(r':00', '', time)

    return time


def _normalize_age(age: str) -> str:
    """Normalize age requirement."""
    if not age:
        return "a/a"

    age = age.lower().strip()

    if "all" in age or "aa" == age:
        return "a/a"
    if "21" in age:
        return "21+"
    if "18" in age:
        return "18+"

    return "a/a"
