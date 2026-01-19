"""
Eventbrite API fetcher for concert events.

NOTE: The Eventbrite public search API (/events/search/) was deprecated in Feb 2020.
This fetcher is disabled. To use Eventbrite data, you would need to query specific
venue IDs or organization IDs, which requires knowing them in advance.

See: https://github.com/Automattic/eventbrite-api/issues/83
"""

from typing import List
import logging

from ..models import Concert
from .base import BaseFetcher

logger = logging.getLogger(__name__)


class EventbriteFetcher(BaseFetcher):
    """Fetch concerts from Eventbrite API (DEPRECATED - search API removed in 2020)."""

    @property
    def source_name(self) -> str:
        return "eventbrite"

    def fetch(self) -> List[Concert]:
        """
        Eventbrite search API was deprecated in Feb 2020.
        This fetcher is disabled.
        """
        logger.info("Eventbrite search API deprecated (Feb 2020) - skipping")
        return []
