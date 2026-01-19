"""
Date filtering to remove past events.
"""

from datetime import datetime
from typing import List
import logging

from ..models import Concert

logger = logging.getLogger(__name__)


def filter_past_events(concerts: List[Concert]) -> List[Concert]:
    """
    Filter out concerts that have already passed.

    Only includes concerts from today onwards.

    Args:
        concerts: List of concerts to filter

    Returns:
        Filtered list of concerts with only current and future events
    """
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

    filtered = []

    for concert in concerts:
        # Get concert date, handling both datetime and date objects
        concert_date = concert.date
        if hasattr(concert_date, 'replace'):
            # Normalize to start of day for comparison
            if hasattr(concert_date, 'hour'):
                concert_date = concert_date.replace(hour=0, minute=0, second=0, microsecond=0)

        # Include concert if it's today or in the future
        if concert_date >= today:
            filtered.append(concert)

    original_count = len(concerts)
    final_count = len(filtered)
    removed = original_count - final_count

    logger.info(f"Date filter: {original_count} -> {final_count} (removed {removed} past events)")

    return filtered
