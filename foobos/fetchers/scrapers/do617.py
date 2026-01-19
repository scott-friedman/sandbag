"""
Scraper for Do617 - Boston event aggregator.
https://do617.com/
"""

from datetime import datetime
from typing import List, Optional
import logging
import re

from bs4 import BeautifulSoup

from .base import BaseScraper
from ...models import Concert
from ...utils import get_cached, save_cache, parse_date
from ...config import PUNK_GENRES

logger = logging.getLogger(__name__)


class Do617Scraper(BaseScraper):
    """Scrape Do617 for Boston concerts."""

    @property
    def source_name(self) -> str:
        return "scrape:do617"

    @property
    def url(self) -> str:
        return "https://do617.com/events/category/music"

    def fetch(self) -> List[Concert]:
        """Fetch concerts from Do617."""
        self._log_fetch_start()

        # Check cache first
        cached = get_cached("scrape_do617")
        if cached:
            logger.info(f"[{self.source_name}] Using cached data ({len(cached)} events)")
            return [Concert.from_dict(c) for c in cached]

        concerts = []
        try:
            soup = self._get_soup()
            concerts = self._parse_listings(soup)

            # Cache the results
            save_cache("scrape_do617", [c.to_dict() for c in concerts])
            self._log_fetch_complete(len(concerts))

        except Exception as e:
            self._log_fetch_error(e)

        return concerts

    def _parse_listings(self, soup: BeautifulSoup) -> List[Concert]:
        """Parse event listings from Do617."""
        concerts = []

        # Do617 uses event cards/listings
        # Look for common event container patterns
        event_containers = (
            soup.find_all("div", class_=re.compile(r"event", re.I)) or
            soup.find_all("article", class_=re.compile(r"event", re.I)) or
            soup.find_all("li", class_=re.compile(r"event", re.I))
        )

        for container in event_containers:
            concert = self._parse_event_container(container)
            if concert and self._is_punk_related(concert):
                concerts.append(concert)

        return concerts

    def _parse_event_container(self, container) -> Optional[Concert]:
        """Parse a single event container into a Concert."""
        try:
            # Extract event title (usually the bands)
            title_elem = (
                container.find("h2") or
                container.find("h3") or
                container.find(class_=re.compile(r"title", re.I))
            )
            if not title_elem:
                return None

            title = self._clean_text(title_elem.get_text())
            bands = self._split_bands(title)
            if not bands:
                return None

            # Extract date
            date_elem = container.find(class_=re.compile(r"date", re.I))
            date_str = self._clean_text(date_elem.get_text()) if date_elem else ""
            date = parse_date(date_str, default_year=datetime.now().year)
            if not date:
                return None

            # Extract venue
            venue_elem = container.find(class_=re.compile(r"venue|location", re.I))
            venue_name = self._clean_text(venue_elem.get_text()) if venue_elem else "Unknown Venue"

            # Extract location (city)
            venue_location = "Boston"
            if "cambridge" in venue_name.lower():
                venue_location = "Cambridge"
            elif "somerville" in venue_name.lower():
                venue_location = "Somerville"

            # Extract time
            time_elem = container.find(class_=re.compile(r"time", re.I))
            time_str = self._clean_text(time_elem.get_text()) if time_elem else ""
            time = self._parse_time(time_str)

            # Extract price
            price_elem = container.find(class_=re.compile(r"price|cost", re.I))
            price_str = self._clean_text(price_elem.get_text()) if price_elem else ""
            price_advance, price_door = self._parse_price(price_str)

            # Extract link
            link_elem = container.find("a", href=True)
            source_url = link_elem["href"] if link_elem else self.url
            if source_url and not source_url.startswith("http"):
                source_url = f"https://do617.com{source_url}"

            # Generate venue ID
            venue_id = self._generate_venue_id(venue_name)

            return Concert(
                date=date,
                venue_id=venue_id,
                venue_name=venue_name,
                venue_location=venue_location,
                bands=bands,
                age_requirement="18+",  # Default
                price_advance=price_advance,
                price_door=price_door,
                time=time,
                flags=[],
                source=self.source_name,
                source_url=source_url,
                genre_tags=[]
            )

        except Exception as e:
            logger.debug(f"Error parsing event container: {e}")
            return None

    def _generate_venue_id(self, venue_name: str) -> str:
        """Generate a venue ID slug from name."""
        name_lower = venue_name.lower()

        venue_map = {
            "middle east": "middleeast",
            "paradise": "paradise",
            "sinclair": "sinclair",
            "great scott": "greatscott",
            "brighton music": "brighton",
            "house of blues": "hob",
            "royale": "royale",
            "orpheum": "orpheum",
            "midway": "midway",
            "o'brien": "obriens",
        }

        for pattern, slug in venue_map.items():
            if pattern in name_lower:
                return slug

        slug = name_lower.replace("'", "").replace(".", "").replace(",", "")
        slug = "_".join(slug.split())
        return slug[:30]

    def _is_punk_related(self, concert: Concert) -> bool:
        """Check if concert is potentially punk/hardcore related."""
        # Check bands against known punk bands
        from ...config import PRIORITY_BANDS
        for band in concert.bands:
            if band in PRIORITY_BANDS:
                return True

        # Check genre tags
        for tag in concert.genre_tags:
            if any(g in tag.lower() for g in PUNK_GENRES):
                return True

        # Check band names for punk-related keywords
        punk_keywords = ["punk", "hardcore", "metal", "thrash", "crust", "grind"]
        combined = " ".join(concert.bands).lower()
        if any(kw in combined for kw in punk_keywords):
            return True

        # Include by default (will be filtered later by deduplicator if duplicate)
        return True
