# filepath: c:\inetpub\podsinspace\geomap_module\models.py
# This file defines the database model for storing visitor location data.
# Comments added to help a community college student understand each part.

from database import db  # shared SQLAlchemy db instance used across the project
from datetime import datetime, timezone  # used to set timestamp fields


class VisitorLocation(db.Model):
    """Model to store visitor IP location data.

    Each instance represents one IP address and related geo-info (city, country, etc.)
    that we tracked visiting the site.
    """
    __tablename__ = 'visitor_location'  # name of the table in the database
    # optional: if the app uses multiple databases, this chooses which DB
    __bind_key__ = 'visitors'

    # Primary key - unique identifier for each row
    id = db.Column(db.Integer, primary_key=True)

    # IP address (supports IPv4 and IPv6 length). 'unique=True' means one row per IP.
    ip_address = db.Column(db.String(45), unique=True, nullable=False)

    # Latitude and longitude of the visitor (floats). Default to 0.0 so column is never NULL.
    lat = db.Column(db.Float, nullable=False, default=0.0)
    lon = db.Column(db.Float, nullable=False, default=0.0)

    # Human-readable location fields (may be blank if lookup fails)
    city = db.Column(db.String(100))
    region = db.Column(db.String(100))
    country = db.Column(db.String(100))

    # Extra fields often returned by geo-IP services
    country_code = db.Column(db.String(10))      # e.g. 'US'
    continent = db.Column(db.String(50))         # e.g. 'North America'
    zipcode = db.Column(db.String(20))           # postal code if available
    # Internet Service Provider name
    isp = db.Column(db.String(200))
    organization = db.Column(db.String(200))     # owning organization
    # time zone string, e.g. 'America/Denver'
    timezone = db.Column(db.String(50))
    currency = db.Column(db.String(10))          # currency code like 'USD'

    # Tracking how often this IP visited
    visit_count = db.Column(db.Integer, default=1)

    # Timestamps: first time seen and last time seen (use UTC)
    first_visit = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc))
    last_visit = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Browser user agent string and the page they visited last
    user_agent = db.Column(db.String(255))
    page_visited = db.Column(db.String(255))

    def increment_visit(self, page_visited=None, user_agent=None):
        """Increase visit_count and update last_visit.

        Call this when we see the same IP again. Optionally update which page
        they visited and their user agent string.
        """
        self.visit_count += 1
        # Use UTC time for consistency across servers/timezones
        self.last_visit = datetime.now(timezone.utc)
        if page_visited:
            self.page_visited = page_visited
        if user_agent:
            self.user_agent = user_agent

    def to_dict(self):
        """Return a plain Python dict of the model suitable for JSON output.

        Datetimes are converted to ISO strings to make them easy to serialize.
        """
        return {
            'id': self.id,
            'ip_address': self.ip_address,
            'lat': self.lat,
            'lon': self.lon,
            'city': self.city,
            'region': self.region,
            'country': self.country,
            'visit_count': self.visit_count,
            'first_visit': self.first_visit.isoformat() if self.first_visit else None,
            'last_visit': self.last_visit.isoformat() if self.last_visit else None,
            'user_agent': self.user_agent,
            'page_visited': self.page_visited
        }

    def __repr__(self):
        """Developer-friendly string for debugging (shows IP and location)."""
        return f'<VisitorLocation {self.ip_address} from {self.city}, {self.country}>'
