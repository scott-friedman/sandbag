"""
Concert data model.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import hashlib


@dataclass
class Concert:
    """Represents a single concert/show."""

    date: datetime
    venue_id: str
    venue_name: str
    venue_location: str  # "Cambridge", "Boston", etc.
    bands: List[str]  # Ordered list, headliner first

    # Optional fields
    age_requirement: str = "a/a"  # "a/a", "18+", "21+"
    price_advance: Optional[int] = None
    price_door: Optional[int] = None
    time: str = "8pm"
    flags: List[str] = field(default_factory=list)  # ["@", "$", "*"]
    source: str = ""  # "ticketmaster", "scrape:safe_in_a_crowd", etc.
    source_url: Optional[str] = None
    genre_tags: List[str] = field(default_factory=list)

    # Generated fields
    id: str = field(default="", init=False)
    last_updated: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Generate unique ID after initialization."""
        if not self.id:
            self.id = self._generate_id()

    def _generate_id(self) -> str:
        """Generate unique ID from date + venue + headliner."""
        date_str = self.date.strftime("%Y-%m-%d")
        headliner = self.bands[0] if self.bands else "unknown"
        unique_str = f"{date_str}|{self.venue_id}|{headliner}".lower()
        return hashlib.md5(unique_str.encode()).hexdigest()[:12]

    @property
    def day_of_week(self) -> str:
        """Return abbreviated day of week (Mon, Tue, etc.)."""
        return self.date.strftime("%a")

    @property
    def date_display(self) -> str:
        """Return formatted date for display (e.g., 'Fri Jan 24')."""
        return self.date.strftime("%a %b %-d")

    @property
    def price_display(self) -> str:
        """Return formatted price string (e.g., '$25/$30')."""
        if self.price_advance and self.price_door:
            return f"${self.price_advance}/${self.price_door}"
        elif self.price_advance:
            return f"${self.price_advance}"
        elif self.price_door:
            return f"${self.price_door}"
        return ""

    @property
    def headliner(self) -> str:
        """Return the headlining band."""
        return self.bands[0] if self.bands else ""

    @property
    def support(self) -> List[str]:
        """Return support bands (all except headliner)."""
        return self.bands[1:] if len(self.bands) > 1 else []

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "date": self.date.isoformat(),
            "day_of_week": self.day_of_week,
            "venue": {
                "id": self.venue_id,
                "name": self.venue_name,
                "location": self.venue_location
            },
            "bands": self.bands,
            "age_requirement": self.age_requirement,
            "price": {
                "advance": self.price_advance,
                "door": self.price_door,
                "display": self.price_display
            },
            "time": self.time,
            "flags": self.flags,
            "source": self.source,
            "source_url": self.source_url,
            "genre_tags": self.genre_tags,
            "last_updated": self.last_updated.isoformat()
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Concert":
        """Create Concert from dictionary."""
        venue = data.get("venue", {})
        price = data.get("price", {})

        concert = cls(
            date=datetime.fromisoformat(data["date"]),
            venue_id=venue.get("id", ""),
            venue_name=venue.get("name", ""),
            venue_location=venue.get("location", ""),
            bands=data.get("bands", []),
            age_requirement=data.get("age_requirement", "a/a"),
            price_advance=price.get("advance"),
            price_door=price.get("door"),
            time=data.get("time", "8pm"),
            flags=data.get("flags", []),
            source=data.get("source", ""),
            source_url=data.get("source_url"),
            genre_tags=data.get("genre_tags", [])
        )
        concert.id = data.get("id", concert._generate_id())
        if "last_updated" in data:
            concert.last_updated = datetime.fromisoformat(data["last_updated"])
        return concert
