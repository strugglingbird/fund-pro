# fund-pro 开发规范（基准文档）

> 适用于本仓库所有代码改动。修改业务或结构性改动前先读一遍，对照验收。

---

## 1. 架构与边界

### 1.1 分层

```
┌──────────────────────────────────────────────┐
│ 前端  src/App.vue → src/components/         │
│  - 只做 UI 编排、调用 API、组合 props/emit   │
│  - 格式化逻辑在 src/utils/，拖拽在 mixins/  │
└──────────────────────────────────────────────┘
                     │ HTTP/JSON
                     ▼
┌──────────────────────────────────────────────┐
│ HTTP 层  backend/app.py                     │
│  - 路由分发 + 参数校验                       │
│  - 统一异常处理                              │
│  - 不写业务计算                              │
└──────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────┐
│ 业务层  backend/services.py                 │
│  - DashboardService 聚合持仓、自选、行情    │
│  - 纯函数计算 / 数据转换 / 跨表 join         │
└──────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────┐
│ 数据源层  backend/providers/                │
│  - core / quotes / fund123 / eastmoney /     │
│    market / news / funds                     │
│  - 每个子模块负责一个外部源                  │
│  - 提供缓存装饰（不在 services 层重复缓存）  │
└──────────────────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────┐
│ 持久层  backend/database.py + 归档层         │
│  backend/fund_archives.py                    │
└──────────────────────────────────────────────┘
```

**禁止** 跨层调用：
- 组件不得直接 import `providers`，只能通过 `src/api/dashboard.js` 调 `/api/*`。
- `services` 不得 import `app`。
- `providers` 不得 import `services` 或 `app`。

### 1.2 时区

- 所有「自然日 / 交易时段 / 当前时间」判断一律用 `providers.core.market_now()`（naive UTC+8）。
- **注意**：数据库里 `created_at / updated_at / trade_date` 走 SQL CURRENT_TIMESTAMP，存的是 **UTC**。读取后 + 8 小时展示，跨日查询时尤其小心（已在 `app.py._now_iso()` 处统一返回 `+08:00` 字符串）。
- 任何新增时间字段都要在 commit 记录里标注时区。

### 1.3 数据库双方言

`database.py` 同时支持 SQLite 与 MySQL。新建表 / 改字段必须遵守：
- 占位符统一写 `?`；`MySQLConnection._adapt_sql` 会改写为 `%s`。
- 唯一性约束与「忽略重复」靠 `INSERT OR IGNORE`；MySQL 通道自动重写为 `INSERT IGNORE`。
- 枚举字段（`asset_type`、`category`、`status`、`alert_type`）必须在 `_adapt_sql` 不动枚举字面量，且默认值用字符串而非整数。
- **不要** 在 providers 或 services 里直接拼 SQL；如需要跨模块访问库，统一 `database.get_connection()`。

---

## 2. 后端规范

### 2.1 providers 子包边界（必须遵守）

| 子模块 | 负责 | 禁止 |
|---|---|---|
| `core` | 时区、缓存装饰（`cache_market_value`）、通用 HTTP（`http_get` / `http_get_with_curl`）、`to_float`、`market_now`、`format_timestamp`、`FORCE_REFRESH` ContextVar、`KOSPI_CACHE_KEY` 等全局常量 | 写任何具体业务字段 |
| `quotes` | 个股 / ETF / 跨标的实时报价（腾讯 / 东财个股 / 港股） | 抓板块、基金估值 |
| `fund123` | fund123.com 的账户内嵌页（含 cookies / csrf / searchFund / matiaria） | 调腾讯、东财 |
| `eastmoney` | 东财 push2 / push2his 接口、ETF 资金流 | 抓基金估值 |
| `market` | 大盘指数、涨跌家数、KOSPI、板块榜、当日分时、指数对比 | 抓个股 |
| `news` | AkShare / 第三方快讯聚合、分组 | 抓行情 |
| `funds` | 场外基金估值 6 级回退链（fund123 估计 / fundgz / 东财 FundValuationLast / pingzhongdata / fund123 页面文本 / 东财净值披露） | 抓 ETF |

