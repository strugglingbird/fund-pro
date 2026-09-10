"""External market-data providers, split per upstream source.

This package used to be a single ``providers.py`` module. It is kept as a facade so
``app.py``, ``services.py`` and ``fund_archives.py`` keep importing from one place::

    from providers import fetch_fund_valuation, market_now

Submodules are organised by data source; ``core`` holds the shared HTTP, cache and
market-clock helpers, ``funds`` orchestrates the fallback chains.
"""
from .core import (
    CHINA_TIMEZONE,
    FORCE_REFRESH,
    MARKET_CACHE,
    MARKET_CACHE_LOCK,
    ak,
    build_opener,
    cache_entry,
    cache_market_value,
    cached_value,
    format_timestamp,
    fund_valuation_ttl,
    http_get,
    http_get_with_curl,
    http_post_json,
    is_before_market_open,
    market_now,
    market_quote_ttl,
    new_cookie_opener,
    seconds_until_next_market_open,
    store_value,
    to_float,
    to_ratio_percent,
)
from .eastmoney import (
    fetch_eastmoney_fund_profile,
    fetch_eastmoney_fundgz_valuation,
    fetch_eastmoney_valuation,
)
from .fund123 import (
    fetch_fund123_holdings,
    fetch_fund123_history_nav_list,
    fetch_fund123_history_navs,
    fetch_fund123_intraday_chart,
    fetch_fund123_intraday_valuation,
    fetch_fund123_metadata,
    fetch_fund123_page_guess,
    fetch_fund123_performance_curve,
    fetch_fund123_previous_nav,
    fetch_fund123_valuation,
    parse_fund123_nav_date,
    select_fund123_previous_nav,
)
from .funds import fetch_fund_valuation, fetch_intraday_chart, lookup_instrument
from .market import (
    MARKET_INDEXES,
    fetch_eastmoney_sector_rankings,
    fetch_kospi_index,
    fetch_market_breadth,
    fetch_market_indices,
    fetch_sector_rankings,
)
from .news import fetch_financial_news, IMPORTANT_NEWS_KEYWORDS
from .quotes import (
    fetch_quote_by_code,
    fetch_tencent_intraday_chart,
    fetch_tencent_watch_quote_batch,
    fetch_yahoo_intraday_chart,
    tencent_symbol,
)

__all__ = [
    "CHINA_TIMEZONE",
    "FORCE_REFRESH",
    "IMPORTANT_NEWS_KEYWORDS",
    "MARKET_CACHE",
    "MARKET_CACHE_LOCK",
    "MARKET_INDEXES",
    "ak",
    "build_opener",
    "cache_entry",
    "cache_market_value",
    "cached_value",
    "fetch_eastmoney_fund_profile",
    "fetch_eastmoney_fundgz_valuation",
    "fetch_eastmoney_sector_rankings",
    "fetch_eastmoney_valuation",
    "fetch_financial_news",
    "fetch_fund_valuation",
    "fetch_fund123_holdings",
    "fetch_fund123_history_nav_list",
    "fetch_fund123_history_navs",
    "fetch_fund123_intraday_chart",
    "fetch_fund123_intraday_valuation",
    "fetch_fund123_metadata",
    "fetch_fund123_page_guess",
    "fetch_fund123_performance_curve",
    "fetch_fund123_previous_nav",
    "fetch_fund123_valuation",
    "fetch_intraday_chart",
    "fetch_kospi_index",
    "fetch_market_breadth",
    "fetch_market_indices",
    "fetch_quote_by_code",
    "fetch_sector_rankings",
    "fetch_tencent_intraday_chart",
    "fetch_tencent_watch_quote_batch",
    "fetch_yahoo_intraday_chart",
    "format_timestamp",
    "fund_valuation_ttl",
    "http_get",
    "http_get_with_curl",
    "http_post_json",
    "is_before_market_open",
    "lookup_instrument",
    "market_now",
    "market_quote_ttl",
    "new_cookie_opener",
    "parse_fund123_nav_date",
    "seconds_until_next_market_open",
    "select_fund123_previous_nav",
    "store_value",
    "tencent_symbol",
    "to_float",
    "to_ratio_percent",
]
