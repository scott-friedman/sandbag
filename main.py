#!/usr/bin/env python3
"""
foobos - Boston Punk Concert Listing Generator

CLI entry point for fetching, processing, and generating concert listings.
"""

import argparse
import logging
import sys
from pathlib import Path
from datetime import datetime

from foobos.config import OUTPUT_DIR, DATA_DIR, CACHE_DIR
from foobos.fetchers import TicketmasterFetcher
from foobos.fetchers.scrapers import SafeInACrowdScraper, Do617Scraper, MiddleEastScraper, AXSVenuesScraper
from foobos.processors import normalize_concerts, deduplicate_concerts, filter_by_genre
from foobos.generators import generate_all_html
from foobos.utils.cache import clear_cache

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def setup_directories():
    """Ensure required directories exist."""
    for dir_path in [OUTPUT_DIR, DATA_DIR, CACHE_DIR]:
        Path(dir_path).mkdir(parents=True, exist_ok=True)


def cmd_fetch(args):
    """Fetch concert data from all sources."""
    logger.info("Starting fetch from all sources...")
    all_concerts = []

    # Ticketmaster API
    try:
        logger.info("Fetching from Ticketmaster...")
        tm_fetcher = TicketmasterFetcher()
        tm_concerts = tm_fetcher.fetch()
        logger.info(f"Ticketmaster: {len(tm_concerts)} concerts")
        all_concerts.extend(tm_concerts)
    except Exception as e:
        logger.error(f"Ticketmaster fetch failed: {e}")

    # Safe In A Crowd (critical for DIY shows)
    try:
        logger.info("Scraping Safe In A Crowd...")
        siac_scraper = SafeInACrowdScraper()
        siac_concerts = siac_scraper.fetch()
        logger.info(f"Safe In A Crowd: {len(siac_concerts)} concerts")
        all_concerts.extend(siac_concerts)
    except Exception as e:
        logger.error(f"Safe In A Crowd scrape failed: {e}")

    # Do617
    try:
        logger.info("Scraping Do617...")
        do617_scraper = Do617Scraper()
        do617_concerts = do617_scraper.fetch()
        logger.info(f"Do617: {len(do617_concerts)} concerts")
        all_concerts.extend(do617_concerts)
    except Exception as e:
        logger.error(f"Do617 scrape failed: {e}")

    # Middle East
    try:
        logger.info("Scraping Middle East...")
        me_scraper = MiddleEastScraper()
        me_concerts = me_scraper.fetch()
        logger.info(f"Middle East: {len(me_concerts)} concerts")
        all_concerts.extend(me_concerts)
    except Exception as e:
        logger.error(f"Middle East scrape failed: {e}")

    # AXS Venues (Roadrunner, Royale, Big Night Live, MGM Music Hall)
    try:
        logger.info("Scraping AXS venues (Roadrunner, Royale, Big Night Live, MGM)...")
        axs_scraper = AXSVenuesScraper()
        axs_concerts = axs_scraper.fetch()
        logger.info(f"AXS Venues: {len(axs_concerts)} concerts")
        all_concerts.extend(axs_concerts)
    except Exception as e:
        logger.error(f"AXS venues scrape failed: {e}")

    logger.info(f"Total raw concerts fetched: {len(all_concerts)}")

    # Save raw data
    import json
    raw_path = Path(DATA_DIR) / "raw_concerts.json"
    with open(raw_path, "w") as f:
        json.dump([c.to_dict() for c in all_concerts], f, indent=2)
    logger.info(f"Saved raw data to {raw_path}")

    return all_concerts


