"""
Venue registry module - centralized venue lookup and normalization.

Loads venues.json at import time and provides functions for:
- Looking up canonical venue IDs from variants
- Getting venue information (name, location, state)
- Formatting location with state abbreviation for non-MA venues
"""

import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)

# Module-level caches populated on first access
_venues_by_id: Dict[str, Dict[str, Any]] = {}
_id_variants_map: Dict[str, str] = {}  # variant → canonical ID
_loaded = False


def _load_venues() -> None:
    """Load venues from venues.json and build lookup maps."""
    global _venues_by_id, _id_variants_map, _loaded

    if _loaded:
        return

    # Find venues.json relative to this module
    module_dir = Path(__file__).parent
    venues_path = module_dir.parent.parent / "data" / "venues.json"

    if not venues_path.exists():
        logger.warning(f"venues.json not found at {venues_path}")
        _loaded = True
        return

    try:
        with open(venues_path) as f:
            data = json.load(f)
            venues = data.get("venues", [])

        for venue in venues:
            venue_id = venue.get("id", "")
            if not venue_id:
                continue

            # Store venue by canonical ID
            _venues_by_id[venue_id] = venue

            # Map canonical ID to itself
            _id_variants_map[venue_id] = venue_id

            # Map all variants to canonical ID
            for variant in venue.get("id_variants", []):
                variant_lower = variant.lower()
                _id_variants_map[variant_lower] = venue_id

        logger.debug(f"Loaded {len(_venues_by_id)} venues with {len(_id_variants_map)} ID mappings")
        _loaded = True

    except Exception as e:
        logger.error(f"Error loading venues.json: {e}")
        _loaded = True


def get_canonical_id(venue_id: str) -> Optional[str]:
    """
    Get the canonical venue ID for a given venue ID or variant.

    Args:
        venue_id: Raw venue ID that may be a variant

    Returns:
        Canonical venue ID, or None if not found
    """
    _load_venues()

    if not venue_id:
        return None

    # Normalize the input
    venue_id_lower = venue_id.lower().strip()

    # Direct lookup
    if venue_id_lower in _id_variants_map:
        return _id_variants_map[venue_id_lower]

    # Try with underscores instead of spaces
    venue_id_underscore = venue_id_lower.replace(" ", "_")
    if venue_id_underscore in _id_variants_map:
        return _id_variants_map[venue_id_underscore]

    # Try without underscores
    venue_id_nounderscore = venue_id_lower.replace("_", "")
    if venue_id_nounderscore in _id_variants_map:
        return _id_variants_map[venue_id_nounderscore]

    return None


def get_venue_info(venue_id: str) -> Optional[Dict[str, Any]]:
    """
    Get full venue information for a venue ID.

    Args:
        venue_id: Venue ID (canonical or variant)

    Returns:
        Venue dict with name, location, state, etc., or None if not found
    """
    _load_venues()

    canonical_id = get_canonical_id(venue_id)
    if canonical_id and canonical_id in _venues_by_id:
        return _venues_by_id[canonical_id]

    return None


def format_location(venue_id: str) -> Optional[str]:
    """
    Format location for display, adding state abbreviation for non-MA venues.

    Args:
        venue_id: Venue ID (canonical or variant)

    Returns:
        "City" for MA venues, "City, ST" for non-MA venues, or None if not found
    """
    venue = get_venue_info(venue_id)
    if not venue:
        return None

    location = venue.get("location", "")
    state = venue.get("state", "MA")

    if not location:
        return None

    # MA is default/assumed, so no state suffix needed
    if state == "MA":
        return location

    return f"{location}, {state}"


def get_all_venues() -> list:
    """
    Get all venues from the registry.

    Returns:
        List of all venue dicts
    """
    _load_venues()
    return list(_venues_by_id.values())


def reload_venues() -> None:
    """Force reload of venues from disk. Useful for testing."""
    global _venues_by_id, _id_variants_map, _loaded
    _venues_by_id = {}
    _id_variants_map = {}
    _loaded = False
    _load_venues()
