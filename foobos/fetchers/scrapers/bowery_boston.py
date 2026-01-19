"""
Scraper for Bowery Boston venues via their centralized calendar.

Bowery Boston (boweryboston.com) manages multiple Boston-area venues:
- Roadrunner
- Royale
- The Sinclair
- Fête Music Hall
- Arts at the Armory

Their /see-all-shows page contains JSON-LD structured data for all events.
"""

from datetime import datetime
from typing import List, Dict, Optional
import logging
import re
import json

from bs4 import BeautifulSoup

from .base import BaseScraper
from ...models import Concert
from ...utils import get_cached, save_cache, parse_date

logger = logging.getLogger(__name__)


# Map venue names from Bowery to our standardized IDs
VENUE_MAP = {
    "roadrunner": {
        "id": "roadrunner",
        "name": "Roadrunner",
        "location": "Boston",
        "patterns": ["roadrunner"],
    },
    "royale": {
        "id": "royale",
        "name": "Royale",
        "location": "Boston",
        "patterns": ["royale"],
    },
    "sinclair": {
        "id": "sinclair",
        "name": "The Sinclair",
        "location": "Cambridge",
        "patterns": ["sinclair"],
    },
    "fete_ballroom": {
        "id": "fete_ballroom",
        "name": "Fête Music Hall - Ballroom",
        "location": "Boston",
        "patterns": ["fête music hall - ballroom", "fete music hall - ballroom", "fete ballroom"],
    },
    "fete_lounge": {
        "id": "fete_lounge",
        "name": "Fête Music Hall - Lounge",
        "location": "Boston",
        "patterns": ["fête music hall - lounge", "fete music hall - lounge", "fete lounge"],
    },
    "armory": {
        "id": "armory",
        "name": "Arts at the Armory",
        "location": "Somerville",
        "patterns": ["arts at the armory", "armory"],
    },
    "suffolk_downs": {
        "id": "suffolk_downs",
        "name": "The Stage at Suffolk Downs",
        "location": "Boston",
        "patterns": ["suffolk downs", "stage at suffolk"],
    },
}


class BoweryBostonScraper(BaseScraper):
    """Scrape Bowery Boston's centralized event calendar."""

    @property
    def source_name(self) -> str:
        return "scrape:bowery_boston"

    @property
    def url(self) -> str:
        return "https://www.boweryboston.com/see-all-shows"

    def fetch(self) -> List[Concert]:
        """Fetch concerts from Bowery Boston."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_bowery_boston")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []

        try:
            soup = self._get_soup(self.url)
            concerts = self._parse_json_ld(soup)

            # Log per-venue counts
            venue_counts = {}
            for c in concerts:
                venue_counts[c.venue_name] = venue_counts.get(c.venue_name, 0) + 1
            for venue, count in sorted(venue_counts.items()):
                logger.info(f"[{self.source_name}] {venue}: {count} events")

        except Exception as e:
            logger.error(f"[{self.source_name}] Failed to fetch: {e}")

        # Cache the results
        if concerts:
            save_cache("scrape_bowery_boston", [c.to_dict() for c in concerts])

        self._log_fetch_complete(len(concerts))
        return concerts

    def _parse_json_ld(self, soup: BeautifulSoup) -> List[Concert]:
        """Parse events from JSON-LD structured data."""
        concerts = []

        for script in soup.find_all("script", type="application/ld+json"):
            try:
                if not script.string:
                    continue

                data = json.loads(script.string)

                # Handle both single events and arrays
                events = data if isinstance(data, list) else [data]

                for event in events:
                    concert = self._parse_event(event)
                    if concert:
                        concerts.append(concert)

            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.debug(f"JSON-LD parse error: {e}")
                continue

        return concerts

    def _parse_event(self, event: Dict) -> Optional[Concert]:
        """Parse a single event from JSON-LD data."""
        try:
            if not isinstance(event, dict):
                return None

            event_type = event.get("@type", "")
            if event_type not in ["Event", "MusicEvent", "Festival"]:
                return None

            name = event.get("name", "")
            if not name:
                return None

            # Parse date - JSON-LD times are in UTC
            start_date = event.get("startDate")
            if not start_date:
                return None

            try:
                if "T" in str(start_date):
                    # Parse UTC time and convert to Eastern (UTC-5)
                    utc_dt = datetime.fromisoformat(start_date.replace("Z", "").split("+")[0])
                    from datetime import timedelta
                    event_date = utc_dt - timedelta(hours=5)
                else:
                    event_date = parse_date(start_date)
            except ValueError:
                event_date = parse_date(start_date)

            if not event_date:
                return None

            # Skip past events
            if event_date.date() < datetime.now().date():
                return None

            # Parse venue
            location = event.get("location", {})
            venue_name = location.get("name", "") if isinstance(location, dict) else ""
            venue_info = self._map_venue(venue_name)

            # Parse time from the already-converted event_date
            show_time = "8pm"
            if event_date.hour != 0 or event_date.minute != 0:
                hour = event_date.hour
                minute = event_date.minute
                if hour >= 12:
                    display_hour = hour - 12 if hour > 12 else 12
                    ampm = "pm"
                else:
                    display_hour = hour if hour > 0 else 12
                    ampm = "am"
                if minute == 0:
                    show_time = f"{display_hour}{ampm}"
                else:
                    show_time = f"{display_hour}:{minute:02d}{ampm}"

            # Parse price from offers
            offers = event.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}
            price = offers.get("price") or offers.get("lowPrice")
            try:
                price_advance = int(float(price)) if price else None
            except (ValueError, TypeError):
                price_advance = None

            # Parse bands from name and performer
            bands = self._parse_event_name(name)

            # Add performers if available
            performers = event.get("performer", [])
            if isinstance(performers, dict):
                performers = [performers]
            for performer in performers:
                if isinstance(performer, dict):
                    perf_name = performer.get("name", "")
                    if perf_name and perf_name not in bands:
                        bands.append(perf_name)

            # Default age requirement (most Bowery shows are 18+)
            age_req = "18+"

            return Concert(
                date=event_date,
                venue_id=venue_info["id"],
                venue_name=venue_info["name"],
                venue_location=venue_info["location"],
                bands=bands,
                age_requirement=age_req,
                price_advance=price_advance,
                price_door=None,
                time=show_time,
                flags=[],
                source=self.source_name,
                source_url=event.get("url", self.url),
                genre_tags=[]
            )

        except Exception as e:
            logger.debug(f"Error parsing event: {e}")
            return None

    def _map_venue(self, venue_name: str) -> Dict:
        """Map a venue name to our standardized venue info."""
        if not venue_name:
            return {"id": "unknown", "name": "Unknown Venue", "location": "Boston"}

        venue_lower = venue_name.lower()

        for venue_key, venue_info in VENUE_MAP.items():
            for pattern in venue_info["patterns"]:
                if pattern in venue_lower:
                    return venue_info

        # Unknown venue - use the name as-is
        venue_id = re.sub(r'[^a-z0-9]+', '_', venue_name.lower()).strip('_')
        return {"id": venue_id, "name": venue_name, "location": "Boston"}

    def _parse_event_name(self, name: str) -> List[str]:
        """Parse band names from event title."""
        # Remove common suffixes
        name = re.sub(r'\s*[-:]\s*(tour|live|concert|show|presents|tickets).*$', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s*\(.*?(tour|live|vip|meet|sold out).*?\)$', '', name, flags=re.IGNORECASE)

        # Split by common separators
        bands = self._split_bands(name)

        return bands if bands else [name.strip()]
