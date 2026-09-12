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
│  - core / quotes / fund123 / market /        │
│    news / funds                              │
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
- **注意**：数据库里 `created_at / updated_at / trade_date` 走 SQL CURRENT_TIMESTAMP，存的是 **UTC**。读取后 + 8 小时展示，跨日查询时尤其小心。后端对外返回的 `generated_at` 已由 `format_timestamp()` 统一转换为北京时间字符串。
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
| `core` | 时区、缓存（`cache_market_value`）、通用 HTTP（`http_get` / `http_post_json`）、`to_float`、`market_now`、`format_timestamp`、`FORCE_REFRESH` ContextVar | 写任何具体业务字段 |
| `quotes` | 个股 / ETF / 指数实时报价（腾讯 qt.gtimg、交易日历）；美股指数分时已移除 | 抓板块、基金估值 |
| `fund123` | fund123.com 的账户内嵌页（含 cookies / csrf / searchFund / matiaria） | 调腾讯行情 |
| `market` | 大盘指数、涨跌家数、板块榜（腾讯 proxy.finance.qq.com） | 抓个股；不得再引入东财 push2 系列 |
| `news` | AkShare 快讯聚合、分组 | 抓行情 |
| `funds` | 场外基金估值回退链（fund123 盘中估值 → fund123 页面文本解析） | 抓 ETF |

**已下线的数据源**：东方财富全系（push2 / push2ex / np-listapi / fundgz / pingzhongdata / FundValuationLast）与韩国 KOSPI 已于 2026-09-11 移除，
相关接口（东财 clist / ulist.np / 涨跌停池）会对本项目请求直接断连，不要再重新引入。

**新增数据源**：在 `providers/` 下开新文件（如 `sina.py`），禁止塞回已有文件。
**导出**：`providers/__init__.py` 显式 re-export 所有公开符号，对外接口不变。

### 2.2 缓存（marktet 行情）

- 唯一来源：`core.cache_market_value(key, ttl_strategy, factory)`。
- `ttl_strategy`：`'session'`（每次开/收盘刷新一次）或 `'mkt_*'`，不要自己写 `time.time() + N`。
- 缓存 key 集中在文件顶部 `CACHE_KEYS`，用全大写下划线，`market_*` 前缀代表市场层、`fund_*` 前缀代表场外、`quote_*` 前缀代表个股。
- **`marktet_cache.cached_value` 已删除**：用 `cache_market_value` 工厂模式替代。如果发现旧用法直接替换。
- **`ContextVar(FORCE_REFRESH)`**：由 `app.py` 在请求作用域内 set/reset；providers 函数读它判断是否绕缓存。**禁止在 providers 自己实现忽略缓存开关**。

### 2.3 fund123 会话

`backend/providers/fund123.py` 使用 `core.new_cookie_opener()` 打开会话，从 `/fund` 页提取 CSRF，再调用各 JSON endpoint。新增 fund123 子接口时，优先复用已有的 `open_session()`、`search_fund()`、`fetch_material()`、`resolve_product()` 等工具，禁止复制粘贴 `urllib.request.build_opener` + `cookielib.CookieJar()` 样板。

### 2.4 路由（app.py）

- 当前 `backend/app.py` 使用 `if parsed.path == ...` 链式分发。新增路由继续沿用该模式，保持与现有代码一致；如未来路由数量显著增长，再统一迁移到 `ROUTES` 表。
- 参数校验在 `app.py` 的 handler 内直接进行，缺失/非法参数返回 **400**。
- JSON 序列化使用 `self._send_json(payload)`；错误使用 `self._send_error(message, status=400/500)`。
- 错误返回固定结构 `{"error": "..."}`（当前未使用 `detail` 字段）。
- 后端进程启动时自动起归档线程，新增后台任务沿用同样的 pattern（`threading.Thread(target=..., name=..., daemon=True)`）。

### 2.5 services.py

- `DashboardService` 是唯一的业务编排类。新增业务方法请注入到该类，不要在模块顶层写新类。
- 「空行情字典」「空市场宽度结构」使用 `services.empty_quote()`、`services.empty_market_breadth()` 工厂函数返回，禁止在 method 内部手抄 dict 字面量。
- 对价格为 `0` 的边界必须显式用 `is not None` 判断，禁止用 `or` 回退（会把 `0` 当 false 处理）。
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

前端基线为 Vue 3.5.42 + Element Plus 2.14.5，继续使用 Options API 和 Vue CLI 5。入口使用 `createApp`，组件库设置简体中文；图标从 `@element-plus/icons-vue` 显式导入。不得使用 Vue 2 的 `.sync`、`slot-scope`、`slot` 属性或 `beforeDestroy`。

