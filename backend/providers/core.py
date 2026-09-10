"""Shared HTTP, caching and market-clock helpers used by every data provider.

Every upstream adapter imports from here so TLS handling, cache semantics and
China Standard Time rules stay consistent across sources.
"""
import http.cookiejar
import json
import shutil
import ssl
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from contextvars import ContextVar
from datetime import datetime, timedelta, timezone

try:
    import akshare as ak
except ImportError:
    ak = None


# Upstream feeds present incomplete certificate chains, so verification is off.
SSL_CONTEXT = ssl._create_unverified_context()

USER_AGENT = "Mozilla/5.0 FundProWorkbench/0.1"
CHINA_TIMEZONE = timezone(timedelta(hours=8))

# Set per request handler so `force=true` can bypass the in-process cache.
FORCE_REFRESH = ContextVar("force_refresh", default=False)

MARKET_CACHE = {}
MARKET_CACHE_LOCK = threading.Lock()

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def market_now():
    """Return naive China Standard Time so market rules are host-timezone independent."""
    return datetime.now(CHINA_TIMEZONE).replace(tzinfo=None)


def format_timestamp(value=None):
    """Render a Beijing-time timestamp for the `generated_at` response fields."""
    return (value or market_now()).strftime(TIMESTAMP_FORMAT)


def cache_market_value(key, loader=None, ttl_seconds=0):
    """Read a live-data cache entry, fetching and replacing it only when expired."""
    now = time.time()
    with MARKET_CACHE_LOCK:
        cached = MARKET_CACHE.get(key)
        if not FORCE_REFRESH.get() and cached and cached["expires_at"] > now:
            return cached["value"]
    if loader is None:
        return None
    value = loader()
    if value is not None:
        with MARKET_CACHE_LOCK:
            MARKET_CACHE[key] = {"value": value, "expires_at": now + max(ttl_seconds, 1)}
    return value


def cached_value(key):
    """Return the latest cached value, including a stale one while it refreshes in the background."""
    with MARKET_CACHE_LOCK:
        cached = MARKET_CACHE.get(key)
        return cached["value"] if cached else None


def cache_entry(key):
    """Return the raw cache record so callers can inspect freshness without loading."""
    with MARKET_CACHE_LOCK:
        return MARKET_CACHE.get(key)


def store_value(key, value, ttl_seconds):
    """Write a cache record directly, used by background refresh threads."""
    with MARKET_CACHE_LOCK:
        MARKET_CACHE[key] = {"value": value, "expires_at": time.time() + max(ttl_seconds, 1)}
    return value


def seconds_until_next_market_open(now=None):
    now = now or market_now()
    target = now.replace(hour=9, minute=30, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    while target.weekday() >= 5:
        target += timedelta(days=1)
    return max(int((target - now).total_seconds()), 1)


def is_before_market_open(now=None):
    now = now or market_now()
    return (now.hour, now.minute) < (9, 30)


def market_quote_ttl(now=None):
    now = now or market_now()
    if is_before_market_open(now) or (now.hour, now.minute) >= (15, 0):
        return seconds_until_next_market_open(now)
    return 15


def fund_valuation_ttl(now=None):
    now = now or market_now()
    if is_before_market_open(now):
        return seconds_until_next_market_open(now)
    if (now.hour, now.minute) >= (15, 0):
        # Keep checking for the official NAV publication after the close.
        return 300
    return 60


def build_opener(cookie_jar=None):
    """Build an urllib opener that tolerates upstream TLS and optionally keeps cookies."""
    handlers = [urllib.request.HTTPSHandler(context=SSL_CONTEXT)]
    if cookie_jar is not None:
        handlers.insert(0, urllib.request.HTTPCookieProcessor(cookie_jar))
    return urllib.request.build_opener(*handlers)


def new_cookie_opener():
    return build_opener(http.cookiejar.CookieJar())


def http_get(url, headers=None, encoding="utf-8", opener=None):
    request = urllib.request.Request(
        url,
        headers=headers or {"User-Agent": USER_AGENT}
    )
    client = opener or build_opener()
    with client.open(request, timeout=10) as response:
        return response.read().decode(encoding, errors="ignore")


def http_post_json(url, payload, headers=None, opener=None):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers or {
            "Content-Type": "application/json",
            "User-Agent": USER_AGENT
        },
        method="POST"
    )
    client = opener or build_opener()
    with client.open(request, timeout=10) as response:
        return response.read().decode("utf-8", errors="ignore")


def http_get_with_curl(url):
    """Use the OS curl client for the Eastmoney feed's browser-specific TLS behavior."""
    curl_binary = shutil.which("curl.exe") or shutil.which("curl")
    if not curl_binary:
        raise OSError("curl executable is unavailable")
    result = subprocess.run(
        [curl_binary, "-L", "-s", "-A", "Mozilla/5.0", url],
        capture_output=True,
        text=True,
        timeout=10,
        check=False
    )
    if result.returncode != 0 or not result.stdout:
        raise OSError(result.stderr.strip() or "curl request failed")
    return result.stdout


def to_float(value):
    try:
        return float(str(value).replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


def to_ratio_percent(value):
    """Convert decimal ratios such as 0.0963 into percentage values."""
    numeric = to_float(value)
    if numeric is None:
        return None
    return numeric * 100 if abs(numeric) <= 1 else numeric
