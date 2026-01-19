"""
Base fetcher class with common functionality.
"""

from abc import ABC, abstractmethod
from typing import List
import logging

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import requests

from ..models import Concert

logger = logging.getLogger(__name__)


class BaseFetcher(ABC):
    """Abstract base class for concert data fetchers."""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "foobos/1.0 (Boston punk concert aggregator)"
        })

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Return the source name for logging and attribution."""
        pass

    @abstractmethod
    def fetch(self) -> List[Concert]:
        """
        Fetch concerts from this source.

        Returns:
            List of Concert objects
        """
        pass

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((requests.RequestException, requests.Timeout)),
        reraise=True
    )
    def _make_request(self, url: str, params: dict = None, **kwargs) -> requests.Response:
        """
        Make HTTP request with retry logic.

        Args:
            url: URL to request
            params: Query parameters
            **kwargs: Additional arguments passed to requests.get

        Returns:
            Response object
        """
        timeout = kwargs.pop("timeout", 30)
        response = self.session.get(url, params=params, timeout=timeout, **kwargs)
        response.raise_for_status()
        return response

    def _log_fetch_start(self):
        """Log fetch operation start."""
        logger.info(f"[{self.source_name}] Starting fetch...")

    def _log_fetch_complete(self, count: int):
        """Log fetch operation completion."""
        logger.info(f"[{self.source_name}] Fetched {count} concerts")

    def _log_fetch_error(self, error: Exception):
        """Log fetch operation error."""
        logger.error(f"[{self.source_name}] Fetch failed: {error}")
