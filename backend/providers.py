import json
import os
import re
import ssl
import http.cookiejar
import shutil
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import redirect_stderr
from contextvars import ContextVar
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from io import StringIO

try:
    import akshare as ak
except ImportError:
    ak = None


SSL_CONTEXT = ssl._create_unverified_context()

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

IMPORTANT_NEWS_KEYWORDS = (
    "国务院", "证监会", "央行", "财政部", "发改委", "美联储", "降准", "降息", "加息",
    "政策", "监管", "业绩", "财报", "回购", "增持", "并购", "重组", "停牌", "涨停",
    "跌停", "GDP", "CPI", "PMI", "关税", "战争"
)
NEWS_CACHE = {"expires_at": 0, "payload": None}
NEWS_CACHE_LOCK = threading.Lock()
MARKET_CACHE = {}
MARKET_CACHE_LOCK = threading.Lock()
KOSPI_REFRESH_LOCK = threading.Lock()
KOSPI_REFRESHING = False
FORCE_REFRESH = ContextVar("force_refresh", default=False)
CHINA_TIMEZONE = timezone(timedelta(hours=8))


def market_now():
    """Return naive China Standard Time so market rules are host-timezone independent."""
    return datetime.now(CHINA_TIMEZONE).replace(tzinfo=None)


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


def http_get(url, headers=None, encoding="utf-8", opener=None):
    request = urllib.request.Request(
        url,
        headers=headers or {
            "User-Agent": "Mozilla/5.0 FundProWorkbench/0.1"
        }
    )
    client = opener or urllib.request.build_opener(urllib.request.HTTPSHandler(context=SSL_CONTEXT))
    with client.open(request, timeout=10) as response:
        return response.read().decode(encoding, errors="ignore")


def http_post_json(url, payload, headers=None, opener=None):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers or {
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 FundProWorkbench/0.1"
        },
        method="POST"
    )
    client = opener or urllib.request.build_opener(urllib.request.HTTPSHandler(context=SSL_CONTEXT))
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


def fetch_quote_by_code(code):
    normalized = str(code).strip()
    if not normalized:
        return None
    return cache_market_value(
        f"quote:{normalized}",
        lambda: _fetch_quote_by_code_live(normalized),
        market_quote_ttl()
    )


def fetch_akshare_watch_quote(code, asset_type):
    """Use AkShare spot data for exchange-traded watchlist instruments."""
    normalized = str(code).strip()
    if not normalized or ak is None:
        return fetch_quote_by_code(normalized)
    cache_key = "akshare-etf-spot" if asset_type == "etf" else "akshare-stock-spot"
    try:
        frame = cache_market_value(
            cache_key,
            lambda: ak.fund_etf_spot_em() if asset_type == "etf" else ak.stock_zh_a_spot_em(),
            market_quote_ttl()
        )
        if frame is not None:
            rows = frame.to_dict(orient="records")
            row = next((item for item in rows if str(item.get("代码", "")).zfill(6) == normalized.zfill(6)), None)
            if row:
                current = _to_float(row.get("最新价"))
                previous = _to_float(row.get("昨收"))
                change = _to_float(row.get("涨跌幅"))
                if current is not None:
                    return {"name": row.get("名称") or normalized, "current_price": current,
                            "previous_close": previous or current, "change_rate": change or 0,
                            "daily_change_rate": change or 0, "estimated_change_rate": None,
                            "source_label": "AkShare 实时行情"}
    except Exception:
        pass
    return fetch_quote_by_code(normalized)


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
    changes = [_to_float(value) for value in frame["涨跌幅"].tolist()]
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


def _fetch_quote_by_code_live(code):
    normalized = str(code).strip()
    if not normalized:
        return None

    market_prefix = "sh" if normalized.startswith(("5", "6", "9")) else "sz"
    url = f"https://qt.gtimg.cn/q={market_prefix}{normalized}"
    try:
        payload = http_get(url, encoding="gbk")
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


def fetch_market_indices():
    """Return cached major-market index quotes without blocking the page on serial I/O."""
    indices = list(cache_market_value(
        "market-indices",
        _fetch_market_indices_live,
        market_quote_ttl()
    ) or [])
    kospi = (cache_market_value("kospi-index-page", fetch_kospi_index, market_quote_ttl())
             if FORCE_REFRESH.get() else _get_cached_market_value("kospi-index-page"))
    if kospi:
        indices.append(kospi)
    if not FORCE_REFRESH.get():
        _schedule_kospi_refresh()
    return indices


def _get_cached_market_value(key):
    """Return the latest cached value, including a stale one while it refreshes in the background."""
    with MARKET_CACHE_LOCK:
        cached = MARKET_CACHE.get(key)
        return cached["value"] if cached else None


