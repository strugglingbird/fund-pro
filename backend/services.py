import threading
import time
import math
from datetime import datetime, timedelta

from database import get_connection, init_db
from providers import fetch_akshare_watch_quote, fetch_financial_news, fetch_fund_valuation, fetch_intraday_chart, fetch_market_breadth, fetch_market_indices, fetch_quote_by_code, fetch_sector_fund_flow_snapshot, fetch_sector_rankings


DEMO_HOLDINGS = [
    ("沪深300ETF", "510300", "etf", 1500, 4.08),
    ("贵州茅台", "600519", "stock", 20, 1628.0),
    ("天弘中证食品饮料ETF联接C", "001632", "fund", 3000, 1.62)
]


FALLBACK_SECTORS = {
    "gainers": [
        {"name": "证券", "change_rate": 3.68, "reason": "风险偏好抬升，市场预期成交额回暖。"},
        {"name": "创新药", "change_rate": 2.94, "reason": "政策边际改善，叠加事件催化。"},
        {"name": "半导体", "change_rate": 2.41, "reason": "产业链订单预期修复，资金回流高景气科技。"},
        {"name": "通信设备", "change_rate": 2.17, "reason": "算力基础设施需求预期升温。"},
        {"name": "机器人", "change_rate": 1.96, "reason": "产业催化带动主题资金活跃。"},
        {"name": "有色金属", "change_rate": 1.72, "reason": "资源品价格预期改善。"},
        {"name": "软件开发", "change_rate": 1.55, "reason": "科技成长风格获得资金关注。"},
        {"name": "汽车零部件", "change_rate": 1.31, "reason": "行业景气预期边际修复。"},
        {"name": "消费电子", "change_rate": 1.08, "reason": "新品周期带来需求预期。"},
        {"name": "国防军工", "change_rate": 0.86, "reason": "订单和主题催化共同支撑。"}
    ],
    "losers": [
        {"name": "煤炭", "change_rate": -1.88, "reason": "高股息方向短线获利了结。"},
        {"name": "银行", "change_rate": -1.26, "reason": "防守板块被调仓，资金切向弹性资产。"},
        {"name": "电力", "change_rate": -0.97, "reason": "缺少新增催化，板块表现偏弱。"},
        {"name": "房地产", "change_rate": -0.83, "reason": "基本面修复预期仍待验证。"},
        {"name": "交通运输", "change_rate": -0.71, "reason": "防守属性方向出现资金流出。"},
        {"name": "食品饮料", "change_rate": -0.62, "reason": "消费板块短线缺少催化。"},
        {"name": "家用电器", "change_rate": -0.54, "reason": "资金偏好转向高弹性方向。"},
        {"name": "建筑装饰", "change_rate": -0.46, "reason": "基建预期未出现新增驱动。"},
        {"name": "公用事业", "change_rate": -0.38, "reason": "红利资产出现阶段性调整。"},
        {"name": "纺织服饰", "change_rate": -0.27, "reason": "行业成交活跃度相对偏低。"}
    ]
}


_SECTOR_FLOW_COLLECTOR_LOCK = threading.Lock()
_SECTOR_FLOW_COLLECTOR_STARTED = False


def _is_sector_flow_collection_window(now):
    return now.weekday() < 5 and (9, 30) <= (now.hour, now.minute) < (15, 0)


