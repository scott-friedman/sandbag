"""
Email notification system for foobos concert updates.
"""

from .email_sender import send_daily_notification
from .diff_detector import detect_new_concerts
from .email_template import generate_email_html

__all__ = [
    "send_daily_notification",
    "detect_new_concerts",
    "generate_email_html",
]