- 自定义双向绑定使用 `v-model:visible` 等参数，对应 `update:visible` 事件，并声明 `emits`。Element Plus 弹窗内部用 `v-model`。
- 插槽使用 `#header` / `#footer` / `#default`，日期值格式为 `YYYY-MM-DD`，清空日期范围时处理 `null`。
- 图表实例使用 `markRaw`，在 `beforeUnmount` 清理图表、监听器及定时器。
- 升级组件库必须执行 `npm test`（真实组件、模拟 API）和前端 lint/build；生产仍用 Vue CLI，Vite 仅供 Vitest 测试。

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
├── HoldingsPanel.vue          持仓收益（桌面表格 / 移动端卡片列表）
├── WatchlistPanel.vue         自选（带分组、排序；桌面表格 / 移动端卡片列表）
├── MarketPanel.vue            大盘指数 + 板块
├── NewsPanel.vue              消息快讯（按 tag / 板块筛选）
├── FloatingActions.vue        可拖拽的「刷新 / 脱敏」悬浮按钮（移动端隐藏，改下拉刷新与点击数值）
├── MetricRail.vue             指标卡片轨道（移动端一行 3 卡片位 + 横滑分页 + 文字自适应字号）
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
- 双向绑定通过 Vue 3 的 `v-model:参数`（`watchlistCategory`、`selectedWatchGroupId`、`activeMarketTab` 等）。
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
| `dialog.js` | `dialogVisible` 计算属性（`v-model:visible` ↔ `update:visible`） | 所有使用 `v-model="dialogVisible"` 的弹窗组件 |
| `viewport.js` | 响应式 `isMobile`（`matchMedia('(max-width: 768px)')`） | 断点会改变**结构**时（如表格 ↔ 卡片列表）；只改样式仍用 CSS 媒体查询 |

mixin 必须是 `export default { data(), methods() }` 的纯对象，不耦合具体业务字段。组件用 `mixins: [numberFormat, draggableFab, dialogModel]` 注册。

**响应式断点约定**：CSS 断点写在 `src/styles/workspace.css`，JS 断点统一走 `viewport.js`，两者必须同为 `768px`。**禁止** 用 CSS `display: none` 同时渲染表格和卡片两套 DOM——`el-table` 会重复触发测量逻辑，且 DOM 体积翻倍。新增移动端专属结构时，注册 `viewport` mixin 并用 `v-if="isMobile"` 切换。

**禁止** 为只转发 props 的字段写无意义 computed（例如 `newsLoading() { return this.loading }`）。模板直接使用 props。

### 3.4 utils（`src/utils/`）

- `format.js`：14 个 formatter 已经抽成纯函数。**禁止** 在组件 `methods` 里再写一遍 `formatMoney / formatPercent / formatNetValue`。
- 新增格式化函数请加到 `format.js` 而不是组件里。
- 函数必须接受 `null/undefined` 并返回占位（一般是 `''` 或 `'—'`），与前端 `loading` 态解耦。
- `backButton.js`：`registerBackButton(handler)` 注册 Android 物理返回键，返回取消监听函数；`handler` 返回 `true` 表示已消费本次返回。非原生端与插件缺失时返回空实现，调用方不需要判断平台。

### 3.5 样式（`src/styles/`）

| 文件 | 内容 |
|---|---|
| `global.css` | 主题变量（`--bg`/`--text`/`--danger` 等）、`body` 背景、滚动条 |
| `workspace.css` | 全部「面板/dialog 共享」的 layout class（`.app-shell`、`.workspace-nav`、`.brand-mark`、`.menu-card`、`.stat-card`、`.holding-table`、`.mobile-tabbar`、`.data-card` 等） |

移动端专属 class 约定（新增时沿用，不要另起名字）：

