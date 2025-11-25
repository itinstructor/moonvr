import re
from flask import request
import logging


def validate_password(password):
    """
    Validate password meets requirements:
    - At least 8 characters
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one number
    Returns: (is_valid: bool, error_message: str)
    """
    if len(password) < 12:
        return False, "Password must be at least 12 characters long"
    if not re.search(r'[A-Z]', password):
        return False, "Password must contain at least one uppercase letter"
    if not re.search(r'[a-z]', password):
        return False, "Password must contain at least one lowercase letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    return True, ""


def get_client_ip():
    """Get client IP from request headers (respects proxies)."""
    hdr = request.headers.get
    for h in ("X-Real-Ip", "X-Real-IP", "X-Forwarded-For", "X-MS-Forwarded-Client-IP"):
        v = hdr(h)
        if v:
            return v.split(",")[0].strip()
    return request.environ.get("REMOTE_ADDR") or request.remote_addr


def log_login_attempt(username, success, user_agent=None):
    """Log login attempt to database."""
    from .models import LoginAttempt
    from database import db
    
    try:
        attempt = LoginAttempt(
            username=username,
            ip_address=get_client_ip(),
            success=success,
            user_agent=user_agent or request.headers.get('User-Agent', '')[:255]
        )
        db.session.add(attempt)
        db.session.commit()
    except Exception:
        logging.exception("Failed to log login attempt")
        db.session.rollback()


