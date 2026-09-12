from database import get_connection, init_db
from fund_archives import read_archive
from providers import cache_market_value, fetch_tencent_watch_quote_batch, fetch_financial_news, fetch_fund123_intraday_chart, fetch_fund_valuation, fetch_intraday_chart, fetch_market_breadth, fetch_market_indices, fetch_quote_by_code, fetch_sector_rankings, fetch_tencent_intraday_chart, format_timestamp, market_now


def empty_quote():
    """Placeholder written onto a watchlist item when every quote source failed."""
    return {
        "current_price": None,
        "previous_close": None,
        "daily_change_rate": None,
        "estimated_price": None,
        "estimated_change_rate": None,
        "source_label": "暂无行情"
    }


def empty_market_breadth():
    """Placeholder returned when neither the live snapshot nor the fallback is available."""
    return {
        "available": False,
        "rising": 0,
        "falling": 0,
        "flat": 0,
        "limit_up": 0,
        "limit_down": 0,
        "total": 0,
        "data_date": None,
        "is_realtime": False,
        "source_label": "暂无行情（腾讯行业板块汇总不可用）"
    }


# Indices offered for intraday comparison with the portfolio P&L curve.
PNL_TREND_INDEX_TARGETS = (
    ("sh000001", "上证指数"),
    ("sz399006", "创业板指"),
    ("sh000688", "科创50")
)
PNL_TREND_CACHE_TTL = 60
# A-share continuous trading minutes, used as the canonical intraday grid.
INTRADAY_SESSIONS = ((9 * 60 + 30, 11 * 60 + 30), (13 * 60, 15 * 60))


def intraday_minute_grid():
    """Return every trading minute from 09:30 to 15:00 as ``HH:MM`` strings."""
    grid = []
    for start, end in INTRADAY_SESSIONS:
        for minute in range(start, end + 1):
            grid.append(f"{minute // 60:02d}:{minute % 60:02d}")
    return grid


def forward_fill(points, grid):
    """Align sorted ``(time, value)`` pairs onto the minute grid, carrying values forward."""
    ordered = sorted(points, key=lambda item: item[0])
    values = []
    cursor = 0
    last = None
    for minute in grid:
        while cursor < len(ordered) and ordered[cursor][0] <= minute:
            last = ordered[cursor][1]
            cursor += 1
        values.append(last)
    return values


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