def cmd_process(args):
    """Process fetched concert data."""
    import json

    # Load raw data
    raw_path = Path(DATA_DIR) / "raw_concerts.json"
    if not raw_path.exists():
        logger.error("No raw data found. Run 'fetch' first.")
        return []

    logger.info("Loading raw concert data...")
    from foobos.models import Concert
    with open(raw_path) as f:
        raw_data = json.load(f)

    concerts = [Concert.from_dict(d) for d in raw_data]
    logger.info(f"Loaded {len(concerts)} raw concerts")

    # Normalize
    logger.info("Normalizing concerts...")
    concerts = normalize_concerts(concerts)

    # Deduplicate
    logger.info("Deduplicating concerts...")
    concerts = deduplicate_concerts(concerts)

    # Genre filter (non-strict by default)
    logger.info("Filtering by genre...")
    concerts = filter_by_genre(concerts, strict=args.strict if hasattr(args, 'strict') else False)

    logger.info(f"Processed concerts: {len(concerts)}")

    # Save processed data
    processed_path = Path(DATA_DIR) / "processed_concerts.json"
    with open(processed_path, "w") as f:
        json.dump([c.to_dict() for c in concerts], f, indent=2)
    logger.info(f"Saved processed data to {processed_path}")

    return concerts


def cmd_generate(args):
    """Generate HTML from processed concert data."""
    import json

    # Load processed data
    processed_path = Path(DATA_DIR) / "processed_concerts.json"
    if not processed_path.exists():
        logger.error("No processed data found. Run 'process' first.")
        return

    logger.info("Loading processed concert data...")
    from foobos.models import Concert
    with open(processed_path) as f:
        processed_data = json.load(f)

    concerts = [Concert.from_dict(d) for d in processed_data]
    logger.info(f"Loaded {len(concerts)} processed concerts")

    # Generate HTML
    logger.info("Generating HTML...")
    generate_all_html(concerts)

    logger.info(f"HTML files generated in {OUTPUT_DIR}")


def cmd_all(args):
    """Run full pipeline: fetch, process, generate."""
    logger.info("=" * 60)
    logger.info("foobos - Full Pipeline")
    logger.info(f"Started at {datetime.now().isoformat()}")
    logger.info("=" * 60)

    setup_directories()

    # Fetch
    concerts = cmd_fetch(args)
    if not concerts:
        logger.warning("No concerts fetched. Checking for cached data...")

    # Process
    concerts = cmd_process(args)
    if not concerts:
        logger.error("No concerts to process. Aborting.")
        return 1

    # Generate
    cmd_generate(args)

    logger.info("=" * 60)
    logger.info("Pipeline complete!")
    logger.info(f"Finished at {datetime.now().isoformat()}")
    logger.info("=" * 60)

    return 0


def cmd_clear_cache(args):
    """Clear the API response cache."""
    logger.info("Clearing cache...")
    clear_cache()
    logger.info("Cache cleared.")


def main():
    parser = argparse.ArgumentParser(
        description="foobos - Boston Punk Concert Listing Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py all              # Run full pipeline
  python main.py fetch            # Only fetch data
  python main.py process          # Only process data
  python main.py generate         # Only generate HTML
  python main.py clear-cache      # Clear API cache
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # fetch command
    fetch_parser = subparsers.add_parser("fetch", help="Fetch concert data from all sources")

    # process command
    process_parser = subparsers.add_parser("process", help="Process fetched concert data")
    process_parser.add_argument(
        "--strict",
        action="store_true",
        help="Use strict genre filtering (only explicit punk/hardcore)"
    )

    # generate command
    generate_parser = subparsers.add_parser("generate", help="Generate HTML from processed data")

    # all command (full pipeline)
    all_parser = subparsers.add_parser("all", help="Run full pipeline: fetch, process, generate")
    all_parser.add_argument(
        "--strict",
        action="store_true",
        help="Use strict genre filtering"
    )

    # clear-cache command
    cache_parser = subparsers.add_parser("clear-cache", help="Clear the API response cache")

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 1

    setup_directories()

    commands = {
        "fetch": cmd_fetch,
        "process": cmd_process,
        "generate": cmd_generate,
        "all": cmd_all,
        "clear-cache": cmd_clear_cache,
    }

    try:
        result = commands[args.command](args)
        return result if result is not None else 0
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        return 130
    except Exception as e:
        logger.exception(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
