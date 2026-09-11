"""Market-wide aggregates: index quotes, breadth and industry sector rankings."""
import json
import urllib.error
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from .core import (
    cache_market_value,
    http_get,
    market_now,
    market_quote_ttl,
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

# Tencent's public board feed. `sort_type` only accepts `price`, so the full
# industry list is fetched once and ordered locally instead of two sorted calls.
TENCENT_SECTOR_RANK_URL = "https://proxy.finance.qq.com/cgi/cgi-bin/rank/pt/getRank"
TENCENT_SECTOR_HEADERS = {"User-Agent": "Mozilla/5.0", "Referer": "https://gu.qq.com/"}
TENCENT_SECTOR_QUERY = urllib.parse.urlencode({
    "board_type": "hy",
    "sort_type": "price",
    "direct": "down",
    "offset": 0,
    "count": 100
})


def fetch_market_indices():
    """Return cached major-market index quotes without blocking the page on serial I/O."""
    return list(cache_market_value(
        "market-indices",
        _fetch_market_indices_live,
        market_quote_ttl()
    ) or [])


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


def fetch_market_breadth():
    """Summarise all A-share advancing and declining counts."""
    return cache_market_value("market-breadth", _fetch_market_breadth_live, market_quote_ttl())


def _fetch_market_breadth_live():
    """Sum Tencent's live board aggregates into a whole-market advance/decline count.

    Summing the per-board `zgb` counts covers the whole A-share market without
    downloading a full-market snapshot.
    """
    try:
        boards = fetch_tencent_sector_board()
    except (OSError, json.JSONDecodeError, KeyError, ValueError):
        boards = []
    rising = sum(board["rising"] for board in boards)
    total = sum(board["total"] for board in boards)
    if not boards or total <= 0:
        return None
    # Tencent publishes "rising/total" per board only, so unchanged names stay
    # counted in `falling`; the response shape is unchanged.
    falling = max(total - rising, 0)

    data_date = _previous_market_date()
    return {
        "available": True,
        "rising": rising,
        "falling": falling,
        "flat": 0,
        # No remaining upstream exposes a market-wide limit-move count, so the
        # fields stay in the payload but are always zero.
        "limit_up": 0,
        "limit_down": 0,
        "total": total,
        "data_date": f"{data_date[:4]}-{data_date[4:6]}-{data_date[6:]}",
        "is_realtime": True,
        "source_label": "腾讯财经行业板块汇总"
    }


def _previous_market_date(now=None):
    now = now or market_now()
    candidate = now.date()
    if now.weekday() >= 5 or (now.hour, now.minute) < (9, 30):
        candidate -= timedelta(days=1)
    while candidate.weekday() >= 5:
        candidate -= timedelta(days=1)
    return candidate.strftime("%Y%m%d")


def fetch_tencent_sector_board():
    """Return Tencent's industry board snapshot.

    Each row carries the board's change rate plus `zgb` = "rising/total", which
    is the same aggregate the previous THS provider exposed, so market breadth
    can be summed from the boards without an extra full-market snapshot call.
    """
    body = http_get(f"{TENCENT_SECTOR_RANK_URL}?{TENCENT_SECTOR_QUERY}", headers=TENCENT_SECTOR_HEADERS)
    rows = ((json.loads(body).get("data") or {}).get("rank_list") or [])
    boards = []
    for row in rows:
        name = row.get("name")
        change_rate = to_float(row.get("zdf"))
        if not name or change_rate is None:
            continue
        rising, total = _parse_board_counts(row.get("zgb"))
        leader = row.get("lzg") or {}
        boards.append({
            "name": str(name),
            "code": row.get("code"),
            "change_rate": change_rate,
            "rising": rising,
            "total": total,
            "leader_name": leader.get("name"),
            "leader_change_rate": to_float(leader.get("zdf"))
        })
    return boards


def _sector_reason(board):
    """Render the sector blurb shown under each name, using the board's top gainer."""
    leader = board.get("leader_name")
    leader_rate = board.get("leader_change_rate")
    if leader and leader_rate is not None:
        return dict(board, reason=f"领涨 {leader} {leader_rate:+.2f}%")
    return dict(board, reason="腾讯财经行业板块实时涨跌幅")


def _parse_board_counts(value):
    """Split Tencent's `zgb` field ("rising/total") into integers."""
    parts = str(value or "").split("/")
    rising = to_float(parts[0]) if parts else None
    total = to_float(parts[1]) if len(parts) > 1 else None
    return int(rising or 0), int(total or 0)


def fetch_sector_rankings():
    return cache_market_value(
        "sector-rankings",
        _fetch_sector_rankings_live,
        market_quote_ttl()
    )


def _fetch_sector_rankings_live():
    """Rank industry sectors from Tencent's public feed."""
    boards = fetch_tencent_sector_board()
    if not boards:
        return None
    ranked = sorted(boards, key=lambda item: item["change_rate"], reverse=True)
    return {
        "gainers": [_sector_reason(board) for board in ranked[:10]],
        "losers": [_sector_reason(board) for board in ranked[-10:][::-1]],
        "source_label": "腾讯财经行业板块实时行情"
    }
