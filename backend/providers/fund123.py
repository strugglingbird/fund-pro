"""Off-exchange fund data from fund123: valuation, intraday estimates, NAV, holdings, performance.

Every fund123 endpoint requires a short-lived CSRF token that is embedded in the
``/fund`` page, so each call opens a cookie session first. The session, search and
product-id resolution steps are shared by all endpoints below.
"""
import json
import re
import urllib.error
import urllib.parse
from datetime import datetime, timedelta

from .core import (
    CHINA_TIMEZONE,
    FORCE_REFRESH,
    cache_market_value,
    format_timestamp,
    http_get,
    http_post_json,
    is_before_market_open,
    market_now,
    new_cookie_opener,
    seconds_until_next_market_open,
    to_float,
    to_ratio_percent,
)

FUND123_BASE = "https://www.fund123.cn"
FUND123_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/json",
    "Origin": FUND123_BASE,
    "Referer": f"{FUND123_BASE}/fund",
    "User-Agent": "Mozilla/5.0 FundProWorkbench/0.1",
    "X-API-Key": "foobar"
}

CSRF_PATTERN = re.compile(r'"csrf"\s*:\s*"(?P<csrf>[^"]+)"')
PRODUCT_ID_PATTERN = re.compile(r'"productId"\s*:\s*"(?P<product_id>[^"]+)"')
NET_VALUE_PATTERN = re.compile(r'"netValue"\s*:\s*"(?P<nav>\d+(?:\.\d+)?)"')

PERFORMANCE_INTERVALS = {
    "ONE": "ONE_MONTH",
    "THREE": "THREE_MONTH",
    "SIX": "SIX_MONTH",
    "ONE_YEAR": "ONE_YEAR"
}
PERFORMANCE_WINDOW_DAYS = {"ONE": 31, "THREE": 92, "SIX": 184, "ONE_YEAR": 366}


def open_session():
    """Open a cookie session and return ``(csrf, opener)``; ``(None, None)`` when unavailable."""
    opener = new_cookie_opener()
    try:
        page = http_get(f"{FUND123_BASE}/fund", headers=FUND123_HEADERS, opener=opener)
    except urllib.error.URLError:
        return None, None
    csrf_match = CSRF_PATTERN.search(page)
    if not csrf_match:
        return None, None
    return urllib.parse.quote(csrf_match.group("csrf"), safe=""), opener


def search_fund(code, csrf, opener):
    """Resolve basic fund metadata through fund123's public search flow."""
    body = http_post_json(
        f"{FUND123_BASE}/api/fund/searchFund?_csrf={csrf}",
        {"fundCode": code},
        headers=FUND123_HEADERS,
        opener=opener
    )
    return json.loads(body).get("fundInfo") or {}


def fetch_material(code, opener):
    """Fetch the fund detail page, which carries productId, netValue and netValueDate."""
    return http_get(
        f"{FUND123_BASE}/matiaria?fundCode={urllib.parse.quote(code)}",
        headers=FUND123_HEADERS,
        opener=opener
    )


def resolve_product(code, csrf, opener):
    """Return ``(fund_info, product_id, material)``, preferring the productId on the detail page."""
    fund_info = search_fund(code, csrf, opener)
    material = fetch_material(code, opener)
    match = PRODUCT_ID_PATTERN.search(material or "")
    product_id = match.group("product_id") if match else fund_info.get("key")
    return fund_info, product_id, material


def fetch_fund123_metadata(code):
    """Resolve an off-exchange fund name through fund123's public search flow."""
    csrf, opener = open_session()
    if not csrf:
        return None
    try:
        fund_info = search_fund(code, csrf, opener)
    except (urllib.error.URLError, json.JSONDecodeError):
        return None
    name = fund_info.get("fundName")
    if not name:
        return None
    return {
        "name": name,
        "key": fund_info.get("key"),
        "source_label": "fund123 基金检索"
    }


def fetch_fund123_intraday_valuation(code):
    """Use fund123's forecastGrowth field to derive the intraday estimated NAV."""
    csrf, opener = open_session()
    if not csrf:
        return None
    try:
        fund_info = search_fund(code, csrf, opener)
        product_id = fund_info.get("key")
        if not product_id:
            return None

        history_nav = fetch_fund123_previous_nav(product_id, csrf, opener)
        material = fetch_material(code, opener)
        nav_match = NET_VALUE_PATTERN.search(material)
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
            f"{FUND123_BASE}/api/fund/queryFundEstimateIntraday?_csrf={csrf}",
            {
                "startTime": today,
                "endTime": tomorrow,
                "limit": 200,
                "productId": product_id,
                "format": True,
                "source": "WEALTHBFFWEB"
            },
            headers=FUND123_HEADERS,
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


