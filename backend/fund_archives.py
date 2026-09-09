"""Archive confirmed end-of-session estimate curves for tracked OTC funds."""
import json
import logging
import threading
from datetime import datetime

from database import DATABASE_ENGINE, get_connection
from providers import CHINA_TIMEZONE, fetch_fund123_intraday_chart, market_now, ak

logger = logging.getLogger(__name__)
_calendar_day = None
_calendar_is_open = False


def is_trading_day(day):
    global _calendar_day, _calendar_is_open
    if _calendar_day != day:
        if ak is None:
            raise RuntimeError('AkShare is required to verify the trading calendar')
        dates = {str(d)[:10] for d in ak.tool_trade_date_hist_sina()['trade_date']}
        if not dates or day > max(dates):
            raise RuntimeError('Trading calendar does not cover the requested date')
        _calendar_day, _calendar_is_open = day, day in dates
    return _calendar_is_open


def read_archive(code, trade_date):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT payload FROM fund_estimate_archives WHERE code = ? AND trade_date = ?",
            (code, trade_date)
        ).fetchone()
        return json.loads(row['payload']) if row else None
    finally:
        conn.close()


def archive_dates(code):
    conn = get_connection()
    try:
        return [row['trade_date'] for row in conn.execute(
            "SELECT trade_date FROM fund_estimate_archives WHERE code = ? ORDER BY trade_date DESC",
            (code,)
        ).fetchall()]
    finally:
        conn.close()


def save_archive(code, chart, day):
    points = (chart or {}).get('points') or []
    if not points:
        return False
    stamps = [datetime.fromtimestamp(p['timestamp'] / 1000, CHINA_TIMEZONE) for p in points]
    # Reject stale, mixed-date or incomplete pre-close responses; retry later.
    if any(s.strftime('%Y-%m-%d') != day for s in stamps) or max(stamps).strftime('%H:%M') < '15:00':
        return False
    payload = dict(chart, code=code, trade_date=day, asset_type='fund', archived=True)
    conn = get_connection()
    try:
        sql = ('INSERT IGNORE' if DATABASE_ENGINE == 'mysql' else 'INSERT OR IGNORE')
        conn.execute(sql + ' INTO fund_estimate_archives (code, trade_date, payload, saved_at) VALUES (?, ?, ?, ?)',
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
        codes = [r['code'] for r in conn.execute(
            "SELECT code FROM holdings WHERE asset_type = 'fund' UNION SELECT code FROM watchlist_items WHERE asset_type = 'fund'"
        ).fetchall()]
    finally:
        conn.close()
    for code in codes:
        try:
            if not read_archive(code, day):
                if save_archive(code, fetch_fund123_intraday_chart(code), day):
                    logger.info('Archived fund %s on %s', code, day)
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
