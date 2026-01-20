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
    """Normalize venue ID to standard slug."""
    if not venue_id:
        return "unknown"

    venue_id = venue_id.lower().strip()

    # Normalize apostrophes and special characters
    venue_id = venue_id.replace("'", "'").replace("'", "'")  # Curly to straight

    # Standard mappings - consolidate duplicates
    id_map = {
        # Middle East variants
        "middle_east": "middleeast",
        "middle-east": "middleeast",
        "themiddleeast": "middleeast",
        "middle_east_-_upstairs": "middleeast_up",
        "middle_east_-_downstairs": "middleeast_down",
        "middle_east-_downstairs": "middleeast_down",
        "middle_east_-_corner/bakery": "middleeast_corner",
        "middle_east_-_zuzu": "middleeast_zuzu",

        # Paradise variants
        "paradise_rock_club": "paradise",
        "paradise_rock": "paradise",
        "paradiserock": "paradise",
        "paradise_rock_club_presented_b": "paradise",

        # Sinclair variants
        "sinclair_cambridge": "sinclair",
        "thesinclair": "sinclair",
        "the_sinclair_music_hall": "sinclair",
        "the_sinclair_-_cambridge": "sinclair",

        # Royale variants
        "royale_boston": "royale",

        # Roadrunner variants
        "roadrunner-boston": "roadrunner",

        # Lizard Lounge variants
        "lizard_lounge": "lizardlounge",

        # House of Blues variants
        "house_of_blues": "hob_boston",
        "houseofblues": "hob_boston",
        "citizens_house_of_blues_boston": "hob_boston",
        "hob": "hob_boston",

        # O'Brien's variants (note the curly apostrophe and straight apostrophe)
        "obriens_pub": "obriens",
        "obrien": "obriens",
        "o'brien's_pub": "obriens",
        "o'brien's_pub": "obriens",

        # Crystal Ballroom variants
        "crystal_ballroom_at_somerville": "crystal",

        # Jungle variants
        "jungle_tix": "jungle",

        # Brighton Music Hall
        "brighton_music_hall": "brighton",
        "brightonmusic": "brighton",
        "brighton_music_hall_presented_": "brighton",

        # Orpheum Theatre
        "orpheum_theatre_presented_by_c": "orpheum",

        # Great Scott
        "great_scott": "greatscott",
        "greatscottboston": "greatscott",

        # Midway Cafe
        "midway_cafe": "midway",
        "midwaycafe": "midway",

        # Deep Cuts
        "deep_cuts": "deepcuts",
        "deep-cuts": "deepcuts",

        # Groton Hill Music Center
        "groton_hill_music_center": "grotonhill",
        "groton-hill": "grotonhill",
        "groton_hill": "grotonhill",

        # Symphony Hall / BSO
        "symphony_hall": "symphonyhall",
        "symphony-hall": "symphonyhall",
        "bso": "symphonyhall",
        "boston_symphony_orchestra": "symphonyhall",
        "boston_symphony_hall": "symphonyhall",

        # Berklee Performance Center variants
        "berklee": "berklee_bpc",
        "berklee_performing_arts_center": "berklee_bpc",

        # Big Night Live variants
        "bignightlive": "big_night_live",

        # Bijou variants
        "bijou_nightclub": "bijou",

        # Blue Ocean Music Hall variants
        "blue_ocean": "blue_ocean_music_hall",

        # Cafe 939 / Red Room variants
        "cafe_939": "cafe939",
        "red_room_at_cafe_939": "cafe939",

        # Centro Nightclub variants
        "centro_night_club": "centro_nightclub",

        # Chevalier Theatre variants
        "chevalier": "chevalier_theatre",

        # City Winery variants
        "citywinery": "city_winery",

        # Fenway Park variants
        "fenway": "fenway_park",

        # Lynn Auditorium variants
        "lynn_memorial_auditorium": "lynn_auditorium",

        # Memoire variants
        "memoire_boston": "memoire",

        # MGM Music Hall variants
        "mgm_music_hall_at_fenway": "mgm_music_hall",

        # Off The Rails variants
        "off_the_rails": "off_the_rails_music_venue",

        # Palladium variants
        "palladium-ma": "palladium",

        # Leader Bank Pavilion variants
        "pavilion": "leader_bank_pavilion",

        # Providence Performing Arts Center variants
        "providence_performing_arts": "providence_performing_arts_cen",

        # Rockwell variants
        "the_rockwell": "rockwell",

        # Scullers Jazz Club variants
        "scullers": "scullers_jazz_club",

        # Sonia variants
        "sonia_live_music_venue": "sonia",

        # TD Garden variants
        "tdgarden": "td_garden",

        # The Grand variants
        "the_grand_(boston)": "the_grand",

        # Hanover Theatre variants
        "the_hanover_theatre": "hanover_theatre",

        # Strand Theatre variants
        "strand_theatre-ri": "the_strand_theatre_-_providenc",

        # The VETS / Veterans Memorial variants
        "the_vets": "veterans_memorial_auditorium",
        "the_vets_-_veterans_memorial_a": "veterans_memorial_auditorium",

        # Wally's variants
        "wallys_pub": "wallys",

        # Xfinity Center variants
        "xfinity_center": "xfinity_center_-_ma",
    }

    return id_map.get(venue_id, venue_id)


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
    }

    name_lower = name.lower().strip()
    return name_map.get(name_lower, name)


def _normalize_location(location: str, venue_id: str = None) -> str:
    """Normalize city/location name."""
    if not location:
        return "Boston"

    location = location.strip()

    # Fix known wrong locations based on venue
    if venue_id:
        venue_location_fixes = {
            "hob_boston": "Boston",  # House of Blues often has wrong Orlando location
        }
        if venue_id in venue_location_fixes:
            return venue_location_fixes[venue_id]

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
        "orlando": "Boston",  # Fix wrong Orlando locations
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
