"""Orchestration layer that picks a source for fund valuations and intraday curves."""
import os

from .core import (
    fund_valuation_ttl,
    cache_market_value,
    market_now,
    seconds_until_next_market_open,
)
from . import eastmoney
from . import fund123
from .quotes import fetch_quote_by_code, fetch_tencent_intraday_chart, fetch_yahoo_intraday_chart

# Tencent has no US index coverage, so those symbols are routed to Yahoo.
YAHOO_INDEX_SYMBOLS = {"usDJI": "^DJI", "usIXIC": "^IXIC", "usINX": "^GSPC"}


def fetch_fund_valuation(code):
    normalized = str(code).strip()
    if not normalized:
        return None
    cache_key = f"fund-valuation:{normalized}"
    cached = cache_market_value(cache_key)
    if cached is not None:
        return cached
    value = _fetch_fund_valuation_live(normalized)
    if value is None:
        return None
    return cache_market_value(cache_key, lambda: value, _valuation_ttl(value))


def _valuation_ttl(value, now=None):
    """Once the official NAV is published after the close, stop re-polling until the next session."""
    now = now or market_now()
    if (now.hour, now.minute) >= (15, 0) and value.get("current_price") is not None:
        return seconds_until_next_market_open(now)
    return fund_valuation_ttl(now)


def _fetch_fund_valuation_live(normalized):
    configured_url = os.environ.get("FUND123_ESTIMATE_URL")
    if configured_url:
        custom = fund123.fetch_fund123_valuation(configured_url, normalized)
        if custom:
            return custom

    return (
        fund123.fetch_fund123_intraday_valuation(normalized)
        or eastmoney.fetch_eastmoney_fundgz_valuation(normalized)
        or eastmoney.fetch_eastmoney_valuation(normalized)
        or eastmoney.fetch_eastmoney_fund_profile(normalized)
        or fund123.fetch_fund123_page_guess(normalized)
    )


def fetch_intraday_chart(asset_type, code):
    if asset_type == "fund":
        return fund123.fetch_fund123_intraday_chart(code)
    if asset_type == "index":
        normalized = str(code).strip()
        if normalized.startswith("^") or normalized in YAHOO_INDEX_SYMBOLS:
            return fetch_yahoo_intraday_chart(YAHOO_INDEX_SYMBOLS.get(normalized, normalized))
        return fetch_tencent_intraday_chart(normalized, is_index=True)
    return fetch_tencent_intraday_chart(code)


def lookup_instrument(asset_type, code):
    """Return name and latest public quote for the add-holding form."""
    normalized = str(code).strip()
    if not normalized:
        return None

    if asset_type == "fund":
        metadata = fund123.fetch_fund123_metadata(normalized) or {}
        valuation = fetch_fund_valuation(normalized) or {}
        if not metadata and not valuation:
            return None
        return {
            "name": metadata.get("name") or valuation.get("name") or normalized,
            "current_price": valuation.get("current_price"),
            "estimated_price": valuation.get("estimated_price"),
            "previous_close": valuation.get("previous_close"),
            "change_rate": valuation.get("change_rate"),
            "daily_change_rate": valuation.get("daily_change_rate"),
            "estimated_change_rate": valuation.get("estimated_change_rate"),
            "source_label": valuation.get("source_label") or metadata.get("source_label")
        }

    return fetch_quote_by_code(normalized)
