"""
Cloudflare Turnstile integration for bot protection.

This module provides site-wide Turnstile verification with session-based caching
to avoid re-challenging verified users on every request.

Features:
- Automatic verification for all non-static routes
- Session-based verification caching (verified users aren't re-challenged)
- Configurable TTL for verification sessions
- Challenge page with auto-redirect after verification

Setup:
1. Get your Turnstile site key and secret key from Cloudflare dashboard
2. Add keys to .env file in project root:
   TURNSTILE_SITE_KEY=your-site-key
   TURNSTILE_SECRET_KEY=your-secret-key
   TURNSTILE_VERIFY_TTL=3600
3. Keys are automatically loaded from .env file

Usage:
    from turnstile import init_turnstile, turnstile_required
    
    # Initialize in your Flask app
    init_turnstile(app)
    
    # Middleware automatically protects all routes
"""
from typing import Dict, Optional
import os
import time
import logging
import requests
from functools import wraps
from flask import request, session, render_template_string, redirect, url_for
import ipaddress

# ------------- IP Whitelist for Turnstile bypass ------------------ #
# Populated exclusively from environment variables (no hardcoded defaults).
TURNSTILE_IP_WHITELIST = set()

# Optional CIDR ranges (populated from environment if provided)
TURNSTILE_IP_NETWORKS = []  # type: list[ipaddress._BaseNetwork]


def is_ip_whitelisted():
    ip = request.headers.get("CF-Connecting-IP") or \
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or \
        request.headers.get("X-Real-IP") or \
        request.remote_addr or "unknown"

    # Exact IP allowlist check
    if ip in TURNSTILE_IP_WHITELIST:
        return True

    # CIDR allowlist check
    try:
        ip_obj = ipaddress.ip_address(ip)
        for net in TURNSTILE_IP_NETWORKS:
            if ip_obj in net:
                return True
    except ValueError:
        # Not a valid IP string; treat as not whitelisted
        pass

    return False


# --------- Load environment variables from .env file ---------------- #
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        logging.info(f"Loaded environment variables from {env_path}")
except ImportError:
    logging.warning(
        "python-dotenv not installed. Using environment variables only.")

# --------------- Optional IP/CIDR allowlist from environment --------- #
def _parse_ip_allowlist_env(env_value: str):
    ips = set()
    nets = []
    for raw in env_value.split(','):
        item = raw.strip()
        if not item:
            continue
        try:
            # CIDR range
            if '/' in item:
                nets.append(ipaddress.ip_network(item, strict=False))
            else:
                # Normalize IP string
                ips.add(str(ipaddress.ip_address(item)))
        except ValueError:
            logging.warning(f"Invalid IP or CIDR in TURNSTILE_IP_WHITELIST: '{item}'")
    return ips, nets

# Load IPs/ranges from environment if set.
_env_ip_list = os.environ.get("TURNSTILE_IP_WHITELIST", "")
_env_ip_ranges = os.environ.get("TURNSTILE_IP_RANGES", "")
if _env_ip_list or _env_ip_ranges:
    env_combined = ",".join([s for s in (_env_ip_list, _env_ip_ranges) if s])
    _ips, _nets = _parse_ip_allowlist_env(env_combined)
    TURNSTILE_IP_WHITELIST.update(_ips)
    TURNSTILE_IP_NETWORKS.extend(_nets)

# --------------- Configuration from environment --------------------- #
TURNSTILE_SITE_KEY = os.environ.get("TURNSTILE_SITE_KEY", "")
TURNSTILE_SECRET_KEY = os.environ.get("TURNSTILE_SECRET_KEY", "")
TURNSTILE_VERIFY_TTL = int(os.environ.get(
    "TURNSTILE_VERIFY_TTL", "3600"))  # 1 hour default
TURNSTILE_ENABLED = bool(TURNSTILE_SITE_KEY and TURNSTILE_SECRET_KEY)

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

# Session key for storing verification timestamp
SESSION_VERIFIED_KEY = "_turnstile_verified_at"


def validate_turnstile(token: str, secret_key: str, remoteip: Optional[str] = None) -> Dict:
    """
    Validate a Turnstile token with Cloudflare's API.

    Returns dict with 'success' boolean and optional 'error-codes' list.
    """
    if not token or not secret_key:
        return {"success": False, "error-codes": ["missing-input"]}

    payload = {
        "secret": secret_key,
        "response": token,
    }
    if remoteip:
        payload["remoteip"] = remoteip

    try:
        resp = requests.post(TURNSTILE_VERIFY_URL, data=payload, timeout=10)
        if resp.ok:
            return resp.json()
        else:
            logging.warning(
                f"Turnstile API returned {resp.status_code}: {resp.text[:200]}")
            return {"success": False, "error-codes": ["api-error"]}
    except Exception as e:
        logging.exception(f"Turnstile validation failed: {e}")
        return {"success": False, "error-codes": ["network-error"]}


def is_turnstile_verified() -> bool:
    """Check if current session has a valid Turnstile verification or is whitelisted by IP."""
    if not TURNSTILE_ENABLED:
        return True  # If Turnstile not configured, allow all
    if is_ip_whitelisted():
        return True
    verified_at = session.get(SESSION_VERIFIED_KEY)
    if not verified_at:
        return False
    # Check if verification has expired
    age = time.time() - verified_at
    return age < TURNSTILE_VERIFY_TTL


def mark_turnstile_verified():
    """Mark current session as Turnstile-verified."""
    session[SESSION_VERIFIED_KEY] = time.time()
    session.permanent = True


