"""
Send email notifications via Gmail SMTP.
"""

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import List

from ..config import (
    SMTP_HOST,
    SMTP_PORT,
    GMAIL_ADDRESS,
    GMAIL_APP_PASSWORD,
    NOTIFY_RECIPIENTS,
    NOTIFICATIONS_ENABLED,
    DATA_DIR,
)
from ..models import Concert
from .diff_detector import detect_new_concerts, save_notified_ids
from .email_template import generate_email_html, generate_email_subject

logger = logging.getLogger(__name__)


def send_daily_notification(
    concerts: List[Concert],
    dry_run: bool = False
) -> bool:
    """
    Send daily email notification with concert listings.

    Args:
        concerts: List of concerts to include
        dry_run: If True, save preview HTML instead of sending

    Returns:
        True if successful, False otherwise
    """
    if not concerts:
        logger.warning("No concerts to send in notification")
        return False

    # Detect new concerts
    new_concerts, all_ids = detect_new_concerts(concerts)
    new_ids = {c.id for c in new_concerts}

    # Generate email content
    html_content = generate_email_html(concerts, new_ids)
    subject = generate_email_subject(new_count=len(new_ids))

    if dry_run:
        # Save preview instead of sending
        preview_path = Path(DATA_DIR) / "email_preview.html"
        preview_path.parent.mkdir(parents=True, exist_ok=True)
        with open(preview_path, "w") as f:
            f.write(html_content)
        logger.info(f"Email preview saved to {preview_path}")
        logger.info(f"Subject: {subject}")
        logger.info(f"Total shows: {len(concerts)}, New shows: {len(new_ids)}")
        return True

    # Check if notifications are enabled
    if not NOTIFICATIONS_ENABLED:
        logger.warning(
            "Notifications not enabled. Set GMAIL_ADDRESS, GMAIL_APP_PASSWORD, "
            "and NOTIFY_RECIPIENTS environment variables."
        )
        return False

    # Send email
    try:
        success = _send_email(subject, html_content)
        if success:
            # Save notified IDs on success
            save_notified_ids(all_ids)
            logger.info(f"Notification sent successfully to {NOTIFY_RECIPIENTS}")
        return success
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")
        return False


def _send_email(subject: str, html_content: str) -> bool:
    """
    Send email via Gmail SMTP.

    Args:
        subject: Email subject
        html_content: HTML email body

    Returns:
        True if sent successfully
    """
    # Parse recipients
    recipients = [r.strip() for r in NOTIFY_RECIPIENTS.split(",") if r.strip()]
    if not recipients:
        logger.error("No valid recipients configured")
        return False

    # Create message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = GMAIL_ADDRESS
    msg["To"] = ", ".join(recipients)

    # Attach HTML content
    html_part = MIMEText(html_content, "html")
    msg.attach(html_part)

    # Send via SMTP
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, recipients, msg.as_string())

        logger.info(f"Email sent to {len(recipients)} recipient(s)")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(
            f"SMTP authentication failed. Check GMAIL_ADDRESS and GMAIL_APP_PASSWORD. "
            f"Error: {e}"
        )
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending email: {e}")
        return False