**新增数据源**：在 `providers/` 下开新文件（如 `sina.py`），禁止塞回已有文件。
**导出**：`providers/__init__.py` 显式 re-export 所有公开符号，对外接口不变。

### 2.2 缓存（marktet 行情）

- 唯一来源：`core.cache_market_value(key, ttl_strategy, factory)`。
- `ttl_strategy`：`'session'`（每次开/收盘刷新一次）或 `'mkt_*'`，不要自己写 `time.time() + N`。
- 缓存 key 集中在文件顶部 `CACHE_KEYS`，用全大写下划线，`market_*` 前缀代表市场层、`fund_*` 前缀代表场外、`quote_*` 前缀代表个股。
- **`marktet_cache.cached_value` 已删除**：用 `cache_market_value` 工厂模式替代。如果发现旧用法直接替换。
- **`ContextVar(FORCE_REFRESH)`**：由 `app.py` 在请求作用域内 set/reset；providers 函数读它判断是否绕缓存。**禁止在 providers 自己实现忽略缓存开关**。

### 2.3 fund123 会话（高频复用，已抽工具）

```
build_fund123_opener()                → opener（带 CookieJar）
open_fund123_home(opener)             → 调 / 并检查 csrf
fetch_fund123_search(opener, code)    → 拿 productId
open_fund123_trade(opener, url)       → 通过 cookies 抓估值页或历史页
fetch_fund123_nav_text(opener, code)  → 净值披露文本 → structured
```

**禁止** 再有人复制粘贴「`urllib.request.build_opener(cookielib.CookieJar())`」样板。需要新增 fund123 子接口，**先**查 `fund123.py` 是否已有可复用工具。

### 2.4 路由（app.py）

- 路由表集中在 `backend/app.py` 顶部的 `ROUTES = [(method, regex, handler), ...]`，`do_GET` / `do_POST` / `do_PUT` / `do_DELETE` 都从这个表查，**禁止** 再追加 if/elif 分支。
- 参数校验统一在 `handlers.py` 或 `app._require_*` 工具内；**返回 400 而不是 500**。
- JSON 序列化用 `helpers.json_response(payload, status=200)`；**禁止** 手动 `send_response + send_header + wfile.write(json.dumps(...))`。
- 错误返回固定结构 `{"error": "...", "detail": "..."}`，已在 `app._emit_error` 实现。
- 后端进程启动时自动起归档线程（已有），新增后台任务沿用同样的 pattern（`threading.Thread(target=..., name=..., daemon=True)`，并在 `fund_archives.run_scheduler` 中注册周期）。

### 2.5 services.py

- `DashboardService` 是唯一的业务编排类。新增业务方法请注入到该类，不要在模块顶层写新类。
- 重复的「空行情字典」「空市场宽度结构」在 `services.py` 顶部用 `_EMPTY_*` 一次性定义，**禁止** 在 method 内部再 dict 字面量手抄。
- 所有返回给前端的字典，**必须** 包含 `generated_at`（北京时间字符串），便于前端展示。
- 暴露给前端的字段集合一旦定型不再删；改字段名走软废弃（同时返回新旧名，等前端切完再删）。

### 2.6 死代码 / 移除清单

下列函数已删除，禁止复活或重构回来：

| 函数 | 原位置 | 删除原因 |
|---|---|---|
| `fetch_akshare_watch_quote` | `providers.py` | 后台手动刷新场景未启用，前端从未消费 |
| `select_fund123_today_nav` | `providers.fund123` | 与 `fetch_fund123_nav_text` 重复，没有唯一买家 |
| `_build_position_analysis` | `services.py` | 拼模板字符串，前端并未消费 `analysis` 字段 |
| `marktet_cache.cached_value` | `providers.py` | 被 `cache_market_value` 工厂替代 |

删除后请同步 README 的「已移除功能」段。

---

## 3. 前端规范

### 3.1 组件拆分（强约束）

