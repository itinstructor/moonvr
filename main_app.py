#!/usr/bin/env python3
"""
Flask web application that shows two live MJPEG camera streams:
 - Pod Tank (camera 0)
 - (camera 2 mapped as /stream1.mjpg on the Pi side)

Designed with clear comments for learners.
This version keeps:
 - Clean structure
 - Rotating log files (no noisy debug routes)
 - Simple relay caching for efficiency

Does NOT include extra debug endpoints or complex UI logic.
"""

from zoneinfo import ZoneInfo
from flask import Flask, render_template, request, url_for, Response, redirect
import os
import logging
import logging.handlers
from urllib.parse import unquote, parse_qsl
from typing import Dict
from datetime import datetime, timedelta, timezone

# Database and visitor tracking
from database import db  # <-- db is already created in database.py
from geomap_module import geomap_bp
from geomap_module.models import VisitorLocation
from geomap_module.helpers import get_ip, get_location
from geomap_module.routes import VISITOR_COOLDOWN_HOURS

# Cloudflare Turnstile bot protection
from turnstile import init_turnstile

# ---------------------------------------------------------------------------
# LOGGING SETUP
# ---------------------------------------------------------------------------
# We log to files so we can review what happened later (errors, starts, etc.)
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "main_app.log")

# Configure logging with TimedRotatingFileHandler
handler = logging.handlers.TimedRotatingFileHandler(
    LOG_FILE, when="midnight", interval=1, backupCount=14, encoding="utf-8"
)
handler.suffix = "%Y-%m-%d.log"  # Keep .log extension in rotated files


MOUNTAIN_TZ = ZoneInfo("America/Denver")


class MountainFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, MOUNTAIN_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")


handler.setFormatter(MountainFormatter(
    "%(asctime)s %(levelname)s %(message)s"))

# Get root logger and configure it
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
# Remove any existing handlers to avoid duplicates
root_logger.handlers.clear()
root_logger.addHandler(handler)

logging.info("Application start")

# ---------------------------------------------------------------------------
# FLASK APP SETUP
# ---------------------------------------------------------------------------
# static_url_path lets static files be served under /moonvr/static
app = Flask(__name__,
            static_folder='static',
            static_url_path='/moonvr/static')

app.config['APPLICATION_ROOT'] = '/moonvr'
# ---------------------------------------------------------------------------
# DATABASE SETUP
# ---------------------------------------------------------------------------

# Ensure the instance folder exists
os.makedirs(app.instance_path, exist_ok=True)

# Set both databases to be in the instance folder
BLOG_DB_PATH = os.path.join(app.instance_path, "blog.db")
VISITORS_DB_PATH = os.path.join(app.instance_path, "visitors.db")

app.config["SQLALCHEMY_DATABASE_URI"] = (
    f"sqlite:///{BLOG_DB_PATH}"  # main DB
)
app.config["SQLALCHEMY_BINDS"] = {"visitors": f"sqlite:///{VISITORS_DB_PATH}"}
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Set secret key for sessions

SECRET_KEY_FILE = os.path.join(os.path.dirname(__file__), "secret_key.txt")
logging.info(f"SECRET_KEY_FILE path being checked: {SECRET_KEY_FILE}")

if os.path.exists(SECRET_KEY_FILE):
    with open(SECRET_KEY_FILE, "r") as f:
        app.config["SECRET_KEY"] = f.read().strip()
    logging.info("Secret key loaded from file")
    logging.info(f"Secret key configured: {app.config['SECRET_KEY'][:10]}...")
else:
    logging.error("secret_key.txt not found! Run generate_secret_key.py first")
    raise RuntimeError(
        "Secret key file missing. Run generate_secret_key.py to create it."
    )
logging.info(f"SECRET_KEY_FILE path being checked: {SECRET_KEY_FILE}")

# Initialize the database with this app (don't create a new SQLAlchemy instance)
db.init_app(app)


# Register the geomap blueprint for visitor tracking
app.register_blueprint(geomap_bp, url_prefix="/moonvr")

# Register Mars Blog blueprint - KEEP THIS BLOCK, remove the import at top
logging.info("Attempting to import Mars Blog blueprint...")
try:
    from blog import blog_bp  # Import here, just before registration

    logging.info(f"Blog blueprint imported: {blog_bp}")
    app.register_blueprint(blog_bp, url_prefix="/moonvr")
    logging.info("Blog blueprint registered at /moonvr")
except Exception as e:
    logging.exception("Failed to register Mars Blog blueprint")
    logging.error(f"Error details: {str(e)}")

