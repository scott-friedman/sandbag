"""
Genre filtering for punk/hardcore/metal concerts.
"""

from typing import List
import logging

from rapidfuzz import fuzz

from ..models import Concert
from ..config import PUNK_GENRES, EXCLUDE_GENRES, PRIORITY_BANDS

logger = logging.getLogger(__name__)


def filter_by_genre(concerts: List[Concert], strict: bool = False) -> List[Concert]:
    """
    Filter concerts to only include punk/hardcore/metal shows.

    Args:
        concerts: List of concerts to filter
        strict: If True, require explicit genre match. If False, include
                concerts that might be relevant based on heuristics.

    Returns:
        Filtered list of concerts
    """
    filtered = []

    for concert in concerts:
        if _is_relevant(concert, strict):
            filtered.append(concert)

    original_count = len(concerts)
    final_count = len(filtered)
    removed = original_count - final_count

    logger.info(f"Genre filter: {original_count} -> {final_count} (removed {removed})")

    return filtered


def _is_relevant(concert: Concert, strict: bool = False) -> bool:
    """Check if a concert is relevant based on genre."""
    # Always include priority bands
    if _has_priority_band(concert):
        return True

    # Check explicit genre tags
    for tag in concert.genre_tags:
        tag_lower = tag.lower()

        # Check for punk-related genres
        for punk_genre in PUNK_GENRES:
            if punk_genre in tag_lower:
                return True

        # Check for excluded genres (only if strict)
        if strict:
            for exclude_genre in EXCLUDE_GENRES:
                if exclude_genre in tag_lower:
                    return False

    # If not strict, use heuristics
    if not strict:
        # Check band names for punk-related keywords
        if _has_punk_keywords_in_bands(concert):
            return True

        # Include shows at known punk/hardcore venues
        if _is_punk_venue(concert.venue_id):
            return True

        # Include shows from punk-focused scrapers
        if concert.source in ["scrape:safe_in_a_crowd"]:
            return True

    # Default: exclude if strict, include if not
    return not strict


def _has_priority_band(concert: Concert) -> bool:
    """Check if any band is in the priority list."""
    for band in concert.bands:
        # Exact match
        if band in PRIORITY_BANDS:
            return True

        # Fuzzy match (handle slight variations)
        for priority_band in PRIORITY_BANDS:
            if fuzz.ratio(band.lower(), priority_band.lower()) > 90:
                return True

    return False


def _has_punk_keywords_in_bands(concert: Concert) -> bool:
    """Check if band names contain punk-related keywords."""
    punk_keywords = [
        "punk", "hardcore", "crust", "grind", "thrash", "doom",
        "sludge", "death", "black", "metal", "noise", "power",
        "violence", "chaos", "destroy", "dead", "hate", "war",
        "blood", "death", "murder", "kill", "rot", "grave"
    ]

    combined_bands = " ".join(concert.bands).lower()

    for keyword in punk_keywords:
        if keyword in combined_bands:
            return True

    return False


def _is_punk_venue(venue_id: str) -> bool:
    """Check if venue is known for punk/hardcore shows."""
    # Venues that primarily book punk/hardcore
    punk_venues = [
        "middleeast",
        "obriens",
        "elks",
        "vfw",
        "legion",
        "greatscott",
        "midway",
        "deepcuts",
    ]

    # Venues that frequently book punk/hardcore
    punk_friendly = [
        "paradise",
        "sinclair",
        "brighton",
        "royale",
        "palladium",
    ]

    venue_lower = venue_id.lower()

    if venue_lower in punk_venues:
        return True

    if venue_lower in punk_friendly:
        return True  # Include but might want less strict filtering

    return False