def _schedule_kospi_refresh():
    """Keep the slower overseas fallback out of the first screen's request path."""
    global KOSPI_REFRESHING
    with MARKET_CACHE_LOCK:
        cached = MARKET_CACHE.get("kospi-index-page")
        is_fresh = cached and cached["expires_at"] > time.time()
    if is_fresh:
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
                with MARKET_CACHE_LOCK:
                    MARKET_CACHE["kospi-index-page"] = {
                        "value": value,
                        "expires_at": time.time() + market_quote_ttl()
                    }
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
                    current = _to_float(row.get("最新价"))
                    previous = _to_float(row.get("昨收"))
                    change = _to_float(row.get("涨跌幅"))
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
        current = _to_float(meta.get("regularMarketPrice")) or (closes[-1] if closes else None)
        previous = _to_float(meta.get("chartPreviousClose")) or _to_float(meta.get("previousClose"))
        if current is None:
            return None
        change = ((current - previous) / previous * 100) if previous else 0
        return {"name": "韩国KOSPI", "code": "KS11", "intraday_symbol": "^KS11", "market": "kr", "current_price": current, "previous_close": previous or current, "change_rate": change, "source_label": "Yahoo Finance 全球指数"}
    except (KeyError, IndexError, TypeError, ValueError, urllib.error.URLError):
        return None


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


def fetch_financial_news():
    """Aggregate important real-time financial headlines from AkShare sources."""
    with NEWS_CACHE_LOCK:
        if not FORCE_REFRESH.get() and NEWS_CACHE["payload"] and NEWS_CACHE["expires_at"] > time.time():
            return NEWS_CACHE["payload"]

    groups = []
    if ak is not None:
        source_specs = [
            ("财联社电报", lambda: ak.stock_info_global_cls(symbol="重点"), 6),
            ("东方财富", ak.stock_info_global_em, 4),
            ("新浪财经", ak.stock_info_global_sina, 4),
            ("富途牛牛", ak.stock_info_global_futu, 4),
            ("同花顺", ak.stock_info_global_ths, 4)
        ]
        for source, fetcher, limit in source_specs:
            try:
                groups.append({
                    "source": source,
                    "items": _normalise_news_items(fetcher(), source, limit)
                })
            except Exception:
                continue

    groups = [group for group in groups if group["items"]]
    if not groups:
        return None

    items = [item for group in groups for item in group["items"]]
    payload = {
        "items": items,
        "groups": groups,
        "total_count": len(items),
        "source_label": "AkShare 财经快讯聚合",
        "generated_at": market_now().strftime("%Y-%m-%d %H:%M:%S")
    }
    with NEWS_CACHE_LOCK:
        NEWS_CACHE["payload"] = payload
        NEWS_CACHE["expires_at"] = time.time() + 30
    return payload


def _normalise_news_items(frame, source, limit):
    """Map the different AkShare news DataFrame layouts into one UI schema."""
    columns = list(frame.columns)
    records = frame.to_dict(orient="records")
    title_key = next((column for column in columns if "标题" in str(column)), columns[0])
    content_key = next(
        (column for column in columns if any(text in str(column) for text in ("内容", "摘要", "快讯"))),
        columns[1] if len(columns) > 1 else columns[0]
    )
    time_key = next((column for column in columns if "时间" in str(column)), None)
    url_key = next((column for column in columns if "链接" in str(column)), None)
    items = []
    for index, row in enumerate(records):
        title = _clean_news_text(row.get(title_key))
        summary = _clean_news_text(row.get(content_key))
        if not title:
            title, summary = summary, ""
        if not title:
            continue
        score = sum(keyword in f"{title} {summary}" for keyword in IMPORTANT_NEWS_KEYWORDS)
        if source == "财联社电报":
            score += 2
        items.append({
            "id": f"{source}-{index}-{title[:16]}",
            "title": title,
            "summary": summary or "重点财经快讯，建议结合市场走势跟踪影响。",
            "source": source,
            "published_at": str(row.get(time_key) or "最新"),
            "url": str(row.get(url_key) or ""),
            "importance": score
        })

    important = [item for item in items if item["importance"] > 0]
    selected = sorted(
        important or items,
        key=lambda item: item["published_at"],
        reverse=True
    )[:limit]
    for item in selected:
        item.pop("importance", None)
    return selected