# Create database tables if they don't exist
# Initialize database tables for all modules
with app.app_context():
    try:
        db.create_all()
        logging.info("Database tables created/verified")
    except Exception as e:
        logging.exception("Failed to create database tables")

# ---------------------------------------------------------------------------
# CLOUDFLARE TURNSTILE PROTECTION
# ---------------------------------------------------------------------------
# Initialize Turnstile bot protection (automatically protects all routes)
init_turnstile(app)

# ---------------------------------------------------------------------------
# VISITOR TRACKING MIDDLEWARE
# ---------------------------------------------------------------------------


@app.before_request
def track_visitor():
    """
    Middleware to track visitor IP locations on each request.
    Runs before every request to log visitor information.
    Increments visit counter for returning visitors.
    """
    # Skip tracking for static files, API endpoints, and health checks
    if (
        request.path.startswith("/moonvr/static/")
        or request.path.startswith("/moonvr/api/")
        or request.path
        in [
            "/moonvr/health",
            "/moonvr/server_info",
            "/moonvr/waitress_info",
        ]
        or request.path == "/moonvr/stream_proxy"
    ):
        return

    # Store everything in UTC - no timezone conversion here
    now_utc = datetime.now(timezone.utc)
    logging.info(
        f"[{now_utc.isoformat()}] Visitor tracking triggered for path: {request.path}"
    )

    try:
        # Get visitor's IP address
        ip = get_ip()
        logging.info(f"Detected IP: {ip}")

        # Check if we've already tracked this IP
        existing_visitor = VisitorLocation.query.filter_by(
            ip_address=ip
        ).first()

        if existing_visitor:
            # Check if we should update (cooldown period)
            last_visit = existing_visitor.last_visit
            if last_visit and last_visit.tzinfo is None:
                last_visit = last_visit.replace(tzinfo=timezone.utc)

            recent_cutoff = now_utc - timedelta(hours=VISITOR_COOLDOWN_HOURS)
            if last_visit and last_visit > recent_cutoff:
                logging.info(f"Visitor {ip} tracked recently, skipping")
                return

            # Update existing visitor
            existing_visitor.increment_visit(
                page_visited=request.path,
                user_agent=request.headers.get("User-Agent", "")[:255],
            )
            db.session.commit()
            logging.info(
                f"Updated visitor from {ip} - Visit #{existing_visitor.visit_count}"
            )
        else:
            # New visitor - get location data
            logging.info(f"New visitor {ip}, fetching location data...")
            location_data = get_location(ip)
            logging.info(f"Location data received: {location_data}")

            # Always create visitor record, even if geolocation fails
            visitor = VisitorLocation(
                ip_address=ip,
                lat=location_data.get("lat") if location_data else 0.0,
                lon=location_data.get("lon") if location_data else 0.0,
                city=location_data.get("city") if location_data else None,
                region=location_data.get("region") if location_data else None,
                country=location_data.get(
                    "country") if location_data else None,
                country_code=(
                    location_data.get(
                        "country_code") if location_data else None
                ),
                continent=(
                    location_data.get("continent") if location_data else None
                ),
                zipcode=location_data.get(
                    "zipcode") if location_data else None,
                isp=location_data.get("isp") if location_data else None,
                organization=(
                    location_data.get(
                        "organization") if location_data else None
                ),
                timezone=(
                    location_data.get("timezone") if location_data else None
                ),
                currency=(
                    location_data.get("currency") if location_data else None
                ),
                user_agent=request.headers.get("User-Agent", "")[:255],
                page_visited=request.path,
            )

            db.session.add(visitor)
            db.session.commit()
            logging.info(f"Successfully tracked new visitor from {ip}")

    except Exception as e:
        logging.error(f"Error tracking visitor: {e}", exc_info=True)
        db.session.rollback()


@app.after_request
def set_security_headers(response):
    """
    Add security headers to allow cross-origin resources.
    This fixes COEP blocking issues with Leaflet map markers and other CDN assets.
    """
    # Allow cross-origin resources (fixes Leaflet marker images, CDN assets)
    response.headers['Cross-Origin-Resource-Policy'] = 'cross-origin'
    response.headers['Cross-Origin-Embedder-Policy'] = 'unsafe-none'
    return response


# ---------------------------------------------------------------------------
# ROUTES: WEB PAGES
# ---------------------------------------------------------------------------
@app.route("/moonvr", methods=["GET", "POST"])
def index():
    """
    Main page.
    """

    return render_template("index.html")
# Champions page route


