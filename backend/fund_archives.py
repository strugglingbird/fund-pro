"""Archive confirmed end-of-session estimate curves for tracked OTC funds."""
import json
import logging
import threading
from datetime import datetime

from database import DATABASE_ENGINE, get_connection
from providers import (
    CHINA_TIMEZONE,
    fetch_fund123_intraday_chart,
    fetch_tencent_intraday_chart,
    fetch_trading_days,
    market_now,
)

logger = logging.getLogger(__name__)
_calendar_day = None
_calendar_is_open = False
_calendar_days = set()

# ~640 sessions reach back roughly three years, which covers any date the
# archiver can reasonably ask about.
CALENDAR_SESSION_COUNT = 640


def _load_trading_calendar():
    """Collect exchange sessions from the SSE composite index daily K-line."""
    days = set(fetch_trading_days(CALENDAR_SESSION_COUNT))
    if not days:
        raise RuntimeError('Trading calendar is unavailable')
    return days


def is_trading_day(day):
    global _calendar_day, _calendar_is_open, _calendar_days
    if _calendar_day != day:
        if not _calendar_days:
            _calendar_days = _load_trading_calendar()
        if not _calendar_days or day > max(_calendar_days):
            raise RuntimeError('Trading calendar does not cover the requested date')
        _calendar_day, _calendar_is_open = day, day in _calendar_days
    return _calendar_is_open


def archive_table(asset_type):
    if asset_type not in ('fund', 'stock', 'etf'):
        raise ValueError('Unsupported archive asset type')
    return 'fund_estimate_archives' if asset_type == 'fund' else 'exchange_price_archives'


def read_archive(code, trade_date, asset_type='fund'):
    conn = get_connection()
    try:
        row = conn.execute(
            f"SELECT payload FROM {archive_table(asset_type)} WHERE code = ? AND trade_date = ?",
            (code, trade_date)
        ).fetchone()
        return json.loads(row['payload']) if row else None
    finally:
        conn.close()


def archive_dates(code, asset_type='fund'):
    conn = get_connection()
    try:
        return [row['trade_date'] for row in conn.execute(
            f"SELECT trade_date FROM {archive_table(asset_type)} WHERE code = ? ORDER BY trade_date DESC",
            (code,)
        ).fetchall()]
    finally:
        conn.close()


def save_archive(code, chart, day, asset_type='fund'):
    points = (chart or {}).get('points') or []
    if not points:
        return False
    if asset_type == 'fund':
        stamps = [datetime.fromtimestamp(p['timestamp'] / 1000, CHINA_TIMEZONE) for p in points]
    else:
        # Use the source's session date, never today's server date for stale quotes.
        if chart.get('trade_date') != day:
            return False
        stamps = [datetime.strptime(day + ' ' + p['time'], '%Y-%m-%d %H:%M') for p in points]
    # Reject stale, mixed-date or incomplete pre-close responses; retry later.
    if any(s.strftime('%Y-%m-%d') != day for s in stamps) or max(stamps).strftime('%H:%M') < '15:00':
        return False
    payload = dict(chart, code=code, trade_date=day, asset_type=asset_type, archived=True)
    conn = get_connection()
    try:
        sql = ('INSERT IGNORE' if DATABASE_ENGINE == 'mysql' else 'INSERT OR IGNORE')
        conn.execute(sql + f' INTO {archive_table(asset_type)} (code, trade_date, payload, saved_at) VALUES (?, ?, ?, ?)',
                     (code, day, json.dumps(payload, ensure_ascii=False), market_now().isoformat()))
        conn.commit()
        return True
    finally:
        conn.close()


def collect_close():
    now = market_now()
    if now.weekday() >= 5 or (now.hour, now.minute) < (15, 5):
        return
    day = now.strftime('%Y-%m-%d')
    if not is_trading_day(day):
        return
    conn = get_connection()
    try:
        instruments = conn.execute(
            "SELECT code, asset_type FROM holdings WHERE asset_type IN ('fund', 'stock', 'etf') UNION SELECT code, asset_type FROM watchlist_items WHERE asset_type IN ('fund', 'stock', 'etf')"
        ).fetchall()
    finally:
        conn.close()
    for instrument in instruments:
        code, asset_type = instrument['code'], instrument['asset_type']
        try:
            if not read_archive(code, day, asset_type):
                chart = fetch_fund123_intraday_chart(code) if asset_type == 'fund' else fetch_tencent_intraday_chart(code)
                if save_archive(code, chart, day, asset_type):
                    logger.info('Archived %s %s on %s', asset_type, code, day)
        except Exception:
            logger.exception('Failed to archive fund %s on %s; will retry', code, day)


def start_archive_worker():
    stop = threading.Event()

    def work():
        while not stop.is_set():
            try:
                collect_close()
            except Exception:
                logger.exception('Fund archive collection failed; will retry')
            stop.wait(300)

    thread = threading.Thread(target=work, name='fund-close-archive', daemon=True)
    thread.start()
    return stop