def _clean_news_text(value):
    text = re.sub(r"<[^>]+>", "", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def fetch_tencent_intraday_chart(code, is_index=False):
    normalized = str(code).strip()
    market_prefix = "sh" if normalized.startswith(("5", "6", "9")) else "sz"
    symbol = normalized if is_index else f"{market_prefix}{normalized}"
    try:
        payload = json.loads(http_get(f"https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={symbol}"))
        quote = (payload.get("data") or {}).get(symbol) or {}
        minute_data = quote.get("data") or {}
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
        previous_close = _to_float(meta.get("chartPreviousClose")) or _to_float(meta.get("previousClose"))
        return {
            "name": meta.get("longName") or meta.get("shortName") or "指数",
            "code": str(symbol).lstrip("^"),
            "previous_close": previous_close,
            "points": points,
            "source_label": "Yahoo Finance 分时行情"
        } if points else None
    except (KeyError, IndexError, TypeError, ValueError, urllib.error.URLError, json.JSONDecodeError):
        return None


def fetch_fund123_intraday_chart(code):
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://www.fund123.cn",
        "Referer": "https://www.fund123.cn/fund",
        "User-Agent": "Mozilla/5.0 FundProWorkbench/0.1",
        "X-API-Key": "foobar"
    }
    try:
        cookie_jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cookie_jar),
            urllib.request.HTTPSHandler(context=SSL_CONTEXT)
        )
        page = http_get("https://www.fund123.cn/fund", headers=headers, opener=opener)
        csrf_match = re.search(r'"csrf"\s*:\s*"(?P<csrf>[^"]+)"', page)
        if not csrf_match:
            return None
        csrf = urllib.parse.quote(csrf_match.group("csrf"), safe="")
        search_body = http_post_json(
            f"https://www.fund123.cn/api/fund/searchFund?_csrf={csrf}",
            {"fundCode": code}, headers=headers, opener=opener
        )
        fund_info = (json.loads(search_body).get("fundInfo") or {})
        material = http_get(
            f"https://www.fund123.cn/matiaria?fundCode={urllib.parse.quote(code)}",
            headers=headers,
            opener=opener
        )
        product_id_match = re.search(r'"productId"\s*:\s*"(?P<product_id>[^"]+)"', material)
        product_id = product_id_match.group("product_id") if product_id_match else fund_info.get("key")
        if not product_id:
            return None
        history_nav = fetch_fund123_previous_nav(product_id, csrf, headers, opener)
        material = http_get(
            f"https://www.fund123.cn/matiaria?fundCode={urllib.parse.quote(code)}",
            headers=headers, opener=opener
        )
        nav_match = re.search(r'"netValue"\s*:\s*"(?P<nav>\d+(?:\.\d+)?)"', material)
        if not history_nav and not nav_match:
            return None
        previous_close = round(history_nav or float(nav_match.group("nav")), 4)
        today = market_now().strftime("%Y-%m-%d")
        tomorrow = (market_now() + timedelta(days=1)).strftime("%Y-%m-%d")
        estimate_body = http_post_json(
            f"https://www.fund123.cn/api/fund/queryFundEstimateIntraday?_csrf={csrf}",
            {"startTime": today, "endTime": tomorrow, "limit": 200, "productId": product_id, "format": True, "source": "WEALTHBFFWEB"},
            headers=headers, opener=opener
        )
        estimates = (json.loads(estimate_body).get("list") or [])
        points = []
        estimates.sort(key=lambda item: float(item.get("time") or 0))
        for item in estimates:
            rate = float(item.get("forecastGrowth") or 0)
            price = round(previous_close * (1 + rate), 4)
            points.append({
                "time": datetime.fromtimestamp(float(item.get("time") or 0) / 1000).strftime("%H:%M"),
                "price": price
            })
        return {
            "name": fund_info.get("fundName") or code,
            "code": code,
            "previous_close": previous_close,
            "points": points,
            "updated_at": datetime.fromtimestamp(float(estimates[-1]["time"]) / 1000).strftime("%Y-%m-%d %H:%M:%S") if estimates and estimates[-1].get("time") else None,
            "source_label": "fund123 盘中预估"
        } if points else None
    except (urllib.error.URLError, ValueError, json.JSONDecodeError):
        return None


def fetch_fund123_history_navs(product_id, csrf, headers, opener):
    """Fetch the latest fund123 NAV records as ``(YYYYMMDD, nav)`` pairs."""
    now = market_now()
    today = now.date()
    payload = {
        "productId": product_id,
        # Keep a three-month window matching fund123's accepted request shape.
        "startDate": (today - timedelta(days=92)).strftime("%Y%m%d"),
        "endDate": today.strftime("%Y%m%d"),
        "pageNum": 1,
        "pageSize": 10
    }
    try:
        body = http_post_json(
            f"https://www.fund123.cn/api/fund/queryFundHistoryNetValueList?_csrf={csrf}",
            payload,
            headers=headers,
            opener=opener
        )
        response = json.loads(body)
    except (urllib.error.URLError, ValueError, json.JSONDecodeError):
        return None

    data = response.get("data") or response
    rows = data.get("list") or data.get("records") or response.get("list") or []
    candidates = []
    for row in rows:
        date_value = str(row.get("netValueDate") or row.get("date") or row.get("navDate") or "")
        date_digits = re.sub(r"\D", "", date_value)[:8]
        value = row.get("netValue") or row.get("nav") or row.get("unitNetValue") or row.get("value")
        try:
            nav = float(value)
        except (TypeError, ValueError):
            continue
        if nav > 0:
            candidates.append((date_digits, round(nav, 4)))

    return candidates


def select_fund123_previous_nav(candidates, now=None):
    """Choose a stable reference NAV without advancing it at midnight."""
    now = now or market_now()
    today = now.date()
    # Before 09:30, retain the value shown during the prior calendar day.
    reference_date = today - timedelta(days=2 if (now.hour, now.minute) < (9, 30) else 1)
    prior_dates = [
        item for item in candidates
        if item[0] and item[0] <= reference_date.strftime("%Y%m%d")
    ]
    if prior_dates:
        return max(prior_dates, key=lambda item: item[0])[1]
    return candidates[0][1] if candidates else None