@app.route("/moonvr/champions")
def champions():
    """Page recognizing moonvr Champions."""
    return render_template("champions.html")


@app.route("/moonvr/about")
def about():
    """Static About page."""
    return render_template("about.html")


@app.route("/moonvr/stats")
def stats_page():
    """HTML page that displays waitress/server streaming statistics."""
    return render_template("waitress_stats.html")


@app.route("/moonvr/health")
def health():
    """
    Simple health check used by monitoring or load balancers.
    Returns JSON if the app is alive.
    """
    return {"status": "ok"}


@app.route("/moonvr/server_info")
def server_info():
    import threading

    return {
        "server": request.environ.get("SERVER_SOFTWARE", "unknown"),
        "active_threads": len(threading.enumerate()),
        "media_relays": list(getattr(globals(), "_media_relays", {}).keys()),
    }


@app.route("/moonvr/debug/visitors")
def debug_visitors():
    """Debug endpoint - converts UTC timestamps to Mountain Time for display only."""
    try:
        # Import zoneinfo here for display conversion only

        from zoneinfo import ZoneInfo

        MOUNTAIN_TZ = ZoneInfo("America/Denver")

        visitors = (
            VisitorLocation.query.order_by(VisitorLocation.first_visit.desc())
            .limit(20)
            .all()
        )

        def to_mountain(utc_dt):
            """Convert UTC datetime to Mountain Time for display."""
            if utc_dt is None:
                return None
            if utc_dt.tzinfo is None:
                utc_dt = utc_dt.replace(tzinfo=timezone.utc)
            return utc_dt.astimezone(MOUNTAIN_TZ).strftime(
                "%Y-%m-%d %H:%M:%S %Z"
            )

        return {
            "total_count": VisitorLocation.query.count(),
            "timezone_display": "America/Denver (Mountain Time)",
            "timezone_storage": "UTC",
            "recent_visitors": [
                {
                    "ip": v.ip_address,
                    "city": v.city,
                    "region": v.region,
                    "country": v.country,
                    "lat": v.lat,
                    "lon": v.lon,
                    "visits": v.visit_count,
                    "last_visit_mdt": to_mountain(v.last_visit),
                    "first_visit_mdt": to_mountain(v.first_visit),
                    "last_visit_utc": (
                        v.last_visit.isoformat() if v.last_visit else None
                    ),
                    "first_visit_utc": (
                        v.first_visit.isoformat() if v.first_visit else None
                    ),
                }
                for v in visitors
            ],
        }
    except Exception as e:
        import traceback

        return {"error": str(e), "traceback": traceback.format_exc()}, 500


@app.route("/moonvr/debug/request_info")
def debug_request_info():
    """Return headers and environ to help verify forwarded IPs under IIS."""
    from geomap_module.helpers import get_ip

    return {
        "detected_ip": get_ip(),
        "remote_addr": request.remote_addr,
        "environ_remote_addr": request.environ.get("REMOTE_ADDR"),
        "headers": {k: v for k, v in request.headers.items()},
        "x_forwarded_for": request.headers.get("X-Forwarded-For"),
        "x_real_ip": request.headers.get("X-Real-IP"),
    }


# ---------------------------------------------------------------------------
# TEMPLATE CONTEXT
# ---------------------------------------------------------------------------
@app.context_processor
def inject_urls():
    """
    Makes app_root available in all templates if needed for building links.
    """
    return dict(app_root=app.config["APPLICATION_ROOT"])


@app.context_processor
def inject_script_root():
    """Make script_root available in all templates for building static URLs"""
    return dict(script_root=request.script_root if request.script_root else '')


# ---------------------------------------------------------------------------
# MAIN ENTRY POINT
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Development mode ONLY (use waitress_app.py in production).")
    # DO NOT use debug=True in production behind IIS
    app.run(host="127.0.0.1", port=5000, debug=False)

try:
    import geoip2.database
except Exception:
    geoip2 = None

GEOIP_DB_PATH = os.path.join(os.path.dirname(
    __file__), 'geoip', 'GeoLite2-City.mmdb')

geo_reader = None
if geoip2 is not None and os.path.exists(GEOIP_DB_PATH):
    try:
        geo_reader = geoip2.database.Reader(GEOIP_DB_PATH)
        logging.info(f"GeoIP DB loaded: {GEOIP_DB_PATH}")
    except Exception as e:
        logging.exception(f"Failed to open GeoIP DB ({GEOIP_DB_PATH}): {e}")
        geo_reader = None
else:
    logging.warning("GeoIP reader not initialized (missing package or DB).")