def get_client_ip() -> str:
    """Extract client IP, respecting Cloudflare and proxy headers."""
    return (
        request.headers.get("CF-Connecting-IP") or
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip() or
        request.headers.get("X-Real-IP") or
        request.remote_addr or
        "unknown"
    )


# Challenge page HTML template
CHALLENGE_PAGE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Security Check</title>
    <script src="https://challenges.cloudflare.com/turnstile/v0/api.js" async defer></script>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            min-height: 100vh;
            margin: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .challenge-container {
            background: white;
            padding: 3rem;
            border-radius: 1rem;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            text-align: center;
            max-width: 500px;
        }
        h1 {
            color: #333;
            margin: 0 0 1rem 0;
            font-size: 1.8rem;
        }
        p {
            color: #666;
            margin: 0 0 2rem 0;
            line-height: 1.5;
        }
        .turnstile-widget {
            display: inline-block;
            margin: 1rem 0;
        }
        .error {
            color: #d32f2f;
            margin-top: 1rem;
            display: none;
        }
        .spinner {
            border: 3px solid #f3f3f3;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 40px;
            height: 40px;
            animation: spin 1s linear infinite;
            margin: 1rem auto;
            display: none;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
    </style>
</head>
<body>
    <div class="challenge-container">
        <h1>🔒 Security Verification</h1>
        <p>Please complete this quick security check to continue to the site.</p>
        
        <form id="challenge-form" method="POST" action="{{ verify_url }}">
            <input type="hidden" name="next" value="{{ next_url }}">
            <div class="turnstile-widget">
                <div class="cf-turnstile" 
                     data-sitekey="{{ site_key }}"
                     data-callback="onTurnstileSuccess"
                     data-error-callback="onTurnstileError"
                     data-theme="light"></div>
            </div>
        </form>
        
        <div class="spinner" id="spinner"></div>
        <div class="error" id="error">Verification failed. Please try again.</div>
    </div>

    <script>
        function onTurnstileSuccess(token) {
            document.getElementById('spinner').style.display = 'block';
            document.getElementById('challenge-form').submit();
        }
        
        function onTurnstileError(error) {
            console.error('Turnstile error:', error);
            document.getElementById('error').style.display = 'block';
        }
    </script>
</body>
</html>
"""


def init_turnstile(app):
    """
    Initialize Turnstile protection for the Flask app.
    Adds middleware to check verification on all requests.
    """
    if not TURNSTILE_ENABLED:
        logging.warning(
            "Turnstile NOT enabled (missing TURNSTILE_SITE_KEY or TURNSTILE_SECRET_KEY)")
        return

    logging.info(
        f"Turnstile enabled with site key: {TURNSTILE_SITE_KEY[:10]}...")

    # Get the application root for proper URL construction
    app_root = app.config.get('APPLICATION_ROOT', '').rstrip('/')

    # Add verification endpoint
    @app.route(f"{app_root}/turnstile/verify", methods=["POST"])
    def turnstile_verify():
        """Process Turnstile verification and redirect back."""
        token = request.form.get("cf-turnstile-response")
        next_url = request.form.get("next", "/")
        client_ip = get_client_ip()

        validation = validate_turnstile(token, TURNSTILE_SECRET_KEY, client_ip)

        if validation.get("success"):
            mark_turnstile_verified()
            logging.info(f"Turnstile verification SUCCESS for {client_ip}")
            return redirect(next_url)
        else:
            errors = validation.get("error-codes", [])
            logging.warning(
                f"Turnstile verification FAILED for {client_ip}: {errors}")
            # Show challenge again with error
            return render_template_string(
                CHALLENGE_PAGE,
                site_key=TURNSTILE_SITE_KEY,
                verify_url=url_for("turnstile_verify"),
                next_url=next_url,
                error=True
            )

    # Add challenge page endpoint
    @app.route(f"{app_root}/turnstile/challenge")
    def turnstile_challenge():
        """Show the Turnstile challenge page."""
        next_url = request.args.get("next", "/")
        return render_template_string(
            CHALLENGE_PAGE,
            site_key=TURNSTILE_SITE_KEY,
            verify_url=url_for("turnstile_verify"),
            next_url=next_url
        )

    # Add middleware to check verification before each request
    @app.before_request
    def check_turnstile_verification():
        """
        Middleware to verify Turnstile for all requests.
        Skips static files, health checks, and Turnstile endpoints.
        """
        if not TURNSTILE_ENABLED:
            return

        path = request.path or ""

        # Skip verification for these paths
        app_root = app.config.get('APPLICATION_ROOT', '').rstrip('/')
        skip_paths = [
            f"{app_root}/turnstile/",
            f"{app_root}/static/",
            f"{app_root}/health",
            f"{app_root}/server_info",
        ]
        if any(path.startswith(p) for p in skip_paths):
            return

        # Check if already verified
        if is_turnstile_verified():
            return

        # Not verified - redirect to challenge page
        logging.info(
            f"Turnstile verification required for {get_client_ip()} accessing {path}")
        return redirect(url_for("turnstile_challenge", next=request.url))


def turnstile_required(f):
    """
    Decorator to require Turnstile verification for specific routes.
    Use this for extra protection on sensitive endpoints.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if TURNSTILE_ENABLED and not is_turnstile_verified():
            return redirect(url_for("turnstile_challenge", next=request.url))
        return f(*args, **kwargs)
    return decorated_function
