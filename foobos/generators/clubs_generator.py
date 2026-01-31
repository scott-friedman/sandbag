"""
Generate clubs.html - venue directory page.
"""

import json
import logging
from pathlib import Path

from ..config import OUTPUT_DIR, DATA_DIR, SITE_URL
from .helpers import html_header, html_footer
from ..utils.venue_registry import format_location

logger = logging.getLogger(__name__)


def generate_clubs_page() -> None:
    """Generate the clubs.html venue directory page."""
    # Load venue data
    venues_path = Path(DATA_DIR) / "venues.json"

    if venues_path.exists():
        with open(venues_path) as f:
            data = json.load(f)
            venues = data.get("venues", [])
    else:
        # Use default venue list if no data file
        venues = _get_default_venues()

    # Sort venues alphabetically
    venues = sorted(venues, key=lambda v: v.get("name", "").lower())

    # Separate active and closed venues for counting
    active_venues = [v for v in venues if v.get("status") != "closed"]
    closed_venues = [v for v in venues if v.get("status") == "closed"]

    # SEO description
    description = f"Directory of {len(active_venues)} live music venues across New England with addresses and info."

    # Build ItemList of MusicVenue schemas
    venue_items = []
    for i, venue in enumerate(venues):
        venue_item = {
            "@type": "ListItem",
            "position": i + 1,
            "item": {
                "@type": "MusicVenue",
                "name": venue.get("name", ""),
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": venue.get("address", ""),
                    "addressLocality": venue.get("location", "")
                }
            }
        }
        if venue.get("website"):
            venue_item["item"]["url"] = venue.get("website")
        venue_items.append(venue_item)

    structured_data = {
        "@context": "https://schema.org",
        "@type": "ItemList",
        "name": "Boston Live Music Venues",
        "numberOfItems": len(venues),
        "itemListElement": venue_items
    }

    html = html_header(
        title="foobos - Club Directory",
        description=description,
        canonical_url=f"{SITE_URL}/clubs.html",
        structured_data=structured_data
    )
    html += '''
<h2><i>Club Directory</i></h2>

<p><a href="list.html">Back to The List</a></p>

<hr>

<p>
Live music venues across New England.
</p>

'''

    for venue in venues:
        venue_id = venue.get("id", "")
        name = venue.get("name", "Unknown Venue")
        location = venue.get("location", "")
        state = venue.get("state", "MA")
        address = venue.get("address", "")
        phone = venue.get("phone", "")
        website = venue.get("website", "")
        capacity = venue.get("capacity", "")
        notes = venue.get("notes", "")
        status = venue.get("status", "")
        closed_year = venue.get("closed_year", "")

        # Format location with state for non-MA venues
        display_location = format_location(venue_id)
        if not display_location:
            # Fallback: add state suffix for non-MA
            if state and state != "MA" and location:
                display_location = f"{location}, {state}"
            else:
                display_location = location

        # Build venue name with closed indicator
        display_name = name
        if status == "closed":
            if closed_year:
                display_name = f"{name} (Closed {closed_year})"
            else:
                display_name = f"{name} (Closed)"

        html += f'<p><a name="{venue_id}"><b>{display_name}</b></a>'
        if display_location:
            html += f", {display_location}"
        html += "<br>\n"

        if address:
            html += f"&nbsp;&nbsp;&nbsp;{address}<br>\n"

        details = []
        if phone:
            details.append(phone)
        if capacity and status != "closed":
            details.append(f"Capacity: {capacity}")

        if details:
            html += f"&nbsp;&nbsp;&nbsp;{' | '.join(details)}<br>\n"

        if website and status != "closed":
            html += f'&nbsp;&nbsp;&nbsp;<a href="{website}">{website}</a><br>\n'

        if notes:
            html += f"&nbsp;&nbsp;&nbsp;<i>{notes}</i><br>\n"

        html += "</p>\n\n"

    html += '''<hr>

<p><a href="list.html">Back to The List</a></p>

'''
    html += html_footer()

    output_path = Path(OUTPUT_DIR) / "clubs.html"
    with open(output_path, "w") as f:
        f.write(html)

    logger.info(f"Generated clubs.html with {len(venues)} venues")


def _get_default_venues():
    """Return default venue list if no data file exists."""
    return [
        {
            "id": "middleeast",
            "name": "Middle East",
            "location": "Cambridge",
            "address": "472-480 Massachusetts Ave, Cambridge, MA 02139",
            "phone": "(617) 864-3278",
            "website": "https://mideastclub.com",
            "capacity": 575
        },
        {
            "id": "paradise",
            "name": "Paradise Rock Club",
            "location": "Boston",
            "address": "967 Commonwealth Ave, Boston, MA 02215",
            "phone": "(617) 562-8800",
            "website": "https://crossroadspresents.com/paradise-rock-club",
            "capacity": 933
        },
        {
            "id": "sinclair",
            "name": "The Sinclair",
            "location": "Cambridge",
            "address": "52 Church St, Cambridge, MA 02138",
            "phone": "(617) 547-5200",
            "website": "https://sinclaircambridge.com",
            "capacity": 525
        },
        {
            "id": "brightonmusichall",
            "name": "Brighton Music Hall",
            "location": "Allston",
            "address": "158 Brighton Ave, Allston, MA 02134",
            "phone": "(617) 779-0140",
            "website": "https://crossroadspresents.com/brighton-music-hall",
            "capacity": 450
        },
        {
            "id": "royale",
            "name": "Royale",
            "location": "Boston",
            "address": "279 Tremont St, Boston, MA 02116",
            "phone": "(617) 338-7699",
            "website": "https://royaleboston.com",
            "capacity": 1200
        },
        {
            "id": "palladium",
            "name": "The Palladium",
            "location": "Worcester",
            "address": "261 Main St, Worcester, MA 01608",
            "phone": "(508) 797-9696",
            "website": "https://thepalladium.net",
            "capacity": 2000
        },
        {
            "id": "obriens",
            "name": "O'Brien's Pub",
            "location": "Allston",
            "address": "3 Harvard Ave, Allston, MA 02134",
            "phone": "(617) 782-6245",
            "capacity": 100,
            "notes": "Key DIY/punk venue"
        },
        {
            "id": "midway",
            "name": "The Midway Cafe",
            "location": "Jamaica Plain",
            "address": "3496 Washington St, Jamaica Plain, MA 02130",
            "phone": "(617) 524-9038",
            "website": "https://midwaycafe.com",
            "capacity": 100,
            "notes": "Long-running punk/queer venue"
        },
        {
            "id": "oncesomerville",
            "name": "ONCE Somerville",
            "location": "Somerville",
            "address": "156 Highland Ave, Somerville, MA 02143",
            "website": "https://oncesomerville.com",
            "capacity": 400
        },
        {
            "id": "roadrunner",
            "name": "Roadrunner",
            "location": "Boston",
            "address": "89 Guest St, Boston, MA 02135",
            "website": "https://roadrunnerboston.com",
            "capacity": 3500
        },
        {
            "id": "houseoflues",
            "name": "House of Blues",
            "location": "Boston",
            "address": "15 Lansdowne St, Boston, MA 02215",
            "phone": "(888) 693-2583",
            "website": "https://houseofblues.com/boston",
            "capacity": 2425
        }
    ]
