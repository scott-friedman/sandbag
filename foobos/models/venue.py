"""
Venue data model.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Venue:
    """Represents a concert venue."""

    id: str  # Short slug (e.g., "paradise", "middleeast")
    name: str  # Display name (e.g., "Paradise Rock Club")
    location: str  # City (e.g., "Boston", "Cambridge")

    # Address info
    address: str = ""
    phone: str = ""
    website: str = ""

    # Venue details
    capacity: Optional[int] = None
    description: str = ""
    transit: str = ""  # Transit directions
    default_age: str = "18+"

    # External IDs for API matching
    ticketmaster_id: str = ""

    # For HTML generation
    html_anchor: str = field(default="", init=False)
    region: str = "Boston"  # For grouping in club directory

    def __post_init__(self):
        if not self.html_anchor:
            self.html_anchor = self.id

    @property
    def full_name(self) -> str:
        """Return full name with location (e.g., 'Paradise Rock Club, Boston')."""
        return f"{self.name}, {self.location}"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "location": self.location,
            "full_name": self.full_name,
            "address": self.address,
            "phone": self.phone,
            "website": self.website,
            "capacity": self.capacity,
            "description": self.description,
            "transit": self.transit,
            "default_age": self.default_age,
            "ticketmaster_id": self.ticketmaster_id,
            "html_anchor": self.html_anchor,
            "region": self.region
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Venue":
        """Create Venue from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            location=data["location"],
            address=data.get("address", ""),
            phone=data.get("phone", ""),
            website=data.get("website", ""),
            capacity=data.get("capacity"),
            description=data.get("description", ""),
            transit=data.get("transit", ""),
            default_age=data.get("default_age", "18+"),
            ticketmaster_id=data.get("ticketmaster_id", ""),
            region=data.get("region", "Boston")
        )