def fetch_fund123_previous_nav(product_id, csrf, headers, opener):
    """Load OTC fund previous NAV once per day after the 09:30 market open."""
    cache_key = f"fund-previous-nav:{product_id}"
    if is_before_market_open() and not FORCE_REFRESH.get():
        # Before the next session opens, reuse the last confirmed closing NAV.
        return cache_market_value(cache_key)
    return cache_market_value(
        cache_key,
        lambda: select_fund123_previous_nav(
            fetch_fund123_history_navs(product_id, csrf, headers, opener) or []
        ),
        seconds_until_next_market_open()
    )


def select_fund123_today_nav(candidates, now=None):
    """Return today's published NAV only; no estimate is treated as a quote."""
    now = now or market_now()
    today = now.strftime("%Y%m%d")
    today_values = [item for item in candidates if item[0] == today]
    return max(today_values, key=lambda item: item[0])[1] if today_values else None


def parse_fund123_nav_date(material, now=None):
    """Normalize fund123's netValueDate (usually MM-DD) to YYYYMMDD."""
    match = re.search(r'"netValueDate"\s*:\s*"(?P<date>[^\"]+)"', material or "")
    if not match:
        return None
    now = now or market_now()
    digits = re.sub(r"\D", "", match.group("date"))
    if len(digits) >= 8:
        return digits[:8]
    if len(digits) != 4:
        return None
    candidate = f"{now.year}{digits}"
    try:
        candidate_date = datetime.strptime(candidate, "%Y%m%d").date()
    except ValueError:
        return None
    if candidate_date > now.date() + timedelta(days=7):
        candidate = f"{now.year - 1}{digits}"
    return candidate


def fetch_intraday_chart(asset_type, code):
    if asset_type == "fund":
        return fetch_fund123_intraday_chart(code)
    if asset_type == "index":
        normalized = str(code).strip()
        yahoo_symbols = {"usDJI": "^DJI", "usIXIC": "^IXIC", "usINX": "^GSPC"}
        if normalized.startswith("^") or normalized in yahoo_symbols:
            return fetch_yahoo_intraday_chart(yahoo_symbols.get(normalized, normalized))
        return fetch_tencent_intraday_chart(normalized, is_index=True)
    return fetch_tencent_intraday_chart(code)


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
    now = market_now()
    current_price = value.get("current_price")
    previous_close = value.get("previous_close")
    nav_is_published = current_price is not None
    ttl = seconds_until_next_market_open(now) if (now.hour, now.minute) >= (15, 0) and nav_is_published else fund_valuation_ttl(now)
    return cache_market_value(cache_key, lambda: value, ttl)


def _fetch_fund_valuation_live(normalized):

    configured_url = os.environ.get("FUND123_ESTIMATE_URL")
    if configured_url:
        fund123 = fetch_fund123_valuation(configured_url, normalized)
        if fund123:
            return fund123

    fund123_intraday = fetch_fund123_intraday_valuation(normalized)
    if fund123_intraday:
        return fund123_intraday

    fundgz = fetch_eastmoney_fundgz_valuation(normalized)
    if fundgz:
        return fundgz

    eastmoney = fetch_eastmoney_valuation(normalized)
    if eastmoney:
        return eastmoney
    profile = fetch_eastmoney_fund_profile(normalized)
    if profile:
        return profile
    return fetch_fund123_page_guess(normalized)


def fetch_eastmoney_fundgz_valuation(code):
    """Read the public fundgz script, which also works for many OTC fund codes."""
    try:
        body = http_get(
            f"https://fundgz.1234567.com.cn/js/{urllib.parse.quote(code)}.js",
            headers={"Referer": "https://fund.eastmoney.com/", "User-Agent": "Mozilla/5.0 FundProWorkbench/0.1"}
        )
    except urllib.error.URLError:
        return None

    match = re.search(r"jsonpgz\((?P<payload>\{.*\})\)", body)
    if not match:
        return None
    try:
        payload = json.loads(match.group("payload"))
        nav = float(payload.get("dwjz") or 0)
        estimate = float(payload.get("gsz") or nav)
        if estimate <= 0:
            return None
        return {
            "name": payload.get("name") or code,
            "current_price": None,
            "estimated_price": round(estimate, 4),
            "previous_close": round(nav, 4),
            "change_rate": float(payload.get("gszzl") or 0),
            "daily_change_rate": None,
            "estimated_change_rate": float(payload.get("gszzl") or 0),
            "time": payload.get("gztime") or payload.get("jzrq") or "",
            "source_label": "东方财富基金估值"
        }
    except (ValueError, json.JSONDecodeError):
        return None


def fetch_eastmoney_fund_profile(code):
    """Fall back to the fund detail script when intraday valuation is unavailable."""
    try:
        body = http_get(
            f"https://fund.eastmoney.com/pingzhongdata/{urllib.parse.quote(code)}.js",
            headers={"Referer": f"https://fund.eastmoney.com/{code}.html", "User-Agent": "Mozilla/5.0 FundProWorkbench/0.1"}
        )
    except urllib.error.URLError:
        return None

    name_match = re.search(r'var\s+fS_name\s*=\s*"(?P<name>[^"]+)"', body)
    trend_match = re.search(r"var\s+Data_netWorthTrend\s*=\s*(?P<trend>\[.*?\]);", body, re.S)
    if not name_match or not trend_match:
        return None
    try:
        trend = json.loads(trend_match.group("trend"))
        latest = trend[-1] if trend else {}
        previous = trend[-2] if len(trend) > 1 else latest
        current_price = float(latest.get("y") or 0)
        previous_close = float(previous.get("y") or current_price)
        if current_price <= 0:
            return None
        change_rate = ((current_price - previous_close) / previous_close * 100) if previous_close else 0
        return {
            "name": name_match.group("name"),
            "current_price": current_price,
            "previous_close": previous_close,
            "change_rate": change_rate,
            "daily_change_rate": change_rate,
            "estimated_change_rate": None,
            "source_label": "东方财富最新净值"
        }
    except (ValueError, json.JSONDecodeError):
        return None


