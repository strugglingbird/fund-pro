"""Eastmoney / 天天基金 fallbacks used when fund123 cannot serve a valuation."""
import json
import re
import urllib.error
import urllib.parse

from .core import http_get


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