def _capture_sector_fund_flow_snapshot():
    """Persist one real-time industry fund-flow snapshot and prune old samples."""
    snapshot = fetch_sector_fund_flow_snapshot()
    if not snapshot:
        return False
    now = datetime.now()
    captured_at = now.strftime("%Y-%m-%d %H:%M:%S")
    trade_date = now.strftime("%Y-%m-%d")
    cutoff = (now - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    try:
        conn.executemany(
            """
            INSERT OR IGNORE INTO sector_fund_flow_snapshots
                (captured_at, trade_date, sector_name, net_inflow)
            VALUES (?, ?, ?, ?)
            """,
            [(captured_at, trade_date, item["name"], item["net_inflow"]) for item in snapshot]
        )
        conn.execute("DELETE FROM sector_fund_flow_snapshots WHERE captured_at < ?", (cutoff,))
        conn.commit()
        return True
    finally:
        conn.close()


def _sector_fund_flow_collector_loop():
    while True:
        now = datetime.now()
        if _is_sector_flow_collection_window(now):
            try:
                _capture_sector_fund_flow_snapshot()
            except Exception:
                pass
            # Align following samples to 30-second boundaries.
            time.sleep(max(3, 30 - datetime.now().second % 30))
        else:
            time.sleep(60)


def _start_sector_fund_flow_collector():
    global _SECTOR_FLOW_COLLECTOR_STARTED
    with _SECTOR_FLOW_COLLECTOR_LOCK:
        if _SECTOR_FLOW_COLLECTOR_STARTED:
            return
        thread = threading.Thread(target=_sector_fund_flow_collector_loop, name="sector-fund-flow-collector", daemon=True)
        thread.start()
        _SECTOR_FLOW_COLLECTOR_STARTED = True


def _build_sector_fund_flow_demo():
    """Provide a clearly labelled preview until the first trading-day samples exist."""
    names = ["证券", "电力设备", "银行", "白酒", "创新药", "机器人", "有色金属", "AI 芯片", "通信设备", "半导体", "PCB", "国产芯片"]
    targets = [186.4, 28.6, 16.4, 7.8, -11.5, -20.7, -31.8, -43.2, -65.4, -92.6, -118.3, -338.6]
    times = [f"{hour:02d}:{minute:02d}" for hour, start, end in [(9, 30, 60), (10, 0, 60), (11, 0, 31), (13, 0, 60), (14, 0, 60), (15, 0, 1)] for minute in range(start, end)]
    times = [f"{value}:{second:02d}" for value in times for second in (0, 30) if value != "15:00" or second == 0]
    times = list(dict.fromkeys(times))
    series = []
    for index, (name, target) in enumerate(zip(names, targets)):
        values = []
        for point, _ in enumerate(times):
            progress = point / max(len(times) - 1, 1)
            if name == "机器人":
                if progress < 0.48:
                    value = -145 * math.sin(progress / 0.48 * math.pi / 2)
                else:
                    afternoon = (progress - 0.48) / 0.52
                    value = -145 + 425 * (1 - (1 - afternoon) ** 1.7)
            elif name == "AI 芯片":
                value = target * progress + math.sin(progress * math.pi * 5) * 62
            else:
                wave = math.sin(progress * math.pi * (2 + index % 3) + index) * (3.5 + index * 0.45)
                value = target * progress + wave * (1 - progress * 0.35)
            values.append(round(value, 2))
        values[0] = 0
        series.append({"name": name, "data": values})
    today = datetime.now().strftime("%Y-%m-%d")
    return {"trade_date": today, "start_at": times[0], "updated_at": f"{today} {times[-1]}:00", "times": times, "series": series, "source_label": "模拟演示数据", "unit": "亿元", "is_demo": True}


class DashboardService:
    def __init__(self):
        init_db()
        _start_sector_fund_flow_collector()

    def list_holdings(self):
        conn = get_connection()
        try:
            rows = conn.execute(
                "SELECT id, name, code, asset_type, quantity, cost_price, created_at FROM holdings ORDER BY id DESC"
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def create_holding(self, payload):
        name = str(payload.get("name", "")).strip()
        code = str(payload.get("code", "")).strip()
        asset_type = str(payload.get("asset_type", "")).strip()
        quantity = float(payload.get("quantity", 0) or 0)
        cost_price = float(payload.get("cost_price", 0) or 0)

        if not all([name, code, asset_type]) or quantity <= 0 or cost_price <= 0:
            raise ValueError("持仓参数不完整")

        conn = get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO holdings (name, code, asset_type, quantity, cost_price) VALUES (?, ?, ?, ?, ?)",
                (name, code, asset_type, quantity, cost_price)
            )
            conn.commit()
            return {
                "id": cursor.lastrowid,
                "name": name,
                "code": code,
                "asset_type": asset_type,
                "quantity": quantity,
                "cost_price": cost_price
            }
        finally:
            conn.close()

    def delete_holding(self, holding_id):
        conn = get_connection()
        try:
            conn.execute("DELETE FROM holdings WHERE id = ?", (holding_id,))
            conn.commit()
        finally:
            conn.close()

    def update_holding(self, holding_id, payload):
        quantity = float(payload.get("quantity", 0) or 0)
        cost_price = float(payload.get("cost_price", 0) or 0)
        if quantity <= 0 or cost_price <= 0:
            raise ValueError("份额和成本价必须大于 0")

        conn = get_connection()
        try:
            cursor = conn.execute(
                "UPDATE holdings SET quantity = ?, cost_price = ? WHERE id = ?",
                (quantity, cost_price, holding_id)
            )
            if cursor.rowcount == 0:
                raise ValueError("持仓不存在或已被删除")
            conn.commit()
            row = conn.execute(
                "SELECT id, name, code, asset_type, quantity, cost_price, created_at FROM holdings WHERE id = ?",
                (holding_id,)
            ).fetchone()
            return dict(row)
        finally:
            conn.close()

    def seed_demo_holdings(self):
        conn = get_connection()
        try:
            existing = conn.execute("SELECT COUNT(*) AS total FROM holdings").fetchone()["total"]
            if existing:
                return 0
            conn.executemany(
                "INSERT INTO holdings (name, code, asset_type, quantity, cost_price) VALUES (?, ?, ?, ?, ?)",
                DEMO_HOLDINGS
            )
            conn.commit()
            return len(DEMO_HOLDINGS)
        finally:
            conn.close()

    def list_watchlist(self):
        conn = get_connection()
        try:
            groups = [dict(row) for row in conn.execute("SELECT id, name, category, sort_order FROM watchlist_groups ORDER BY category, sort_order, id").fetchall()]
            items = [dict(row) for row in conn.execute("SELECT id, group_id, name, code, asset_type FROM watchlist_items ORDER BY id DESC").fetchall()]
        finally:
            conn.close()
        for item in items:
            market = fetch_fund_valuation(item["code"]) if item["asset_type"] == "fund" else fetch_akshare_watch_quote(item["code"], item["asset_type"])
            item.update(market or {"current_price": None, "previous_close": None, "daily_change_rate": None, "estimated_price": None, "estimated_change_rate": None, "source_label": "暂无行情"})
        return {"groups": groups, "items": items, "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    def create_watchlist_group(self, payload):
        name, category = str(payload.get("name", "")).strip(), str(payload.get("category", "")).strip()
        if not name or category not in {"exchange", "fund"}:
            raise ValueError("分组名称或类型不正确")
        conn = get_connection()
        try:
            sort_order = conn.execute("SELECT COALESCE(MAX(sort_order), 0) + 1 AS value FROM watchlist_groups WHERE category = ?", (category,)).fetchone()["value"]
            cursor = conn.execute("INSERT INTO watchlist_groups (name, category, sort_order) VALUES (?, ?, ?)", (name, category, sort_order))
            conn.commit()
            return {"id": cursor.lastrowid, "name": name, "category": category, "sort_order": sort_order}
        finally: conn.close()

    def delete_watchlist_group(self, group_id):
        conn = get_connection()
        try:
            cursor = conn.execute("DELETE FROM watchlist_groups WHERE id = ?", (group_id,))
            if not cursor.rowcount: raise ValueError("分组不存在")
            conn.commit()
        finally: conn.close()

    def move_watchlist_group(self, group_id, direction):
        if direction not in {"up", "down"}:
            raise ValueError("移动方向不正确")
        conn = get_connection()
        try:
            current = conn.execute("SELECT id, category, sort_order FROM watchlist_groups WHERE id = ?", (group_id,)).fetchone()
            if not current:
                raise ValueError("分组不存在")
            operator = "<" if direction == "up" else ">"
            order = "DESC" if direction == "up" else "ASC"
            neighbor = conn.execute(
                f"SELECT id, sort_order FROM watchlist_groups WHERE category = ? AND sort_order {operator} ? ORDER BY sort_order {order}, id {order} LIMIT 1",
                (current["category"], current["sort_order"])
            ).fetchone()
            if not neighbor:
                return
            conn.execute("UPDATE watchlist_groups SET sort_order = ? WHERE id = ?", (neighbor["sort_order"], current["id"]))
            conn.execute("UPDATE watchlist_groups SET sort_order = ? WHERE id = ?", (current["sort_order"], neighbor["id"]))
            conn.commit()
        finally: conn.close()

    def create_watchlist_item(self, payload):
        group_id, name, code = int(payload.get("group_id", 0)), str(payload.get("name", "")).strip(), str(payload.get("code", "")).strip()
        asset_type = str(payload.get("asset_type", "")).strip()
        if not all([group_id, name, code]) or asset_type not in {"stock", "etf", "fund"}: raise ValueError("自选参数不完整")
        conn = get_connection()
        try:
            group = conn.execute("SELECT category FROM watchlist_groups WHERE id = ?", (group_id,)).fetchone()
            if not group or (group["category"] == "fund") != (asset_type == "fund"): raise ValueError("标的类型与分组不匹配")
            cursor = conn.execute("INSERT INTO watchlist_items (group_id, name, code, asset_type) VALUES (?, ?, ?, ?)", (group_id, name, code, asset_type))
            conn.commit()
            return {"id": cursor.lastrowid, "group_id": group_id, "name": name, "code": code, "asset_type": asset_type}
        finally: conn.close()

    def delete_watchlist_item(self, item_id):
        conn = get_connection()
        try:
            conn.execute("DELETE FROM watchlist_items WHERE id = ?", (item_id,)); conn.commit()
        finally: conn.close()

    def get_dashboard(self):
        positions = []
        total_market_value = 0.0
        total_cost = 0.0
        total_holding_pnl = 0.0
        total_today_pnl = 0.0
        total_estimated_pnl = 0.0
        total_actual_base = 0.0
        total_estimated_base = 0.0

        for holding in self.list_holdings():
            market = self._load_market_data(holding)
            quantity = float(holding["quantity"])
            cost_price = float(holding["cost_price"])
            previous_close = float(market.get("previous_close") or cost_price)
            quoted_current_price = market.get("current_price")
            current_price = float(quoted_current_price) if quoted_current_price is not None else None
            estimated_price = market.get("estimated_price")
            if holding["asset_type"] == "fund":
                previous_close = round(previous_close, 4)
                current_price = round(current_price, 4) if current_price is not None else None
                estimated_price = round(float(estimated_price), 4) if estimated_price is not None else None
            else:
                current_price = current_price if current_price is not None else previous_close
            estimated_change_rate = market.get("estimated_change_rate")
            if holding["asset_type"] == "fund" and estimated_price is None and estimated_change_rate is not None and previous_close:
                estimated_price = round(previous_close * (1 + float(estimated_change_rate) / 100), 4)

            market_value = quantity * (current_price or estimated_price or previous_close)
            cost_amount = quantity * cost_price
            holding_pnl = market_value - cost_amount
            holding_pnl_rate = (holding_pnl / cost_amount * 100) if cost_amount else 0
            yesterday_market_value = quantity * previous_close
            daily_change_rate = market.get("daily_change_rate")
            today_pnl = None
            if daily_change_rate is not None:
                today_pnl = yesterday_market_value * float(daily_change_rate) / 100
            today_pnl_rate = float(daily_change_rate) if daily_change_rate is not None else 0
            estimated_pnl = None
            if holding["asset_type"] != "fund":
                estimated_price = current_price
                estimated_change_rate = daily_change_rate
                estimated_pnl = today_pnl
            elif estimated_change_rate is not None and previous_close:
                estimated_pnl = yesterday_market_value * float(estimated_change_rate) / 100

            total_market_value += market_value
            total_cost += cost_amount
            total_holding_pnl += holding_pnl
            total_today_pnl += today_pnl or 0
            total_estimated_pnl += estimated_pnl or 0
            if today_pnl is not None:
                total_actual_base += yesterday_market_value
            if estimated_pnl is not None:
                total_estimated_base += yesterday_market_value

            positions.append(
                {
                    **holding,
                    "current_price": current_price,
                    "estimated_price": estimated_price,
                    "market_value": market_value,
                    "holding_pnl": holding_pnl,
                    "holding_pnl_rate": holding_pnl_rate,
                    "previous_close": previous_close,
                    "today_pnl": today_pnl,
                    "today_pnl_rate": today_pnl_rate,
                    "daily_change_rate": daily_change_rate,
                    "estimated_change_rate": estimated_change_rate,
                    "estimated_pnl": estimated_pnl,
                    "source_label": market.get("source_label", "本地估算"),
                    "analysis": self._build_position_analysis(holding, today_pnl_rate, market)
                }
            )

        total_today_pnl_rate = (total_today_pnl / total_actual_base * 100) if total_actual_base else 0
        total_estimated_pnl_rate = (total_estimated_pnl / total_estimated_base * 100) if total_estimated_base else 0
        total_holding_pnl_rate = (total_holding_pnl / total_cost * 100) if total_cost else 0
        live_sectors = fetch_sector_rankings()
        market_breadth = fetch_market_breadth()
        sectors = {
            **(live_sectors or FALLBACK_SECTORS),
            "source_label": (live_sectors or {}).get("source_label", "本地回退榜单")
        }
        return {
            "portfolio": {
                "positions": positions,
                "total_market_value": total_market_value,
                "total_cost": total_cost,
                "total_holding_pnl": total_holding_pnl,
                "total_holding_pnl_rate": total_holding_pnl_rate,
                "total_today_pnl": total_today_pnl,
                "total_estimated_pnl": total_estimated_pnl,
                "total_estimated_pnl_rate": total_estimated_pnl_rate,
                "total_today_pnl_rate": total_today_pnl_rate
            },
            "news": self._empty_news(),
            "market_breadth": market_breadth or {"available": False, "rising": 0, "falling": 0, "flat": 0, "limit_up": 0, "limit_down": 0, "total": 0, "data_date": None, "is_realtime": False, "source_label": "AkShare 全 A 股实时行情"},
            "sectors": sectors,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def get_market_indices(self):
        return {"items": fetch_market_indices(), "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

    def get_sector_fund_flow(self):
        """Return the latest trading day's sampled sector rotation series."""
        conn = get_connection()
        try:
            latest_date_row = conn.execute(
                "SELECT MAX(trade_date) AS trade_date FROM sector_fund_flow_snapshots"
            ).fetchone()
            trade_date = latest_date_row["trade_date"] if latest_date_row else None
            if not trade_date:
                return _build_sector_fund_flow_demo()
            latest_at_row = conn.execute(
                "SELECT MAX(captured_at) AS captured_at FROM sector_fund_flow_snapshots WHERE trade_date = ?",
                (trade_date,)
            ).fetchone()
            latest_at = latest_at_row["captured_at"]
            sectors = conn.execute(
                """
                SELECT sector_name FROM sector_fund_flow_snapshots
                WHERE captured_at = ?
                ORDER BY ABS(net_inflow) DESC
                LIMIT 12
                """,
                (latest_at,)
            ).fetchall()
            names = [row["sector_name"] for row in sectors]
            if not names:
                return {"trade_date": trade_date, "start_at": None, "updated_at": latest_at, "series": [], "source_label": "AkShare 同花顺行业资金流", "unit": "亿元"}
            placeholders = ",".join("?" for _ in names)
            rows = conn.execute(
                f"""
                SELECT captured_at, sector_name, net_inflow
                FROM sector_fund_flow_snapshots
                WHERE trade_date = ? AND sector_name IN ({placeholders})
                ORDER BY captured_at, sector_name
                """,
                [trade_date, *names]
            ).fetchall()
            times = sorted({row["captured_at"][-8:] for row in rows})
            values = {name: {} for name in names}
            for row in rows:
                values[row["sector_name"]][row["captured_at"][-8:]] = row["net_inflow"]
            return {
                "trade_date": trade_date,
                "start_at": times[0] if times else None,
                "updated_at": latest_at,
                "times": times,
                "series": [{"name": name, "data": [values[name].get(time) for time in times]} for name in names],
                "source_label": "AkShare 同花顺行业资金流",
                "unit": "亿元"
            }
        finally:
            conn.close()

    def get_news(self):
        return fetch_financial_news() or self._empty_news()

    def get_intraday_chart(self, asset_type, code):
        return fetch_intraday_chart(asset_type, code)

    @staticmethod
    def _empty_news():
        return {
            "items": [],
            "groups": [],
            "total_count": 0,
            "source_label": "AkShare 财经快讯",
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

    def _load_market_data(self, holding):
        if holding["asset_type"] == "fund":
            data = fetch_fund_valuation(holding["code"])
        else:
            data = fetch_quote_by_code(holding["code"])

        if data:
            return data
        return {
            "name": holding["name"],
            "current_price": holding["cost_price"],
            "previous_close": holding["cost_price"],
            "change_rate": 0,
            "daily_change_rate": 0,
            "estimated_change_rate": None,
            "source_label": "本地回退数据"
        }

    def _build_position_analysis(self, holding, today_pnl_rate, market):
        if holding["asset_type"] == "fund":
            if market.get("source_label", "").startswith("fund123"):
                source_hint = "fund123 估值"
            else:
                source_hint = market.get("source_label", "基金估值")
            if today_pnl_rate > 1:
                return f"{source_hint}显示盘中走强，可结合指数联动判断是否加仓。"
            if today_pnl_rate < -1:
                return f"{source_hint}偏弱，适合检查对应行业指数和成交额变化。"
            return f"{source_hint}波动平稳，建议结合净值披露与板块强弱继续观察。"

        if today_pnl_rate > 2:
            return "日内强于大盘，若伴随放量可关注趋势延续。"
        if today_pnl_rate < -2:
            return "回撤较明显，适合复核消息面是否出现负面扰动。"
        return "走势相对平稳，可结合板块轮动判断是否继续持有。"
