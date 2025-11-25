"""
Filename: waitress_app.py
Description: This script sets up and runs a Waitress WSGI server
to serve a Flask web application.
"""
# --- EARLY STARTUP LOGGING ---
try:
    with open(os.path.join(os.path.dirname(__file__), "waitress_startup.log"), "a", encoding="utf-8") as f:
        import datetime
        f.write(f"[STARTUP] waitress_app.py started at {datetime.datetime.now().isoformat()}\n")
except Exception:
    pass
from zoneinfo import ZoneInfo
from main_app import app
import os
from sys import path
import logging
import logging.handlers
from datetime import datetime

# Add current directory to path to ensure imports work
path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Get the absolute path to this script's directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(SCRIPT_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "waitress_app.log")

THREADS = 64

# Set up logging with Mountain Time formatting

MOUNTAIN_TZ = ZoneInfo("America/Denver")

class MountainFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        dt = datetime.fromtimestamp(record.created, MOUNTAIN_TZ)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")


# Configure TimedRotatingFileHandler for waitress_app.log
waitress_handler = logging.handlers.TimedRotatingFileHandler(
    LOG_FILE,
    when="midnight",
    interval=1,
    backupCount=14,
    encoding="utf-8"
)
# Rotated files: waitress_app.log.2025-10-12.log
waitress_handler.suffix = "%Y-%m-%d.log"
waitress_handler.setFormatter(MountainFormatter(
    "%(asctime)s %(levelname)s %(message)s"))

# Get the waitress_app logger
logger = logging.getLogger('waitress_app')
logger.setLevel(logging.INFO)
logger.handlers.clear()  # Remove any existing handlers
logger.addHandler(waitress_handler)
logger.propagate = False  # Don't propagate to root logger

# Also configure the waitress library logger
waitress_logger = logging.getLogger("waitress")
waitress_logger.setLevel(logging.INFO)
waitress_logger.handlers.clear()
waitress_logger.addHandler(waitress_handler)
waitress_logger.propagate = False

# Test logging
logger.info("=== Waitress app logging configured with daily rotation ===")
logger.info(f"Script directory: {SCRIPT_DIR}")
logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"Log file: {LOG_FILE}")
try:
    logger.info(
        f"Env HTTP_PLATFORM_PORT: {os.environ.get('HTTP_PLATFORM_PORT')}")
    logger.info(f"Env PYTHONPATH: {os.environ.get('PYTHONPATH')}")
    logger.info(
        f"Env PATH contains venv Scripts: {'\\.venv\\Scripts' in os.environ.get('PATH', '')}")
except Exception:
    pass
logger.info("Flask app imported successfully")


def main():
    # Prefer IIS-provided port; fall back to 8080 for local/manual runs
    port_env = os.environ.get("HTTP_PLATFORM_PORT")
    try:
        port = int(port_env) if port_env else 8080
    except Exception:
        port = 8080
    host = "127.0.0.1"

    logger.info(f"Starting Waitress server on {host}:{port}")

    try:
        from waitress import serve
        serve(
            app,
            host=host,
            port=port,
            threads=THREADS,
            connection_limit=1000,
        )
    except Exception as e:
        logger.exception(f"Failed to start Waitress: {e}")
        exit(1)


if __name__ == "__main__":
    logger.info("Running as main script")
    main()
else:
    logger.info("Module imported by IIS")