| class | 用途 |
|---|---|
| `.page-heading` | 页面级工具条，**只放操作区**（`.panel-actions` 的更新时间 + 刷新按钮）。页面标题与介绍已全部移除（`h2`/`p` 子规则一并删除），不要再往回加；`justify-content: flex-end` 让操作区靠右单行，移动端同理。移动端把按钮一并隐藏（`.page-heading .panel-actions .el-button { display: none }`），刷新由下拉手势承担、只留更新时间；桌面端没有下拉手势，按钮必须保留 |
| `.panel-header` / `.panel-tip` | 卡片标题行（`el-card` 的 `#header`）：**任何视口都保持单行**——标题在左，右侧放 `.panel-tip`（数据日期 / 条数）或「完整复盘 / 更多」按钮，靠 `justify-content: space-between` 两端对齐。移动端**不要**给它加 `flex-direction: column`（曾这么写过，小标题会掉到第二行白占一行高度）。宽度不够时优先让 `.panel-tip` 收缩，不要换成折行 |
| `.temperature-*` | 首页市场温度卡：`.temperature-main > div:first-child` 让「市场情绪」标签与情绪值同行基线对齐（不再各占一行）；`.temperature-metrics` 默认 4 列一行，移动端媒体查询改 2 列两行。指标项超过 4 个时要重新算列数，别让文字换行 |
| `.metric-rail` / `.metric-rail__cell` / `.metric-rail__dot` | 指标卡轨道：移动端一行 3 卡片位 + 横滑分页，桌面端恢复栅格。卡片内的 `.stat-label` / `.stat-value` / `.stat-foot` / `.index-label` / `.index-value` 会被组件按宽度自动缩字号（下限即元素上的 `--fit-min`），**不要再给这些元素写死 `nowrap` 之外的截断规则**：要改缩放下限只改 `--fit-min`，要新增可自适应的元素就把它加进 `MetricRail` 的 `fitSelector` |
| `.mobile-tabbar` / `.mobile-tabbar__item` | 底部 Tab Bar，仅在 `@media (max-width: 768px)` 内 `display: flex` |
| `.pull-refresh` / `.pull-refresh__icon` | 下拉刷新指示器，高度由内联 style 驱动（静止 0、跟随手指撑开、刷新中固定 52px）；只有 `.is-animating`（回弹/收尾）才加高度过渡，跟随手指时必须即时响应 |
| `.data-card-list` / `.data-card` / `.data-card__cell` | 移动端数据卡片，替代需要横向滚动的宽表格，与 `viewport.js` 的 `isMobile` 配套 |
| `.data-card__foot` / `.data-card__actions` | 卡片底部行。汇总项**必须复用 `.data-card__cell`**（标签在上、数值在下），并且与 `.data-card__grid` 共用同一条列规则（三等分 + 10px 列间距）与同一个文本对齐（居中）——两处只要有一项不同（列宽被按钮挤窄、或上方左对齐下方居中）就会看出错位。网格用 `grid` 而非 `flex`：自选基金卡有 5 个字段，`flex` 换行后尾行会被 `space-between` 推到两端。操作按钮统一放 `.data-card__actions`，嵌在**元信息行右端**（`margin-left: auto`），不要另起一行——该行右侧原本是空白，独占一行会白占约 34px/卡。按钮 26px 高（`.data-card__meta .el-button`），默认 32px 会撑高整行 |

移动端顶部**不再有任何常驻操作按钮**（不再占掉导航条右侧空间）：刷新走下拽手势
（`src/utils/pullToRefresh.js`，注册在 `App.vue` 的 `mounted`；`touchmove` 必须显式
`passive: false`，否则 `preventDefault` 无效、页面会跟着一起滚），脱敏走「点击数值」
（`App.vue` 的 `MASK_TOGGLE_SELECTOR`，只圈汇总卡数值与卡片数值，并排除
`.stat-card--clickable`——那张卡整卡可点开会打开走势弹窗）。页头的「刷新行情 / 刷新快讯」
（`.page-heading .panel-actions` 里的 `.el-button`）同样在移动端隐藏，功能并入下拉刷新。
桌面端维持右下角两个悬浮球与两个页头刷新按钮不变，**不要**再把刷新/脱敏按钮加回移动端顶部。

`env(safe-area-inset-*)` 只允许出现在 `.app-shell`、`.mobile-tabbar` 两处（分别负责内容区、底部 Tab Bar 的安全区），其他位置不要重复加。移动端顶部条已整条移除（`.workspace-nav { display: none }`），所以不需要再为它留安全区。

**禁止** 在 `.vue` 的 `<style scoped>` 里重复定义这些类。如确实需要局部样式，请用组件自己的局部 class，并通过 `:deep(...)` 选择子组件的最深一层 UI（Element Plus 内部不破例）。

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
- [ ] 前端改动：`npm test` 组件回归通过
- [ ] `npx vue-cli-service build` 成功，`dist/index.html` 与 `dist/js/*.js` 全部产出
- [ ] curl `GET /api/health` 返回 200；`GET /api/holdings` 与 `GET /api/watchlist` 返回合理结构
- [ ] 新增的依赖已写入 `requirements.txt` / `package.json`
- [ ] 数据库改动：SQLite 测试 + MySQL（如果改了 schema）测试都通过
- [ ] README.md 已同步（受影响的小节更新或注明「无需变动」）
- [ ] 没有遗留的 `print()` / `console.log()`（除了临时 debug，已在 commit 删除）
- [ ] 没有遗留的 `TODO` / `FIXME`（或已写在 issue/backlog）

---

_最后修订：2026-09-12。改动本文件请同步告知维护者。_
