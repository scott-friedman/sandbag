#!/usr/bin/env python3
"""
Quick test script to evaluate SeatGeek API coverage vs existing data sources.

Usage:
    export SEATGEEK_CLIENT_ID="your_client_id"
    python test_seatgeek.py
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from foobos.config import (
    SEATGEEK_CLIENT_ID,
    SEATGEEK_BASE_URL,
    BOSTON_LATLONG,
    SEARCH_RADIUS_MILES,
    WEEKS_AHEAD,
    DATA_DIR,
)
from foobos.fetchers.seatgeek import SeatGeekFetcher
from foobos.utils.cache import clear_cache


def test_seatgeek_api():
    """Test SeatGeek API and analyze results."""

    print("=" * 70)
    print("SeatGeek API Test")
    print("=" * 70)

    # Check for API key
    if not SEATGEEK_CLIENT_ID:
        print("\nERROR: SEATGEEK_CLIENT_ID environment variable not set.")
        print("\nTo set it, run:")
        print('  export SEATGEEK_CLIENT_ID="your_client_id"')
        print("\nYou can get a client ID from: https://seatgeek.com/account/develop")
        return 1

    print(f"\nClient ID: {SEATGEEK_CLIENT_ID[:8]}...")
    print(f"API Base URL: {SEATGEEK_BASE_URL}")
    print(f"Search Location: Boston ({BOSTON_LATLONG[0]}, {BOSTON_LATLONG[1]})")
    print(f"Search Radius: {SEARCH_RADIUS_MILES} miles")
    print(f"Date Range: Today to {WEEKS_AHEAD} weeks ahead")

    # Clear SeatGeek cache to get fresh data
    cache_file = Path(DATA_DIR) / "cache" / "seatgeek_boston.json"
    if cache_file.exists():
        print(f"\nClearing cached SeatGeek data...")
        cache_file.unlink()

    # Fetch from SeatGeek
    print("\n" + "-" * 70)
    print("Fetching events from SeatGeek...")
    print("-" * 70)

    fetcher = SeatGeekFetcher()
    concerts = fetcher.fetch()

    print(f"\nTotal concerts fetched: {len(concerts)}")

    if not concerts:
        print("\nNo concerts returned. Check your API credentials or try again later.")
        return 1

    # Analyze results
    print("\n" + "-" * 70)
    print("SeatGeek Data Analysis")
    print("-" * 70)

    # By venue
    venues = defaultdict(int)
    for c in concerts:
        venues[c.venue_name] += 1

    print(f"\nUnique venues: {len(venues)}")
    print("\nTop 20 venues by event count:")
    for venue, count in sorted(venues.items(), key=lambda x: -x[1])[:20]:
        print(f"  {count:3d}  {venue}")

    # By genre
    genres = defaultdict(int)
    for c in concerts:
        for g in c.genre_tags:
            genres[g] += 1

    print(f"\nGenre tags found: {len(genres)}")
    if genres:
        print("\nTop 20 genres by frequency:")
        for genre, count in sorted(genres.items(), key=lambda x: -x[1])[:20]:
            print(f"  {count:3d}  {genre}")

    # Date distribution
    dates = defaultdict(int)
    for c in concerts:
        dates[c.date.strftime("%Y-%m")] += 1

    print("\nEvents by month:")
    for month, count in sorted(dates.items()):
        print(f"  {month}: {count}")

    # Sample events
    print("\n" + "-" * 70)
    print("Sample Events (first 15)")
    print("-" * 70)
    for c in concerts[:15]:
        bands = ", ".join(c.bands[:3])
        if len(c.bands) > 3:
            bands += f" +{len(c.bands) - 3} more"
        price = c.price_display if c.price_advance else "TBA"
        print(f"  {c.date.strftime('%b %d')} - {bands}")
        print(f"           @ {c.venue_name}, {c.venue_location}")
        print(f"           {price} | {c.time} | {c.age_requirement}")
        if c.genre_tags:
            print(f"           Genres: {', '.join(c.genre_tags[:5])}")
        print()

    # Compare with existing data if available
    print("\n" + "-" * 70)
    print("Comparison with Existing Data")
    print("-" * 70)

    processed_path = Path(DATA_DIR) / "processed_concerts.json"
    if processed_path.exists():
        from foobos.models import Concert
        with open(processed_path) as f:
            existing_data = json.load(f)
        existing = [Concert.from_dict(d) for d in existing_data]

        print(f"\nExisting processed concerts: {len(existing)}")

        # Count by source
        sources = defaultdict(int)
        for c in existing:
            sources[c.source] += 1

        print("\nExisting data by source:")
        for source, count in sorted(sources.items(), key=lambda x: -x[1]):
            print(f"  {count:4d}  {source}")

        # Find potential new events from SeatGeek
        existing_keys = set()
        for c in existing:
            # Create a key based on date + venue + headliner
            key = (c.date.strftime("%Y-%m-%d"), c.venue_id, c.bands[0].lower() if c.bands else "")
            existing_keys.add(key)

        sg_keys = set()
        new_events = []
        for c in concerts:
            key = (c.date.strftime("%Y-%m-%d"), c.venue_id, c.bands[0].lower() if c.bands else "")
            sg_keys.add(key)
            if key not in existing_keys:
                new_events.append(c)

        overlap = len(sg_keys & existing_keys)

        print(f"\nSeatGeek events: {len(concerts)}")
        print(f"Overlap with existing: {overlap}")
        print(f"Potentially new events: {len(new_events)}")

        if new_events:
            print("\nSample of potentially new events from SeatGeek:")
            for c in new_events[:10]:
                bands = ", ".join(c.bands[:2])
                print(f"  {c.date.strftime('%b %d')} - {bands} @ {c.venue_name}")

        # Venue coverage comparison
        existing_venues = set(c.venue_id for c in existing)
        sg_venues = set(c.venue_id for c in concerts)

        new_venues = sg_venues - existing_venues
        if new_venues:
            print(f"\nNew venues from SeatGeek ({len(new_venues)}):")
            for v in sorted(new_venues)[:15]:
                count = sum(1 for c in concerts if c.venue_id == v)
                venue_name = next((c.venue_name for c in concerts if c.venue_id == v), v)
                print(f"  {count:3d}  {venue_name}")
    else:
        print("\nNo existing processed data found for comparison.")
        print("Run 'python main.py all' first to generate comparison data.")

    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)

    return 0


if __name__ == "__main__":
    sys.exit(test_seatgeek_api())
