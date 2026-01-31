"""
Generate index.html - simple landing page matching foopee.com style.
"""

import logging
import shutil
from pathlib import Path

from ..config import OUTPUT_DIR, PROJECT_ROOT, SITE_URL, SITE_NAME
from .helpers import html_header, html_footer

logger = logging.getLogger(__name__)


def generate_landing_page() -> None:
    """Generate the simple index.html landing page."""

    # WebSite structured data
    structured_data = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": SITE_NAME,
        "url": SITE_URL,
        "description": "Boston area concert listings and live music guide"
    }

    html = html_header(
        title="foobos",
        description="foobos - Boston area concert listings and live music guide",
        canonical_url=f"{SITE_URL}/index.html",
        structured_data=structured_data
    )
    html += '''
<center>

<br><br><br><br><br>
<font size=+10 face="arial black,helvetica">foobos</font>

<br><br>
<font face="arial black,helvetica">
[ <a href="list.html">shows</a> ] <br>
[ <a href="fool.html">what is foobos?</a> ] <br>
</font>

</center>

'''
    html += html_footer()

    output_path = Path(OUTPUT_DIR) / "index.html"
    with open(output_path, "w") as f:
        f.write(html)

    logger.info("Generated index.html (landing page)")

    # Generate fool.html - in-sane.JPG on black background
    # This page uses custom styling so we build it manually but still include analytics
    from ..config import GA4_MEASUREMENT_ID, ANALYTICS_ENABLED

    analytics_script = ""
    if ANALYTICS_ENABLED and GA4_MEASUREMENT_ID:
        analytics_script = f'''
<!-- Google Analytics 4 -->
<script async src="https://www.googletagmanager.com/gtag/js?id={GA4_MEASUREMENT_ID}"></script>
<script>
  window.dataLayer = window.dataLayer || [];
  function gtag(){{dataLayer.push(arguments);}}
  gtag('js', new Date());
  gtag('config', '{GA4_MEASUREMENT_ID}');
</script>
'''

    fool_html = f'''<!DOCTYPE html>
<html>
<head>
<title>what is foobos?</title>{analytics_script}
<style>
html, body {{
  background: #000000;
  margin: 0;
  padding: 0;
  min-height: 100%;
  width: 100%;
}}
body {{
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
}}
img {{
  max-width: 100%;
  max-height: 100vh;
  width: auto;
  height: auto;
}}
</style>
</head>
<body>
<img src="in-sane.JPG" alt="SANE">
</body>
</html>
'''

    fool_path = Path(OUTPUT_DIR) / "fool.html"
    with open(fool_path, "w") as f:
        f.write(fool_html)

    logger.info("Generated fool.html")

    # Copy in-sane.JPG to output directory (skip if same location)
    src_img = Path(PROJECT_ROOT) / "in-sane.JPG"
    dst_img = Path(OUTPUT_DIR) / "in-sane.JPG"
    if src_img.exists() and src_img.resolve() != dst_img.resolve():
        shutil.copy2(src_img, dst_img)
        logger.info("Copied in-sane.JPG to output")
