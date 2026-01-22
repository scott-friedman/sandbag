"""
Detect new concerts by comparing current concerts against previously notified ones.
"""

import json
import logging
from pathlib import Path
from typing import List, Set, Tuple

from ..models import Concert
from ..config import DATA_DIR

logger = logging.getLogger(__name__)

LAST_NOTIFIED_FILE = Path(DATA_DIR) / "last_notified.json"


def detect_new_concerts(concerts: List[Concert]) -> Tuple[List[Concert], Set[str]]:
    """
    Compare current concerts against previously notified concerts.

    Args:
        concerts: List of current concerts

    Returns:
        Tuple of (new_concerts, all_current_ids)
        - new_concerts: Concerts not in the previous notification
        - all_current_ids: Set of all current concert IDs (for saving later)
    """
    current_ids = {c.id for c in concerts}
    previous_ids = _load_previous_ids()

    new_ids = current_ids - previous_ids
    new_concerts = [c for c in concerts if c.id in new_ids]

    # Sort new concerts by date
    new_concerts.sort(key=lambda c: c.date)

    logger.info(f"Found {len(new_concerts)} new concerts out of {len(concerts)} total")

    return new_concerts, current_ids


def _load_previous_ids() -> Set[str]:
    """Load previously notified concert IDs from file."""
    if not LAST_NOTIFIED_FILE.exists():
        logger.info("No previous notification record found")
        return set()

    try:
        with open(LAST_NOTIFIED_FILE) as f:
            data = json.load(f)
            return set(data.get("concert_ids", []))
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Error loading previous IDs: {e}")
        return set()


def save_notified_ids(concert_ids: Set[str]) -> None:
    """
    Save concert IDs after successful notification.

    Args:
        concert_ids: Set of concert IDs that were included in the notification
    """
    try:
        # Ensure data directory exists
        LAST_NOTIFIED_FILE.parent.mkdir(parents=True, exist_ok=True)

        with open(LAST_NOTIFIED_FILE, "w") as f:
            json.dump({
                "concert_ids": list(concert_ids)
            }, f, indent=2)

        logger.info(f"Saved {len(concert_ids)} concert IDs to {LAST_NOTIFIED_FILE}")
    except IOError as e:
        logger.error(f"Error saving notified IDs: {e}")