def fetch_fund123_metadata(code):
    """Resolve an off-exchange fund name through fund123's public search flow."""
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.fund123.cn",
        "Referer": "https://www.fund123.cn/fund",
        "User-Agent": "Mozilla/5.0 FundProWorkbench/0.1"
    }
    try:
        page = http_get("https://www.fund123.cn/fund", headers=headers)
        csrf_match = re.search(r'"csrf"\s*:\s*"(?P<csrf>[^"]+)"', page)
        if not csrf_match:
            return None
        csrf = urllib.parse.quote(csrf_match.group("csrf"), safe="")
        body = http_post_json(
            f"https://www.fund123.cn/api/fund/searchFund?_csrf={csrf}",
            {"fundCode": code},
            headers={**headers, "Content-Type": "application/json", "X-API-Key": "foobar"}
        )
        payload = json.loads(body)
        fund_info = payload.get("fundInfo") or {}
        name = fund_info.get("fundName")
        return {
            "name": name,
            "key": fund_info.get("key"),
            "source_label": "fund123 基金检索"
        } if name else None
    except (urllib.error.URLError, json.JSONDecodeError):
        return None


def fetch_fund123_holdings(code):
    """Fetch the latest disclosed stock holdings for an OTC fund from fund123."""
    normalized = str(code).strip()
    if not normalized:
        return None
    return cache_market_value(
        f"fund-holdings:{normalized}",
        lambda: _fetch_fund123_holdings_live(normalized),
        21600
    )


def fetch_fund123_history_nav_list(code, start_date=None, end_date=None):
    """Fetch disclosed OTC-fund NAV history for the selected date range."""
    normalized = str(code).strip()
    if not normalized:
        return None
    start = re.sub(r"\D", "", str(start_date or ""))[:8]
    end = re.sub(r"\D", "", str(end_date or ""))[:8]
    today = market_now().strftime("%Y%m%d")
    start = start if len(start) == 8 else (market_now() - timedelta(days=92)).strftime("%Y%m%d")
    end = end if len(end) == 8 else today
    if start > end:
        start, end = end, start
    return cache_market_value(
        f"fund-history:{normalized}:{start}:{end}",
        lambda: _fetch_fund123_history_nav_list_live(normalized, start, end),
        600
    )


def fetch_fund123_performance_curve(code, interval="THREE"):
    normalized = str(code).strip()
    allowed = {"ONE", "THREE", "SIX", "ONE_YEAR"}
    if not normalized or interval not in allowed:
        return None
    return cache_market_value(
        f"fund-performance:{normalized}:{interval}",
        lambda: _fetch_fund123_performance_curve_live(normalized, interval),
        600
    )


def _fetch_fund123_performance_curve_live(code, interval):
    headers = {"Accept": "application/json, text/plain, */*", "Content-Type": "application/json", "Origin": "https://www.fund123.cn", "Referer": "https://www.fund123.cn/fund", "User-Agent": "Mozilla/5.0 FundProWorkbench/0.1", "X-API-Key": "foobar"}
    try:
        jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar), urllib.request.HTTPSHandler(context=SSL_CONTEXT))
        page = http_get("https://www.fund123.cn/fund", headers=headers, opener=opener)
        csrf_match = re.search(r'"csrf"\s*:\s*"(?P<csrf>[^"]+)"', page)
        if not csrf_match: return None
        csrf = urllib.parse.quote(csrf_match.group("csrf"), safe="")
        material = http_get(f"https://www.fund123.cn/matiaria?fundCode={urllib.parse.quote(code)}", headers=headers, opener=opener)
        product_match = re.search(r'"productId"\s*:\s*"(?P<product_id>[^"]+)"', material)
        if not product_match: return None
        api_interval = {"ONE": "ONE_MONTH", "THREE": "THREE_MONTH", "SIX": "SIX_MONTH", "ONE_YEAR": "ONE_YEAR"}[interval]
        body = http_post_json(f"https://www.fund123.cn/api/fund/queryFundQuotationCurves?_csrf={csrf}", {"productId": product_match.group("product_id"), "dateInterval": api_interval}, headers=headers, opener=opener)
        points = json.loads(body).get("points") or []
    except (urllib.error.URLError, ValueError, json.JSONDecodeError):
        return None
    series = {"fund": [], "indexbase": []}
    for point in points:
        kind, date, rate = point.get("type"), point.get("reportDateTimestamp"), _to_float(point.get("rate"))
        if kind in series and date and rate is not None: series[kind].append({"date": date, "rate": round(rate * 100, 2)})
    days_by_interval = {"ONE": 31, "THREE": 92, "SIX": 184, "ONE_YEAR": 366}
    all_dates = [item["date"] for values in series.values() for item in values]
    if all_dates:
        latest_date = max(datetime.strptime(date, "%Y-%m-%d").date() for date in all_dates)
        cutoff = latest_date - timedelta(days=days_by_interval[interval])
        for kind in series:
            series[kind] = [item for item in series[kind] if datetime.strptime(item["date"], "%Y-%m-%d").date() >= cutoff]
    return {"fund": series["fund"], "index": series["indexbase"], "source_label": "fund123 业绩走势"}


