"""On-exchange quotes and intraday curves from Tencent, plus Yahoo for overseas symbols."""
import json
import re
import urllib.error
import urllib.parse
from datetime import datetime

from .core import (
    cache_market_value,
    http_get,
    market_quote_ttl,
    to_float,
)


def tencent_symbol(code):
    """Resolve the sh/sz prefix Tencent expects for a six-digit A-share code."""
    normalized = str(code).strip().zfill(6)
    prefix = "sh" if normalized.startswith(("5", "6", "9")) else "sz"
    return normalized, f"{prefix}{normalized}"


def fetch_quote_by_code(code):
    normalized = str(code).strip()
    if not normalized:
        return None
    return cache_market_value(
        f"quote:{normalized}",
        lambda: _fetch_quote_by_code_live(normalized),
        market_quote_ttl()
    )


def _fetch_quote_by_code_live(code):
    normalized = str(code).strip()
    if not normalized:
        return None

    _, symbol = tencent_symbol(normalized)
    try:
        payload = http_get(f"https://qt.gtimg.cn/q={symbol}", encoding="gbk")
    except urllib.error.URLError:
        return None

    parts = payload.split("~")
    if len(parts) < 33:
        return None

    try:
        return {
            "name": parts[1] or normalized,
            "current_price": float(parts[3] or 0),
            "previous_close": float(parts[4] or 0),
            "change_rate": float(parts[32] or 0),
            "daily_change_rate": float(parts[32] or 0),
            "estimated_change_rate": None,
            "source_label": "腾讯行情"
        }
    except ValueError:
        return None


def fetch_tencent_watch_quote_batch(items):
    """Fetch many on-exchange (stock / ETF) quotes from Tencent's batch endpoint.

    ``items`` is an iterable of ``(code, asset_type)`` tuples. Asset type is ignored
    beyond market-prefix resolution — all on-exchange securities share the same
    ``qt.gtimg.cn/q=`` shape. Codes are normalised to 6 digits with the sh/sz
    prefix Tencent expects. Returns ``{normalized_code: quote_dict}`` for the
    entries Tencent actually returned; missing codes are simply absent.
    """
    specs = []
    for code, _asset_type in items:
        normalized = str(code or "").strip().zfill(6)
        if len(normalized) != 6 or not normalized.isdigit():
            continue
        specs.append(tencent_symbol(normalized))
    if not specs:
        return {}

    quote_map = {symbol: normalized for normalized, symbol in specs}
    try:
        # Tencent caps ``q=`` at a few hundred codes per call; the watchlist is
        # well within that, so a single request covers every item.
        payload = http_get(
            "https://qt.gtimg.cn/q=" + ",".join(symbol for _, symbol in specs),
            encoding="gbk"
        )
    except urllib.error.URLError:
        return {}

    results = {}
    for raw_line in payload.splitlines():
        if "=" not in raw_line:
            continue
        head, _, value = raw_line.partition("=")
        symbol = head.lstrip().lstrip("v_").strip()
        normalized = quote_map.get(symbol)
        if not normalized:
            continue
        value = value.strip().strip(";").strip('"')
        parts = value.split("~")
        if len(parts) < 33:
            continue
        try:
            results[normalized] = {
                "name": parts[1] or normalized,
                "current_price": float(parts[3] or 0),
                "previous_close": float(parts[4] or 0),
                "change_rate": float(parts[32] or 0),
                "daily_change_rate": float(parts[32] or 0),
                "estimated_change_rate": None,
                "source_label": "腾讯实时行情",
            }
        except ValueError:
            continue
    return results


def fetch_tencent_intraday_chart(code, is_index=False):
    normalized = str(code).strip()
    _, prefixed = tencent_symbol(normalized)
    symbol = normalized if is_index else prefixed
    try:
        payload = json.loads(http_get(f"https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={symbol}"))
        quote = (payload.get("data") or {}).get(symbol) or {}
        minute_data = quote.get("data") or {}
        raw_date = re.sub(r'\D', '', str(minute_data.get('date') or ''))
        trade_date = datetime.strptime(raw_date, '%Y%m%d').strftime('%Y-%m-%d') if len(raw_date) == 8 else None
        rows = minute_data.get("data") or []
        points = []
        for row in rows:
            fields = row.split()
            if len(fields) >= 2:
                points.append({"time": f"{fields[0][:2]}:{fields[0][2:]}", "price": float(fields[1])})
        details = (quote.get("qt") or {}).get(symbol) or []
        return {
            "name": details[1] if len(details) > 4 else normalized,
            "code": normalized,
            "trade_date": trade_date,
            "previous_close": float(details[4]) if len(details) > 4 else None,
            "points": points,
            "source_label": "腾讯分时行情"
        } if points else None
    except (urllib.error.URLError, ValueError, json.JSONDecodeError):
        return None


def fetch_yahoo_intraday_chart(symbol):
    """Use Yahoo's public minute feed for indexes unavailable from Tencent."""
    try:
        encoded_symbol = urllib.parse.quote(str(symbol).strip(), safe="")
        payload = json.loads(http_get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded_symbol}?range=1d&interval=5m",
            headers={"User-Agent": "Mozilla/5.0"}
        ))
        result = payload["chart"]["result"][0]
        meta = result.get("meta", {})
        quote = result.get("indicators", {}).get("quote", [{}])[0]
        points = [
            {"time": datetime.fromtimestamp(timestamp).strftime("%H:%M"), "price": float(price)}
            for timestamp, price in zip(result.get("timestamp", []), quote.get("close", []))
            if price is not None
        ]
        previous_close = to_float(meta.get("chartPreviousClose")) or to_float(meta.get("previousClose"))
        return {
            "name": meta.get("longName") or meta.get("shortName") or "指数",
            "code": str(symbol).lstrip("^"),
            "previous_close": previous_close,
            "points": points,
            "source_label": "Yahoo Finance 分时行情"
        } if points else None
    except (KeyError, IndexError, TypeError, ValueError, urllib.error.URLError, json.JSONDecodeError):
        return None
