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


# Venue configurations - using venue websites
BOSTON_VENUES = {
    "roadrunner": {
        "name": "Roadrunner",
        "location": "Boston",
        "url": "https://roadrunnerboston.com/events/",
        "capacity": 3500,
    },
    "royale": {
        "name": "Royale",
        "location": "Boston",
        "url": "https://royaleboston.com/events/",
        "capacity": 1200,
    },
    "bignightlive": {
        "name": "Big Night Live",
        "location": "Boston",
        "url": "https://bignightlive.com/events/",
        "capacity": 1500,
    },
    "sinclair": {
        "name": "The Sinclair",
        "location": "Cambridge",
        "url": "https://www.sinclaircambridge.com/events",
        "capacity": 525,
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

        try:
            soup = self._get_soup(venue_config["url"])

            # Try JSON-LD first (most reliable)
            json_ld_concerts = self._parse_json_ld(soup, venue_id, venue_config)
            concerts.extend(json_ld_concerts)

            # If no JSON-LD, try common event page patterns
            if not concerts:
                concerts = self._parse_event_page(soup, venue_id, venue_config)

        except Exception as e:
            logger.debug(f"Error scraping {venue_config['name']}: {e}")

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