def fetch_fund123_intraday_chart(code):
    csrf, opener = open_session()
    if not csrf:
        return None
    try:
        fund_info, product_id, material = resolve_product(code, csrf, opener)
        if not product_id:
            return None
        history_nav = fetch_fund123_previous_nav(product_id, csrf, opener)
        nav_match = NET_VALUE_PATTERN.search(material or "")
        if not history_nav and not nav_match:
            return None
        previous_close = round(history_nav or float(nav_match.group("nav")), 4)
        today = market_now().strftime("%Y-%m-%d")
        tomorrow = (market_now() + timedelta(days=1)).strftime("%Y-%m-%d")
        estimate_body = http_post_json(
            f"{FUND123_BASE}/api/fund/queryFundEstimateIntraday?_csrf={csrf}",
            {"startTime": today, "endTime": tomorrow, "limit": 200, "productId": product_id, "format": True, "source": "WEALTHBFFWEB"},
            headers=FUND123_HEADERS, opener=opener
        )
        estimates = (json.loads(estimate_body).get("list") or [])
        points = []
        estimates.sort(key=lambda item: float(item.get("time") or 0))
        for item in estimates:
            rate = float(item.get("forecastGrowth") or 0)
            price = round(previous_close * (1 + rate), 4)
            points.append({
                "time": datetime.fromtimestamp(float(item.get("time") or 0) / 1000, CHINA_TIMEZONE).strftime("%H:%M"),
                "timestamp": float(item.get("time") or 0),
                "forecast_growth": rate,
                "price": price
            })
        return {
            "name": fund_info.get("fundName") or code,
            "code": code,
            "previous_close": previous_close,
            "points": points,
            "updated_at": datetime.fromtimestamp(float(estimates[-1]["time"]) / 1000, CHINA_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S") if estimates and estimates[-1].get("time") else None,
            "source_label": "fund123 盘中预估"
        } if points else None
    except (urllib.error.URLError, ValueError, json.JSONDecodeError):
        return None


def fetch_fund123_history_navs(product_id, csrf, opener):
    """Fetch the latest fund123 NAV records as ``(YYYYMMDD, nav)`` pairs."""
    today = market_now().date()
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
            f"{FUND123_BASE}/api/fund/queryFundHistoryNetValueList?_csrf={csrf}",
            payload,
            headers=FUND123_HEADERS,
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


def fetch_fund123_previous_nav(product_id, csrf, opener):
    """Load OTC fund previous NAV once per day after the 09:30 market open."""
    cache_key = f"fund-previous-nav:{product_id}"
    if is_before_market_open() and not FORCE_REFRESH.get():
        # Before the next session opens, reuse the last confirmed closing NAV.
        return cache_market_value(cache_key)
    return cache_market_value(
        cache_key,
        lambda: select_fund123_previous_nav(
            fetch_fund123_history_navs(product_id, csrf, opener) or []
        ),
        seconds_until_next_market_open()
    )


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


def _fetch_fund123_holdings_live(code):
    csrf, opener = open_session()
    if not csrf:
        return None
    try:
        fund_info, product_id, _material = resolve_product(code, csrf, opener)
        if not product_id:
            return None
        body = http_post_json(
            f"{FUND123_BASE}/api/fund/queryFundHolding?_csrf={csrf}",
            {"productId": product_id},
            headers=FUND123_HEADERS,
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
            "weight": to_ratio_percent(row.get("netWorthRatio") or row.get("holdingRatio") or row.get("holdRatio") or row.get("holdPercent") or row.get("ratio") or row.get("proportion")),
            "change_rate": to_ratio_percent(row.get("changeRate") or row.get("riseRate") or row.get("change_ratio")),
            "shares": to_float(row.get("holdingQuantity") or row.get("holdAmount") or row.get("shareNum") or row.get("shares") or row.get("amount")),
            "market_value": to_float(row.get("marketValue") or row.get("holdingMarketValue") or row.get("marketAmount") or row.get("marketVal"))
        })
    return {
        "name": fund_info.get("fundName") or code,
        "items": items,
        "report_date": payload.get("reportDate") if isinstance(payload, dict) else None,
        "stock_position": stock_position,
        "source_label": "fund123 基金持仓",
        "updated_at": format_timestamp()
    }


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


