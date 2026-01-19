"""
Eventbrite API fetcher for concert events.
Eventbrite is especially good for DIY shows and smaller venues.
"""

from datetime import datetime, timedelta
from typing import List, Optional
import logging

from ..config import (
    EVENTBRITE_API_KEY,
    EVENTBRITE_BASE_URL,
    BOSTON_LATLONG,
    SEARCH_RADIUS_MILES,
    WEEKS_AHEAD,
)
from ..models import Concert
from ..utils import get_cached, save_cache
from .base import BaseFetcher

logger = logging.getLogger(__name__)


class EventbriteFetcher(BaseFetcher):
    """Fetch concerts from Eventbrite API."""

    @property
    def source_name(self) -> str:
        return "eventbrite"

    def fetch(self) -> List[Concert]:
        """
        Fetch concerts from Eventbrite API.

        Returns:
            List of Concert objects
        """
        self._log_fetch_start()

        if not EVENTBRITE_API_KEY:
            logger.warning("EVENTBRITE_API_KEY not set, skipping Eventbrite fetch")
            return []

        # Check cache first
        cached = get_cached("eventbrite_boston")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []
        try:
            events = self._fetch_events()
            for event in events:
                concert = self._parse_event(event)
                if concert:
                    concerts.append(concert)

            # Cache the results
            save_cache("eventbrite_boston", [c.to_dict() for c in concerts])
            self._log_fetch_complete(len(concerts))

        except Exception as e:
            self._log_fetch_error(e)

        return concerts

    def _fetch_events(self) -> List[dict]:
        """Fetch raw events from Eventbrite API."""
        all_events = []

        # Date range
        start_date = datetime.now()
        end_date = start_date + timedelta(weeks=WEEKS_AHEAD)

        # Eventbrite uses location.address and location.within
        # Search for music events in Boston area
        headers = {
            "Authorization": f"Bearer {EVENTBRITE_API_KEY}",
        }

        # Search params - Eventbrite v3 API
        params = {
            "location.latitude": BOSTON_LATLONG[0],
            "location.longitude": BOSTON_LATLONG[1],
            "location.within": f"{SEARCH_RADIUS_MILES}mi",
            "categories": "103",  # Music category
            "start_date.range_start": start_date.strftime("%Y-%m-%dT00:00:00Z"),
            "start_date.range_end": end_date.strftime("%Y-%m-%dT23:59:59Z"),
            "expand": "venue,category,subcategory",
        }

        page = 1
        has_more = True

        while has_more and page <= 10:  # Cap at 10 pages
            params["page"] = page

            try:
                response = self._make_request(
                    f"{EVENTBRITE_BASE_URL}/events/search/",
                    params=params,
                    headers=headers
                )
                data = response.json()

                if "events" in data:
                    all_events.extend(data["events"])

                # Check pagination
                pagination = data.get("pagination", {})
                has_more = pagination.get("has_more_items", False)
                page += 1

            except Exception as e:
                logger.error(f"Error fetching Eventbrite page {page}: {e}")
                break

        return all_events

    def _parse_event(self, event: dict) -> Optional[Concert]:
        """Parse Eventbrite event into Concert object."""
        try:
            # Extract date
            start = event.get("start", {})
            date_str = start.get("local") or start.get("utc")
            if not date_str:
                return None

            try:
                date = datetime.strptime(date_str[:19], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                date = datetime.strptime(date_str[:10], "%Y-%m-%d")

            # Extract time
            time = "8pm"
            if date_str and "T" in date_str:
                try:
                    time_part = date_str.split("T")[1][:5]
                    time_obj = datetime.strptime(time_part, "%H:%M")
                    time = time_obj.strftime("%-I%p").lower()
                except (ValueError, IndexError):
                    pass

            # Extract venue
            venue_data = event.get("venue", {})
            if venue_data:
                venue_name = venue_data.get("name", "Unknown Venue")
                address = venue_data.get("address", {})
                venue_city = address.get("city", "Boston")
            else:
                venue_name = "TBA"
                venue_city = "Boston"

            venue_id = self._get_venue_id(venue_name)

            # Extract event name (which is typically the artist/band)
            name = event.get("name", {})
            if isinstance(name, dict):
                event_title = name.get("text", "") or name.get("html", "")
            else:
                event_title = str(name)

            if not event_title:
                return None

            # Parse bands from title
            bands = self._parse_bands_from_title(event_title)
            if not bands:
                bands = [event_title]

            # Extract price (Eventbrite requires separate API call for tickets)
            # We'll mark as unknown
            price_advance = None
            price_door = None

            # Check if free
            is_free = event.get("is_free", False)
            if is_free:
                price_advance = 0
                price_door = 0

            # Determine age requirement
            age_restriction = event.get("age_restriction")
            if age_restriction == "all_ages":
                age_req = "a/a"
            elif age_restriction == "21+":
                age_req = "21+"
            else:
                age_req = "18+"

            # Genre from category/subcategory
            genre_tags = []
            category = event.get("category", {})
            if category:
                cat_name = category.get("name", "").lower()
                if cat_name:
                    genre_tags.append(cat_name)
            subcategory = event.get("subcategory", {})
            if subcategory:
                subcat_name = subcategory.get("name", "").lower()
                if subcat_name:
                    genre_tags.append(subcat_name)

            return Concert(
                date=date,
                venue_id=venue_id,
                venue_name=venue_name,
                venue_location=venue_city,
                bands=bands,
                age_requirement=age_req,
                price_advance=price_advance,
                price_door=price_door,
                time=time,
                flags=[],
                source="eventbrite",
                source_url=event.get("url"),
                genre_tags=genre_tags
            )

        except Exception as e:
            logger.debug(f"Error parsing Eventbrite event: {e}")
            return None

    def _get_venue_id(self, venue_name: str) -> str:
        """Map venue name to our venue slug."""
        if not venue_name:
            return "unknown"

        # Slugify
        slug = venue_name.lower()
        slug = slug.replace("'", "").replace(".", "").replace(",", "")
        slug = "_".join(slug.split())
        return slug[:30]

    def _parse_bands_from_title(self, title: str) -> List[str]:
        """Parse band names from event title.

        Common formats:
        - "Band Name at Venue"
        - "Band Name w/ Support Act"
        - "Band Name with Support Act"
        - "Band Name, Other Band, Third Band"
        """
        bands = []

        # Remove common venue prefixes
        title = title.strip()

        # Split on common separators
        import re

        # Remove "at Venue" or "@ Venue" suffixes
        title = re.sub(r'\s+(?:at|@)\s+[\w\s]+$', '', title, flags=re.IGNORECASE)

        # Split on w/, with, +, &, and commas
        parts = re.split(r'\s+(?:w/|with|and|&|\+|,)\s+', title, flags=re.IGNORECASE)

        for part in parts:
            part = part.strip()
            if part and len(part) > 1:
                bands.append(part)

        return bands