def _fetch_fund123_history_nav_list_live(code, start_date, end_date):
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://www.fund123.cn",
        "Referer": "https://www.fund123.cn/fund",
        "User-Agent": "Mozilla/5.0 FundProWorkbench/0.1",
        "X-API-Key": "foobar"
    }
    try:
        cookie_jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cookie_jar),
            urllib.request.HTTPSHandler(context=SSL_CONTEXT)
        )
        page = http_get("https://www.fund123.cn/fund", headers=headers, opener=opener)
        csrf_match = re.search(r'"csrf"\s*:\s*"(?P<csrf>[^"]+)"', page)
        if not csrf_match:
            return None
        csrf = urllib.parse.quote(csrf_match.group("csrf"), safe="")
        search_body = http_post_json(
            f"https://www.fund123.cn/api/fund/searchFund?_csrf={csrf}",
            {"fundCode": code}, headers=headers, opener=opener
        )
        fund_info = (json.loads(search_body).get("fundInfo") or {})
        material = http_get(
            f"https://www.fund123.cn/matiaria?fundCode={urllib.parse.quote(code)}",
            headers=headers, opener=opener
        )
        product_id_match = re.search(r'"productId"\s*:\s*"(?P<product_id>[^"]+)"', material)
        product_id = product_id_match.group("product_id") if product_id_match else fund_info.get("key")
        if not product_id:
            return None
        body = http_post_json(
            f"https://www.fund123.cn/api/fund/queryFundHistoryNetValueList?_csrf={csrf}",
            {
                "productId": product_id,
                "startDate": start_date,
                "endDate": end_date,
                "pageNum": 1,
                "pageSize": 100
            },
            headers=headers,
            opener=opener
        )
        payload = json.loads(body)
    except (urllib.error.URLError, ValueError, json.JSONDecodeError):
        return None

    rows = payload.get("list") or (payload.get("data") or {}).get("list") or []
    items = []
    for row in rows:
        unit_nav = _to_float(row.get("netValue"))
        if unit_nav is None:
            continue
        items.append({
            "date": row.get("netValueDate") or row.get("date") or "--",
            "unit_nav": round(unit_nav, 4),
            "total_nav": round(_to_float(row.get("totalNetValue")) or unit_nav, 4),
            "daily_change_rate": _to_ratio_percent(row.get("dayOfGrowth"))
        })
    items.sort(key=lambda item: item["date"], reverse=True)
    return {
        "name": fund_info.get("fundName") or code,
        "items": items,
        "source_label": "fund123 历史净值",
        "updated_at": market_now().strftime("%Y-%m-%d %H:%M:%S")
    }


def _fetch_fund123_holdings_live(code):
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://www.fund123.cn",
        "Referer": "https://www.fund123.cn/fund",
        "User-Agent": "Mozilla/5.0 FundProWorkbench/0.1",
        "X-API-Key": "foobar"
    }
    try:
        cookie_jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cookie_jar),
            urllib.request.HTTPSHandler(context=SSL_CONTEXT)
        )
        page = http_get("https://www.fund123.cn/fund", headers=headers, opener=opener)
        csrf_match = re.search(r'"csrf"\s*:\s*"(?P<csrf>[^"]+)"', page)
        if not csrf_match:
            return None
        csrf = urllib.parse.quote(csrf_match.group("csrf"), safe="")
        search_body = http_post_json(
            f"https://www.fund123.cn/api/fund/searchFund?_csrf={csrf}",
            {"fundCode": code},
            headers=headers,
            opener=opener
        )
        fund_info = (json.loads(search_body).get("fundInfo") or {})
        material = http_get(
            f"https://www.fund123.cn/matiaria?fundCode={urllib.parse.quote(code)}",
            headers=headers,
            opener=opener
        )
        product_id_match = re.search(r'"productId"\s*:\s*"(?P<product_id>[^"]+)"', material)
        product_id = product_id_match.group("product_id") if product_id_match else fund_info.get("key")
        if not product_id:
            return None
        body = http_post_json(
            f"https://www.fund123.cn/api/fund/queryFundHolding?_csrf={csrf}",
            {"productId": product_id},
            headers=headers,
            opener=opener
        )
        payload = json.loads(body)
    except (urllib.error.URLError, ValueError, json.JSONDecodeError):
        return None

    rows = _find_fund_holding_rows(payload)
    stock_position = _find_stock_position(payload)
    items = []
    for index, row in enumerate(rows):
        name = (
            row.get("stockName") or row.get("securityName") or row.get("securityShortName")
            or row.get("stockShortName") or row.get("name") or row.get("fundName")
        )
        if not name:
            continue
        items.append({
            "id": f"{code}-{index}",
            "name": name,
            "code": row.get("stockCode") or row.get("securityCode") or row.get("securityId") or row.get("code") or "--",
            "weight": _to_ratio_percent(row.get("netWorthRatio") or row.get("holdingRatio") or row.get("holdRatio") or row.get("holdPercent") or row.get("ratio") or row.get("proportion")),
            "change_rate": _to_ratio_percent(row.get("changeRate") or row.get("riseRate") or row.get("change_ratio")),
            "shares": _to_float(row.get("holdingQuantity") or row.get("holdAmount") or row.get("shareNum") or row.get("shares") or row.get("amount")),
            "market_value": _to_float(row.get("marketValue") or row.get("holdingMarketValue") or row.get("marketAmount") or row.get("marketVal"))
        })
    return {
        "name": fund_info.get("fundName") or code,
        "items": items,
        "report_date": payload.get("reportDate") if isinstance(payload, dict) else None,
        "stock_position": stock_position,
        "source_label": "fund123 基金持仓",
        "updated_at": market_now().strftime("%Y-%m-%d %H:%M:%S")
    }


