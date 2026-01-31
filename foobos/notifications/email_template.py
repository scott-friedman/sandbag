"""
Generate HTML email template for concert notifications.
"""

from datetime import datetime, timedelta
from typing import List

from ..models import Concert


def generate_email_html(
    concerts: List[Concert],
    mode: str = "new",
    date_str: str = None,
    total_count: int = None
) -> str:
    """
    Generate HTML email with concert table.

    Args:
        concerts: Concerts to include in email
        mode: "new" for new concerts only, "upcoming" for next 3 days fallback
        date_str: Date string for subject (defaults to today)
        total_count: Total number of concerts in the system

    Returns:
        HTML string for email body
    """
    if date_str is None:
        date_str = datetime.now().strftime("%b %d, %Y")

    # Sort concerts by date
    sorted_concerts = sorted(concerts, key=lambda c: c.date)

    # Generate subtitle based on mode
    if mode == "new":
        title = "New Shows"
        new_count = len(sorted_concerts)
        subtitle = f"{new_count} new show{'s' if new_count != 1 else ''} added"
        if total_count is not None:
            subtitle += f" &middot; {total_count:,} total shows listed"
    else:
        # Upcoming mode - show date range
        today = datetime.now().date()
        end_date = today + timedelta(days=3)
        subtitle = f"No new shows today &middot; Here's what's coming up ({today.strftime('%b %d')} - {end_date.strftime('%b %d')})"
        title = "Upcoming Shows"

    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>foobos - {title}</title>
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
    <h1>foobos - {title}</h1>
    <p class="subtitle">{subtitle}</p>"""

    if not sorted_concerts:
        if mode == "new":
            html += """
    <p class="empty-message">No new shows found.</p>
"""
        else:
            html += """
    <p class="empty-message">No shows in the next 3 days.</p>
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
            # Format date
            date_formatted = concert.date.strftime("%a %b %d")

            # Format artists
            artists = ", ".join(concert.bands) if concert.bands else "TBA"

            html += f"""            <tr>
                <td class="date-cell">{date_formatted}</td>
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


def generate_email_subject(mode: str = "new", count: int = 0, date_str: str = None, total_count: int = None) -> str:
    """
    Generate email subject line.

    Args:
        mode: "new" for new concerts, "upcoming" for next 3 days fallback
        count: Number of shows
        date_str: Date string (defaults to today)
        total_count: Total number of concerts in the system

    Returns:
        Email subject string
    """
    if date_str is None:
        date_str = datetime.now().strftime("%b %d")

    if mode == "new":
        total_str = f", {total_count:,} total" if total_count is not None else ""
        if count == 1:
            return f"foobos: 1 new show added{total_str} ({date_str})"
        else:
            return f"foobos: {count} new shows added{total_str} ({date_str})"
    else:
        return f"foobos: Upcoming shows ({date_str})"
