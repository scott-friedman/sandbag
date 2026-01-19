"""
Ticketmaster Discovery API fetcher.
"""

from datetime import datetime, timedelta
from typing import List, Optional
import logging

from ..config import (
    TICKETMASTER_API_KEY,
    TICKETMASTER_BASE_URL,
    BOSTON_DMA,
    WEEKS_AHEAD,
    PUNK_GENRES,
    EXCLUDE_GENRES,
    VENUE_TICKETMASTER_IDS
)
from ..models import Concert
from ..utils import get_cached, save_cache
from .base import BaseFetcher

logger = logging.getLogger(__name__)


class TicketmasterFetcher(BaseFetcher):
    """Fetch concerts from Ticketmaster Discovery API."""

    @property
    def source_name(self) -> str:
        return "ticketmaster"

    def fetch(self) -> List[Concert]:
        """
        Fetch concerts from Ticketmaster API.

        Returns:
            List of Concert objects
        """
        self._log_fetch_start()

        if not TICKETMASTER_API_KEY:
            logger.warning("TICKETMASTER_API_KEY not set, skipping Ticketmaster fetch")
            return []

        # Check cache first
        cached = get_cached("ticketmaster_boston")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []
        try:
            events = self._fetch_events()
            for event in events:
                concert = self._parse_event(event)
                if concert and self._is_relevant(concert):
                    concerts.append(concert)

            # Cache the results
            save_cache("ticketmaster_boston", [c.to_dict() for c in concerts])
            self._log_fetch_complete(len(concerts))

        except Exception as e:
            self._log_fetch_error(e)

        return concerts

    def _fetch_events(self) -> List[dict]:
        """Fetch raw events from Ticketmaster API."""
        all_events = []

        # Date range: today to WEEKS_AHEAD weeks from now
        start_date = datetime.now()
        end_date = start_date + timedelta(weeks=WEEKS_AHEAD)

        params = {
            "apikey": TICKETMASTER_API_KEY,
            "dmaId": BOSTON_DMA,
            "classificationName": "music",
            "startDateTime": start_date.strftime("%Y-%m-%dT00:00:00Z"),
            "endDateTime": end_date.strftime("%Y-%m-%dT23:59:59Z"),
            "size": 200,  # Max per page
            "sort": "date,asc"
        }

        page = 0
        total_pages = 1

        while page < total_pages and page < 10:  # Cap at 10 pages (2000 events)
            params["page"] = page

            try:
                response = self._make_request(
                    f"{TICKETMASTER_BASE_URL}/events.json",
                    params=params
                )
                data = response.json()

                if "_embedded" in data and "events" in data["_embedded"]:
                    all_events.extend(data["_embedded"]["events"])

                # Get pagination info
                if "page" in data:
                    total_pages = min(data["page"].get("totalPages", 1), 10)

                page += 1

            except Exception as e:
                logger.error(f"Error fetching page {page}: {e}")
                break

        return all_events

    def _parse_event(self, event: dict) -> Optional[Concert]:
        """Parse Ticketmaster event into Concert object."""
        try:
            # Extract date
            dates = event.get("dates", {})
            start = dates.get("start", {})
            date_str = start.get("localDate")
            if not date_str:
                return None
            date = datetime.strptime(date_str, "%Y-%m-%d")

            # Extract time
            time_str = start.get("localTime", "20:00:00")
            try:
                time_obj = datetime.strptime(time_str, "%H:%M:%S")
                time = time_obj.strftime("%-I%p").lower()  # "8pm"
            except ValueError:
                time = "8pm"

            # Extract venue
            venues = event.get("_embedded", {}).get("venues", [])
            if not venues:
                return None
            venue_data = venues[0]
            venue_name = venue_data.get("name", "Unknown Venue")
            venue_city = venue_data.get("city", {}).get("name", "Boston")
            venue_id = self._get_venue_id(venue_data.get("id", ""), venue_name)

            # Extract bands/artists
            attractions = event.get("_embedded", {}).get("attractions", [])
            bands = [a.get("name", "") for a in attractions if a.get("name")]
            if not bands:
                bands = [event.get("name", "Unknown Artist")]

            # Extract price
            price_ranges = event.get("priceRanges", [])
            price_advance = None
            price_door = None
            if price_ranges:
                price_advance = int(price_ranges[0].get("min", 0))
                price_door = int(price_ranges[0].get("max", 0))

            # Extract genres
            genre_tags = []
            classifications = event.get("classifications", [])
            for c in classifications:
                if c.get("genre", {}).get("name"):
                    genre_tags.append(c["genre"]["name"].lower())
                if c.get("subGenre", {}).get("name"):
                    genre_tags.append(c["subGenre"]["name"].lower())

            # Determine age requirement (default to 18+ for most venues)
            age_req = self._get_age_requirement(event)

            # Determine flags
            flags = self._get_flags(event)

            return Concert(
                date=date,
                venue_id=venue_id,
                venue_name=venue_name,
                venue_location=venue_city,
                bands=bands,
                age_requirement=age_req,
                price_advance=price_advance if price_advance else None,
                price_door=price_door if price_door else None,
                time=time,
                flags=flags,
                source="ticketmaster",
                source_url=event.get("url"),
                genre_tags=genre_tags
            )

        except Exception as e:
            logger.debug(f"Error parsing event: {e}")
            return None

    def _get_venue_id(self, tm_venue_id: str, venue_name: str) -> str:
        """Map Ticketmaster venue ID to our venue slug."""
        # Check if we have a mapping for this Ticketmaster ID
        for our_id, tm_id in VENUE_TICKETMASTER_IDS.items():
            if tm_id == tm_venue_id:
                return our_id

        # Fall back to slugifying the venue name
        slug = venue_name.lower()
        slug = slug.replace("'", "").replace(".", "").replace(",", "")
        slug = "_".join(slug.split())
        return slug[:30]

    def _get_age_requirement(self, event: dict) -> str:
        """Determine age requirement from event data."""
        # Check for age restriction in event info
        info = event.get("info", "").lower()
        please_note = event.get("pleaseNote", "").lower()
        combined = info + " " + please_note

        if "all ages" in combined or "a/a" in combined:
            return "a/a"
        if "21+" in combined or "21 and over" in combined:
            return "21+"
        if "18+" in combined or "18 and over" in combined:
            return "18+"

        # Default based on venue type (most Boston venues are 18+)
        return "18+"

    def _get_flags(self, event: dict) -> List[str]:
        """Determine event flags (sellout, mosh, etc.)."""
        flags = []

        # Check for sold out / limited availability
        dates = event.get("dates", {})
        status = dates.get("status", {}).get("code", "")
        if status in ("offsale", "cancelled"):
            return flags  # Don't include cancelled events

        # Check for likely sellout (high demand indicators)
        # This is a heuristic based on event properties
        if event.get("dates", {}).get("status", {}).get("code") == "limited":
            flags.append("$")

        return flags

    def _is_relevant(self, concert: Concert) -> bool:
        """Check if concert is relevant (punk/hardcore/metal genre)."""
        # Check genre tags
        for tag in concert.genre_tags:
            tag_lower = tag.lower()
            # Check if matches punk genres
            for punk_genre in PUNK_GENRES:
                if punk_genre in tag_lower:
                    return True
            # Check if explicitly excluded
            for exclude in EXCLUDE_GENRES:
                if exclude in tag_lower:
                    return False

        # Check if any band name matches priority list
        from ..config import PRIORITY_BANDS
        for band in concert.bands:
            if band in PRIORITY_BANDS:
                return True

        # Default: include if genre is rock/alternative/metal (broad categories)
        for tag in concert.genre_tags:
            if any(g in tag.lower() for g in ["rock", "alternative", "metal", "indie"]):
                return True

        return False
