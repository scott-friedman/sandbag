"""
Scraper for Boston venue websites.

Many major Boston venues use AXS for ticketing but we scrape from
their own websites which often have server-rendered calendars:
- Roadrunner
- Royale
- Big Night Live
- The Sinclair
- Paradise Rock Club
- Brighton Music Hall
"""

from datetime import datetime
from typing import List, Optional, Dict
import logging
import re
import json

from bs4 import BeautifulSoup

from .base import BaseScraper
from ...models import Concert
from ...utils import get_cached, save_cache, parse_date

logger = logging.getLogger(__name__)


# Non-music event keywords to filter out (for multi-purpose venues like Arts at the Armory)
NON_MUSIC_KEYWORDS = [
    # Dance classes (not concerts)
    "swing", "salsa class", "latin dance class", "dance class", "dance lesson",
    "ballroom", "tango class", "bachata class",
    # Markets and fairs
    "farmers market", "flea market", "craft fair", "bazaar", "holiday market",
    "artisan market", "vintage market",
    # Workshops and classes
    "workshop", "yoga", "meditation", "pilates", "fitness", "training session",
    "art class", "painting class", "pottery", "crafting",
    # Comedy and spoken word
    "comedy", "stand-up", "open mic comedy", "improv", "storytelling",
    "poetry slam", "poetry workshop", "the moth", "storyslam",
    # Sports and gaming
    "wrestling", "trivia", "game night", "bingo", "karaoke",
    "ttrpg", "rpg convention", "board game",
    # Meetings and community events
    "meeting", "club meeting", "networking", "mixer",
    "brunch", "breakfast", "luncheon",
    # Kids events (usually not concert listings)
    "kids", "children's", "family day", "storytime",
    # Wellness
    "wellness", "healing", "reiki", "sound bath",
]

# Keywords that indicate it IS a music event (override non-music if present)
MUSIC_KEYWORDS = [
    "concert", "live music", "band", "singer", "songwriter", "jazz",
    "rock", "punk", "metal", "folk", "blues", "reggae", "ska",
    "hip hop", "rap", "r&b", "soul", "funk", "electronic", "dj set",
    "orchestra", "symphony", "chamber", "quartet", "trio",
    "album release", "record release", "tour", "farewell show",
]


# Venue configurations - using venue websites
BOSTON_VENUES = {
    "royale": {
        "name": "Royale",
        "location": "Boston",
        "url": "https://royaleboston.com/events/",
        "capacity": 1200,
        "parser": "json_ld",
    },
    "sinclair": {
        "name": "The Sinclair",
        "location": "Cambridge",
        "url": "https://www.sinclaircambridge.com/events/",
        "capacity": 525,
        "parser": "sinclair",
    },
    "armory": {
        "name": "Arts at the Armory",
        "location": "Somerville",
        "url": "https://artsatthearmory.org/upcoming-events/",
        "capacity": 300,
        "parser": "json_ld",
    },
}


