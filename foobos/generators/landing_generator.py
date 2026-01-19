"""
Generate index.html - simple landing page matching foopee.com style.
"""

import logging
from pathlib import Path

from ..config import OUTPUT_DIR

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
[ <a href="list.html">the list</a> ]<br>
[ <a href="by-date.0.html">concerts by date</a> ]<br>
[ <a href="by-band.html">concerts by band</a> ]<br>
[ <a href="by-club.html">concerts by venue</a> ]
</div>

</body>
</html>
'''

    output_path = Path(OUTPUT_DIR) / "index.html"
    with open(output_path, "w") as f:
        f.write(html)

    logger.info("Generated index.html (landing page)")