def _fetch_fund123_history_nav_list_live(code, start_date, end_date):
    csrf, opener = open_session()
    if not csrf:
        return None
    try:
        fund_info, product_id, _material = resolve_product(code, csrf, opener)
        if not product_id:
            return None
        body = http_post_json(
            f"{FUND123_BASE}/api/fund/queryFundHistoryNetValueList?_csrf={csrf}",
            {
                "productId": product_id,
                "startDate": start_date,
                "endDate": end_date,
                "pageNum": 1,
                "pageSize": 100
            },
            headers=FUND123_HEADERS,
            opener=opener
        )
        payload = json.loads(body)
    except (urllib.error.URLError, ValueError, json.JSONDecodeError):
        return None

    rows = payload.get("list") or (payload.get("data") or {}).get("list") or []
    items = []
    for row in rows:
        unit_nav = to_float(row.get("netValue"))
        if unit_nav is None:
            continue
        items.append({
            "date": row.get("netValueDate") or row.get("date") or "--",
            "unit_nav": round(unit_nav, 4),
            "total_nav": round(to_float(row.get("totalNetValue")) or unit_nav, 4),
            "daily_change_rate": to_ratio_percent(row.get("dayOfGrowth"))
        })
    items.sort(key=lambda item: item["date"], reverse=True)
    return {
        "name": fund_info.get("fundName") or code,
        "items": items,
        "source_label": "fund123 历史净值",
        "updated_at": format_timestamp()
    }


def fetch_fund123_performance_curve(code, interval="THREE"):
    normalized = str(code).strip()
    if not normalized or interval not in PERFORMANCE_INTERVALS:
        return None
    return cache_market_value(
        f"fund-performance:{normalized}:{interval}",
        lambda: _fetch_fund123_performance_curve_live(normalized, interval),
        600
    )


def _fetch_fund123_performance_curve_live(code, interval):
    csrf, opener = open_session()
    if not csrf:
        return None
    try:
        material = fetch_material(code, opener)
        product_match = PRODUCT_ID_PATTERN.search(material or "")
        if not product_match:
            return None
        body = http_post_json(
            f"{FUND123_BASE}/api/fund/queryFundQuotationCurves?_csrf={csrf}",
            {"productId": product_match.group("product_id"), "dateInterval": PERFORMANCE_INTERVALS[interval]},
            headers=FUND123_HEADERS, opener=opener
        )
        points = json.loads(body).get("points") or []
    except (urllib.error.URLError, ValueError, json.JSONDecodeError):
        return None
    series = {"fund": [], "indexbase": []}
    for point in points:
        kind, date, rate = point.get("type"), point.get("reportDateTimestamp"), to_float(point.get("rate"))
        if kind in series and date and rate is not None:
            series[kind].append({"date": date, "rate": round(rate * 100, 2)})
    all_dates = [item["date"] for values in series.values() for item in values]
    if all_dates:
        latest_date = max(datetime.strptime(date, "%Y-%m-%d").date() for date in all_dates)
        cutoff = latest_date - timedelta(days=PERFORMANCE_WINDOW_DAYS[interval])
        for kind in series:
            series[kind] = [item for item in series[kind] if datetime.strptime(item["date"], "%Y-%m-%d").date() >= cutoff]
    return {"fund": series["fund"], "index": series["indexbase"], "source_label": "fund123 业绩走势"}


def fetch_fund123_valuation(url_template, code):
    """Read estimates from a self-hosted adapter address configured via FUND123_ESTIMATE_URL."""
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


def fetch_fund123_page_guess(code):
    candidates = [
        f"{FUND123_BASE}/fund/detail/{code}",
        f"{FUND123_BASE}/mfund/detail/{code}",
        f"{FUND123_BASE}/fund/{code}"
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


def _find_stock_position(payload):
    if not isinstance(payload, dict):
        return None
    for asset in payload.get("assetList") or []:
        if not isinstance(asset, dict) or not asset.get("stock"):
            continue
        return to_ratio_percent(asset.get("proportionOfAssets"))
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
