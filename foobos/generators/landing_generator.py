"""
Generate index.html - simple landing page matching foopee.com style.
"""

import logging
import shutil
from pathlib import Path

from ..config import OUTPUT_DIR, PROJECT_ROOT

logger = logging.getLogger(__name__)


def generate_landing_page() -> None:
    """Generate the simple index.html landing page."""

    html = '''<!DOCTYPE html>
<html>
<head>
<title>foobos</title>
<style>
body {
  font-family: Arial, Helvetica, sans-serif;
  background: #FFFFFF;
  color: #000000;
  text-align: center;
  padding: 60px 20px;
  margin: 0;
}
.site-title {
  font-size: 56px;
  font-weight: bold;
  margin-bottom: 40px;
}
.nav-links {
  margin: 25px 0;
  line-height: 2.2;
}
.nav-links a {
  color: #0000FF;
  text-decoration: none;
  font-size: 16px;
}
.nav-links a:visited {
  color: #800080;
}
.nav-links a:hover {
  text-decoration: underline;
}
</style>
</head>
<body>

<div class="site-title">foobos</div>

<div class="nav-links">
[ <a href="list.html">shows</a> ]<br>
[ <a href="fool.html">what is foobos?</a> ]
</div>

</body>
</html>
'''

    output_path = Path(OUTPUT_DIR) / "index.html"
    with open(output_path, "w") as f:
        f.write(html)

    logger.info("Generated index.html (landing page)")

    # Generate fool.html - the-fool.png on black background
    fool_html = '''<!DOCTYPE html>
<html>
<head>
<title>what is foobos?</title>
<style>
html, body {
  background: #000000;
  margin: 0;
  padding: 0;
  min-height: 100%;
  width: 100%;
}
body {
  display: flex;
  justify-content: center;
  align-items: center;
  min-height: 100vh;
}
img {
  max-width: 100%;
  max-height: 100vh;
  width: auto;
  height: auto;
}
</style>
</head>
<body>
<img src="the-fool.png" alt="The Fool">
</body>
</html>
'''

    fool_path = Path(OUTPUT_DIR) / "fool.html"
    with open(fool_path, "w") as f:
        f.write(fool_html)

    logger.info("Generated fool.html")

    # Copy the-fool.png to output directory (skip if same location)
    src_img = Path(PROJECT_ROOT) / "the-fool.png"
    dst_img = Path(OUTPUT_DIR) / "the-fool.png"
    if src_img.exists() and src_img.resolve() != dst_img.resolve():
        shutil.copy2(src_img, dst_img)
        logger.info("Copied the-fool.png to output")
