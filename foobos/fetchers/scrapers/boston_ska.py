"""
Scraper for Boston Ska show calendar.

Boston Ska (bostonska.net) is a comprehensive listing of ska, punk,
and rocksteady shows in the Boston area, established in 2012.

Data format:
- Event cards with venue name and full address
- Dates in "Day, Month Day Year, Time" format
- Multiple ticketing platform links
"""

from datetime import datetime
from typing import List, Optional
import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper
from ...models import Concert
from ...utils import get_cached, save_cache, parse_date

logger = logging.getLogger(__name__)


# Map venue names to standardized IDs
VENUE_PATTERNS = {
    "middle east": {"id": "middleeast", "name": "Middle East", "location": "Cambridge"},
    "sonia": {"id": "sonia", "name": "Sonia", "location": "Cambridge"},
    "o'brien's": {"id": "obriens", "name": "O'Brien's Pub", "location": "Allston"},
    "midway cafe": {"id": "midway", "name": "Midway Cafe", "location": "Jamaica Plain"},
    "paradise": {"id": "paradise", "name": "Paradise Rock Club", "location": "Boston"},
    "sinclair": {"id": "sinclair", "name": "The Sinclair", "location": "Cambridge"},
    "brighton music": {"id": "brighton", "name": "Brighton Music Hall", "location": "Allston"},
    "house of blues": {"id": "hob", "name": "House of Blues", "location": "Boston"},
    "royale": {"id": "royale", "name": "Royale", "location": "Boston"},
    "roadrunner": {"id": "roadrunner", "name": "Roadrunner", "location": "Boston"},
    "once": {"id": "once", "name": "ONCE Ballroom", "location": "Somerville"},
    "crystal ballroom": {"id": "crystal", "name": "Crystal Ballroom", "location": "Somerville"},
    "vault": {"id": "vault", "name": "The Vault", "location": "New Bedford"},
    "thunder road": {"id": "thunderroad", "name": "Thunder Road", "location": "Somerville"},
}


