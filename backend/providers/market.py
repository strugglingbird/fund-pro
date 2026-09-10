"""Market-wide aggregates: index quotes, KOSPI, breadth and industry sector rankings."""
import json
import threading
import time
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr
from datetime import timedelta
from io import StringIO

from .core import (
    FORCE_REFRESH,
    ak,
    cache_market_value,
    cache_entry,
    cached_value,
    http_get,
    http_get_with_curl,
    market_now,
    market_quote_ttl,
    store_value,
    to_float,
)

MARKET_INDEXES = [
    ("上证指数", "sh000001"),
    ("深证成指", "sz399001"),
    ("创业板指", "sz399006"),
    ("科创50", "sh000688"),
    ("恒生指数", "hkHSI"),
    ("恒生科技指数", "hkHSTECH"),
    ("道琼斯", "usDJI"),
    ("纳斯达克", "usIXIC"),
    ("标普500", "usINX")
]

KOSPI_CACHE_KEY = "kospi-index-page"
KOSPI_REFRESH_LOCK = threading.Lock()
KOSPI_REFRESHING = False


def fetch_market_indices():
    """Return cached major-market index quotes without blocking the page on serial I/O."""
    indices = list(cache_market_value(
        "market-indices",
        _fetch_market_indices_live,
        market_quote_ttl()
    ) or [])
    kospi = (cache_market_value(KOSPI_CACHE_KEY, fetch_kospi_index, market_quote_ttl())
             if FORCE_REFRESH.get() else cached_value(KOSPI_CACHE_KEY))
    if kospi:
        indices.append(kospi)
    if not FORCE_REFRESH.get():
        _schedule_kospi_refresh()
    return indices


def _schedule_kospi_refresh():
    """Keep the slower overseas fallback out of the first screen's request path."""
    global KOSPI_REFRESHING
    cached = cache_entry(KOSPI_CACHE_KEY)
    if cached and cached["expires_at"] > time.time():
        return
    with KOSPI_REFRESH_LOCK:
        if KOSPI_REFRESHING:
            return
        KOSPI_REFRESHING = True

    def refresh():
        global KOSPI_REFRESHING
        try:
            value = fetch_kospi_index()
            if value:
                store_value(KOSPI_CACHE_KEY, value, market_quote_ttl())
        finally:
            with KOSPI_REFRESH_LOCK:
                KOSPI_REFRESHING = False

    threading.Thread(target=refresh, name="kospi-index-refresh", daemon=True).start()


def _fetch_market_index_quote(index_spec):
    fallback_name, symbol = index_spec
    try:
        payload = http_get(f"https://qt.gtimg.cn/q={symbol}", encoding="gbk")
        parts = payload.split("~")
        if len(parts) < 33:
            return None
        current_price = float(parts[3] or 0)
        previous_close = float(parts[4] or 0)
        if current_price <= 0:
            return None
        return {
            "name": parts[1] or fallback_name,
            "code": symbol[2:],
            "intraday_symbol": symbol,
            "market": "hk" if symbol.startswith("hk") else "us" if symbol.startswith("us") else "cn",
            "current_price": current_price,
            "previous_close": previous_close,
            "change_rate": float(parts[32] or 0),
            "source_label": "腾讯行情"
        }
    except (urllib.error.URLError, ValueError):
        return None


def _fetch_market_indices_live():
    """Fetch all remote index quotes concurrently so cold starts stay within UI timeouts."""
    indices = []
    with ThreadPoolExecutor(max_workers=len(MARKET_INDEXES)) as executor:
        quote_futures = [executor.submit(_fetch_market_index_quote, index_spec) for index_spec in MARKET_INDEXES]
        for future in quote_futures:
            quote = future.result()
            if quote:
                indices.append(quote)
    return indices


def fetch_kospi_index():
    """Return KOSPI, falling back when AkShare's global snapshot is unavailable."""
    if ak is not None:
        try:
            frame = cache_market_value("kospi-index", ak.index_global_spot_em, market_quote_ttl())
            if frame is not None:
                rows = frame.to_dict(orient="records")
                row = next((item for item in rows if str(item.get("代码", "")) == "KS11" or "韩国" in str(item.get("名称", "")) or "KOSPI" in str(item.get("名称", "")).upper()), None)
                if row:
                    current = to_float(row.get("最新价"))
                    previous = to_float(row.get("昨收"))
                    change = to_float(row.get("涨跌幅"))
                    if current is not None:
                        return {"name": "韩国KOSPI", "code": "KS11", "intraday_symbol": "^KS11", "market": "kr", "current_price": current, "previous_close": previous or current, "change_rate": change or 0, "source_label": "AkShare 全球指数"}
        except Exception:
            pass

    try:
        payload = json.loads(http_get(
            "https://query1.finance.yahoo.com/v8/finance/chart/%5EKS11?range=5d&interval=1d",
            headers={"User-Agent": "Mozilla/5.0"}
        ))
        result = payload["chart"]["result"][0]
        meta = result.get("meta", {})
        quote = result.get("indicators", {}).get("quote", [{}])[0]
        closes = [value for value in quote.get("close", []) if value is not None]
        current = to_float(meta.get("regularMarketPrice")) or (closes[-1] if closes else None)
        previous = to_float(meta.get("chartPreviousClose")) or to_float(meta.get("previousClose"))
        if current is None:
            return None
        change = ((current - previous) / previous * 100) if previous else 0
        return {"name": "韩国KOSPI", "code": "KS11", "intraday_symbol": "^KS11", "market": "kr", "current_price": current, "previous_close": previous or current, "change_rate": change, "source_label": "Yahoo Finance 全球指数"}
    except (KeyError, IndexError, TypeError, ValueError, urllib.error.URLError):
        return None