`src/App.vue` **只做**：
- 顶部导航 + 路由切换（`activeMenu`）
- 全局状态与数据拉取编排（dashboard / watchlist / marketIndices / newsFeed）
- 全局 Boolean（`holdingsNumbersVisible`、各 dialog 可见性）
- 把 data + handlers 通过 props / events 下发给面板与 dialog
- 启动轮询

**禁止** 在 `App.vue` 写模板细节、骨架、表格列定义；这些必须落在 `src/components/<Name>Panel.vue` 或 `<Name>Dialog.vue`。

组件清单（参照现有结构）：

```
src/components/
├── HomePanel.vue              首页（汇总卡 + 指数 + 消息预览 + 持仓预览）
├── HoldingsPanel.vue          持仓收益
├── WatchlistPanel.vue         自选（带分组、排序）
├── MarketPanel.vue            大盘指数 + 板块
├── NewsPanel.vue              消息快讯（按 tag / 板块筛选）
├── FloatingActions.vue        可拖拽的「刷新 / 脱敏」悬浮按钮
├── IntradayChartDialog.vue    分时 K 线详情
├── PnlTrendDialog.vue         当日收益走势 + 三指数对比
├── CreateHoldingDialog.vue
├── EditHoldingDialog.vue
├── WatchItemDialog.vue
└── FundHoldingWatchDialog.vue 把基金持仓加入自选
```

新增面板或弹窗请遵循：
- 文件名 PascalCase，后缀 `Panel` 或 `Dialog`。
- props 字段全部走 `props: { ... }`，**禁止** 在组件内部假设父级 ref 的存在。
- 双向绑定通过 `.sync`（`watchlistCategory`、`selectedWatchGroupId`、`activeMarketTab` 等）。
- 业务方法通过 `this.$emit('xxx', payload)` 抛回父组件，**禁止** 在子组件内 import `dashboard.js` 然后调接口写数据库。

### 3.2 props / emits 命名

| 类型 | 规范 | 示例 |
|---|---|---|
| props | kebab-case（模板）+ camelCase（脚本） | `:market-indices` ↔ `marketIndices` |
| 事件名 | kebab-case | `@open-chart`、`@create` |
| 状态事件 | 过去式 | `@reload`、`@removed`、`@added` |
| 动作事件 | 动词原形 | `@refresh`、`@toggle-numbers`、`@move-group` |

事件 payload 约定：

| 事件 | payload |
|---|---|
| `@open-chart` | `instrument` 对象（含 code / market / display_name） |
| `@edit` | 持仓 `holding` |
| `@remove` | `holding.id` |
| `@open-pnl-trend` | 无 |
| `@add-item` | 无（由父组件 open dialog） |

### 3.3 mixin（`src/mixins/`）

| mixin | 用途 | 何时使用 |
|---|---|---|
| `numberFormat.js` | 14 个格式化方法（金额、净值、百分比、持仓字段等） | 任意面板/dialog 渲染金额字段 |
| `draggableFab.js` | 悬浮按钮的拖拽坐标 + `fabJustDragged` 抑制 click | `FloatingActions.vue` 已使用，将来新增悬浮按钮沿用 |

mixin 必须是 `export default { data(), methods() }` 的纯对象，不耦合具体业务字段。组件用 `mixins: [numberFormat, draggableFab]` 注册。

### 3.4 utils（`src/utils/format.js`）

- 14 个 formatter 已经抽成纯函数。**禁止** 在组件 `methods` 里再写一遍 `formatMoney / formatPercent / formatNetValue`。
- 新增格式化函数请加到 `format.js` 而不是组件里。
- 函数必须接受 `null/undefined` 并返回占位（一般是 `''` 或 `'—'`），与前端 `loading` 态解耦。

### 3.5 样式（`src/styles/`）

| 文件 | 内容 |
|---|---|
| `global.css` | 主题变量（`--bg`/`--text`/`--danger` 等）、`body` 背景、滚动条 |
| `workspace.css` | 全部「面板/dialog 共享」的 layout class（`.app-shell`、`.workspace-nav`、`.brand-mark`、`.menu-card`、`.stat-card`、`.holding-table` 等） |

