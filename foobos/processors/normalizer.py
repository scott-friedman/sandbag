"""
Data normalization for concerts from multiple sources.
"""

import re
from typing import List
import logging

from ..models import Concert
from ..utils.venue_registry import get_canonical_id, get_venue_info, format_location

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
    # Normalize date (remove timezone info for consistency)
    if concert.date and concert.date.tzinfo is not None:
        concert.date = concert.date.replace(tzinfo=None)

    # Normalize bands
    concert.bands = [_normalize_band_name(b) for b in concert.bands if b]
    concert.bands = [b for b in concert.bands if b]  # Remove empty

    if not concert.bands:
        return None

    # Normalize venue - use name to help determine correct ID
    concert.venue_id = _normalize_venue_id_with_name(concert.venue_id, concert.venue_name)
    concert.venue_name = _normalize_venue_name(concert.venue_name)
    concert.venue_location = _normalize_location(concert.venue_location, concert.venue_id)

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


def _normalize_venue_id_with_name(venue_id: str, venue_name: str) -> str:
    """Normalize venue ID, using venue name to disambiguate similar IDs."""
    if not venue_id:
        return "unknown"

    # Normalize apostrophes first (handle multiple Unicode apostrophe variants)
    venue_id = venue_id.replace("\u2019", "'").replace("\u2018", "'").replace("`", "'")
    venue_id_lower = venue_id.lower().strip()
    venue_name_lower = (venue_name or "").lower().strip()

    # Direct O'Brien's Pub normalization (catch variants but NOT Sally O'Brien's)
    if "brien" in venue_id_lower and "sally" not in venue_id_lower:
        return "obriens"

    # Sally O'Brien's should remain separate
    if "sallyobrien" in venue_id_lower or "sally_obrien" in venue_id_lower:
        return "sallyobriens"

    # Handle Middle East variants by looking at the venue name
    if "middleeast" in venue_id_lower or "middle_east" in venue_id_lower or "middle-east" in venue_id_lower:
        if "upstairs" in venue_name_lower:
            return "middleeast_up"
        elif "downstairs" in venue_name_lower:
            return "middleeast_down"
        elif "corner" in venue_name_lower or "bakery" in venue_name_lower:
            return "middleeast_corner"
        elif "zuzu" in venue_name_lower:
            return "middleeast_zuzu"
        else:
            return "middleeast"

    # Fall back to standard normalization
    return _normalize_venue_id(venue_id)


def _normalize_venue_id(venue_id: str) -> str:
    """Normalize venue ID to standard slug using venue registry."""
    if not venue_id:
        return "unknown"

    venue_id = venue_id.lower().strip()

    # Normalize apostrophes and special characters
    venue_id = venue_id.replace("'", "'").replace("'", "'")  # Curly to straight

    # Use venue registry to get canonical ID
    canonical = get_canonical_id(venue_id)
    if canonical:
        return canonical

    # Fall back to basic normalization for unknown venues
    return venue_id.replace(" ", "_")


