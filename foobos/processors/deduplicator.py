"""
Concert deduplication using fuzzy matching.
"""

from typing import List, Dict, Tuple
import logging

from rapidfuzz import fuzz

from ..models import Concert

logger = logging.getLogger(__name__)

# Minimum similarity score to consider events as duplicates
SIMILARITY_THRESHOLD = 80  # Lowered from 85 to catch more variants


def deduplicate_concerts(concerts: List[Concert]) -> List[Concert]:
    """
    Remove duplicate concerts using fuzzy matching.

    Duplicates are identified by matching:
    - Same date
    - Similar venue (fuzzy match)
    - Similar headliner (fuzzy match)

    When duplicates are found, prefer data from more reliable sources.
    """
    if not concerts:
        return []

    # Group by date first
    by_date: Dict[str, List[Concert]] = {}
    for concert in concerts:
        date_key = concert.date.strftime("%Y-%m-%d")
        if date_key not in by_date:
            by_date[date_key] = []
        by_date[date_key].append(concert)

    deduplicated = []

    for date_key, day_concerts in by_date.items():
        day_deduplicated = _deduplicate_day(day_concerts)
        deduplicated.extend(day_deduplicated)

    original_count = len(concerts)
    final_count = len(deduplicated)
    removed = original_count - final_count

    logger.info(f"Deduplication: {original_count} -> {final_count} (removed {removed} duplicates)")

    return deduplicated


def _deduplicate_day(concerts: List[Concert]) -> List[Concert]:
    """Deduplicate concerts within a single day."""
    if len(concerts) <= 1:
        return concerts

    # Track which concerts have been merged
    merged_indices = set()
    result = []

    for i, concert_a in enumerate(concerts):
        if i in merged_indices:
            continue

        # Find all duplicates of this concert
        duplicates = [concert_a]

        for j, concert_b in enumerate(concerts[i + 1:], start=i + 1):
            if j in merged_indices:
                continue

            if _are_duplicates(concert_a, concert_b):
                duplicates.append(concert_b)
                merged_indices.add(j)

        # Merge duplicates into single best record
        merged = _merge_concerts(duplicates)
        result.append(merged)

    return result


def _normalize_name(name: str) -> str:
    """Normalize a name for comparison."""
    import re
    name = name.lower().strip()
    # Remove common prefixes/suffixes
    name = re.sub(r'^the\s+', '', name)
    name = re.sub(r',\s*the$', '', name)
    # Remove venue city suffixes
    name = re.sub(r'\s*[-–]\s*(boston|cambridge|somerville|brookline|allston|brighton).*$', '', name, flags=re.I)
    # Normalize punctuation and whitespace
    name = re.sub(r'[^\w\s]', '', name)
    name = re.sub(r'\s+', ' ', name)
    return name.strip()


def _are_duplicates(a: Concert, b: Concert) -> bool:
    """Check if two concerts are duplicates."""
    # Must be same date (already filtered by day)

    # Check venue similarity with normalization
    venue_a = _normalize_name(a.venue_name or a.venue_id)
    venue_b = _normalize_name(b.venue_name or b.venue_id)

    venue_score = fuzz.ratio(venue_a, venue_b)
    venue_similar = venue_score >= SIMILARITY_THRESHOLD

    # Also check raw venue_id for exact matches
    if not venue_similar and a.venue_id and b.venue_id:
        venue_similar = a.venue_id.lower() == b.venue_id.lower()

    if not venue_similar:
        return False

    # Check headliner similarity
    if not a.bands or not b.bands:
        return False

    headliner_a = _normalize_name(a.headliner)
    headliner_b = _normalize_name(b.headliner)

    headliner_score = fuzz.ratio(headliner_a, headliner_b)

    return headliner_score >= SIMILARITY_THRESHOLD


def _merge_concerts(concerts: List[Concert]) -> Concert:
    """Merge multiple duplicate concerts into the best single record."""
    if len(concerts) == 1:
        return concerts[0]

    # Sort by source reliability (prefer ticketmaster > scrape:safe_in_a_crowd > others)
    source_priority = {
        "ticketmaster": 1,
        "scrape:safe_in_a_crowd": 2,
        "scrape:middle_east": 3,
        "scrape:do617": 4,
    }

    concerts.sort(key=lambda c: source_priority.get(c.source, 99))

    # Start with the most reliable source as base
    best = concerts[0]

    # Merge in additional info from other sources
    for concert in concerts[1:]:
        # Merge bands (union of all bands mentioned)
        all_bands = list(best.bands)
        for band in concert.bands:
            if band and not any(fuzz.ratio(band.lower(), b.lower()) > 90 for b in all_bands):
                all_bands.append(band)
        best.bands = all_bands

        # Use price if missing
        if not best.price_advance and concert.price_advance:
            best.price_advance = concert.price_advance
        if not best.price_door and concert.price_door:
            best.price_door = concert.price_door

        # Merge flags
        best.flags = list(set(best.flags + concert.flags))

        # Merge genre tags
        best.genre_tags = list(set(best.genre_tags + concert.genre_tags))

        # Use time if more specific
        if best.time == "8pm" and concert.time != "8pm":
            best.time = concert.time

        # Use age requirement if more specific
        if best.age_requirement == "a/a" and concert.age_requirement != "a/a":
            best.age_requirement = concert.age_requirement

    # Update source to indicate merge
    sources = list(set(c.source for c in concerts))
    if len(sources) > 1:
        best.source = f"merged:{'+'.join(sorted(sources))}"

    return best