**禁止** 在 `.vue` 的 `<style scoped>` 里重复定义这些类。如确实需要局部样式，请用组件自己的局部 class，并通过 `v-deep` 选择子组件的最深一层 UI（Element UI 内部不破例）。

样式修改前先 `grep -r ".your-class" src/styles src/components`，确认它是不是「共享 layout」。
**禁止** 让组件 `<style scoped>` 与 `workspace.css` 出现同名 class。

### 3.6 UI 状态约束（来自 AGENTS.md）

异步视图必须提供：

| 状态 | 触发条件 | 占位 |
|---|---|---|
| skeleton | `loading && !loaded`（首页为 `initialLoading`） | 居中的 `<div class="loading-state">…加载中…</div>` |
| success | 加载完成且有数据 | 真实表格 / 卡片 |
| empty | 加载完成且无数据 | `<el-empty description="..." />` |
| error | 接口 4xx/5xx | `this.$message.error` + 保留已有数据（不允许一刷新清空） |

明细要求（继承自 `AGENTS.md`）：
- 场外基金的官方 NAV 与盘中估值**必须分字段**展示，估值显示 `估算` 字样 + `source_label`。
- 涨/跌色按**中国**市场约定：涨红跌绿（Element UI 默认即可，不要覆盖颜色变量）。

---

## 4. 通用规范

### 4.1 文档同步（强约束，AGENTS.md 已生效）

每次改动代码都要在 commit 报告中说明：
1. README.md 受影响章节是否需要更新。
2. `docs/CODE_STANDARDS.md` 是否需要更新（例如改了组件命名、加了新数据源）。
3. 如果删除了功能，更新 README 的「已移除功能」小节。

### 4.2 Git 提交

- commit message 第一行 ≤ 50 字，使用祈使句；详细说明放空一行后。
- 提交 secret（数据库密码、cookie、API key）会被 `git-secrets` 与 `.gitignore` 拦截，确认 `.gitignore` 包含：
  ```
  backend/.env
  backend/*.db
  *.pyc
  __pycache__/
  frontend/
  dist/
  node_modules/
  ```
- 修改 SQL 必须随 commit 写「MySQL/SQLite 双方言验证」记录。

### 4.3 部署

执行 `bash scripts/deploy.sh` 或对应 skill `fund-pro-deploy`。本地构建验证：

```bash
# 后端
cd backend && python -m compileall -q .
python run.py &  # 默认 :5000

# 前端
cd .. && npx --no-install vue-cli-service lint --no-fix
npx --no-install vue-cli-service build
```

构建失败禁止部署；lint 出现的 warning 必须确认属于 Element UI 自有组件，未覆盖不阻断。

### 4.4 命名禁词

| 禁词 | 替代 |
|---|---|
| `tmp.js` / `temp.js` | 真名（如 `tabCounter.js`、`checkRefs.js`） |
| `test1.py` `test2.py` | 真名或 commit 一次性删 |
| `xxx` `aaa` `asdf` | 与业务相关的具体名词 |
| `data1` `data2` | `quoteByCode` / `breadcrumbItems` |

---

## 5. 验收清单（提交前自查）

- [ ] `python -m compileall -q backend && python -c "import backend.app; print('ok')"` 通过
- [ ] `npx vue-cli-service lint --no-fix` 无新增 error
- [ ] `npx vue-cli-service build` 成功，`dist/index.html` 与 `dist/js/*.js` 全部产出
- [ ] curl `GET /api/health` 返回 200；`GET /api/holdings` 与 `GET /api/watchlist` 返回合理结构
- [ ] 新增的依赖已写入 `requirements.txt` / `package.json`
- [ ] 数据库改动：SQLite 测试 + MySQL（如果改了 schema）测试都通过
- [ ] README.md 已同步（受影响的小节更新或注明「无需变动」）
- [ ] 没有遗留的 `print()` / `console.log()`（除了临时 debug，已在 commit 删除）
- [ ] 没有遗留的 `TODO` / `FIXME`（或已写在 issue/backlog）

---

_最后修订：2026-09-10。改动本文件请同步告知维护者。_