def fetch_market_breadth():
    """Summarise all A-share advancing, declining and limit-move counts."""
    return cache_market_value("market-breadth", _fetch_market_breadth_live, market_quote_ttl())


def _fetch_market_breadth_live():
    if ak is None:
        return None
    try:
        frame = cache_market_value("akshare-stock-spot", ak.stock_zh_a_spot_em, market_quote_ttl())
        live_breadth = _build_market_breadth_from_spot(frame)
        if live_breadth:
            live_breadth.update({
                "data_date": market_now().strftime("%Y-%m-%d"),
                "is_realtime": True,
                "source_label": "AkShare 全 A 股实时行情"
            })
            return live_breadth
    except Exception:
        pass
    return _fetch_previous_market_breadth()


def _build_market_breadth_from_spot(frame):
    if frame is None or "涨跌幅" not in frame:
        return None
    changes = [to_float(value) for value in frame["涨跌幅"].tolist()]
    changes = [value for value in changes if value is not None]
    if not changes:
        return None
    return {
        "available": True,
        "rising": sum(value > 0 for value in changes),
        "falling": sum(value < 0 for value in changes),
        "flat": sum(value == 0 for value in changes),
        "limit_up": sum(value >= 9.9 for value in changes),
        "limit_down": sum(value <= -9.9 for value in changes),
        "total": len(changes)
    }


def _previous_market_date(now=None):
    now = now or market_now()
    candidate = now.date()
    if now.weekday() >= 5 or (now.hour, now.minute) < (9, 30):
        candidate -= timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate.strftime("%Y%m%d")


def _fetch_previous_market_breadth():
    """Use public last-trading-day aggregates when the real-time A-share snapshot is unavailable."""
    if ak is None:
        return None
    data_date = _previous_market_date()
    try:
        industry_frame = ak.stock_board_industry_summary_ths()
        rising = int(industry_frame["上涨家数"].fillna(0).sum())
        falling = int(industry_frame["下跌家数"].fillna(0).sum())
        if rising + falling <= 0:
            return None
    except Exception:
        return None

    limit_up = 0
    limit_down = 0
    try:
        limit_up = len(ak.stock_zt_pool_em(date=data_date))
    except Exception:
        pass
    try:
        limit_down = len(ak.stock_zt_pool_dtgc_em(date=data_date))
    except Exception:
        pass
    return {
        "available": True,
        "rising": rising,
        "falling": falling,
        "flat": 0,
        "limit_up": limit_up,
        "limit_down": limit_down,
        "total": rising + falling,
        "data_date": f"{data_date[:4]}-{data_date[4:6]}-{data_date[6:]}",
        "is_realtime": False,
        "source_label": "AkShare 同花顺行业汇总 / 东方财富涨跌停池"
    }


def fetch_sector_rankings():
    return cache_market_value(
        "sector-rankings",
        _fetch_sector_rankings_live,
        market_quote_ttl()
    )


def _fetch_sector_rankings_live():
    """Load live industry-sector gainers and losers through AkShare."""
    if ak is not None:
        try:
            # AkShare displays a tqdm progress bar while paging the THS list.
            with redirect_stderr(StringIO()):
                frame = ak.stock_board_industry_summary_ths()
            columns = list(frame.columns)
            name_key = next((column for column in columns if "名称" in str(column)), columns[1])
            change_key = next((column for column in columns if "涨跌幅" in str(column)), columns[2])
            records = frame.to_dict(orient="records")
            sectors = []
            for row in records:
                name = row.get(name_key)
                change_rate = row.get(change_key)
                if not name or change_rate is None:
                    continue
                try:
                    rate = float(change_rate)
                except (TypeError, ValueError):
                    continue
                sectors.append({
                    "name": str(name),
                    "change_rate": rate,
                    "reason": "AkShare 同花顺行业板块实时涨跌幅"
                })
            if sectors:
                return {
                    "gainers": sorted(sectors, key=lambda item: item["change_rate"], reverse=True)[:10],
                    "losers": sorted(sectors, key=lambda item: item["change_rate"])[:10],
                    "source_label": "AkShare 同花顺行业板块实时行情"
                }
        except Exception:
            pass

    return fetch_eastmoney_sector_rankings()


def fetch_eastmoney_sector_rankings():
    """Fall back to Eastmoney's public feed when AkShare is unavailable."""
    fields = "f12,f14,f2,f3"
    hosts = ["push2.eastmoney.com", "82.push2.eastmoney.com"]

    def fetch_ranked_sectors(descending):
        query = urllib.parse.urlencode(
            {
                "pn": 1,
                "pz": 10,
                "po": 1 if descending else 0,
                "np": 1,
                "fltt": 2,
                "invt": 2,
                "fid": "f3",
                "fs": "m:90+t:2",
                "fields": fields
            }
        )
        rows = []
        for host in hosts:
            try:
                body = http_get_with_curl(f"https://{host}/api/qt/clist/get?{query}")
                rows = ((json.loads(body).get("data") or {}).get("diff") or [])
                if rows:
                    break
            except (OSError, json.JSONDecodeError):
                continue
        return [
            {
                "name": row.get("f14") or row.get("f12"),
                "code": row.get("f12"),
                "change_rate": float(row.get("f3") or 0),
                "reason": "东方财富行业板块实时涨跌幅"
            }
            for row in rows
            if row.get("f14") is not None and row.get("f3") is not None
        ]

    try:
        gainers = fetch_ranked_sectors(descending=True)
        losers = fetch_ranked_sectors(descending=False)
        return {
            "gainers": gainers,
            "losers": losers,
            "source_label": "东方财富行业板块实时行情（回退）"
        } if gainers and losers else None
    except Exception:
        return None
