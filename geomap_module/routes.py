# Routes for the geomap_module - shows visitor locations and provides JSON APIs.
# Comments added to help a community college student understand each part.

from flask import render_template, jsonify, request
from . import geomap_bp  # Blueprint for this module (registered in app factory)
from .models import VisitorLocation  # SQLAlchemy model for visitor data
from .helpers import get_ip, get_location  # helper functions (not used directly here)
from database import db  # shared SQLAlchemy db instance used by the app
import logging
from datetime import datetime, timezone, timedelta

# How long to ignore repeated visits from the same IP (used by tracking logic elsewhere)
VISITOR_COOLDOWN_HOURS = 1  # 1 hour

# Try to use zoneinfo (modern timezone support). If not available, fall back to a fixed offset.
# Using ZoneInfo ensures correct DST handling when converting times.
try:
    from zoneinfo import ZoneInfo
    MOUNTAIN_TZ = ZoneInfo("America/Denver")  # Mountain Time with DST support
    TIMEZONE_NAME = "Mountain Time (MST/MDT)"
except (ImportError, Exception):
    # If zoneinfo is not available (older Python), use a fixed offset as a fallback.
    # This fallback does NOT handle DST transitions correctly.
    MOUNTAIN_TZ = timezone(timedelta(hours=-6))  # approximate MDT offset
    TIMEZONE_NAME = "Mountain Time (UTC-6, no DST)"
    logging.warning("zoneinfo not available, using fixed UTC-6 offset. Install tzdata for DST support.")


def to_mountain_time(utc_dt):
    """
    Convert a UTC datetime to Mountain Time and return a nicely formatted string.
    - Expects utc_dt in UTC (naive or tz-aware). If naive, we treat it as UTC.
    - Returns None if utc_dt is None.
    - Returns a string like: '2025-10-12 01:23:45 PM MDT'
    """
    if utc_dt is None:
        return None
    try:
        # Make timezone-aware as UTC if no tzinfo set
        if utc_dt.tzinfo is None:
            utc_dt = utc_dt.replace(tzinfo=timezone.utc)
        # Convert timestamp to Mountain Time (ZoneInfo or fallback)
        mt_dt = utc_dt.astimezone(MOUNTAIN_TZ)
        # Format the datetime in a readable form
        return mt_dt.strftime('%Y-%m-%d %I:%M:%S %p %Z')
    except Exception as e:
        # If conversion fails, log the error and return the raw datetime string
        logging.error(f"Error converting time to Mountain: {e}")
        return str(utc_dt)


@geomap_bp.route("/visitors")
def visitors_map():
    """
    Render the visitors page.
    - Pulls all VisitorLocation rows from the DB ordered by most recent visit.
    - Converts numeric/optional fields to safe types for templates (e.g., lat/lon to float).
    - Converts UTC timestamps to Mountain Time strings using to_mountain_time().
    - Returns the template 'visitors.html' with the prepared data.
    """
    try:
        # Query all visitor records, most recent first
        visitors_query = VisitorLocation.query.order_by(VisitorLocation.last_visit.desc()).all()
        
        # Build a list of plain dictionaries for the template (easier to work with in Jinja)
        visitor_data = []
        for v in visitors_query:
            visitor_data.append({
                'ip': v.ip_address,
                'lat': float(v.lat) if v.lat else 0.0,
                'lon': float(v.lon) if v.lon else 0.0,
                'city': v.city or 'Unknown',
                'region': v.region or '',
                'country': v.country or 'Unknown',
                'visits': v.visit_count or 0,
                'first_visit': to_mountain_time(v.first_visit),
                'last_visit': to_mountain_time(v.last_visit),
                'user_agent': v.user_agent or '',
                'page_visited': v.page_visited or '/',
                'isp': v.isp or '',
                'organization': v.organization or ''
            })
        
        total_visitors = len(visitor_data)
        unique_visitors = total_visitors  # IP is unique in this schema, so counts match
        
        # Render the HTML page and pass data for display
        return render_template(
            "visitors.html",
            visitors=visitor_data,
            total_visitors=total_visitors,
            unique_visitors=unique_visitors,
            timezone_display=TIMEZONE_NAME
        )
    except Exception as e:
        # If anything goes wrong, log the exception and render the page with an error message
        logging.exception("Error loading visitors page")
        return render_template(
            "visitors.html",
            visitors=[],
            total_visitors=0,
            unique_visitors=0,
            timezone_display=TIMEZONE_NAME,
            error=str(e)
        )


@geomap_bp.route("/api/visitor-locations")
def get_visitor_locations():
    """
    JSON API endpoint that returns all stored visitor locations.
    - Useful for JavaScript on the frontend (e.g., map marker population).
    - Returns timestamps converted to Mountain Time and also includes raw UTC ISO timestamps.
    """
    try:
        locations = VisitorLocation.query.order_by(VisitorLocation.last_visit.desc()).all()
        
        locations_list = []
        for loc in locations:
            locations_list.append({
                'ip': loc.ip_address,
                'lat': float(loc.lat) if loc.lat else 0.0,
                'lon': float(loc.lon) if loc.lon else 0.0,
                'city': loc.city or 'Unknown',
                'region': loc.region or '',
                'country': loc.country or 'Unknown',
                'visit_count': loc.visit_count or 0,
                'first_visit': to_mountain_time(loc.first_visit),  # human-friendly local time
                'last_visit': to_mountain_time(loc.last_visit),
                'first_visit_utc': loc.first_visit.isoformat() if loc.first_visit else None,  # machine-friendly UTC
                'last_visit_utc': loc.last_visit.isoformat() if loc.last_visit else None
            })
        
        return jsonify(locations_list)
    except Exception as e:
        logging.exception("Error fetching visitor locations")
        return jsonify({"error": str(e)}), 500


@geomap_bp.route("/api/visitor-stats")
def get_visitor_stats():
    """
    JSON API endpoint that returns summary statistics:
    - total_visitors (sum of visit_count)
    - unique_visitors (number of unique IPs/rows)
    - recent_visitors (last 10 by time)
    - top_visitors (top 10 by visits)
    All timestamps shown in Mountain Time strings.
    """
    try:
        unique_visitors = VisitorLocation.query.count()
        
        # Sum visit_count across all rows (SQL aggregation)
        from sqlalchemy import func
        total_visits_result = db.session.query(func.sum(VisitorLocation.visit_count)).scalar()
        total_visitors = total_visits_result or 0
        
        # Recent visitors (most recent last_visit)
        recent_visitors = VisitorLocation.query.order_by(
            VisitorLocation.last_visit.desc()
        ).limit(10).all()
        
        # Top visitors by visit_count
        top_visitors = VisitorLocation.query.order_by(
            VisitorLocation.visit_count.desc()
        ).limit(10).all()
        
        return jsonify({
            "total_visitors": total_visitors,
            "unique_visitors": unique_visitors,
            "timezone": TIMEZONE_NAME,
            "recent_visitors": [
                {
                    "city": v.city,
                    "region": v.region,
                    "country": v.country,
                    "visit_count": v.visit_count,
                    "first_visit": to_mountain_time(v.first_visit),
                    "last_visit": to_mountain_time(v.last_visit)
                }
                for v in recent_visitors
            ],
            "top_visitors": [
                {
                    "city": v.city,
                    "region": v.region,
                    "country": v.country,
                    "visit_count": v.visit_count
                }
                for v in top_visitors
            ]
        })
    except Exception as e:
        logging.exception("Error fetching visitor stats")
        return jsonify({"error": str(e)}), 500


