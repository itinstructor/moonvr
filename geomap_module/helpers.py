from flask import request
import logging
from functools import lru_cache
import os
# --- Optimization: Moved imports to the top of the file ---
import socket
# --- End Optimization ---

def _load_api_key():
    """
    Loads a secret API key from a secure location.

    It's a very important security practice to NEVER write secret keys or passwords
    directly in the code. This function looks for the key in two places:
    1. An "environment variable" on the server. This is a secure way to store secrets
       on a live web server.
    2. A simple text file named "geoip_license.txt" in the project's main directory.
       This is useful for local development on a personal computer.

    Returns:
        The API key as a string, or None if it's not found.
    """
    # First, try to get the key from an environment variable named "GEOIP_LICENSE".
    key = os.environ.get("GEOIP_LICENSE")
    if key and key.strip():
        return key.strip()
    # If not found, look for a file named "geoip_license.txt" in the project's root folder.
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    license_path = os.path.join(root, "geoip_license.txt")
    try:
        if os.path.exists(license_path):
            with open(license_path, "r", encoding="utf-8") as f:
                k = f.read().strip()
                if k:
                    return k
    except Exception:
        # If there's an error reading the file, log it but don't crash the app.
        logging.exception("Failed to read geoip_license.txt")
    return None


# Call the function to load the key. This variable will hold the key if found, otherwise it will be None.
IPGEOLOCATION_API_KEY = _load_api_key()

# This is the file path to a local database that contains IP address location data.
# Using a local database is much faster than asking a web service every time.
# The 'r' before the string means it's a "raw string", which helps with backslashes in Windows paths.
GEOIP_DB_PATH = r"C:\inetpub\podsinspace\geoip\GeoLite2-City.mmdb"

# --- Optimization: Initialize the GeoIP database reader once at startup. ---
# This avoids re-opening the file on every lookup, which is much more efficient.
# The reader object is thread-safe and designed for reuse.
def _init_geoip_reader():
    """Initializes the GeoIP reader, returns None if the DB file is missing."""
    if not os.path.exists(GEOIP_DB_PATH):
        logging.warning(f"GeoIP database not found at {GEOIP_DB_PATH}. Local lookup disabled.")
        return None
    try:
        # Defer import until it's actually needed. This prevents startup errors if geoip2 is not installed.
        import geoip2.database
        return geoip2.database.Reader(GEOIP_DB_PATH)
    except Exception:
        logging.exception("Failed to initialize GeoIP database reader.")
        return None

GEOIP_READER = _init_geoip_reader()
# This is a list of IP address prefixes that are used for private networks (like your home Wi-Fi).
# These IPs are not unique on the internet, so we can't look up their location.
PRIVATE_PREFIXES = ("10.", "172.", "192.168.", "127.", "169.254.")


def _is_private(ip: str) -> bool:
    """
    Checks if an IP address is a private/internal one.

    Args:
        ip: The IP address string to check.

    Returns:
        True if the IP is private, False otherwise.
    """
    if not ip:
        return True
    ip = ip.strip().lower()
    if ip == "localhost":
        return True
    # Check if the IP address starts with any of the private prefixes.
    return any(ip.startswith(p) for p in PRIVATE_PREFIXES)


def get_ip() -> str:
    """
    Gets the real IP address of the visitor.

    When a user visits a website, their IP address is usually in the request. However,
    if the web server is behind a proxy or load balancer (which is common), the direct
    IP the server sees is the proxy's, not the user's.

    Proxies add special HTTP headers (like 'X-Forwarded-For') to pass along the
    original visitor's IP. This function checks for these headers first to find the
    true IP address.

    Returns:
        The visitor's IP address as a string.
    """
    hdr = request.headers.get
    # A list of common headers that proxies use to store the original IP.
    for h in ("X-Real-Ip", "X-Real-IP", "X-Forwarded-For", "X-MS-Forwarded-Client-IP", "X-Original-Remote-Addr"):
        v = hdr(h)
        if v:
            # The header can contain a list of IPs (e.g., "user_ip, proxy1_ip, proxy2_ip").
            # The first one is the original client, so we take that.
            return v.split(",")[0].strip()
    # If no special headers are found, fall back to the standard IP address from the request.
    return request.environ.get("REMOTE_ADDR") or request.remote_addr

# The `@lru_cache` decorator is a powerful tool for optimization. It's like giving the function a short-term memory.
# "LRU" stands for "Least Recently Used".
# `maxsize=10000` means it will remember the results for the last 10,000 unique IP addresses it looked up.
# If the same IP is looked up again, it returns the remembered result instantly instead of re-reading the database file.


