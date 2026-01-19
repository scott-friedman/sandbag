"""
Generate clubs.html - venue directory page.
"""

import json
import logging
from pathlib import Path

from ..config import OUTPUT_DIR, DATA_DIR

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

    html = '''<!DOCTYPE html>
<html>
<head>
<title>foobos - Club Directory</title>
</head>
<body bgcolor="#FFFFFF" text="#000000" link="#0000FF" vlink="#800080">

<h2><i>Club Directory</i></h2>

<p><a href="list.html">Back to The List</a></p>

<hr>

<p>
Venues that frequently book punk, hardcore, and metal shows in the Greater Boston area.
</p>

'''

    for venue in venues:
        venue_id = venue.get("id", "")
        name = venue.get("name", "Unknown Venue")
        location = venue.get("location", "")
        address = venue.get("address", "")
        phone = venue.get("phone", "")
        website = venue.get("website", "")
        capacity = venue.get("capacity", "")
        notes = venue.get("notes", "")

        html += f'<p><a name="{venue_id}"><b>{name}</b></a>'
        if location:
            html += f", {location}"
        html += "<br>\n"

        if address:
            html += f"&nbsp;&nbsp;&nbsp;{address}<br>\n"

        details = []
        if phone:
            details.append(phone)
        if capacity:
            details.append(f"Capacity: {capacity}")

        if details:
            html += f"&nbsp;&nbsp;&nbsp;{' | '.join(details)}<br>\n"

        if website:
            html += f'&nbsp;&nbsp;&nbsp;<a href="{website}">{website}</a><br>\n'

        if notes:
            html += f"&nbsp;&nbsp;&nbsp;<i>{notes}</i><br>\n"

        html += "</p>\n\n"

    html += '''<hr>

<p><a href="list.html">Back to The List</a></p>

</body>
</html>
'''

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