def _to_float(value):
    try:
        return float(str(value).replace("%", "").replace(",", ""))
    except (TypeError, ValueError):
        return None


def _to_ratio_percent(value):
    """Convert fund123 decimal ratios such as 0.0963 to percentage values."""
    numeric = _to_float(value)
    if numeric is None:
        return None
    return numeric * 100 if abs(numeric) <= 1 else numeric


def _find_stock_position(payload):
    if not isinstance(payload, dict):
        return None
    for asset in payload.get("assetList") or []:
        if not isinstance(asset, dict) or not asset.get("stock"):
            continue
        return _to_ratio_percent(asset.get("proportionOfAssets"))
    return None


def _find_fund_holding_rows(payload, depth=0):
    """Locate a stock-holding list even when fund123 nests it by report period."""
    if depth > 5:
        return []
    if isinstance(payload, list):
        if payload and isinstance(payload[0], dict):
            fields = set().union(*(item.keys() for item in payload[:3]))
            if fields.intersection({"stockName", "securityName", "securityShortName", "stockCode", "securityCode"}):
                return payload
        for item in payload:
            found = _find_fund_holding_rows(item, depth + 1)
            if found:
                return found
    if isinstance(payload, dict):
        for key in ("holdingList", "fundHoldingList", "stockHoldingList", "list", "records", "data"):
            if key in payload:
                found = _find_fund_holding_rows(payload[key], depth + 1)
                if found:
                    return found
        for value in payload.values():
            found = _find_fund_holding_rows(value, depth + 1)
            if found:
                return found
    return []


def fetch_fund123_intraday_valuation(code):
    """Use fund123's forecastGrowth field to derive the intraday estimated NAV."""
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://www.fund123.cn",
        "Referer": "https://www.fund123.cn/fund",
        "User-Agent": "Mozilla/5.0 FundProWorkbench/0.1",
        "X-API-Key": "foobar"
    }
    try:
        cookie_jar = http.cookiejar.CookieJar()
        opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(cookie_jar),
            urllib.request.HTTPSHandler(context=SSL_CONTEXT)
        )
        page = http_get("https://www.fund123.cn/fund", headers=headers, opener=opener)
        csrf_match = re.search(r'"csrf"\s*:\s*"(?P<csrf>[^"]+)"', page)
        if not csrf_match:
            return None
        csrf = urllib.parse.quote(csrf_match.group("csrf"), safe="")
        search_body = http_post_json(
            f"https://www.fund123.cn/api/fund/searchFund?_csrf={csrf}",
            {"fundCode": code},
            headers=headers,
            opener=opener
        )
        fund_info = (json.loads(search_body).get("fundInfo") or {})
        product_id = fund_info.get("key")
        if not product_id:
            return None

        history_nav = fetch_fund123_previous_nav(product_id, csrf, headers, opener)
        material = http_get(
            f"https://www.fund123.cn/matiaria?fundCode={urllib.parse.quote(code)}",
            headers=headers,
            opener=opener
        )
        nav_match = re.search(r'"netValue"\s*:\s*"(?P<nav>\d+(?:\.\d+)?)"', material)
        nav_date = parse_fund123_nav_date(material)
        if not history_nav and not nav_match:
            return None
        previous_close = round(history_nav or float(nav_match.group("nav")), 4)
        # fund123's matiaria endpoint publishes the latest confirmed NAV in
        # netValue. It is an actual quote only when its publication date is today.
        current_price = (
            round(float(nav_match.group("nav")), 4)
            if nav_match and nav_date == market_now().strftime("%Y%m%d") else None
        )
        daily_change_rate = (
            (current_price - previous_close) / previous_close * 100
            if current_price is not None and previous_close else None
        )

        today = market_now().strftime("%Y-%m-%d")
        tomorrow = (market_now() + timedelta(days=1)).strftime("%Y-%m-%d")
        estimate_body = http_post_json(
            f"https://www.fund123.cn/api/fund/queryFundEstimateIntraday?_csrf={csrf}",
            {
                "startTime": today,
                "endTime": tomorrow,
                "limit": 200,
                "productId": product_id,
                "format": True,
                "source": "WEALTHBFFWEB"
            },
            headers=headers,
            opener=opener
        )
        estimates = (json.loads(estimate_body).get("list") or [])
        if not estimates:
            return None
        latest = estimates[-1]
        estimated_change_rate = float(latest.get("forecastGrowth") or 0) * 100
        return {
            "name": fund_info.get("fundName") or code,
            "current_price": current_price,
            "estimated_price": round(previous_close * (1 + estimated_change_rate / 100), 4),
            "previous_close": previous_close,
            "change_rate": daily_change_rate,
            "daily_change_rate": daily_change_rate,
            "estimated_change_rate": estimated_change_rate,
            "time": datetime.fromtimestamp(
                float(latest.get("time") or 0) / 1000, CHINA_TIMEZONE
            ).strftime("%Y-%m-%d %H:%M"),
            "source_label": "fund123 盘中预估"
        }
    except (urllib.error.URLError, ValueError, json.JSONDecodeError):
        return None


