import functools
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from services import DashboardService
from fund_archives import archive_dates, read_archive, start_archive_worker
from providers import FORCE_REFRESH
from providers import fetch_fund123_history_nav_list, fetch_fund123_holdings, fetch_fund123_performance_curve, lookup_instrument


service = DashboardService()

ARCHIVE_ASSET_TYPES = ("fund", "stock", "etf")
INSTRUMENT_ASSET_TYPES = ("stock", "etf", "fund", "index")


def handle_write_errors(method):
    """Map validation errors to 400 and unexpected failures to 500 for mutation routes."""
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except ValueError as error:
            return self._send_json({"error": str(error)}, status=400)
        except Exception as error:
            return self._send_json({"error": f"服务异常: {error}"}, status=500)
    return wrapper


class AppHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload, status=200):
        # MySQL returns TIMESTAMP columns as datetime objects; serialize them consistently.
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, message, status=404):
        return self._send_json({"error": message}, status=status)

    def _read_json(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    @staticmethod
    def _query_value(query, key, default=""):
        return query.get(key, [default])[0]

    @staticmethod
    def _parse_id(raw, label):
        try:
            return int(raw)
        except ValueError:
            raise ValueError(f"非法的{label} ID") from None

    def _require_asset_type(self, query, allowed, default=""):
        asset_type = self._query_value(query, "asset_type", default)
        if asset_type not in allowed:
            return None
        return asset_type

    def do_OPTIONS(self):
        self._send_json({"ok": True})

    def do_GET(self):
        force = parse_qs(urlparse(self.path).query).get("force", [""])[0] == "true"
        token = FORCE_REFRESH.set(force)
        try:
            return self._handle_get()
        finally:
            FORCE_REFRESH.reset(token)

    def _handle_get(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        if parsed.path == "/api/dashboard":
            return self._send_json(service.get_dashboard())
        if parsed.path == "/api/holdings":
            return self._send_json({"items": service.list_holdings()})
        if parsed.path == "/api/watchlist":
            return self._send_json(service.list_watchlist())
        if parsed.path == "/api/portfolio/intraday-pnl":
            return self._send_json(service.get_portfolio_intraday_pnl())
        if parsed.path == "/api/market-indices":
            return self._send_json(service.get_market_indices())
        if parsed.path == "/api/news":
            return self._send_json(service.get_news())
        if parsed.path == "/api/health":
            return self._send_json({"status": "ok"})
        if parsed.path == "/api/instruments/estimate-archive":
            return self._get_estimate_archive(query)
        if parsed.path == "/api/instruments/lookup":
            asset_type = self._require_asset_type(query, INSTRUMENT_ASSET_TYPES)
            if asset_type is None:
                return self._send_error("不支持的标的类型", status=400)
            instrument = lookup_instrument(asset_type, self._query_value(query, "code"))
            if not instrument:
                return self._send_error("未查询到该标的，请检查代码或稍后重试", status=404)
            return self._send_json(instrument)
        if parsed.path == "/api/instruments/intraday":
            asset_type = self._require_asset_type(query, INSTRUMENT_ASSET_TYPES)
            if asset_type is None:
                return self._send_error("不支持的标的类型", status=400)
            chart = service.get_intraday_chart(asset_type, self._query_value(query, "code"))
            if not chart:
                return self._send_error("暂无当日分时数据，请稍后重试", status=404)
            return self._send_json(chart)
        if parsed.path == "/api/instruments/fund-holdings":
            holdings = fetch_fund123_holdings(self._query_value(query, "code"))
            if not holdings:
                return self._send_error("暂无基金持仓数据，请稍后重试", status=404)
            return self._send_json(holdings)
        if parsed.path == "/api/instruments/fund-history":
            history = fetch_fund123_history_nav_list(
                self._query_value(query, "code"),
                self._query_value(query, "start_date"),
                self._query_value(query, "end_date")
            )
            if not history:
                return self._send_error("暂无历史净值数据，请稍后重试", status=404)
            return self._send_json(history)
        if parsed.path == "/api/instruments/fund-performance":
            curve = fetch_fund123_performance_curve(
                self._query_value(query, "code"),
                self._query_value(query, "interval", "THREE")
            )
            if not curve:
                return self._send_error("暂无业绩走势数据，请稍后重试", status=404)
            return self._send_json(curve)
        return self._send_error("Not found")

    def _get_estimate_archive(self, query):
        """Return archived dates for a code, or the curve captured on one date."""
        asset_type = self._require_asset_type(query, ARCHIVE_ASSET_TYPES, default="fund")
        if asset_type is None:
            return self._send_error("不支持的归档类型", status=400)
        code = self._query_value(query, "code")
        day = self._query_value(query, "date")
        if not day:
            return self._send_json({"dates": archive_dates(code, asset_type)})
        chart = read_archive(code, day, asset_type)
        if not chart:
            return self._send_error("该日期暂无已归档估值走势", status=404)
        return self._send_json(chart)

    @handle_write_errors
    def do_POST(self):
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        if parsed.path == "/api/holdings":
            return self._send_json(service.create_holding(self._read_json()), status=201)
        if parsed.path == "/api/watchlist/groups":
            return self._send_json(service.create_watchlist_group(self._read_json()), status=201)
        if parsed.path == "/api/watchlist/items":
            return self._send_json(service.create_watchlist_item(self._read_json()), status=201)
        if parsed.path == "/api/seed-demo":
            return self._send_json({"inserted": service.seed_demo_holdings()})
        if len(parts) == 5 and parts[:3] == ["api", "watchlist", "groups"] and parts[4] == "move":
            service.move_watchlist_group(self._parse_id(parts[3], "分组"), self._read_json().get("direction"))
            return self._send_json({"moved": True})
        return self._send_error("Not found")

    @handle_write_errors
    def do_DELETE(self):
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "holdings":
            service.delete_holding(self._parse_id(parts[2], "持仓"))
            return self._send_json({"deleted": True})
        if len(parts) == 4 and parts[:3] == ["api", "watchlist", "groups"]:
            service.delete_watchlist_group(self._parse_id(parts[3], "分组"))
            return self._send_json({"deleted": True})
        if len(parts) == 4 and parts[:3] == ["api", "watchlist", "items"]:
            service.delete_watchlist_item(self._parse_id(parts[3], "自选"))
            return self._send_json({"deleted": True})
        return self._send_error("Not found")

    @handle_write_errors
    def do_PUT(self):
        parts = urlparse(self.path).path.strip("/").split("/")
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "holdings":
            holding = service.update_holding(self._parse_id(parts[2], "持仓"), self._read_json())
            return self._send_json(holding)
        return self._send_error("Not found")

    def log_message(self, format_, *args):
        return


def run():
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "5000"))
    httpd = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Backend listening on http://{host}:{port}")
    archive_stop = start_archive_worker()
    try:
        httpd.serve_forever()
    finally:
        archive_stop.set()
        httpd.server_close()


if __name__ == "__main__":
    run()
