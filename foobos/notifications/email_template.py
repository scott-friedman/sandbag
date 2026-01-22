"""
Generate HTML email template for concert notifications.
"""

from datetime import datetime
from typing import List, Set

from ..models import Concert


def generate_email_html(
    concerts: List[Concert],
    new_concert_ids: Set[str],
    date_str: str = None
) -> str:
    """
    Generate HTML email with concert table.

    Args:
        concerts: All concerts to include in email
        new_concert_ids: IDs of newly added concerts (highlighted)
        date_str: Date string for subject (defaults to today)

    Returns:
        HTML string for email body
    """
    if date_str is None:
        date_str = datetime.now().strftime("%b %d, %Y")

    # Sort concerts by date
    sorted_concerts = sorted(concerts, key=lambda c: c.date)

    # Count new shows
    new_count = len(new_concert_ids)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>foobos Daily Update - {date_str}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.5;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
        }}
        h1 {{
            color: #1a1a1a;
            font-size: 24px;
            margin-bottom: 8px;
        }}
        .subtitle {{
            color: #666;
            margin-bottom: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th {{
            background: #f5f5f5;
            text-align: left;
            padding: 12px 8px;
            border-bottom: 2px solid #ddd;
            font-weight: 600;
        }}
        td {{
            padding: 10px 8px;
            border-bottom: 1px solid #eee;
            vertical-align: top;
        }}
        tr:hover {{
            background: #fafafa;
        }}
        .new-show {{
            background: #fffde7 !important;
        }}
        .new-badge {{
            display: inline-block;
            background: #ffc107;
            color: #333;
            font-size: 10px;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 3px;
            margin-right: 6px;
            text-transform: uppercase;
        }}
        .date-cell {{
            white-space: nowrap;
            font-weight: 500;
        }}
        .venue-cell {{
            color: #555;
        }}
        .venue-location {{
            color: #888;
            font-size: 12px;
        }}
        .artists-cell {{
            font-weight: 500;
        }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #888;
            font-size: 12px;
        }}
        .footer a {{
            color: #666;
        }}
        .empty-message {{
            text-align: center;
            color: #666;
            padding: 40px;
        }}
    </style>
</head>
<body>
    <h1>foobos Daily Update</h1>
    <p class="subtitle">{date_str} &middot; {len(sorted_concerts)} shows"""

    if new_count > 0:
        html += f" &middot; <strong>{new_count} new</strong>"

    html += "</p>"

    if not sorted_concerts:
        html += """
    <p class="empty-message">No upcoming shows found.</p>
"""
    else:
        html += """
    <table>
        <thead>
            <tr>
                <th>Date</th>
                <th>Venue</th>
                <th>Artist(s)</th>
            </tr>
        </thead>
        <tbody>
"""
        for concert in sorted_concerts:
            is_new = concert.id in new_concert_ids
            row_class = ' class="new-show"' if is_new else ''

            # Format date
            date_formatted = concert.date.strftime("%a %b %d")

            # Format artists
            artists = ", ".join(concert.bands) if concert.bands else "TBA"

            # New badge
            new_badge = '<span class="new-badge">New</span>' if is_new else ''

            html += f"""            <tr{row_class}>
                <td class="date-cell">{new_badge}{date_formatted}</td>
                <td class="venue-cell">
                    {concert.venue_name}
                    <div class="venue-location">{concert.venue_location}</div>
                </td>
                <td class="artists-cell">{artists}</td>
            </tr>
"""

        html += """        </tbody>
    </table>
"""

    html += f"""
    <div class="footer">
        <p>
            This email was sent by <a href="https://scott-friedman.github.io/foobos/">foobos</a>.
            View all shows at <a href="https://scott-friedman.github.io/foobos/">foobos</a>.
        </p>
    </div>
</body>
</html>
"""
    return html


def generate_email_subject(date_str: str = None, new_count: int = 0) -> str:
    """
    Generate email subject line.

    Args:
        date_str: Date string (defaults to today)
        new_count: Number of new shows

    Returns:
        Email subject string
    """
    if date_str is None:
        date_str = datetime.now().strftime("%b %d, %Y")

    subject = f"foobos Daily Update - {date_str}"
    if new_count > 0:
        subject += f" ({new_count} new)"

    return subject
