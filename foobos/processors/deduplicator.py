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
    """Check if two concerts are duplicates using majority vote on event info.

    A duplicate is detected if:
    - Same date (already filtered by day)
    - Similar venue AND similar headliner (required)
    OR
    - Same venue AND majority of other info matches (time, price, age, bands)
    """
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
    headliner_similar = False
    if a.bands and b.bands:
        headliner_a = _normalize_name(a.headliner)
        headliner_b = _normalize_name(b.headliner)
        headliner_score = fuzz.ratio(headliner_a, headliner_b)
        headliner_similar = headliner_score >= SIMILARITY_THRESHOLD

    # If venue and headliner both match, it's a duplicate
    if headliner_similar:
        return True

    # If venue matches but headliner doesn't, check majority of other info
    # This catches cases where headliner name is formatted differently
    # but all other event details match
    match_count = 0
    total_checks = 0

    # Check time similarity
    if a.time and b.time:
        total_checks += 1
        if _times_similar(a.time, b.time):
            match_count += 1

    # Check price similarity
    if a.price_advance is not None or b.price_advance is not None:
        total_checks += 1
        if a.price_advance == b.price_advance:
            match_count += 1
    if a.price_door is not None or b.price_door is not None:
        total_checks += 1
        if a.price_door == b.price_door:
            match_count += 1

    # Check age requirement
    if a.age_requirement and b.age_requirement:
        total_checks += 1
        if a.age_requirement == b.age_requirement:
            match_count += 1

    # Check for overlapping bands (any band in common besides headliner)
    if len(a.bands) > 1 and len(b.bands) > 1:
        total_checks += 1
        a_other_bands = {_normalize_name(b) for b in a.bands[1:]}
        b_other_bands = {_normalize_name(b) for b in b.bands[1:]}
        # Check if any supporting bands overlap using fuzzy matching
        has_overlap = False
        for band_a in a_other_bands:
            for band_b in b_other_bands:
                if fuzz.ratio(band_a, band_b) >= SIMILARITY_THRESHOLD:
                    has_overlap = True
                    break
            if has_overlap:
                break
        if has_overlap:
            match_count += 1

    # If majority of event info matches (at least 3 out of available checks),
    # consider it a duplicate even if headliner names differ
    if total_checks >= 3 and match_count >= (total_checks // 2 + 1):
        logger.debug(f"Duplicate detected by majority match: {a.venue_name} - "
                    f"{match_count}/{total_checks} fields match")
        return True

    return False


def _times_similar(time_a: str, time_b: str) -> bool:
    """Check if two times are similar (same or within 30 minutes)."""
    import re

    def parse_time(t: str) -> int:
        """Convert time string to minutes since midnight."""
        t = t.lower().strip()
        match = re.match(r'(\d+)(?::(\d+))?\s*(am|pm)?', t)
        if not match:
            return -1
        hour = int(match.group(1))
        minute = int(match.group(2) or 0)
        period = match.group(3)

        if period == 'pm' and hour != 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0

        return hour * 60 + minute

    mins_a = parse_time(time_a)
    mins_b = parse_time(time_b)

    if mins_a < 0 or mins_b < 0:
        return time_a.lower() == time_b.lower()

    return abs(mins_a - mins_b) <= 30


def _info_richness_score(concert: Concert) -> int:
    """Calculate how much useful information a concert entry contains.

    Higher score = more detailed/complete information.
    """
    score = 0

    # Headliner detail - longer names with tour info are better
    # "Kenny Wayne Shepherd: Ledbetter Heights 30th Anniversary Tour" > "Kenny Wayne Shepherd"
    if concert.bands:
        headliner = concert.bands[0]
        score += len(headliner) // 10  # Bonus for longer, more detailed names
        if ':' in headliner or '-' in headliner or 'tour' in headliner.lower():
            score += 5  # Bonus for tour name in headliner

    # More bands listed is better
    score += len(concert.bands) * 2

    # Price info present
    if concert.price_advance is not None:
        score += 3
    if concert.price_door is not None:
        score += 3

    # Flags indicate additional info (sold out, recommended, etc.)
    score += len(concert.flags) * 4

    # Specific age requirement (not default)
    if concert.age_requirement and concert.age_requirement != "a/a":
        score += 2

    # Specific time (not default 8pm)
    if concert.time and concert.time != "8pm":
        score += 2

    # Genre tags present
    score += len(concert.genre_tags)

    # Source URL present
    if concert.source_url:
        score += 2

    return score


def _merge_concerts(concerts: List[Concert]) -> Concert:
    """Merge multiple duplicate concerts into the best single record.

    Prefers entries with more complete/detailed information, then falls back
    to source reliability for tie-breaking.
    """
    if len(concerts) == 1:
        return concerts[0]

    # Sort by info richness first (descending), then source reliability
    source_priority = {
        "ticketmaster": 1,
        "scrape:safe_in_a_crowd": 2,
        "scrape:middle_east": 3,
        "scrape:do617": 4,
    }

    concerts.sort(key=lambda c: (-_info_richness_score(c), source_priority.get(c.source, 99)))

    # Start with the most info-rich entry as base
    best = concerts[0]

    logger.debug(f"Merging {len(concerts)} duplicates, using base from {best.source} "
                 f"(richness: {_info_richness_score(best)})")

    # Merge in additional info from other sources
    for concert in concerts[1:]:
        # Merge bands - prefer more detailed names and add any missing bands
        all_bands = list(best.bands)
        for band in concert.bands:
            if not band:
                continue
            # Check if this band matches any existing band
            match_found = False
            for i, existing in enumerate(all_bands):
                similarity = fuzz.ratio(band.lower(), existing.lower())
                if similarity > 90:
                    match_found = True
                    # If the new name is more detailed (longer with tour info), use it
                    if len(band) > len(existing) + 5:
                        all_bands[i] = band
                        logger.debug(f"Upgraded band name: '{existing}' -> '{band}'")
                    break
            if not match_found:
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