def _normalize_venue_name(name: str) -> str:
    """Normalize venue display name."""
    if not name:
        return "Unknown Venue"

    # Standard venue names - consolidate duplicates
    name_map = {
        # Middle East variants
        "middle east": "Middle East",
        "middle east downstairs": "Middle East Downstairs",
        "middle east upstairs": "Middle East Upstairs",
        "the middle east upstairs": "Middle East Upstairs",
        "the middle east downstairs": "Middle East Downstairs",
        "the middle east corner bar": "Middle East Corner",
        "middle east - downstairs": "Middle East Downstairs",
        "middle east- downstairs": "Middle East Downstairs",
        "middle east - upstairs": "Middle East Upstairs",
        "middle east - corner/bakery": "Middle East Corner",
        "middle east - zuzu": "Middle East ZuZu",

        # Paradise
        "paradise rock club": "Paradise Rock Club",
        "paradise": "Paradise Rock Club",
        "paradise rock club presented by citizens": "Paradise Rock Club",

        # Sinclair
        "the sinclair": "The Sinclair",
        "sinclair": "The Sinclair",
        "the sinclair music hall": "The Sinclair",

        # Royale
        "royale": "Royale",
        "royale boston": "Royale",

        # Roadrunner
        "roadrunner": "Roadrunner",
        "roadrunner-boston": "Roadrunner",

        # Lizard Lounge
        "lizard lounge": "Lizard Lounge",

        # House of Blues
        "house of blues": "House of Blues",
        "house of blues boston": "House of Blues",
        "citizens house of blues boston": "House of Blues",

        # Brighton Music Hall
        "brighton music hall": "Brighton Music Hall",
        "brighton music hall presented by citizens": "Brighton Music Hall",

        # Orpheum
        "orpheum": "Orpheum Theatre",
        "orpheum theatre": "Orpheum Theatre",
        "orpheum theatre presented by citizens": "Orpheum Theatre",

        # Great Scott
        "great scott": "Great Scott",

        # Crystal Ballroom
        "crystal ballroom": "Crystal Ballroom",
        "crystal ballroom at somerville theatre": "Crystal Ballroom",

        # Jungle
        "jungle": "Jungle",
        "jungle  tix": "Jungle",

        # Midway
        "midway cafe": "Midway Cafe",

        # O'Brien's Pub (Allston)
        "o'brien's pub": "O'Brien's Pub",
        "obriens": "O'Brien's Pub",

        # Sally O'Brien's (Somerville) - different venue!
        "sally o'brien's": "Sally O'Brien's",
        "sallyobriens": "Sally O'Brien's",
        "sally obriens": "Sally O'Brien's",

        # Rockwell
        "the rockwell": "The Rockwell",

        # Deep Cuts
        "deep cuts": "Deep Cuts",

        # Groton Hill Music Center
        "groton hill music center": "Groton Hill Music Center",
        "groton hill": "Groton Hill Music Center",

        # Symphony Hall
        "symphony hall": "Symphony Hall",
        "boston symphony orchestra": "Symphony Hall",

        # Wally's Cafe Jazz Club (Boston)
        "wally's cafe": "Wally's Cafe Jazz Club",
        "wally's cafe jazz club": "Wally's Cafe Jazz Club",
        "wallys cafe": "Wally's Cafe Jazz Club",
        "wallys cafe jazz club": "Wally's Cafe Jazz Club",

        # Wally's Pub (Hampton) - different venue
        "wally's pub": "Wally's Pub",
        "wallys pub": "Wally's Pub",
        "wally's": "Wally's Pub",  # Plain "Wally's" from Ticketmaster is Hampton
    }

    name_lower = name.lower().strip()
    return name_map.get(name_lower, name)


def _normalize_location(location: str, venue_id: str = None) -> str:
    """Normalize city/location name, adding state abbreviation for non-MA venues."""
    if not location:
        return "Boston"

    location = location.strip()

    # Try to get location from venue registry (includes state for non-MA)
    if venue_id:
        registry_location = format_location(venue_id)
        if registry_location:
            return registry_location

        # Fix known wrong locations based on venue
        venue_info = get_venue_info(venue_id)
        if venue_info:
            loc = venue_info.get("location", "")
            state = venue_info.get("state", "MA")
            if loc:
                if state != "MA":
                    return f"{loc}, {state}"
                return loc

    # Standard MA locations (no state suffix needed)
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
        "orlando": "Boston",  # Fix wrong Orlando locations
    }

    # Check for non-MA locations that need state suffix
    non_ma_map = {
        "providence": "Providence, RI",
        "providence, ri": "Providence, RI",
        "derry": "Derry, NH",
        "derry, nh": "Derry, NH",
        "hampton": "Hampton, NH",
        "hampton, nh": "Hampton, NH",
        "portland": "Portland, ME",
        "portland, me": "Portland, ME",
        "burlington": "Burlington, VT",
        "burlington, vt": "Burlington, VT",
        "new haven": "New Haven, CT",
        "new haven, ct": "New Haven, CT",
        "hartford": "Hartford, CT",
        "hartford, ct": "Hartford, CT",
    }

    location_lower = location.lower()

    # Check non-MA first
    if location_lower in non_ma_map:
        return non_ma_map[location_lower]

    return loc_map.get(location_lower, location)


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