@lru_cache(maxsize=10000)
def _geoip2_lookup_local(ip: str):
    """
    Looks up an IP address using the local GeoLite2 database file.
    This is the first and fastest method we try.
    """
    # --- Optimization: Use the pre-initialized reader ---
    if not GEOIP_READER:
        return None
    try:
        # Look up the IP address in the database.
        rec = GEOIP_READER.city(ip)
        return {
            "lat": rec.location.latitude,
            "lon": rec.location.longitude,
            "city": rec.city.name,
            "region": rec.subdivisions.most_specific.name,
            "country": rec.country.name,
            "country_code": rec.country.iso_code,
            "continent": getattr(rec.continent, "name", None),
            "zipcode": rec.postal.code if hasattr(rec, "postal") else None,
            "isp": None,
            "organization": None,
            "timezone": getattr(rec.location, "time_zone", None),
            "currency": None,
        }
    except Exception:
        # If the 'geoip2' library isn't installed, the database file is missing,
        # or the IP isn't in the database, this will fail. We log it for debugging
        # but don't show the full error to avoid cluttering logs. The function will return None.
        logging.debug(
            "Local GeoLite2 lookup not available or failed for %s", ip, exc_info=False)
        return None


def _norm(v):
    """
    A small helper function to "normalize" (clean up) a value.
    It converts the value to a string, removes leading/trailing whitespace,
    and returns None if the result is an empty string. This ensures
    we have consistent, clean data.
    """
    if v is None:
        return None
    # Convert to string and strip whitespace.
    s = str(v).strip()
    # Return the cleaned string, or None if it's empty.
    return s if s else None


# --- Refactoring: Create a reusable requests session for efficiency ---
import requests
HTTP_SESSION = requests.Session()

@lru_cache(maxsize=10000)
def get_location(ip: str):
    """
    Resolve IP -> geolocation dict.
    Priority:
      1. Local GeoLite2 DB (fast, free, offline)
      2. ipgeolocation.io API (more detailed, uses a secret key, requires internet)
      3. ipapi.co API (a free backup service, requires internet)
      4. Reverse DNS lookup (a last resort, gives very little info)
    Returns dict or None.
    """
    # First, check if the IP is a private one. If so, we can't look it up, so we stop here.
    if _is_private(ip):
        logging.info("Skipping geolocation for private IP: %s", ip)
        return None

    # --- Refactoring: Define providers and loop through them for cleaner logic ---
    for provider_func in [_provider_local, _provider_ipgeolocation, _provider_ipapi, _provider_revdns]:
        try:
            result = provider_func(ip)
            if result:
                # Ensure all values are normalized before returning
                return {k: _norm(v) if k not in ("lat", "lon") else (float(v) if v is not None else None)
                        for k, v in result.items()}
        except Exception:
            logging.exception(f"Provider {provider_func.__name__} failed for {ip}")
    
    return None # All providers failed


def _provider_local(ip: str):
    """Provider 1: Local GeoLite2 DB."""
    return _geoip2_lookup_local(ip)


def _provider_ipgeolocation(ip: str):
    """Provider 2: ipgeolocation.io API."""
    if not IPGEOLOCATION_API_KEY:
        logging.debug("IP geolocation API key not available; skipping ipgeolocation.io lookup")
        return None

    url = f"https://api.ipgeolocation.io/ipgeo?apiKey={IPGEOLOCATION_API_KEY}&ip={ip}"
    r = HTTP_SESSION.get(url, timeout=5)
    
    if not r.ok:
        logging.warning("ipgeolocation lookup failed %s for %s: %s", r.status_code, ip, r.text)
        return None

    d = r.json()
    return {
        "lat": d.get("latitude"),
        "lon": d.get("longitude"),
        "city": d.get("city"),
        "region": d.get("state_prov"),
        "country": d.get("country_name"),
        "country_code": d.get("country_code2"),
        "continent": d.get("continent_name"),
        "zipcode": d.get("zipcode"),
        "isp": d.get("isp"),
        "organization": d.get("organization"),
        "timezone": (d.get("time_zone") or {}).get("name"),
        "currency": (d.get("currency") or {}).get("code"),
    }


def _provider_ipapi(ip: str):
    """Provider 3: ipapi.co API."""
    r = HTTP_SESSION.get(f"https://ipapi.co/{ip}/json/", timeout=4)
    if not r.ok:
        return None

    d = r.json()
    # Handle potential error response from ipapi.co
    if d.get("error"):
        logging.warning(f"ipapi.co returned error for {ip}: {d.get('reason')}")
        return None

    return {
        "lat": d.get("latitude"),
        "lon": d.get("longitude"),
        "city": d.get("city"),
        "region": d.get("region"),
        "country": d.get("country_name"),
        "country_code": d.get("country_code"),
        "continent": d.get("continent_name"),
        "zipcode": d.get("postal"),
        "isp": d.get("org"),
        "organization": d.get("org"),
        "timezone": d.get("timezone"),
        "currency": d.get("currency"),
    }


def _provider_revdns(ip: str):
    """Provider 4: Reverse DNS lookup (minimal info)."""
    try:
        try:
            name = socket.gethostbyaddr(ip)[0]
        except Exception:
            name = None
        return {
            "lat": None,
            "lon": None,
            "city": None,
            "region": None,
            "country": None,
            "country_code": None,
            "continent": None,
            "zipcode": None,
            "isp": None,
            "organization": _norm(name),
            "timezone": None,
            "currency": None,
        }
    except Exception: # Should be rare
        return None