class BostonSkaScraper(BaseScraper):
    """Scrape Boston Ska for ska/punk shows."""

    @property
    def source_name(self) -> str:
        return "scrape:boston_ska"

    @property
    def url(self) -> str:
        return "https://www.bostonska.net/"

    def fetch(self) -> List[Concert]:
        """Fetch concerts from Boston Ska."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_boston_ska")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []

        try:
            soup = self._get_soup(self.url)
            concerts = self._parse_listings(soup)
        except Exception as e:
            logger.error(f"[{self.source_name}] Failed to fetch: {e}")

        # Cache the results
        if concerts:
            save_cache("scrape_boston_ska", [c.to_dict() for c in concerts])

        self._log_fetch_complete(len(concerts))
        return concerts

    def _parse_listings(self, soup: BeautifulSoup) -> List[Concert]:
        """Parse concert listings from the page."""
        concerts = []
        seen_events = set()  # Track (date, headliner, venue) to avoid duplicates

        # Look for event entries - the page has event cards/blocks
        # Try various selectors for event containers
        event_containers = soup.find_all(["div", "article", "li"], class_=lambda c: c and ("event" in c.lower() or "show" in c.lower()) if c else False)

        if not event_containers:
            # Fallback: look for date patterns in text and extract events
            text = soup.get_text(separator="\n")
            lines = text.split("\n")

            current_event = {}
            for line in lines:
                line = line.strip()
                if not line:
                    if current_event.get("bands") and current_event.get("date"):
                        concert = self._create_concert(current_event)
                        if concert:
                            # Deduplicate by (date, headliner, venue)
                            event_key = (concert.date.strftime('%Y-%m-%d'),
                                        concert.bands[0].lower() if concert.bands else '',
                                        concert.venue_id)
                            if event_key not in seen_events:
                                seen_events.add(event_key)
                                concerts.append(concert)
                        current_event = {}
                    continue

                # Check for date pattern: "Sunday, January 18 2026, 5:00 pm"
                date_match = re.match(
                    r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s*(\d{4})?,?\s*(\d{1,2}:\d{2}\s*[ap]m)?',
                    line,
                    re.IGNORECASE
                )
                if date_match:
                    if current_event.get("bands") and current_event.get("date"):
                        concert = self._create_concert(current_event)
                        if concert:
                            concerts.append(concert)
                    current_event = {
                        "date_str": f"{date_match.group(2)} {date_match.group(3)}, {date_match.group(4) or datetime.now().year}",
                        "time": date_match.group(5) or "8pm"
                    }
                    parsed = parse_date(current_event["date_str"])
                    if parsed:
                        current_event["date"] = parsed
                    continue

                # Check for venue (line with address pattern or known venue)
                venue_info = self._extract_venue(line)
                if venue_info and not current_event.get("venue"):
                    current_event["venue"] = venue_info
                    continue

                # Check for band names (line without common metadata patterns)
                if not re.search(r'(tickets|eventbrite|facebook\.com|http|www\.|\$\d+|doors|all ages|21\+|18\+)', line.lower()):
                    if len(line) > 3 and len(line) < 200:
                        if "bands" not in current_event:
                            current_event["bands"] = []
                        # Could be comma-separated bands
                        bands = self._split_bands(line)
                        current_event["bands"].extend(bands)

            # Don't forget the last event
            if current_event.get("bands") and current_event.get("date"):
                concert = self._create_concert(current_event)
                if concert:
                    event_key = (concert.date.strftime('%Y-%m-%d'),
                                concert.bands[0].lower() if concert.bands else '',
                                concert.venue_id)
                    if event_key not in seen_events:
                        seen_events.add(event_key)
                        concerts.append(concert)

        else:
            # Parse structured event containers
            for container in event_containers:
                concert = self._parse_event_container(container)
                if concert:
                    # Deduplicate by (date, headliner, venue)
                    event_key = (concert.date.strftime('%Y-%m-%d'),
                                concert.bands[0].lower() if concert.bands else '',
                                concert.venue_id)
                    if event_key not in seen_events:
                        seen_events.add(event_key)
                        concerts.append(concert)

        return concerts

    def _parse_event_container(self, container) -> Optional[Concert]:
        """Parse a structured event container."""
        text = container.get_text(separator=" ")

        # Extract date
        date_match = re.search(
            r'(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)?,?\s*(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2}),?\s*(\d{4})?',
            text,
            re.IGNORECASE
        )
        if not date_match:
            return None

        month = date_match.group(2)
        day = date_match.group(3)
        year = date_match.group(4) or str(datetime.now().year)
        event_date = parse_date(f"{month} {day}, {year}")

        if not event_date or event_date.date() < datetime.now().date():
            return None

        # Extract venue
        venue_info = self._extract_venue(text)
        if not venue_info:
            venue_info = {"id": "unknown", "name": "Unknown Venue", "location": "Boston"}

        # Extract bands - look for header/title elements
        bands = []
        for elem in container.find_all(["h1", "h2", "h3", "h4", "strong", "b"]):
            band_text = elem.get_text().strip()
            if band_text and len(band_text) > 2:
                if not re.search(r'(january|february|march|april|may|june|july|august|september|october|november|december|monday|tuesday|wednesday|thursday|friday|saturday|sunday)', band_text.lower()):
                    bands.extend(self._split_bands(band_text))

        if not bands:
            return None

        # Extract time
        time_match = re.search(r'(\d{1,2}):?(\d{2})?\s*(am|pm|AM|PM)', text)
        show_time = "8pm"
        if time_match:
            hour = time_match.group(1)
            minutes = time_match.group(2) or "00"
            ampm = time_match.group(3).lower()
            if minutes == "00":
                show_time = f"{hour}{ampm}"
            else:
                show_time = f"{hour}:{minutes}{ampm}"

        # Extract age requirement
        age_req = "a/a"
        text_lower = text.lower()
        if "21+" in text_lower or "21 and over" in text_lower:
            age_req = "21+"
        elif "18+" in text_lower or "18 and over" in text_lower:
            age_req = "18+"

        # Extract price
        price_match = re.search(r'\$(\d+)', text)
        price = int(price_match.group(1)) if price_match else None

        return Concert(
            date=event_date,
            venue_id=venue_info["id"],
            venue_name=venue_info["name"],
            venue_location=venue_info["location"],
            bands=bands,
            age_requirement=age_req,
            price_advance=price,
            price_door=None,
            time=show_time,
            flags=[],
            source=self.source_name,
            source_url=self.url,
            genre_tags=["ska", "punk", "reggae"]
        )

    def _create_concert(self, event_data: dict) -> Optional[Concert]:
        """Create a Concert from parsed event data."""
        if not event_data.get("date") or not event_data.get("bands"):
            return None

        if event_data["date"].date() < datetime.now().date():
            return None

        venue = event_data.get("venue", {"id": "unknown", "name": "Unknown Venue", "location": "Boston"})

        # Clean up bands list
        bands = []
        for band in event_data.get("bands", []):
            band = band.strip()
            if band and len(band) > 1:
                bands.append(band)

        if not bands:
            return None

        # Parse time
        show_time = event_data.get("time", "8pm")
        if show_time:
            show_time = show_time.lower().replace(" ", "")

        return Concert(
            date=event_data["date"],
            venue_id=venue["id"],
            venue_name=venue["name"],
            venue_location=venue["location"],
            bands=bands,
            age_requirement=event_data.get("age", "a/a"),
            price_advance=event_data.get("price"),
            price_door=None,
            time=show_time,
            flags=[],
            source=self.source_name,
            source_url=self.url,
            genre_tags=["ska", "punk", "reggae"]
        )

    def _extract_venue(self, text: str) -> Optional[dict]:
        """Extract venue from text."""
        text_lower = text.lower()

        # Check for known venue patterns
        for pattern, venue_info in VENUE_PATTERNS.items():
            if pattern in text_lower:
                return venue_info

        # Check for address pattern that includes city/state
        address_match = re.search(r'([A-Z][A-Za-z\'\s]+),?\s+\d+\s+[A-Za-z\s]+,?\s+(Boston|Cambridge|Somerville|Allston|Brookline|Jamaica Plain|Medford|New Bedford)', text)
        if address_match:
            venue_name = address_match.group(1).strip()
            location = address_match.group(2)
            venue_id = re.sub(r'[^a-z0-9]+', '_', venue_name.lower()).strip('_')
            return {"id": venue_id, "name": venue_name, "location": location}

        return None
