"""
Generate robots.txt for SEO.
"""

import logging
from pathlib import Path

from ..config import OUTPUT_DIR, SITE_URL

logger = logging.getLogger(__name__)


def generate_robots() -> None:
    """Generate robots.txt with sitemap reference."""
    content = f"""User-agent: *
Allow: /

Sitemap: {SITE_URL}/sitemap.xml
"""

    output_path = Path(OUTPUT_DIR) / "robots.txt"
    with open(output_path, "w") as f:
        f.write(content)

    logger.info("Generated robots.txt")