class AXSVenuesScraper(BaseScraper):
    """Scrape Boston venue websites for events."""

    @property
    def source_name(self) -> str:
        return "scrape:boston_venues"

    @property
    def url(self) -> str:
        return "https://roadrunnerboston.com"

    def fetch(self) -> List[Concert]:
        """Fetch concerts from Boston venue websites."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_boston_venues")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        all_concerts = []

        for venue_id, venue_config in BOSTON_VENUES.items():
            try:
                venue_concerts = self._scrape_venue(venue_id, venue_config)
                all_concerts.extend(venue_concerts)
                logger.info(f"[{self.source_name}] {venue_config['name']}: {len(venue_concerts)} events")
            except Exception as e:
                logger.warning(f"[{self.source_name}] Failed to scrape {venue_config['name']}: {e}")

        # Cache the results
        if all_concerts:
            save_cache("scrape_boston_venues", [c.to_dict() for c in all_concerts])

        self._log_fetch_complete(len(all_concerts))
        return all_concerts

    def _scrape_venue(self, venue_id: str, venue_config: Dict) -> List[Concert]:
        """Scrape events from a venue website."""
        concerts = []
        parser_type = venue_config.get("parser", "json_ld")

        try:
            soup = self._get_soup(venue_config["url"])

            if parser_type == "sinclair":
                concerts = self._parse_sinclair(soup, venue_id, venue_config)
            elif parser_type == "json_ld":
                concerts = self._parse_json_ld(soup, venue_id, venue_config)

            # Fallback to generic parsing if no results
            if not concerts:
                concerts = self._parse_event_page(soup, venue_id, venue_config)

        except Exception as e:
            logger.debug(f"Error scraping {venue_config['name']}: {e}")

        return concerts

    def _parse_sinclair(self, soup: BeautifulSoup, venue_id: str, venue_config: Dict) -> List[Concert]:
        """Parse events from The Sinclair's event page format.

        The Sinclair uses semantic HTML without class-based event markers:
        - Links to /events/detail/[ID] indicate event items
        - h3/h4 tags contain artist names
        - Date/time in format "Sun, Jan 18, 2026 Doors 6:30 PM"
        - Age requirement as plain text ("All Ages", "18 & Over", "21 & Over")
        """
        concerts = []
        current_year = datetime.now().year
        seen_events = set()  # Track by artist+date to avoid duplicates

        # Find all links to event detail pages
        event_links = soup.find_all("a", href=re.compile(r"/events/detail/"))

        for link in event_links:
            try:
                # Get the parent container that holds event info
                # Go up to find a container with the full event details
                container = link.find_parent("div")
                if not container:
                    continue

                # Look for a larger container that has the date info
                # Keep going up until we find one with date text
                text = container.get_text()
                while container and not re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2}', text):
                    parent = container.find_parent("div")
                    if parent:
                        container = parent
                        text = container.get_text()
                    else:
                        break

                if not container:
                    continue

                full_text = container.get_text()

                # Extract artist name from h3 or h4
                artist_elem = container.find(["h3", "h4"])
                if not artist_elem:
                    # Try the link text itself
                    artist_elem = link

                event_name = self._clean_text(artist_elem.get_text())
                if not event_name or len(event_name) < 2:
                    continue

                # Skip non-event links (like "Buy Tickets")
                if event_name.lower() in ["buy tickets", "more info", "details", "view"]:
                    continue

                # Extract date - format: "Sun, Jan 18, 2026" or "Jan 18, 2026"
                date_match = re.search(
                    r'(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)?,?\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+(\d{1,2}),?\s*(\d{4})?',
                    full_text
                )
                if not date_match:
                    continue

                month_str = date_match.group(1)
                day = date_match.group(2)
                year = date_match.group(3) or str(current_year)
                date_text = f"{month_str} {day}, {year}"

                event_date = parse_date(date_text, default_year=current_year)
                if not event_date:
                    continue

                # Skip past events
                if event_date.date() < datetime.now().date():
                    continue

                # Create unique key to avoid duplicates
                event_key = f"{event_name.lower()}_{event_date.date()}"
                if event_key in seen_events:
                    continue
                seen_events.add(event_key)

                # Extract time - format: "Doors 6:30 PM" or just "8:00 PM"
                show_time = "8pm"
                time_match = re.search(r'(?:Doors\s+)?(\d{1,2}):?(\d{2})?\s*(AM|PM|am|pm)', full_text)
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
                text_lower = full_text.lower()
                if "21 & over" in text_lower or "21+ " in text_lower or "21+" in text_lower:
                    age_req = "21+"
                elif "18 & over" in text_lower or "18+ " in text_lower or "18+" in text_lower:
                    age_req = "18+"
                elif "all ages" in text_lower:
                    age_req = "a/a"

                # Get supporting acts - look for additional h4 elements
                bands = self._parse_event_name(event_name)
                support_elems = container.find_all("h4")
                for elem in support_elems:
                    support_text = self._clean_text(elem.get_text())
                    if support_text and support_text != event_name:
                        # Check it's not a date or other metadata
                        if not re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', support_text):
                            support_bands = self._split_bands(support_text)
                            for band in support_bands:
                                if band and band not in bands:
                                    bands.append(band)

                concerts.append(Concert(
                    date=event_date,
                    venue_id=venue_id,
                    venue_name=venue_config["name"],
                    venue_location=venue_config["location"],
                    bands=bands,
                    age_requirement=age_req,
                    price_advance=None,
                    price_door=None,
                    time=show_time,
                    flags=[],
                    source=self.source_name,
                    source_url=venue_config["url"],
                    genre_tags=[]
                ))

            except Exception as e:
                logger.debug(f"Error parsing Sinclair event: {e}")
                continue

        return concerts

    def _parse_json_ld(self, soup: BeautifulSoup, venue_id: str, venue_config: Dict) -> List[Concert]:
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
                    if not isinstance(event, dict):
                        continue

                    event_type = event.get("@type", "")
                    if event_type not in ["Event", "MusicEvent", "Festival"]:
                        continue

                    name = event.get("name", "")
                    if not name:
                        continue

                    # Filter out non-music events for multi-purpose venues
                    if not self._is_music_event(name, venue_id):
                        continue

                    # Parse date
                    start_date = event.get("startDate")
                    if not start_date:
                        continue

                    try:
                        if "T" in str(start_date):
                            event_date = datetime.fromisoformat(start_date.replace("Z", "").split("+")[0])
                        else:
                            event_date = parse_date(start_date)
                    except ValueError:
                        event_date = parse_date(start_date)

                    if not event_date:
                        continue

                    # Skip past events
                    if event_date.date() < datetime.now().date():
                        continue

                    # Parse price
                    offers = event.get("offers", {})
                    if isinstance(offers, list):
                        offers = offers[0] if offers else {}
                    price = offers.get("price") or offers.get("lowPrice")
                    try:
                        price_advance = int(float(price)) if price else None
                    except (ValueError, TypeError):
                        price_advance = None

                    # Parse time
                    show_time = "8pm"
                    if "T" in str(start_date):
                        try:
                            dt = datetime.fromisoformat(start_date.replace("Z", "").split("+")[0])
                            hour = dt.hour
                            if hour > 12:
                                show_time = f"{hour - 12}pm"
                            elif hour == 12:
                                show_time = "12pm"
                            elif hour == 0:
                                show_time = "12am"
                            else:
                                show_time = f"{hour}pm" if hour >= 6 else f"{hour}am"
                        except ValueError:
                            pass

                    bands = self._parse_event_name(name)

                    concerts.append(Concert(
                        date=event_date,
                        venue_id=venue_id,
                        venue_name=venue_config["name"],
                        venue_location=venue_config["location"],
                        bands=bands,
                        age_requirement="18+",
                        price_advance=price_advance,
                        price_door=None,
                        time=show_time,
                        flags=[],
                        source=self.source_name,
                        source_url=event.get("url", venue_config["url"]),
                        genre_tags=[]
                    ))

            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.debug(f"JSON-LD parse error: {e}")
                continue

        return concerts

    def _parse_event_page(self, soup: BeautifulSoup, venue_id: str, venue_config: Dict) -> List[Concert]:
        """Parse events from common HTML patterns."""
        concerts = []

        # Look for event containers with common class patterns
        event_selectors = [
            "div.event-card",
            "div.event-item",
            "article.event",
            "div.eventitem",
            "li.event",
            "div[class*='event']",
        ]

        event_elements = []
        for selector in event_selectors:
            try:
                elements = soup.select(selector)
                if elements:
                    event_elements = elements
                    break
            except Exception:
                continue

        for element in event_elements:
            concert = self._parse_event_element(element, venue_id, venue_config)
            if concert:
                concerts.append(concert)

        return concerts

    def _parse_event_element(self, element, venue_id: str, venue_config: Dict) -> Optional[Concert]:
        """Parse a single event element."""
        try:
            # Find event name
            name_elem = element.find(["h2", "h3", "h4", "a"])
            if not name_elem:
                return None

            event_name = self._clean_text(name_elem.get_text())
            if not event_name or len(event_name) < 3:
                return None

            # Filter out non-music events for multi-purpose venues
            if not self._is_music_event(event_name, venue_id):
                return None

            # Find date
            date_text = ""
            date_elem = element.find(class_=re.compile(r"date|time", re.IGNORECASE))
            if date_elem:
                date_text = date_elem.get_text()

            # Also check time element
            time_elem = element.find("time")
            if time_elem:
                date_text = time_elem.get("datetime", "") or time_elem.get_text()

            event_date = parse_date(date_text) if date_text else None
            if not event_date:
                return None

            # Skip past events
            if event_date.date() < datetime.now().date():
                return None

            bands = self._parse_event_name(event_name)

            return Concert(
                date=event_date,
                venue_id=venue_id,
                venue_name=venue_config["name"],
                venue_location=venue_config["location"],
                bands=bands,
                age_requirement="18+",
                price_advance=None,
                price_door=None,
                time="8pm",
                flags=[],
                source=self.source_name,
                source_url=venue_config["url"],
                genre_tags=[]
            )

        except Exception as e:
            logger.debug(f"Error parsing event element: {e}")
            return None

    def _parse_event_name(self, name: str) -> List[str]:
        """Parse band names from event title."""
        # Remove common suffixes
        name = re.sub(r'\s*[-:]\s*(tour|live|concert|show|presents|tickets).*$', '', name, flags=re.IGNORECASE)
        name = re.sub(r'\s*\(.*?(tour|live|vip|meet|sold out).*?\)$', '', name, flags=re.IGNORECASE)

        # Split by common separators
        bands = self._split_bands(name)

        return bands if bands else [name.strip()]

    def _is_music_event(self, event_name: str, venue_id: str) -> bool:
        """Check if an event is likely a music performance.

        For multi-purpose venues like Arts at the Armory, we need to filter out
        non-music events since there's no downstream genre filtering.

        Returns True if the event appears to be music-related.
        """
        # For dedicated music venues, assume all events are music
        if venue_id not in ["armory"]:
            return True

        name_lower = event_name.lower()

        # First check for music keywords - if present, it's likely music
        for keyword in MUSIC_KEYWORDS:
            if keyword in name_lower:
                return True

        # Then check for non-music keywords
        for keyword in NON_MUSIC_KEYWORDS:
            if keyword in name_lower:
                logger.debug(f"Filtering out non-music event: {event_name} (matched: {keyword})")
                return False

        # Default to including the event if uncertain
        # Better to have some false positives than miss real concerts
        return True