class DashboardService:
    def __init__(self):
        init_db()

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
        add_to_watchlist = payload.get("add_to_watchlist")
        add_to_watchlist = True if add_to_watchlist is None else bool(add_to_watchlist)

        if not all([name, code, asset_type]) or quantity <= 0 or cost_price <= 0:
            raise ValueError("持仓参数不完整")

        conn = get_connection()
        try:
            cursor = conn.execute(
                "INSERT INTO holdings (name, code, asset_type, quantity, cost_price) VALUES (?, ?, ?, ?, ?)",
                (name, code, asset_type, quantity, cost_price)
            )
            group_name = self._mirror_into_watchlist(conn, name, code, asset_type) if add_to_watchlist else ""
            conn.commit()
            return {
                "id": cursor.lastrowid,
                "name": name,
                "code": code,
                "asset_type": asset_type,
                "quantity": quantity,
                "cost_price": cost_price,
                "watchlist_added": bool(group_name),
                "watchlist_group_name": group_name
            }
        finally:
            conn.close()

    @staticmethod
    def _mirror_into_watchlist(conn, name, code, asset_type):
        """Mirror a new holding into the default watchlist group of its category.

        Holdings and watchlist items live in separate tables; a freshly created
        holding should show up in the watchlist without a second manual step.
        Best effort by design: returns the group name when the item was inserted
        and "" when the code is already watched or no group of the matching
        category exists. It never raises, so watchlist problems cannot fail the
        holding creation.
        """
        if asset_type not in {"stock", "etf", "fund"}:
            return ""
        # 'fund' entries are valued off-exchange, everything else is on-exchange.
        category = "fund" if asset_type == "fund" else "exchange"
        group = conn.execute(
            "SELECT id, name FROM watchlist_groups WHERE category = ? ORDER BY sort_order, id LIMIT 1",
            (category,)
        ).fetchone()
        if not group:
            return ""
        duplicated = conn.execute(
            "SELECT id FROM watchlist_items WHERE code = ? AND asset_type = ? LIMIT 1",
            (code, asset_type)
        ).fetchone()
        if duplicated:
            return ""
        conn.execute(
            "INSERT INTO watchlist_items (group_id, name, code, asset_type) VALUES (?, ?, ?, ?)",
            (group["id"], name, code, asset_type)
        )
        return group["name"]

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

    def list_watchlist(self):
        conn = get_connection()
        try:
            groups = [dict(row) for row in conn.execute("SELECT id, name, category, sort_order, is_default FROM watchlist_groups ORDER BY category, sort_order, id").fetchall()]
            items = [dict(row) for row in conn.execute("SELECT id, group_id, name, code, asset_type FROM watchlist_items ORDER BY id DESC").fetchall()]
        finally:
            conn.close()
        # Group off-exchange (fund) entries for their dedicated valuation path;
        # the on-exchange entries go through a single batched Tencent request.
        fund_items = [item for item in items if item["asset_type"] == "fund"]
        exchange_items = [item for item in items if item["asset_type"] != "fund"]
        quotes_by_code = fetch_tencent_watch_quote_batch(
            [(item["code"], item["asset_type"]) for item in exchange_items]
        )
        for item in fund_items:
            item.update(fetch_fund_valuation(item["code"]) or empty_quote())
        for item in exchange_items:
            market = quotes_by_code.get(str(item["code"]).strip().zfill(6))
            if market is None:
                market = fetch_quote_by_code(item["code"])
            item.update(market or empty_quote())
        return {"groups": groups, "items": items, "generated_at": format_timestamp()}

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
            group = conn.execute("SELECT is_default FROM watchlist_groups WHERE id = ?", (group_id,)).fetchone()
            if not group:
                raise ValueError("分组不存在")
            # Holdings are mirrored into the default group, so it must always exist.
            if group["is_default"]:
                raise ValueError("默认分组不可删除")
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

    def sync_holdings_to_watchlist(self):
        """Mirror every existing holding into the default group of its category.

        Backfill for holdings created before the auto-watch behaviour existed;
        safe to re-run because ``_mirror_into_watchlist`` skips codes that are
        already watched. Returns per-holding results for reporting.
        """
        conn = get_connection()
        try:
            holdings = conn.execute("SELECT name, code, asset_type FROM holdings ORDER BY id").fetchall()
            added, skipped = [], []
            for holding in holdings:
                group_name = self._mirror_into_watchlist(
                    conn, holding["name"], holding["code"], holding["asset_type"]
                )
                entry = {
                    "name": holding["name"],
                    "code": holding["code"],
                    "asset_type": holding["asset_type"],
                    "group": group_name
                }
                (added if group_name else skipped).append(entry)
            conn.commit()
            return {"total": len(holdings), "added": added, "skipped": skipped}
        finally:
            conn.close()

    def delete_watchlist_item(self, item_id):
        conn = get_connection()
        try:
            conn.execute("DELETE FROM watchlist_items WHERE id = ?", (item_id,)); conn.commit()
        finally: conn.close()

    @staticmethod
    def _build_position(holding, market):
        """Compute one holding's display fields and the amounts the portfolio totals need.

        Returns ``(position, summary)``: ``position`` is the API payload for the
        holdings table, ``summary`` carries the intermediate amounts that
        :meth:`get_dashboard` aggregates across every holding.
        """
        quantity = float(holding["quantity"])
        cost_price = float(holding["cost_price"])
        is_fund = holding["asset_type"] == "fund"
        raw_previous_close = market.get("previous_close")
        previous_close = float(raw_previous_close) if raw_previous_close is not None else cost_price

        quoted_current_price = market.get("current_price")
        current_price = float(quoted_current_price) if quoted_current_price is not None else None
        estimated_price = market.get("estimated_price")
        if is_fund:
            previous_close = round(previous_close, 4)
            current_price = round(current_price, 4) if current_price is not None else None
            estimated_price = round(float(estimated_price), 4) if estimated_price is not None else None
        else:
            current_price = current_price if current_price is not None else previous_close

        estimated_change_rate = market.get("estimated_change_rate")
        if is_fund and estimated_price is None and estimated_change_rate is not None and previous_close != 0:
            estimated_price = round(previous_close * (1 + float(estimated_change_rate) / 100), 4)

        market_value = quantity * (current_price or estimated_price or previous_close)
        cost_amount = quantity * cost_price
        holding_pnl = market_value - cost_amount
        yesterday_market_value = quantity * previous_close
        daily_change_rate = market.get("daily_change_rate")
        today_pnl = None
        if daily_change_rate is not None:
            today_pnl = yesterday_market_value * float(daily_change_rate) / 100

        estimated_pnl = None
        if not is_fund:
            # On-exchange holdings have no separate estimate; today's move is the real one.
            estimated_price = current_price
            estimated_change_rate = daily_change_rate
            estimated_pnl = today_pnl
        elif estimated_change_rate is not None and previous_close:
            estimated_pnl = yesterday_market_value * float(estimated_change_rate) / 100

        position = {
            **holding,
            "current_price": current_price,
            "estimated_price": estimated_price,
            "market_value": market_value,
            "holding_pnl": holding_pnl,
            "holding_pnl_rate": (holding_pnl / cost_amount * 100) if cost_amount else 0,
            "previous_close": previous_close,
            "today_pnl": today_pnl,
            "today_pnl_rate": float(daily_change_rate) if daily_change_rate is not None else 0,
            "daily_change_rate": daily_change_rate,
            "estimated_change_rate": estimated_change_rate,
            "estimated_pnl": estimated_pnl,
            "source_label": market.get("source_label", "本地估算")
        }
        summary = {
            "market_value": market_value,
            "cost_amount": cost_amount,
            "holding_pnl": holding_pnl,
            "today_pnl": today_pnl,
            "estimated_pnl": estimated_pnl,
            "yesterday_market_value": yesterday_market_value
        }
        return position, summary

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
            position, summary = self._build_position(holding, self._load_market_data(holding))
            positions.append(position)
            total_market_value += summary["market_value"]
            total_cost += summary["cost_amount"]
            total_holding_pnl += summary["holding_pnl"]
            total_today_pnl += summary["today_pnl"] or 0
            total_estimated_pnl += summary["estimated_pnl"] or 0
            if summary["today_pnl"] is not None:
                total_actual_base += summary["yesterday_market_value"]
            if summary["estimated_pnl"] is not None:
                total_estimated_base += summary["yesterday_market_value"]

        live_sectors = fetch_sector_rankings()
        market_breadth = fetch_market_breadth()
        return {
            "portfolio": {
                "positions": positions,
                "total_market_value": total_market_value,
                "total_cost": total_cost,
                "total_holding_pnl": total_holding_pnl,
                "total_holding_pnl_rate": (total_holding_pnl / total_cost * 100) if total_cost else 0,
                "total_today_pnl": total_today_pnl,
                "total_estimated_pnl": total_estimated_pnl,
                "total_estimated_pnl_rate": (total_estimated_pnl / total_estimated_base * 100) if total_estimated_base else 0,
                "total_today_pnl_rate": (total_today_pnl / total_actual_base * 100) if total_actual_base else 0
            },
            "news": self._empty_news(),
            "market_breadth": market_breadth or empty_market_breadth(),
            "sectors": {
                **(live_sectors or FALLBACK_SECTORS),
                "source_label": (live_sectors or {}).get("source_label", "本地回退榜单")
            },
            "generated_at": format_timestamp()
        }

    def get_market_indices(self):
        return {"items": fetch_market_indices(), "generated_at": format_timestamp()}

    def get_news(self):
        return fetch_financial_news() or self._empty_news()

    def get_intraday_chart(self, asset_type, code):
        return fetch_intraday_chart(asset_type, code)

    def get_portfolio_intraday_pnl(self):
        """Aggregate today's estimated P&L curve and align benchmark index moves."""
        cached = cache_market_value("portfolio-intraday-pnl")
        if cached is not None:
            return cached
        return cache_market_value("portfolio-intraday-pnl", self._build_portfolio_intraday_pnl, PNL_TREND_CACHE_TTL)

    @staticmethod
    def _load_intraday_curve(holding, trade_date):
        """Prefer today's captured archive, otherwise fall back to the live intraday curve."""
        code = holding["code"]
        asset_type = holding["asset_type"]
        if asset_type in ("fund", "stock", "etf"):
            archived = read_archive(code, trade_date, asset_type)
            if archived:
                return archived
        if asset_type == "fund":
            return fetch_fund123_intraday_chart(code)
        if asset_type in ("stock", "etf"):
            return fetch_tencent_intraday_chart(code)
        return None

    def _build_portfolio_intraday_pnl(self):
        now = market_now()
        trade_date = now.strftime("%Y-%m-%d")
        grid = intraday_minute_grid()
        holdings = self.list_holdings()
        contributions = []
        missing = []
        base_value = 0.0
        sources = set()

        for holding in holdings:
            curve = self._load_intraday_curve(holding, trade_date)
            previous_close = float((curve or {}).get("previous_close") or 0)
            points = (curve or {}).get("points") or []
            pairs = [
                (item.get("time"), float(item["price"]))
                for item in points
                if item.get("time") and item.get("price") is not None
            ]
            if not curve or previous_close <= 0 or not pairs:
                missing.append({"name": holding["name"], "code": holding["code"], "asset_type": holding["asset_type"]})
                continue
            quantity = float(holding["quantity"])
            filled = forward_fill(pairs, grid)
            contributions.append([
                quantity * (value - previous_close) if value is not None else None
                for value in filled
            ])
            base_value += quantity * previous_close
            sources.add("fund123 盘中预估" if holding["asset_type"] == "fund" else "腾讯分时行情")

        pnl = []
        rate = []
        for index in range(len(grid)):
            values = [series[index] for series in contributions]
            if not any(value is not None for value in values):
                pnl.append(None)
                rate.append(None)
                continue
            total = sum(value or 0 for value in values)
            pnl.append(round(total, 2))
            rate.append(round(total / base_value * 100, 4) if base_value else None)

        indices = []
        for symbol, name in PNL_TREND_INDEX_TARGETS:
            chart = fetch_tencent_intraday_chart(symbol, is_index=True)
            previous_close = float((chart or {}).get("previous_close") or 0)
            points = (chart or {}).get("points") or []
            pairs = [
                (item.get("time"), float(item["price"]))
                for item in points
                if item.get("time") and item.get("price") is not None
            ]
            if not chart or previous_close <= 0 or not pairs:
                indices.append({"code": symbol, "name": name, "available": False, "rate": []})
                continue
            filled = forward_fill(pairs, grid)
            indices.append({
                "code": symbol,
                "name": name,
                "available": True,
                "rate": [
                    round((value - previous_close) / previous_close * 100, 4) if value is not None else None
                    for value in filled
                ]
            })

        source_label = "暂无可用分时数据"
        if sources:
            source_label = f"持仓 {'、'.join(sorted(sources))}；指数 腾讯分时行情"
        return {
            "trade_date": trade_date,
            "times": grid,
            "portfolio": {
                "available": bool(contributions),
                "name": "我的持仓预估收益",
                "pnl": pnl,
                "rate": rate,
                "base_value": round(base_value, 2),
                "covered": len(contributions),
                "total": len(holdings)
            },
            "indices": indices,
            "missing_holdings": missing,
            "source_label": source_label,
            "generated_at": format_timestamp(now)
        }

    @staticmethod
    def _empty_news():
        return {
            "items": [],
            "groups": [],
            "total_count": 0,
            "source_label": "财经快讯聚合",
            "generated_at": format_timestamp()
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
