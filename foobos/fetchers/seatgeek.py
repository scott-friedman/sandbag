"""
SeatGeek API fetcher for concert events.
"""

from datetime import datetime, timedelta
from typing import List, Optional
import logging

from ..config import (
    SEATGEEK_CLIENT_ID,
    SEATGEEK_CLIENT_SECRET,
    SEATGEEK_BASE_URL,
    BOSTON_LATLONG,
    SEARCH_RADIUS_MILES,
    WEEKS_AHEAD,
)
from ..models import Concert
from ..utils import get_cached, save_cache
from .base import BaseFetcher

logger = logging.getLogger(__name__)


class SeatGeekFetcher(BaseFetcher):
    """Fetch concerts from SeatGeek API."""

    @property
    def source_name(self) -> str:
        return "seatgeek"

    def fetch(self) -> List[Concert]:
        """
        Fetch concerts from SeatGeek API.

        Returns:
            List of Concert objects
        """
        self._log_fetch_start()

        if not SEATGEEK_CLIENT_ID:
            logger.warning("SEATGEEK_CLIENT_ID not set, skipping SeatGeek fetch")
            return []

        # Check cache first
        cached = get_cached("seatgeek_boston")
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
            save_cache("seatgeek_boston", [c.to_dict() for c in concerts])
            self._log_fetch_complete(len(concerts))

        except Exception as e:
            self._log_fetch_error(e)

        return concerts

    def _fetch_events(self) -> List[dict]:
        """Fetch raw events from SeatGeek API."""
        all_events = []

        # Date range: today to WEEKS_AHEAD weeks from now
        start_date = datetime.now()
        end_date = start_date + timedelta(weeks=WEEKS_AHEAD)

        # Build params for Boston area concerts
        params = {
            "client_id": SEATGEEK_CLIENT_ID,
            "lat": BOSTON_LATLONG[0],
            "lon": BOSTON_LATLONG[1],
            "range": f"{SEARCH_RADIUS_MILES}mi",
            "type": "concert",  # Ensures only concert events, not sports/theater/etc
            "datetime_utc.gte": start_date.strftime("%Y-%m-%dT00:00:00"),
            "datetime_utc.lte": end_date.strftime("%Y-%m-%dT23:59:59"),
            "per_page": 100,
            "sort": "datetime_utc.asc",
        }

        # Add secret if available
        if SEATGEEK_CLIENT_SECRET:
            params["client_secret"] = SEATGEEK_CLIENT_SECRET

        page = 1
        total_pages = 1

        while page <= total_pages and page <= 10:  # Cap at 10 pages (1000 events)
            params["page"] = page

            try:
                response = self._make_request(
                    f"{SEATGEEK_BASE_URL}/events",
                    params=params
                )
                data = response.json()

                if "events" in data:
                    all_events.extend(data["events"])

                # Get pagination info
                meta = data.get("meta", {})
                total = meta.get("total", 0)
                per_page = meta.get("per_page", 100)
                if total > 0 and per_page > 0:
                    total_pages = min((total // per_page) + 1, 10)

                page += 1

            except Exception as e:
                logger.error(f"Error fetching SeatGeek page {page}: {e}")
                break

        return all_events

    def _parse_event(self, event: dict) -> Optional[Concert]:
        """Parse SeatGeek event into Concert object."""
        try:
            # Extract date - use datetime_local to get correct local date
            # (datetime_utc can be next day for late evening events due to timezone offset)
            datetime_local = event.get("datetime_local") or event.get("datetime_utc")
            if not datetime_local:
                return None

            # Parse datetime from local time
            try:
                date = datetime.strptime(datetime_local[:19], "%Y-%m-%dT%H:%M:%S")
            except ValueError:
                date = datetime.strptime(datetime_local[:10], "%Y-%m-%d")

            # Extract time from local datetime
            time = "8pm"
            if datetime_local and "T" in datetime_local:
                try:
                    time_part = datetime_local.split("T")[1][:5]
                    time_obj = datetime.strptime(time_part, "%H:%M")
                    time = time_obj.strftime("%-I%p").lower()
                except (ValueError, IndexError):
                    pass

            # Extract venue
            venue_data = event.get("venue", {})
            if not venue_data:
                return None
            venue_name = venue_data.get("name", "Unknown Venue")
            venue_city = venue_data.get("city", "Boston")
            venue_id = self._get_venue_id(venue_data.get("id", ""), venue_name)

            # Extract bands/performers
            performers = event.get("performers", [])
            bands = []
            for p in performers:
                name = p.get("name", "")
                if name and name not in bands:
                    bands.append(name)

            if not bands:
                # Use event title as fallback
                title = event.get("title", "") or event.get("short_title", "")
                if title:
                    bands = [title]
                else:
                    return None

            # Extract price
            stats = event.get("stats", {})
            price_advance = None
            price_door = None
            lowest = stats.get("lowest_price")
            highest = stats.get("highest_price")
            if lowest:
                price_advance = int(lowest)
            if highest:
                price_door = int(highest)

            # Extract genres from performers
            genre_tags = []
            for p in performers:
                genres = p.get("genres", [])
                for g in genres:
                    genre_name = g.get("name", "").lower()
                    if genre_name and genre_name not in genre_tags:
                        genre_tags.append(genre_name)

            # Determine age requirement
            age_req = "18+"  # Default for most concerts

            # Check for flags
            flags = self._get_flags(event)

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
                flags=flags,
                source="seatgeek",
                source_url=event.get("url"),
                genre_tags=genre_tags
            )

        except Exception as e:
            logger.debug(f"Error parsing SeatGeek event: {e}")
            return None

    def _get_venue_id(self, sg_venue_id: str, venue_name: str) -> str:
        """Map SeatGeek venue to our venue slug."""
        # Common SeatGeek venue mappings (SeatGeek name slug -> our venue_id)
        sg_venue_map = {
            # Major Boston venues
            "house-of-blues-boston": "hob_boston",
            "citizens-house-of-blues-boston": "hob_boston",
            "paradise-rock-club": "paradise",
            "royale-boston": "royale",
            "royale---boston": "royale",
            "the-sinclair": "sinclair",
            "the-sinclair---cambridge": "sinclair",
            "brighton-music-hall": "brighton",
            "middle-east-cambridge": "middleeast",
            "middle-east---upstairs": "middleeast_up",
            "middle-east-downstairs": "middleeast_down",
            "middle-east---downstairs": "middleeast_down",
            "orpheum-theatre-boston": "orpheum",
            "orpheum-theatre---boston": "orpheum",
            "roadrunner-boston": "roadrunner",
            "roadrunner---boston": "roadrunner",
            "td-garden": "tdgarden",
            "fenway-park": "fenway",
            "blue-hills-bank-pavilion": "pavilion",
            "leader-bank-pavilion": "pavilion",
            "xfinity-center-mansfield": "xfinity",
            "wang-theatre": "wang",
            "boch-center-wang-theatre": "wang",
            # Additional venues from SeatGeek
            "mgm-music-hall-at-fenway": "mgm_music_hall",
            "big-night-live": "big_night_live",
            "somerville-theatre": "somerville_theatre",
            "city-winery---boston": "city_winery",
            "city-winery-boston": "city_winery",
            "blue-ocean-music-hall": "blue_ocean",
            "the-cabot": "the_cabot",
            "groton-hill-music-center": "groton_hill",
            "the-grand---boston": "the_grand",
            "the-grand-boston": "the_grand",
            "chevalier-theatre": "chevalier",
            "the-palladium": "palladium",
            "boston-symphony-hall": "symphony_hall",
            "berklee-performance-center": "berklee",
            "cafe-939-at-berklee": "cafe_939",
            "regattabar": "regattabar",
            "scullers-jazz-club": "scullers",
            # Additional Boston-area venues
            "agganis-arena": "agganis",
            "the-wilbur": "wilbur",
            "wilbur-theatre": "wilbur",
            "gillette-stadium": "gillette",
            "club-passim": "clubpassim",
            "sonia": "sonia",
            "sonia-cambridge": "sonia",
            "crystal-ballroom-somerville": "crystal_ballroom",
            "crystal-ballroom---somerville": "crystal_ballroom",
            "hampton-beach-casino-ballroom": "hampton_beach",
            "indian-ranch-amphitheatre": "indian_ranch",
            "indian-ranch": "indian_ranch",
            "boch-center-shubert-theatre": "shubert",
            "shubert-theatre": "shubert",
            "emerson-colonial-theatre": "colonial",
            "colonial-theatre": "colonial",
            "tsongas-center": "tsongas",
            "tsongas-center-at-umass-lowell": "tsongas",
        }

        # Try slug from venue name
        if venue_name:
            slug = venue_name.lower()
            slug = slug.replace("'", "").replace(".", "").replace(",", "").replace(" - ", "-")
            slug = "-".join(slug.split())

            if slug in sg_venue_map:
                return sg_venue_map[slug]

        # Fall back to slugifying the venue name
        if venue_name:
            slug = venue_name.lower()
            slug = slug.replace("'", "").replace(".", "").replace(",", "")
            slug = "_".join(slug.split())
            return slug[:30]

        return "unknown"

    def _get_flags(self, event: dict) -> List[str]:
        """Determine event flags."""
        flags = []

        # Check for high demand / likely sellout
        stats = event.get("stats", {})
        score = event.get("score", 0)

        # High popularity score suggests likely sellout
        if score and score > 0.7:
            flags.append("$")

        return flags
