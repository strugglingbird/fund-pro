import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from services import DashboardService
from fund_archives import archive_dates, read_archive, start_archive_worker
from providers import FORCE_REFRESH
from providers import fetch_fund123_history_nav_list, fetch_fund123_holdings, fetch_fund123_performance_curve, lookup_instrument


service = DashboardService()


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

    def _read_json(self):
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

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
        if parsed.path == "/api/dashboard":
            return self._send_json(service.get_dashboard())
        if parsed.path == "/api/holdings":
            return self._send_json({"items": service.list_holdings()})
        if parsed.path == "/api/watchlist":
            return self._send_json(service.list_watchlist())
        if parsed.path == "/api/market-indices":
            return self._send_json(service.get_market_indices())
        if parsed.path == "/api/news":
            return self._send_json(service.get_news())
        if parsed.path == "/api/health":
            return self._send_json({"status": "ok"})
        if parsed.path == "/api/instruments/estimate-archive":
            query = parse_qs(parsed.query)
            code = query.get('code', [''])[0]
            day = query.get('date', [''])[0]
            if not day:
                return self._send_json({'dates': archive_dates(code)})
            chart = read_archive(code, day)
            return self._send_json(chart or {'error': '该日期暂无已归档估值走势'}, status=200 if chart else 404)
        if parsed.path == "/api/instruments/lookup":
            query = parse_qs(parsed.query)
            code = query.get("code", [""])[0]
            asset_type = query.get("asset_type", [""])[0]
            if asset_type not in {"stock", "etf", "fund", "index"}:
                return self._send_json({"error": "不支持的标的类型"}, status=400)
            instrument = lookup_instrument(asset_type, code)
            if not instrument:
                return self._send_json({"error": "未查询到该标的，请检查代码或稍后重试"}, status=404)
            return self._send_json(instrument)
        if parsed.path == "/api/instruments/intraday":
            query = parse_qs(parsed.query)
            code = query.get("code", [""])[0]
            asset_type = query.get("asset_type", [""])[0]
            if asset_type not in {"stock", "etf", "fund", "index"}:
                return self._send_json({"error": "不支持的标的类型"}, status=400)
            chart = service.get_intraday_chart(asset_type, code)
            if not chart:
                return self._send_json({"error": "暂无当日分时数据，请稍后重试"}, status=404)
            return self._send_json(chart)
        if parsed.path == "/api/instruments/fund-holdings":
            code = parse_qs(parsed.query).get("code", [""])[0]
            holdings = fetch_fund123_holdings(code)
            if not holdings:
                return self._send_json({"error": "暂无基金持仓数据，请稍后重试"}, status=404)
            return self._send_json(holdings)
        if parsed.path == "/api/instruments/fund-history":
            query = parse_qs(parsed.query)
            history = fetch_fund123_history_nav_list(
                query.get("code", [""])[0],
                query.get("start_date", [""])[0],
                query.get("end_date", [""])[0]
            )
            if not history:
                return self._send_json({"error": "暂无历史净值数据，请稍后重试"}, status=404)
            return self._send_json(history)
        if parsed.path == "/api/instruments/fund-performance":
            query = parse_qs(parsed.query)
            curve = fetch_fund123_performance_curve(query.get("code", [""])[0], query.get("interval", ["THREE"])[0])
            if not curve: return self._send_json({"error": "暂无业绩走势数据，请稍后重试"}, status=404)
            return self._send_json(curve)
        return self._send_json({"error": "Not found"}, status=404)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/holdings":
                payload = self._read_json()
                holding = service.create_holding(payload)
                return self._send_json(holding, status=201)
            if parsed.path == "/api/watchlist/groups":
                return self._send_json(service.create_watchlist_group(self._read_json()), status=201)
            if parsed.path == "/api/watchlist/items":
                return self._send_json(service.create_watchlist_item(self._read_json()), status=201)
            parts = parsed.path.strip("/").split("/")
            if len(parts) == 5 and parts[:3] == ["api", "watchlist", "groups"] and parts[4] == "move":
                service.move_watchlist_group(int(parts[3]), self._read_json().get("direction"))
                return self._send_json({"moved": True})
            if parsed.path == "/api/seed-demo":
                inserted = service.seed_demo_holdings()
                return self._send_json({"inserted": inserted})
            return self._send_json({"error": "Not found"}, status=404)
        except ValueError as error:
            return self._send_json({"error": str(error)}, status=400)
        except Exception as error:
            return self._send_json({"error": f"服务异常: {error}"}, status=500)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        try:
            if len(parts) == 3 and parts[0] == "api" and parts[1] == "holdings":
                service.delete_holding(int(parts[2]))
                return self._send_json({"deleted": True})
            if len(parts) == 4 and parts[:3] == ["api", "watchlist", "groups"]:
                service.delete_watchlist_group(int(parts[3]))
                return self._send_json({"deleted": True})
            if len(parts) == 4 and parts[:3] == ["api", "watchlist", "items"]:
                service.delete_watchlist_item(int(parts[3]))
                return self._send_json({"deleted": True})
            return self._send_json({"error": "Not found"}, status=404)
        except ValueError:
            return self._send_json({"error": "非法的持仓 ID"}, status=400)
        except Exception as error:
            return self._send_json({"error": f"服务异常: {error}"}, status=500)

    def do_PUT(self):
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        try:
            if len(parts) == 3 and parts[0] == "api" and parts[1] == "holdings":
                holding = service.update_holding(int(parts[2]), self._read_json())
                return self._send_json(holding)
            return self._send_json({"error": "Not found"}, status=404)
        except ValueError as error:
            return self._send_json({"error": str(error)}, status=400)
        except Exception as error:
            return self._send_json({"error": f"服务异常: {error}"}, status=500)

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
