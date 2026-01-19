"""
Caching utilities for API responses and scraped data.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Any

from ..config import CACHE_DIR, CACHE_TTL_HOURS


def _get_cache_path(key: str) -> Path:
    """Get the cache file path for a given key."""
    # Sanitize key for filesystem
    safe_key = "".join(c if c.isalnum() or c in "-_" else "_" for c in key)
    return Path(CACHE_DIR) / f"{safe_key}.json"


def get_cached(key: str, ttl_hours: Optional[int] = None) -> Optional[Any]:
    """
    Retrieve cached data if it exists and is not expired.

    Args:
        key: Cache key (e.g., "ticketmaster_boston", "scrape_middle_east")
        ttl_hours: Override default TTL in hours

    Returns:
        Cached data or None if expired/missing
    """
    cache_path = _get_cache_path(key)

    if not cache_path.exists():
        return None

    try:
        with open(cache_path, "r") as f:
            cached = json.load(f)

        # Check expiration
        cached_at = datetime.fromisoformat(cached["cached_at"])
        ttl = ttl_hours or CACHE_TTL_HOURS
        if datetime.now() - cached_at > timedelta(hours=ttl):
            return None

        return cached["data"]

    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def save_cache(key: str, data: Any) -> None:
    """
    Save data to cache.

    Args:
        key: Cache key
        data: Data to cache (must be JSON serializable)
    """
    cache_path = _get_cache_path(key)

    # Ensure cache directory exists
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    cache_entry = {
        "cached_at": datetime.now().isoformat(),
        "data": data
    }

    with open(cache_path, "w") as f:
        json.dump(cache_entry, f, indent=2)


def clear_old_cache(max_age_hours: int = 48) -> int:
    """
    Remove cache files older than max_age_hours.

    Returns:
        Number of files removed
    """
    cache_dir = Path(CACHE_DIR)
    if not cache_dir.exists():
        return 0

    removed = 0
    cutoff = datetime.now() - timedelta(hours=max_age_hours)

    for cache_file in cache_dir.glob("*.json"):
        try:
            with open(cache_file) as f:
                cached = json.load(f)
            cached_at = datetime.fromisoformat(cached["cached_at"])
            if cached_at < cutoff:
                cache_file.unlink()
                removed += 1
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            # Remove corrupted cache files
            try:
                cache_file.unlink()
                removed += 1
            except OSError:
                pass

    return removed


def clear_cache() -> int:
    """
    Remove all cache files.

    Returns:
        Number of files removed
    """
    cache_dir = Path(CACHE_DIR)
    if not cache_dir.exists():
        return 0

    removed = 0
    for cache_file in cache_dir.glob("*.json"):
        try:
            cache_file.unlink()
            removed += 1
        except OSError:
            pass

    return removed
