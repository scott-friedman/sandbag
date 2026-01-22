"""
Configuration for foobos concert listing generator.
"""

import os
from pathlib import Path

# Load .env file if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, use system env vars

# Project root directory (parent of foobos package)
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# API Configuration
TICKETMASTER_API_KEY = os.environ.get("TICKETMASTER_API_KEY", "")
TICKETMASTER_BASE_URL = "https://app.ticketmaster.com/discovery/v2"

SEATGEEK_CLIENT_ID = os.environ.get("SEATGEEK_CLIENT_ID", "")
SEATGEEK_CLIENT_SECRET = os.environ.get("SEATGEEK_CLIENT_SECRET", "")
SEATGEEK_BASE_URL = "https://api.seatgeek.com/2"

EVENTBRITE_API_KEY = os.environ.get("EVENTBRITE_API_KEY", "")
EVENTBRITE_BASE_URL = "https://www.eventbriteapi.com/v3"

# Boston metro area - DMA code 246
BOSTON_DMA = "246"
BOSTON_LATLONG = (42.3601, -71.0589)
SEARCH_RADIUS_MILES = 50

# Genre keywords for filtering punk/hardcore/metal shows
PUNK_GENRES = [
    "punk", "hardcore", "post-hardcore", "metalcore", "metal",
    "ska", "oi", "crust", "grindcore", "powerviolence", "noise rock",
    "post-punk", "garage", "psychobilly", "street punk", "pop punk",
    "emo", "screamo", "thrash", "crossover", "d-beat", "anarcho-punk",
    "horror punk", "surf punk", "skate punk", "melodic hardcore"
]

# Genre keywords to exclude (too mainstream/different genre)
EXCLUDE_GENRES = [
    "country", "jazz", "classical", "r&b", "hip-hop", "rap",
    "edm", "electronic", "dance", "house", "techno", "trance",
    "latin", "reggaeton", "k-pop", "pop"
]

# Priority bands - always include these Boston/punk staples
PRIORITY_BANDS = [
    "Converge", "Have Heart", "Bane", "American Nightmare",
    "Dropkick Murphys", "Street Dogs", "Slapshot", "DYS", "SSD",
    "Gang Green", "The FUs", "Negative FX", "Jerry's Kids",
    "Mission of Burma", "Pixies", "Dinosaur Jr.", "Sebadoh",
    "Cave In", "Doomriders", "Defeater", "Shipwreck", "Fiddlehead",
    "The Hope Conspiracy", "Panic", "Righteous Jams", "Mental",
    "Big D and the Kids Table", "The Mighty Mighty Bosstones",
    "Bim Skala Bim", "Westbound Train", "Pile", "Krill", "Kal Marks",
    "Speedy Ortiz", "Palehound", "Vein.fm", "Knocked Loose"
]

# Scraper URLs
SCRAPE_SOURCES = {
    "safe_in_a_crowd": "https://safeinacrowd.com/",
    "do617": "https://do617.com/",
    "ohmyrockness": "https://boston.ohmyrockness.com/",
    "middle_east": "https://www.mideastoffers.com/",
    "sinclair": "https://www.sinclaircambridge.com/events",
    "paradise": "https://crossroadspresents.com/pages/paradise-rock-club",
    "brighton": "https://www.brightonmusichall.com/events",
    "great_scott": "https://www.greatscottboston.com/events",
}

# Venue ID mappings (our slug -> Ticketmaster venue ID)
VENUE_TICKETMASTER_IDS = {
    "paradise": "KovZpZAEekIA",
    "hob": "KovZpZAFnIEA",
    "royale": "KovZpZAFaJkA",
    "sinclair": "KovZpZAJFl6A",
    "brighton": "KovZpZAJFkkA",
    "middleeast": "KovZpZAFaEJA",
    "orpheum": "KovZpZAFaE7A",
    "palladium": "KovZpZAEdFIA",
}

# Output configuration (relative to project root)
OUTPUT_DIR = str(PROJECT_ROOT)
DATA_DIR = str(PROJECT_ROOT / "data")
CACHE_DIR = str(PROJECT_ROOT / "data" / "cache")
CACHE_TTL_HOURS = 12

# How many weeks ahead to fetch/display (10 months ≈ 43 weeks)
WEEKS_AHEAD = 43

# Site branding
SITE_NAME = "foobos"
SITE_TITLE = "foobos"
SITE_DESCRIPTION = "Boston area punk/hardcore/ska/indie shows"
SITE_EMAIL = "foobos@example.com"

# Analytics Configuration
# Set your Google Analytics 4 Measurement ID (format: G-XXXXXXXXXX)
# Get this from: Google Analytics > Admin > Data Streams > Web > Measurement ID
GA4_MEASUREMENT_ID = os.environ.get("GA4_MEASUREMENT_ID", "G-Z6XNS24W12")

# Enable/disable analytics (set to False to disable tracking)
ANALYTICS_ENABLED = bool(GA4_MEASUREMENT_ID)