def lookup_instrument(asset_type, code):
    """Return name and latest public quote for the add-holding form."""
    normalized = str(code).strip()
    if not normalized:
        return None

    if asset_type == "fund":
        metadata = fetch_fund123_metadata(normalized) or {}
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


def fetch_fund123_valuation(url_template, code):
    url = url_template.format(code=urllib.parse.quote(code))
    try:
        body = http_get(url)
    except urllib.error.URLError:
        return None

    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return extract_fund_value_from_text(body, "fund123 自定义抓取")

    return {
        "name": payload.get("name") or code,
        "current_price": None,
        "estimated_price": round(float(payload.get("price") or 0), 4),
        "previous_close": round(float(payload.get("nav") or payload.get("previous_close") or 0), 4),
        "change_rate": float(payload.get("change_rate") or 0),
        "daily_change_rate": None,
        "estimated_change_rate": float(payload.get("change_rate") or 0),
        "time": payload.get("time") or "",
        "source_label": "fund123 自定义抓取"
    }


def fetch_eastmoney_valuation(code):
    query = urllib.parse.urlencode(
        {
            "FCODES": code,
            "FIELDS": "FCODE,SHORTNAME,GSZZL,GZTIME,GSZ,NAV,PDATE"
        }
    )
    urls = [
        f"https://fundcomapi.tiantianfunds.com/mm/newCore/FundValuationLast?{query}",
        f"https://fundcomapi.eastmoney.com/mm/newCore/FundValuationLast?{query}"
    ]
    for url in urls:
        try:
            body = http_get(url)
            data = json.loads(body)
        except (urllib.error.URLError, json.JSONDecodeError):
            continue

        rows = data.get("Datas") or data.get("data") or []
        if not rows:
            continue
        row = rows[0]
        if row.get("GSZ") is None:
            continue
        return {
            "name": row.get("SHORTNAME") or code,
            "current_price": None,
            "estimated_price": round(float(row.get("GSZ") or 0), 4),
            "previous_close": round(float(row.get("NAV") or 0), 4),
            "change_rate": float(row.get("GSZZL") or 0),
            "daily_change_rate": None,
            "estimated_change_rate": float(row.get("GSZZL") or 0),
            "time": row.get("GZTIME") or row.get("PDATE") or "",
            "source_label": "天天基金估值"
        }
    return None


def fetch_fund123_page_guess(code):
    candidates = [
        f"https://www.fund123.cn/fund/detail/{code}",
        f"https://www.fund123.cn/mfund/detail/{code}",
        f"https://www.fund123.cn/fund/{code}"
    ]
    for url in candidates:
        try:
            body = http_get(url)
        except urllib.error.URLError:
            continue
        parsed = extract_fund_value_from_text(body, "fund123 页面抓取")
        if parsed:
            return parsed
    return None


def extract_fund_value_from_text(body, source_label):
    gsz_match = re.search(r'"(?:GSZ|gsz)"\s*[:=]\s*"?(?P<price>\d+\.\d+)"?', body)
    nav_match = re.search(r'"(?:NAV|nav|dwjz)"\s*[:=]\s*"?(?P<nav>\d+\.\d+)"?', body)
    rate_match = re.search(r'"(?:GSZZL|gszzl)"\s*[:=]\s*"?(?P<rate>-?\d+\.\d+)"?', body)
    name_match = re.search(r'"(?:SHORTNAME|name)"\s*[:=]\s*"(?P<name>[^"]+)"', body)
    if not gsz_match:
        return None
    return {
        "name": name_match.group("name") if name_match else "场外基金",
        "current_price": float(gsz_match.group("price")),
        "previous_close": float(nav_match.group("nav")) if nav_match else 0,
        "change_rate": float(rate_match.group("rate")) if rate_match else 0,
        "daily_change_rate": None,
        "estimated_change_rate": float(rate_match.group("rate")) if rate_match else 0,
        "time": market_now().strftime("%Y-%m-%d %H:%M"),
        "source_label": source_label
    }
