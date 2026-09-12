# 量化工作台

个人持仓、场外基金估值、自选行情、市场指数与财经消息工作台。支持浏览器和 Capacitor Android APK；Python 后端提供 HTTP API，本地默认 SQLite，服务器通过 Docker Compose 使用 MySQL。

本文按当前仓库实现整理，包含每分钟刷新、北京时间净值判断和收盘估值归档。后续代码变更必须同步维护本文受影响的内容，规则见 [AGENTS.md](AGENTS.md)。资金轮动功能已移除。

## 阅读导航

- [功能介绍](#功能介绍)
- [软件架构](#软件架构)
- [代码结构](#代码结构)
- [数据流与计算](#数据流与计算)
- [外部数据源](#外部数据源)
- [缓存与定时任务](#缓存与定时任务)
- [数据库结构](#数据库结构)
- [HTTP API](#http-api)
- [环境配置](#环境配置)
- [前端组件库与兼容性](#前端组件库与兼容性)
- [本地开发](#本地开发)
- [构建与部署](#构建与部署)
- [Android APK](#android-apk)
- [数据迁移与备份](#数据迁移与备份)
- [验证与排障](#验证与排障)
- [文档维护](#文档维护)
  - [已移除功能](#已移除功能)

## 功能介绍

| 页面 | 功能 |
| --- | --- |
| 首页 | 市值、当日盈亏、消息数量、更新时间；市场温度、涨跌家数；板块涨幅榜/跌幅榜各前五；最新快讯与更多入口 |
| 持仓收益 | 股票、ETF、场外基金新增/修改/删除；自动识别名称和行情；份额及成本管理；市值、累计持有收益、今日预估/实际收益及对应收益率；新增持仓默认同时加入自选（可取消勾选）；点击「累计今日预估收益」查看当日收益率走势并与指数对比 |
| 自选 | 股票/ETF 与场外基金分开分组；每个分类各有一个默认分组（场内自选/场外基金），不可删除；创建/删除组、添加/删除标的；后端提供分组上移/下移接口；浏览器记住分类下最后选中的组 |
| 市场指数 | 内地、港股、美股 TAB；指数分时图；行业涨幅前十和跌幅前十 |
| 消息快讯 | 财联社、新浪、富途、同花顺渠道卡片；重要关键词筛选、各渠道内时间倒序 |
| 场外基金详情 | 估值/业绩走势 TAB；估值更新时间、归档日期选择；持仓股/历史净值 TAB；持仓股加入自选时选择分组 |

### 页面顶部（无标题头）

各页面顶部不再渲染「页面标题 + 一句话介绍」：`首页` 的 hero 主视觉整块移除，`持仓收益` 的页头整块移除，`自选 / 市场指数 / 消息快讯` 的 `.page-heading` 只保留更新时间与刷新按钮（右对齐单行）。删除后首屏第一个内容块上移到顶部约 114px（桌面）/ 26px（移动，顶部条已整条移除）。原先放在持仓页页头的「导入演示持仓」入口连同 `POST /api/seed-demo` 接口一并删除，演示数据改为自行新增持仓。

### 首页市场温度卡片

卡片标题行右侧显示数据日期（如 `2026-09-11 实时`）。卡片内部只保留三段：「市场情绪」标签与情绪值同一行（基线对齐）→ 右端平均涨跌幅；下方四项宽表指标（主要指数涨跌 / 全市涨跌 / 行业领涨 / 行业领跌）**桌面端一行四列、移动端两列两行**，不再逐项纵向堆叠。移动端卡片高度由约 350px 压到 176px、桌面端约 179px，首屏能多露出一屏后续内容。

### 卡片标题行（`.panel-header`）

所有面板卡片的标题行在**任何视口都保持单行**：标题在左，右侧放数据日期、条数，或「完整复盘 / 更多」这类跳转按钮。移动端曾把这一行折成两行（`flex-direction: column`），已移除——折行既白占一行高度，也和小标题「移到右侧」的诉求相悖。

### 滚动吸顶

三处切页控件在页面滚动时固定在视口顶部，不必先滑回顶部再切换（桌面端与移动端一致）：

| 位置 | 吸附元素 | 行为 |
| --- | --- | --- |
| 指数页 | `.el-tabs.market-index-tabs` | 「内地 / 港股 / 美股」选项卡常驻顶部 |
| 自选页 | `.watchlist-card .el-tabs` | 「场内基金与股票 / 场外基金」选项卡常驻顶部；下方的分组按钮行**不**吸附，随页面滚走 |
| 快讯页 | `.news-source-card .el-card__header` | 每条来源卡片的标题行吸附，滚到下一个来源时被顶走、换成下一个来源 |

三个实现要点：

- **吸附的是 `.el-tabs` 本身，不是内部的 `.el-tabs__header`**：sticky 只能在包含块内移动，选项卡下方没有内容面板时 `.el-tabs` 的高度就等于头部，把 sticky 放在头部会立刻被包含块底边顶走。上下留白因此改由 `.el-tabs` 的 `padding` 提供。
- **Element 的 `.el-card` / `.el-card__body` 默认是 `overflow: hidden / auto`**，会把裁剪盒变成滚动容器从而让内部 sticky 失效，所以自选卡片与快讯卡片显式放开裁剪（`overflow: visible`）。快讯标题行的顶部两角用 `border-radius: inherit` 跟随卡片圆角，避免方角露在圆角之外。
- 底色用「半透明 + 毛玻璃」（`rgba(...)` + `backdrop-filter: blur(10px)`）：静止时与页面 / 卡片底色融为一体、看不出差异，内容从下方穿过时才显形；`top` 取 `env(safe-area-inset-top, 0px)`，刘海屏上不会被状态栏压住。

桌面端快讯为两栏布局，因此左右两栏各自保留自己的吸顶来源标题。

### 移动端指标卡片

首页汇总卡、持仓收益汇总卡、市场指数卡统一由 `src/components/MetricRail.vue` 渲染：屏幕宽度 ≤ 768px 时一行固定 3 个卡片位，超出部分横向滑动查看，带 scroll-snap 与圆点分页指示器（卡片不足 3 个时等分铺满，不显示指示器）；> 768px 时恢复为栅格（769～1199px 两列、≥ 1200px 四列），桌面端布局与交互不变。

**卡片内的文字自适应**：移动端卡片位很窄（390px 屏下卡片约 115px，内容区约 89px），金额一长就会被省略号截断（如 `¥136149....`）。组件因此自带一层字号自适应——命中 `fitSelector` 的元素（默认 `.stat-label` / `.stat-value` / `.stat-foot` / `.index-label` / `.index-value`）只要内容宽度超过自身宽度，就按「可用宽度 ÷ 实际宽度」等比缩小字号直到放得下，下限取元素上的 `--fit-min`（数值 11px、标签与脚注 10px）；缩到下限仍放不下（时间戳、长句脚注）则改为折行显示，宁可多占一行也不出省略号。字号在每次组件更新、容器尺寸变化时重算，窗口变宽会自动还原。桌面端宽度充裕，字号保持原样（数值 30px、时间戳 21px）。

CSS 里的 `text-overflow: ellipsis` 保留为极端情况的兜底，正常不该再出现省略号。

### 移动端导航与卡片列表

屏幕宽度 ≤ 768px 时，页面结构会切换成更贴近原生 App 的形态，桌面端完全不受影响：

| 项目 | 移动端行为 |
| --- | --- |
| 页面切换 | 常驻底部的 Tab Bar（首页/持仓/自选/指数/快讯），落在拇指操作区内 |
| 顶部导航 | 移动端**整条不渲染**（`.workspace-nav { display: none }`）：切页在底部 Tab Bar、刷新是下拉手势、脱敏是点击数值，品牌文字不承载任何功能，删掉后首屏内容直接贴安全区顶部（比原先的窄品牌栏再省约 36px）；桌面端仍是「品牌 + 横向菜单」的吸顶条 |
| 刷新 | 下拉刷新：内容滚到顶部后向下拖拽超过阈值即重新抓取全部数据；指示器在「下拉刷新 / 松开刷新 / 正在刷新…」之间切换，静止时高度为 0，完全不占空间。`body` 上的 `overscroll-behavior-y: contain` 关掉了浏览器自带的下拉刷新，避免两个手势打架 |
| 页头刷新按钮 | 自选页的「刷新行情」与快讯页的「刷新快讯」在移动端隐藏（`.page-heading .panel-actions .el-button { display: none }`），功能由下拉刷新承担，页头只留右侧的更新时间作为刷新结果反馈；桌面端没有下拉手势，两个按钮保留 |
| 脱敏 | 点击页面上的数值即可切换显示 / 隐藏（范围限汇总卡数值与移动端卡片数值），不再占用按钮位 |
| 悬浮按钮 | 桌面端右下角的两个悬浮球在移动端隐藏（会压住表格与数字），移动端改用上面两个手势 |
| 持仓 / 自选 | 宽表格改为卡片列表：每张卡片一行主信息（名称 + 涨跌幅）、一行代码/类型/分组，下面 3 列网格铺开现价、成本价、昨日收盘、预估收益、当日收益、持有收益等字段，不需要横向拖动；持仓卡片底部「实际涨幅（当日）/ 预估涨幅 / 持有收益率」与上方网格共用同一套列规则（三等分 + 10px 列间距），列边界逐像素一致、标签与数值统一居中；修改/删除放在元信息行（代码/类型/份额）右端，省掉独占的一整行；卡片右上角的大号涨幅取预估涨幅 |
| 安全区 | `viewport-fit=cover` + `env(safe-area-inset-*)`，适配刘海屏与底部手势条 |

结构差异（表格 vs 卡片）由 `src/mixins/viewport.js` 暴露的响应式 `isMobile` 决定，而不是用 CSS 同时隐藏两套 DOM；纯样式差异仍走 CSS 媒体查询。

Android 端另接入了物理返回键（`@capacitor/app` 的 `backButton`）：有弹窗时先关弹窗，不在首页时先回首页，只有位于首页才交还系统退出。浏览器端自动降级为空实现。

持仓表默认按预估涨幅降序，含份额、成本、昨收、现价、估值、预估涨幅/收益、当日涨幅/收益，最后为持有收益及收益率。成本价与基金净值展示四位小数。首页和持仓敏感数字默认以 `****` 隐藏：桌面端用右下角悬浮眼睛切换、悬浮刷新重新请求数据（按钮支持拖动），移动端改为「点击数值切换 + 下拉刷新」。

业绩区间为近一个月、三个月、六个月、一年，同时显示基金与对比指数。持仓股展示代码、名称、涨跌幅、占净值比例；历史净值展示日期、单位净值、累计净值、日涨幅，支持日期范围查询。异步区域使用 Skeleton、空状态及失败提示，保存按钮有等待状态。脱敏仅作用于展示，接口仍返回真实数值。

### 当日收益率走势与指数对比

点击持仓收益页「累计今日预估收益」卡片打开弹窗，展示组合当日收益率曲线，并可叠加上证指数、创业板指、科创50 的分时涨跌幅，默认三个全部选中，可任意勾选或取消。组合与指数统一用「当日收益率 / 涨跌幅（%）」口径、共享同一 Y 轴直接对比。

曲线按 A 股连续竞价分钟网格 09:30～11:30、13:00～15:00 生成，共 242 个点。每个持仓取当日分时曲线（优先读取当天已归档数据，缺失时场外抓 fund123 盘中预估、场内抓腾讯分时），按分钟前向填充后聚合：

| 项目 | 计算 |
| --- | --- |
| 单个持仓某一分钟收益 | 份额 ×（该分钟价格 − 昨日收盘价） |
| 组合收益 | 各持仓收益求和；该分钟全部缺失则为 null |
| 组合收益率 | 组合收益 / Σ(份额 × 昨收) × 100 |
| 指数涨跌幅 | （该分钟点位 − 昨收）/ 昨收 × 100 |

某一分钟只要有任一持仓有数据就参与求和，其余按 0 计入，避免标的陆续出现数据造成台阶。取不到分时的持仓列入 `missing_holdings` 并在弹窗提示，不参与曲线。持仓为空或全部取不到分时时不绘图，显示空状态。

指数分时全部来自腾讯接口，任一指数不可用则该项禁用勾选。弹窗打开时请求一次，可手动重新抓取，不参与页面每分钟自动刷新。后端仍同时返回组合金额 `pnl` 与收益率 `rate`，前端图表默认展示收益率。

## 软件架构

按职责分层描述当前实现，与下方运行时流程图配合阅读。资金轮动功能已移除，相关表初始化时被删除。

```
┌──────────────────────────────────────────────────────────────────────┐
│                          客户端 / 部署层                              │
│   浏览器 (Web)        Android WebView (Capacitor APK, HTTPS API)      │
└───────────────┬──────────────────────────────────┬───────────────────┘
                │ HTTPS                            │ 同源 /api
                ▼                                  ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          HTTP 网关层                                  │
│   Caddy 2.8                                                           │
│     - 静态资源 (frontend/ = dist/)                                     │
│     - /api/* 反代 → quant-api:5000                                     │
│     - HTTP IP 入口不入自动 TLS (仅域名入口签发证书)                    │
└───────────────┬──────────────────────────────────────────────────────┘
                │ HTTP (容器内)
                ▼
┌──────────────────────────────────────────────────────────────────────┐
│                          应用服务层 (Python 3.11)                      │
│   backend/run.py (入口, 加载 .env.local)                              │
│     └─ ThreadingHTTPServer (无 Flask/FastAPI/ORM)                      │
│        └─ backend/app.py                                              │
│           - do_GET/POST/PUT/DELETE if/elif 路由链                       │
│           - _send_json / _send_error 统一响应                          │
│           - handle_write_errors 装饰器 (ValueError→400, 其他→500)      │
│           - FORCE_REFRESH ContextVar 控制强制刷新                      │
│           └─ backend/services.py                                      │
│              - DashboardService 编排                                   │
│              - holdings/watchlist CRUD、收益汇总、当日走势              │
│              - 静态 FALLBACK_SECTORS 兜底榜单                          │
└───────────────┬─────────────────────────────┬────────────────────────┘
                │                             │
                ▼                             ▼
┌──────────────────────────────┐  ┌────────────────────────────────────┐
│      数据访问层              │  │        外部数据源层                 │
│  backend/database.py        │  │  backend/providers/ 子包            │
│   - SQLite (本地)           │  │   core: 缓存工厂 (cache_market_     │
│   - MySQL 8.4 (Docker)      │  │          value), Time/TTL          │
│   - ? → %s 占位符转换       │  │   quotes: 腾讯股票/ETF、交易日历    │
│   market: 指数/行业/市场宽度       │
│     INSERT IGNORE 兼容      │  │   fund123: 估值/历史/持仓/业绩      │
│   表:                       │  │   news: 多渠道快讯聚合              │
│   funds: 场外回退链 (fund123)       │
│     watchlist_groups/items  │  │                                     │
│     app_settings            │  │   进程内缓存 (MARKET_CACHE dict)     │
│     fund_estimate_archives  │  │   ttl: 盘中 15~60s, 闭市至下开盘    │
│     exchange_price_archives │  │                                     │
└──────────────────────────────┘  └────────────────────────────────────┘
                ▲
                │ 后台线程
┌───────────────┴──────────────────────────────────────────────────────┐
│                          调度层 (进程内)                              │
│   backend/fund_archives.py                                           │
│     - 每 300s 一轮                                                    │
│     - 北京时间 15:05 后用交易日历确认交易日                           │
│     - SQL UNION 合并 holdings/watchlist_items.code                    │
│     - fund123 估值 (场外) / 腾讯分时 (场内)                           │
│     - 校验: 所有点属于当天, 最晚 ≥15:00, JSON payload                  │
│     - 失败 5 分钟重试, 成功不覆盖, 长期保留                            │
│                                                                        │
└──────────────────────────────────────────────────────────────────────┘
```

运行时流程（请求 → 响应）：

```text
浏览器 / Android WebView
  -> App.vue -> 子组件 (components/) -> Axios (/api)
  -> Vue CLI 开发代理 / 服务器 Caddy
  -> app.py if/elif 路由链 + _send_error 统一异常处理
     -> services.py DashboardService 编排、持仓/自选、收益计算
        -> database.py -> SQLite / MySQL
        -> providers/ 子包 (quotes/market/fund123/news/funds)
           -> 进程内缓存 (core.cache_market_value) -> 外部行情/基金/新闻
     -> fund_archives.py -> 数据库历史估值

后端启动 -> 收盘归档线程 -> 交易日判断 -> 持仓/自选标的去重
  -> fund123 估值 / 腾讯场内分时 -> 日期及收盘点校验 -> 数据库
```

`App.vue` 用 activeMenu 切换菜单，没有 Vue Router 或 Vuex。面板放在 `src/components/`，弹窗与悬浮按钮同理；共享格式化逻辑在 `src/utils/format.js`，可拖拽悬浮按钮在 `src/mixins/`。后端每个 HTTP 请求在线程中执行，部分指数并发抓取；归档使用进程内后台线程。

| 层 | 关键实现 |
| --- | --- |
| 前端 | Vue 3.5.42、Vue CLI 5、Element Plus 2.14.5、ECharts 5、Axios 1；具体安装版本由 package-lock.json 锁定 |
| 后端 | Python 3.11、标准库 ThreadingHTTPServer；没有 Flask/FastAPI、ORM 或独立任务队列 |
| 数据适配 | AkShare 1.18.94（仅快讯）、urllib |
| 存储 | SQLite / PyMySQL 1.1.1；Docker MySQL 8.4；cryptography 46.0.5 支持数据库认证 |
| 网关 | Caddy 2.8，HTTPS、静态文件与 API 反向代理 |
| Android | Capacitor 8.5、JDK 21、Gradle；minSdk 24、compileSdk/targetSdk 36 |

## 代码结构

```text
fund-pro/
  src/
    main.js                 Vue 3/Element Plus 初始化和全局 CSS
    App.vue                 导航、全局状态、定时刷新；不再承载面板/弹窗模板
    api/dashboard.js        Axios 地址、超时及全部 API 函数
    components/             面板 (Home/Holdings/Watchlist/Market/News) + 弹窗 + FloatingActions
    mixins/                 numberFormat、draggableFab
    utils/format.js         14 个共用格式化纯函数
    styles/global.css       主题变量、滚动条、body 背景
    styles/workspace.css    共享的 layout class（卡片、表格、菜单、弹窗骨架等）
  public/
    index.html              HTML 入口模板
    runtime-config.js       浏览器运行时 API 地址
  backend/
    run.py                  后端启动入口
    app.py                  if/elif 路由链 + _send_error 统一异常处理 + JSON
    services.py             DashboardService：持仓/自选 CRUD、收益汇总、当日走势、降级数据
    providers/              子包：core/quotes/fund123/market/news/funds
    database.py             SQLite/MySQL 连接、建表及兼容 SQL
    fund_archives.py        收盘采集、归档校验、历史日期及读取
  docs/
    CODE_STANDARDS.md       项目代码与架构规范（强约束）
  scripts/
    deploy.sh               Linux 构建、复制静态资源、Compose 和校验
    verify-deployment.py    首页同源 JS/CSS 状态、MIME、HTML 误返回检查
    probe_all_sources.py    外部数据源可用性排查
    probe-layout.mjs        无头 Chrome 按指定视口渲染，输出关键元素计算样式与几何并截图
  android/                  Android 工程、Gradle 包装器和构建配置
  capacitor.config.json     App 标识、Web 目录、HTTPS 配置
  vue.config.js             端口、开发代理、浏览器/APK publicPath
  package.json              前端依赖与 npm 命令
  package-lock.json         前端依赖锁文件
  requirements.txt          Python 依赖及固定版本
  babel.config.js           Babel 配置
  .eslintrc.js              JS/Vue 检查规则
  Dockerfile                Python API 镜像
  docker-compose.yml        db、quant-api、caddy 编排
  Caddyfile                 域名/IP 路由、静态文件和 API 代理
  .env.deploy.example       部署环境模板
  .env.android.example      APK API 地址模板
  .dockerignore/.gitignore   构建上下文及版本控制排除
  AGENTS.md                 后续协作及文档维护要求
```

构建生成 `dist/`；部署使用 `frontend/`，挂载到 Caddy `/srv`。这两者是产物目录，不是源代码。Android 原生工程中的 variables.gradle 定义 SDK 版本，app/build.gradle 管理应用构建。

## 数据流与计算

### 场内价格走势归档

股票和场内基金（stock/etf）现在也参与每个交易日 15:05 后的自动归档，覆盖持仓和自选。使用腾讯分时接口，保存源接口的交易日期、分时价格、昨日收盘价和来源；价格走势不是基金单位净值。与场外基金一样每轮完成后 5 分钟重试，必须为当天数据且包含 15:00 或之后的点，长期保留、成功后不覆盖。

新增 `exchange_price_archives` 表，字段 code、trade_date、payload、saved_at，与场外归档相同，以 code+trade_date 为主键；SQLite 用 TEXT，MySQL 用 LONGTEXT 保存 JSON。原有 fund_estimate_archives 保留不变。历史接口 `/api/instruments/estimate-archive` 新增可选 asset_type=stock/etf/fund（默认 fund），返回对应类型的日期和曲线。股票/ETF 详情增加“价格走势日期”选择，加载沿用骨架屏。

场内归档沿用内地交易日和北京时间 15:00 收盘口径，当前不支持海外股票交易时段；价格解析沿用现有沪深代码规则。停牌无有效分时、上游缺日期或缺收盘点时不生成记录。该归档是整段分时曲线，未新增逐日 OHLC K 线或场内基金官方净值接口。

### 看板与自选

1. 页面调用 dashboard，服务从 holdings 读份额、成本和类型，逐个取得行情。
2. providers 根据缓存与回退策略返回数据，services 计算单项及组合收益。
3. 同一看板请求还取得行业排名、市场宽度后返回 JSON。因此全市场抓取也会影响看板响应速度。
4. 指数、快讯由页面通过各自 API 并行请求；自选先查询 groups/items，再按类型附加报价。
5. Vue 更新页面；点击名称打开详情并渲染 ECharts。新增持仓先写数据库，再请求看板，保存成功不等于随后行情刷新成功。
6. 新增持仓在同一事务内按类型镜像到自选：stock/etf 进 exchange 分类的默认组，fund 进 fund 分类的默认组；同代码已存在或没有对应分类分组时跳过，失败不影响持仓创建。关闭「同时加入自选」则不镜像。删除持仓不会删除自选标的。
7. 默认分组（场内自选/场外基金）在 `watchlist_groups.is_default` 标记，每次启动由 `init_db()` 保证每个分类恰好一个；删除默认分组会返回 400，前端对默认分组不显示「删除分组」。

设 Q=份额，C=成本，P0=昨日收盘价，P=现价，E=估值，涨幅单位为百分数：

| 项目 | 公式 |
| --- | --- |
| 昨日市值 | Q × P0 |
| 场外估值 | round(P0 × (1 + 预估涨幅 / 100), 4) |
| fund123 实际涨幅 | 今日净值已确认时 (P - P0) / P0 × 100 |
| 当日收益 | Q × P0 × 当日涨幅 / 100；缺少涨幅则为空 |
| 预估收益 | Q × P0 × 预估涨幅 / 100 |
| 持仓市值 | Q × 首个可用值(P、E、P0) |
| 持有收益/收益率 | 市值 - Q×C；持有收益 / (Q×C) × 100 |
| 组合实际收益率 | 有实际收益的标的收益之和 / 这些标的昨日市值之和 × 100 |
| 组合预估收益率 | 有预估收益的标的收益之和 / 这些标的昨日市值之和 × 100 |

股票/ETF 的估值、预估涨幅、预估收益分别使用现价、当日涨幅、当日收益。组合忽略缺失收益项；全部缺失时汇总返回 0，不表示已确认零涨幅。底层计算是 Python float、SQLite REAL/MySQL DOUBLE，不是定点财务账本。

fund123 netValue 为最新公布净值，主链路校验 netValueDate 等于北京时间当天才填入现价。昨日参考净值在 09:30 前以日历前两天为截止、09:30 后以前一天为截止，取历史记录中最近可用值；这不是完整节假日推算。缺历史净值时仍有回退，限制见后文。

### 收盘归档与回看

后端启动后每轮判断北京时间是否达到 15:05，并用交易日历确认。SQL UNION 合并持仓和自选中 fund/stock/etf 类型代码，跳过当天已有记录；场外抓取 fund123 估值，场内抓取腾讯分时。

所有点必须属于当天，最晚时间不早于 15:00，才保存 JSON。每轮结束等待 300 秒，失败下轮重试；异常写日志，空或不完整曲线跳过。午夜后只处理新日期，没有跨日补采。读取日期列表和选定日期的历史曲线只访问数据库。

归档是上游返回的估值点，不保证逐分钟齐全，不是正式净值；不要求当日正式净值已经发布。数据长期保留，成功后不覆盖，删除持仓/自选也不删归档。服务需在当天收盘后运行；错过整晚、日历不可用或缺少收盘点会形成空档。

## 外部数据源

适配实现见 [providers/](backend/providers/) 包（按数据源分子模块），日历见 [fund_archives.py](backend/fund_archives.py)。以下描述当前调用关系，不保证上游更新频率。

| 使用位置 | 来源 | 回退/说明 |
| --- | --- | --- |
| 持仓股票/ETF、场内识别 | 腾讯 qt.gtimg.cn/q=... | 不经过 AkShare |
| 自选股票/ETF | 腾讯批量报价接口 | 按代码匹配后一次取回 |
| 内地、港股、美股指数 | 腾讯报价，并发请求 | 内地四指数、恒生、恒生科技 hkHSTECH、道琼斯、纳斯达克、标普500 |
| 场内及内地/港股分时 | 腾讯 web.ifzq.gtimg.cn/appstock/app/minute/query | 不可用显示空状态 |
| 美股指数分时 | ~~Yahoo chart API~~ 已移除 | 公开端返回 HTTP 403，没有可用的免费替代，美股指数不提供当日分时 |
| 行业前十排名 | 腾讯 proxy.finance.qq.com/cgi/cgi-bin/rank/pt/getRank | 一次取全部行业后本地排序；失败回退 services.py 的 FALLBACK_SECTORS 静态榜单 |
| 全市涨跌家数 | 腾讯板块 `zgb` 汇总 | 只给「上涨家数/板块总家数」，平盘计入下跌；不再提供涨跌停家数 |
| 财经快讯 | AkShare（财联社 / 新浪 / 富途 / 同花顺） | 单渠道失败跳过，全部失败返回空消息结构 |
| 归档交易日 | 腾讯日 K web.ifzq.gtimg.cn/appstock/app/fqkline/get | 每根日 K 即一个交易日；取不到则不归档并重试 |

AkShare 目前只用于快讯的财联社、新浪、富途、同花顺四个源。东方财富全系接口（push2 / push2ex / np-listapi / fundgz / pingzhongdata / FundValuationLast）与韩国 KOSPI 已移除：
`push2 /api/qt/clist/get` 会对本项目请求直接断连，其余东财接口也不再作为回退路径。

### fund123 接口

域名为 `https://www.fund123.cn`。后端获取 CSRF，部分链路用 CookieJar 保持会话，浏览器不直接跨域抓取。

| 路径 | 参数、字段及用途 |
| --- | --- |
| /fund | 页面 CSRF |
| /api/fund/searchFund | fundCode；读取 fundName、key |
| /matiaria?fundCode=... | productId、netValue、netValueDate；部分估值链路仍取 searchFund 的 key |
| /api/fund/queryFundHistoryNetValueList | productId、startDate、endDate、pageNum、pageSize；昨收和历史净值 |
| /api/fund/queryFundEstimateIntraday | startTime、endTime、limit、productId、format、source；time 和 forecastGrowth |
| /api/fund/queryFundHolding | productId；持仓股和披露信息 |
| /api/fund/queryFundQuotationCurves | productId、dateInterval；ONE/THREE/SIX/ONE_YEAR |

forecastGrowth 是比例，乘 100 展示为百分数。分时估值以参考净值计算并保留四位小数；归档保存原始涨幅和毫秒时间戳。

基金报价回退顺序：可选 FUND123_ESTIMATE_URL → fund123 盘中估值 → fund123 页面文本解析。自定义地址支持 `{code}` 占位符，JSON 格式需符合 fetch_fund123_valuation。东方财富的 fundgz / pingzhongdata / FundValuationLast 回退已移除。

### 消息来源

| 渠道 | 来源 | 最多条数 |
| --- | --- | --- |
| 财联社 | AkShare `stock_info_global_cls()`（默认 symbol='全部'） | 6 |
| 新浪 | AkShare `stock_info_global_sina` | 4 |
| 富途 | AkShare `stock_info_global_futu` | 4 |
| 同花顺 | AkShare `stock_info_global_ths` | 4 |

按政策、央行、财报等关键词筛选，无命中时使用普通消息。按来源时间字符串降序，单渠道失败跳过，全部失败为空消息结构。当前没有央视/财经早餐等其他渠道，也没有 LLM 多空分析服务。

### 降级边界

- services.py 保留 FALLBACK_SECTORS 静态榜单及“本地回退榜单”标签，不能当作实时排名。
- 持仓所有来源失败时以成本价和零涨幅返回“本地回退数据”。
- 市场宽度只有涨跌家数，没有涨跌停家数；涨跌家数按腾讯行业板块 `zgb` 汇总，平盘计入下跌。
- 场外基金没有盘中实时价：交易日盘中只有 fund123 的估值与预估涨幅，`现价/当日涨幅` 为空；
  净值公布后（当日晚间）或休市日（周末/节假日）才有 `现价/当日涨幅`，取 fund123 最新一期已确认净值
  及其相对上一期净值的涨幅。
- 部分第三方异常被静默降级，没有完整数据质量监控或统一上游总超时。数值要结合数据源和日期理解。

## 缓存与定时任务

| 对象 | 普通请求策略 |
| --- | --- |
| 场外报价 09:30～15:00 | 60 秒 |
| 场外报价 09:30 前 | 至下一次开盘计算时间 |
| 场外报价 15:00 后，净值未发布 | 300 秒 |
| 场外报价 15:00 后，已有现价 | 至下一次开盘计算时间 |
| 场内报价、行业榜单、市场宽度和多数指数 | market_quote_ttl：盘中 15 秒，其他至下一次开盘 |
| fund123 昨日净值 | 按 productId 缓存至下次开盘；开盘前尝试复用 |
| 基金持仓股 | 21600 秒 |
| 历史净值、业绩曲线 | 600 秒，按代码/区间隔离 |
| 快讯 | 30 秒 |
| 当日估值分时 | 直接抓取，没有独立持久缓存 |
| 组合当日收益走势 | 60 秒，整体结果按单一 key 缓存 |
| 历史估值 | 数据库长期保存 |

开盘函数按北京时间 09:30 跳过周末，未使用节假日日历，海外报价也共用该规则。仅收盘归档采用实际交易日历。缓存位于进程内，重启清空，没有 Redis 或跨进程共享缓存。

页面每 60000 毫秒刷新看板、指数和消息，自选菜单下额外刷新自选。页面隐藏或手动全量刷新时跳过，已有 loading 的请求不重叠。详情图、持仓股、历史净值不在自动刷新范围。浏览器后台定时器受系统调度限制。

悬浮手动刷新传 force=true，由 ContextVar 控制适用缓存绕过；自动刷新复用有效缓存。force 不会生成上游新报价、覆盖历史归档或刷新所有已打开的详情。看板超时 120 秒；普通指数 15 秒、消息/自选 45 秒，这几类强制请求为 120 秒。看板/指数失败保留已有页面数据。

## 数据库结构

定义见 [database.py](backend/database.py)。没有 ORM/migration 工具，启动创建缺失表并执行少量兼容迁移；目前初始化仍删除旧 sector_fund_flow_snapshots 表，这是移除资金轮动后的清理行为。

| 表 | 字段 | 约束/用途 |
| --- | --- | --- |
| holdings | id, name, code, asset_type, quantity, cost_price, created_at | id 自增；代码字符串保留前导零；同代码可多条持仓 |
| watchlist_groups | id, name, category, sort_order, is_default, created_at | name+category 唯一；category=exchange/fund；每个分类有且仅有一个 is_default=1 的默认分组，删除接口拒绝删除 |
| watchlist_items | id, group_id, name, code, asset_type, created_at | group_id+code+asset_type 唯一；外键级联删除 |
| app_settings | key, value | key 主键，当前存默认分组初始化标记 |
| fund_estimate_archives | code, trade_date, payload, saved_at | 场外估值；code+trade_date 联合主键，独立于持仓/自选生命周期 |
| exchange_price_archives | code, trade_date, payload, saved_at | 股票/ETF 分时价格；code+trade_date 联合主键，独立长期保存 |

SQLite：id 为 INTEGER AUTOINCREMENT，数量/成本 REAL、文本 TEXT。MySQL：id 为 BIGINT AUTO_INCREMENT，数量/成本 DOUBLE、文本 VARCHAR，created_at 主要为 TIMESTAMP，InnoDB/utf8mb4。归档 payload 为 SQLite TEXT/MySQL LONGTEXT，保存 JSON 字符串；trade_date 为 YYYY-MM-DD，saved_at 为北京时间 ISO 字符串。

归档字段示例（仅示意格式）：

```json
{
  "code": "017462",
  "name": "基金名称",
  "asset_type": "fund",
  "trade_date": "2026-09-09",
  "previous_close": 2.5033,
  "updated_at": "2026-09-09 15:00:00",
  "source_label": "fund123 盘中预估",
  "archived": true,
  "points": [{"time": "15:00", "timestamp": 1788937200000, "forecast_growth": 0.01, "price": 2.5283}]
}
```

普通报价、新闻、收益汇总不持久化；持仓表不是每日持仓快照。浏览器 localStorage 保存 quant-workbench-watchlist-{category} 选中组 ID。生产 MySQL 数据在 mysql_data 卷，SQLite 默认 backend/fund_pro.db，可通过 QUANT_DATA_DIR 改路径。

## HTTP API

路由见 [app.py](backend/app.py)，客户端见 [dashboard.js](src/api/dashboard.js)。下表所有路径加 `/api` 前缀，JSON 响应设 Cache-Control: no-store。GET 解析 force=true，具体缓存绕过取决于 provider。

| 方法/路径 | 参数或请求体 | 返回/作用 |
| --- | --- | --- |
| GET /health | 无 | status=ok 与 database（engine/host/port/database/user 或 sqlite path），用于确认实例实际连的存储 |
| GET /dashboard | force 可选 | portfolio、sectors、market_breadth、generated_at |
| GET /portfolio/intraday-pnl | force 可选 | 当日收益走势：times、portfolio(pnl/rate)、indices(rate)、missing_holdings |
| GET /holdings | 无 | items 原始持仓 |
| POST /holdings | name, code, asset_type, quantity, cost_price；add_to_watchlist 可选（默认 true） | 新建，201；响应含 watchlist_added、watchlist_group_name |
| PUT /holdings/{id} | quantity, cost_price | 修改持仓 |
| DELETE /holdings/{id} | 无 | deleted |
| GET /market-indices | force 可选 | items、generated_at |
| GET /news | force 可选 | items、groups、total_count 等 |
| GET /watchlist | force 可选 | groups、items 含行情、generated_at |
| POST /watchlist/groups | name, category | 新建组 |
| POST /watchlist/groups/{id}/move | direction=up/down | 移动顺序 |
| DELETE /watchlist/groups/{id} | 无 | 级联删除组内自选 |
| POST /watchlist/items | group_id, name, code, asset_type | 新建自选 |
| DELETE /watchlist/items/{id} | 无 | 删除自选 |
| GET /instruments/lookup | code, asset_type | 名称和行情 |
| GET /instruments/intraday | code, asset_type | 分时曲线 |
| GET /instruments/fund-holdings | code | 持仓股、披露信息 |
| GET /instruments/fund-history | code, start_date, end_date | 历史净值 |
| GET /instruments/fund-performance | code, interval | 基金及对比指数业绩 |
| GET /instruments/estimate-archive | code, asset_type 可选（默认 fund） | 日期倒序 dates；支持 stock/etf/fund |
| GET /instruments/estimate-archive | code, date=YYYY-MM-DD, asset_type 可选 | 归档曲线，不存在 404 |

业务类型为 stock/etf/fund，分时接口额外支持 index。当前没有登录、权限隔离、多用户表；响应允许 Access-Control-Allow-Origin: *。所有路由由 `backend/app.py` 的 `do_GET/POST/PUT/DELETE` 通过 if/elif 分发，错误统一返回 `{"error": "..."}` 结构（4xx/5xx），突变路由额外包了 `handle_write_errors` 把 `ValueError` 映射到 400、其他异常映射到 500。公网访问控制需由部署环境补充。

## 环境配置

| 变量 | 默认/设置位置 | 用途 |
| --- | --- | --- |
| HOST / PORT | 本地 127.0.0.1 / 5000；镜像 HOST=0.0.0.0 | Python 监听 |
| DATABASE_ENGINE | 本地 sqlite；Docker mysql | 数据库类型 |
| QUANT_DATA_DIR | backend | SQLite 目录 |
| MYSQL_HOST / MYSQL_PORT | db / 3306 | 数据库地址 |
| MYSQL_DATABASE / MYSQL_USER | quant_workbench / quant | 数据库及应用用户 |
| MYSQL_PASSWORD | Compose 必填 | 应用密码 |
| MYSQL_ROOT_PASSWORD | Compose 必填 | MySQL 初始化/健康检查 |
| MYSQL_BIND_ADDRESS | 0.0.0.0 | MySQL 监听地址；0.0.0.0 = 监听所有网卡，127.0.0.1 = 仅本地。公网暴露必须配合云安全组白名单 |
| MYSQL_HOST_PORT | 3306 | MySQL 映射到宿主机的 TCP 端口 |
| FUND123_ESTIMATE_URL | 默认空 | 自建估值适配地址 |

本机开发在 `backend/.env.local` 写 `DATABASE_ENGINE=mysql` 与 MySQL 连接信息，`backend/run.py` 启动前自动加载（shell 已 export 的同名变量优先），生产 / Docker 不使用该文件。

`DATABASE_ENGINE` 缺省时**静默回退到 SQLite**（`backend/fund_pro.db`），不报错、接口照常返回 200，只是读到的是本地旧数据。因此后端启动时会打印当前存储后端，且 `GET /api/health` 的 `database` 字段会返回实际目标；排查"数据不对"时先查这两个位置确认实例连的是哪个库。
| WEB_DOMAIN / API_DOMAIN | .env.deploy 必填 | 站点/API 域名 |
| SERVER_IP | Compose 有默认，部署应显式改写 | Caddy HTTP IP 入口 |
| MYSQL_IMAGE / PYTHON_IMAGE / CADDY_IMAGE | mysql:8.4 / python:3.11-slim / caddy:2.8-alpine | 镜像覆盖 |
| DEPLOY_URL | deploy.sh 必填 | 部署后资源校验地址 |
| VUE_APP_API_BASE_URL | 构建时可选 | API 基址，包含 /api |
| window.__QUANT_API_BASE_URL__ | runtime-config.js 默认空 | 浏览器运行时 API 基址 |
| VUE_APP_TARGET | Android 脚本设 capacitor | publicPath 切换 |

API 基址优先级：构建变量 → 运行时变量 → 同源 /api。改构建变量要重建；运行时变量在输出目录 runtime-config.js 中设置。普通 build 不加载 .env.android，Android 用 --mode android。

Python 不自动加载 dotenv，本地需在 shell 设置变量；.env.deploy 由 Compose --env-file 读取。market_now 显式用 UTC+8，关键净值和归档不依赖容器系统时区，但并非所有来源的历史显示时间都已统一转换。

## 前端组件库与兼容性

前端使用原生 Vue 3.5.42（Options API）和固定版本 Element Plus 2.14.5，保留 Vue CLI 5 构建、原有菜单、API 和收益计算。应用通过 createApp 初始化，Element Plus 全局设置简体中文；图标使用 @element-plus/icons-vue 的 SVG 组件。自定义组件双向绑定使用 v-model:参数，弹窗内部使用 v-model，插槽使用 #header / #footer / #default；日期选择器向后端继续传 YYYY-MM-DD 字符串。组件和拖拽 mixin 在 beforeUnmount 清理事件、定时器及图表。

前端回归使用 Vitest、Vue Test Utils 和 jsdom，测试配置中的 Vite 仅用于测试，生产构建仍为 Vue CLI。npm test 使用真实 Element Plus 组件，模拟 API 与 ECharts，覆盖表单、弹窗、表格、自选分类、日期查询、图表选择、导航、脱敏、刷新失败保留数据和清理钩子。此测试不验证上游行情、真实浏览器绘图或 Android 原生运行。

Vue 3 / Element Plus 面向现代浏览器，不支持 IE；Android 继续依赖系统 WebView 和服务器 HTTPS API。

## 本地开发

要求 Node.js 22+（当前 Capacitor CLI 要求 >=22）、npm、Python 3.11。Linux 部署另需 Bash、Docker Engine/Compose。

```powershell
git clone https://github.com/strugglingbird/fund-pro.git
cd fund-pro
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe backend/run.py
```

另开终端：

```powershell
npm ci
npm run serve
```

前端默认 http://127.0.0.1:8080，/api 代理到 http://127.0.0.1:5000。端口占用时看启动输出。Linux/macOS 使用 .venv/bin/python。Python 不自动热重载，改后端须重启；Vue CLI 支持前端热更新。

```bash
npm run build
npm run lint
npm test
python -m compileall -q backend
```

build 产出 dist。npm run lint 默认只检查，不自动修复；生产构建仍有依赖包体积警告。当前没有统一后端自动化测试套件，计算、日期、归档等变更应做针对性验证。

## 构建与部署

服务器需 Node.js 22+、npm、Python 3、Bash、Docker/Compose。前端在宿主机编译，后端 Docker 构建，脚本不会安装宿主机依赖或设置 DNS。

```bash
cp .env.deploy.example .env.deploy
```

填写环境，不能提交密码：

```dotenv
WEB_DOMAIN=example.com
API_DOMAIN=api.example.com
SERVER_IP=203.0.113.10
MYSQL_DATABASE=quant_workbench
MYSQL_USER=quant
MYSQL_PASSWORD=replace-with-a-strong-password
MYSQL_ROOT_PASSWORD=replace-with-a-different-strong-password
MYSQL_BIND_ADDRESS=0.0.0.0
MYSQL_HOST_PORT=3306
FUND123_ESTIMATE_URL=
```

域名 A 记录指向服务器，开放 80/443。MySQL 映射为 `${MYSQL_BIND_ADDRESS}:${MYSQL_HOST_PORT} -> db:3306`，默认 `MYSQL_BIND_ADDRESS=0.0.0.0` 监听所有网卡，**需要**在云安全组和系统防火墙中**仅对白名单公网 IP 放行** `MYSQL_HOST_PORT`；不希望公网访问时改为 `127.0.0.1` 重建 db 容器。API 的 5000 端口仍只在 Compose 网络内。MySQL 原生连接不经过 Caddy，也不使用网站 HTTPS 证书。证书签发依赖 DNS、端口和证书服务可达；HTTP IP 入口不使用自动 TLS。

远程数据库客户端参数：主机填写服务器公网 IP，端口填写 `MYSQL_HOST_PORT`，数据库和账号使用 `MYSQL_DATABASE`、`MYSQL_USER`。应用账号仅用于工作台数据访问，日常远程连接不应使用 root。MySQL 8 默认 `caching_sha2_password`，客户端需在驱动层显式选择（PyMySQL ≥ 1.0、JDBC MySQL Connector ≥ 8.0、Navicat 16+）。

```bash
DEPLOY_URL=https://example.com bash scripts/deploy.sh
```

实际流程：npm ci → build → 停 Caddy → 清理 frontend 并复制完整 dist → Compose up -d --build → 最多 12 次资源校验。存在短暂停机，没有蓝绿、自动回滚或原子发布保证。构建失败发生在停 Caddy 前。不要只传 index.html 或单个 app.*.js。

| 服务 | 内容与存储 |
| --- | --- |
| db | MySQL/mysql_data 卷；宿主机端口由 MYSQL_BIND_ADDRESS/MYSQL_HOST_PORT 控制；健康检查通过后 API 启动 |
| quant-api | 安装 requirements、复制 backend、python -u run.py；进程内归档线程 |
| caddy | frontend:/srv、Caddyfile；caddy_data/caddy_config 保存证书和配置 |

Dockerfile 配置 Python、监听地址和 pip 镜像。Caddy 在 WEB_DOMAIN/SERVER_IP 上将 /api/* 反代 quant-api:5000；缺失 /js/*、/css/*、/img/*、/fonts/* 返回 404，其余页面路径回退 index.html。API_DOMAIN 直接代理 API。

```bash
docker compose --env-file .env.deploy ps
docker compose --env-file .env.deploy logs --tail=100 quant-api caddy
python3 scripts/verify-deployment.py https://example.com
curl -f https://example.com/api/health
```

校验器检查首页同源脚本/样式状态、MIME 和 HTML 误返回，不检查浏览器运行错误、图片字体、动态接口、收益正确性或归档完整性。发布后还须看控制台与关键 API。

仅后端更新可用 `docker compose --env-file .env.deploy up -d --build quant-api`。首次只运行 Compose 不会生成前端，必须先有完整 frontend。脚本会覆盖 runtime-config.js，自定义运行时地址需重新应用。

## Android APK

APK 内包含 Web 前端，Python/MySQL/归档任务仍在服务器，不是离线内置后台数据库。手机需联网，当前 cleartext=false，使用有效 HTTPS API。

准备 JDK 21、Android SDK API 36，配置 JAVA_HOME、ANDROID_HOME 或 android/local.properties：

```powershell
Copy-Item .env.android.example .env.android
# 编辑 VUE_APP_API_BASE_URL=https://api.example.com/api
npm run build:android
cd android
.\gradlew.bat assembleDebug
```

产物 android/app/build/outputs/apk/debug/app-debug.apk；Linux 用 ./gradlew assembleDebug。android:open 打开 Android Studio，已有原生工程不必重复 android:add。发行包需自行配置签名，仓库不含签名密钥/发行流水线。

Android 构建覆盖 dist，部署浏览器前要重新普通 build，避免 APK 相对路径和固化 API 地址混入网页版本。

物理返回键依赖 `@capacitor/app`（已在 `package.json`）。新增或升级 Capacitor 插件后必须执行一次 `npx cap sync android`，否则 `android/capacitor.settings.gradle` 不会包含该插件，返回键监听不生效。注意 `cap sync` 会把当前 `dist` 复制进 `android/app/src/main/assets/public`，所以只能用 Android 模式构建后的产物同步（`npm run build:android` 已包含这一步），不要对着普通 Web 构建跑 `cap sync`，否则 APK 里的资源路径会变成绝对路径。

## 数据迁移与备份

换电脑克隆源码、安装依赖，另外迁移本地配置和所需数据库。Git 不含生产数据库、证书和进程缓存，也不会自动同步 SQLite 到 MySQL。SQLite 停后端后复制 fund_pro.db，自定义 QUANT_DATA_DIR 按实际位置备份。

MySQL 在服务器备份：

```bash
docker compose --env-file .env.deploy exec -T db sh -c 'MYSQL_PWD="$MYSQL_PASSWORD" mysqldump --no-tablespaces --single-transaction -u "$MYSQL_USER" "$MYSQL_DATABASE"' > quant-backup.sql
```

备份包含持仓、自选和估值历史，放在受控位置。恢复前核对目标库，使用 mysql 导入。不要对需保留的数据执行 docker compose down -v，它会移除数据卷。

当前 gitignore 排除 node_modules、dist、指定 Android 构建目录、.env.android、.env.deploy、默认 SQLite、Python 缓存。自定义数据目录、frontend、备份、其他 env、签名文件未必被排除，提交前检查 git status。

## 验证与排障

| 问题 | 检查 |
| --- | --- |
| 白屏/Unexpected token '<' | JS 是否返回 HTML，是否完整发布依赖；运行资源校验、看浏览器控制台 |
| 看板刷新失败 | 网络/超时、全市场源耗时；看板超时 120 秒；BrokenPipe 常是客户端提前断开 |
| 保存成功列表未更新 | holdings 写入与 dashboard 刷新分别检查 |
| 实际净值为空 | fund123 netValueDate 是否今天，注意回退来源 |
| 走势图为空或某段缺失 | 持仓是否为空；当天归档是否存在、fund123/腾讯分时是否可达；个别标的无分时列入 missing_holdings |
| 快讯为空 | akshare 是否安装可用；财联社/新浪/富途/同花顺各渠道失败会跳过，全部失败返回空结构 |
| 归档日期为空 | 场外持仓/自选是否存在；日历、15:05 后服务运行、15:00 点是否返回 |
| 个别归档缺失 | 异常日志；日期混杂/缺收盘点会跳过，不伪造也不跨日补采 |
| 移动端改样式后看不到效果 | 先强制刷新（改动前后页面可能停在中间态）；再用 `node scripts/probe-layout.mjs <url> 390 844 shot.png` 读 `.mobile-tabbar`/`.workspace-menu` 的 `display` 确认真实视口下的结果，不要用整页渲染的预览面板判断固定定位元素。第 7 个参数可传菜单名（逗号分隔，如 `"持仓,自选"`），脚本会逐个切换后输出该页的 `.page-heading`/`.hero-card`/首个内容块 top，用于核对页头精简是否生效 |
| IP 正常域名异常 | DNS、80/443、安全组、TLS 和网关分别检查 |
| 远程 3306 连不上 | 服务器上 `ss -tlnp \| grep 3306` 看是否监听 `0.0.0.0`；云安全组是否放行 `MYSQL_HOST_PORT`；MySQL 8 默认 `caching_sha2_password`，旧客户端需升级驱动；应用账号应限制为 `quant@'%'` 或指定 IP 而非 `quant@'%'` |

适配器部分使用关闭证书校验的 SSL 上下文，系统尚无完整生产级认证、访问控制、分布式调度及监控。页面脱敏不能替代 API 权限。以上限制是代码现状说明，不代表本次文档更新同时修复这些问题。

## 文档维护

每次代码调整必须在同一变更中更新 README 受影响/新增内容，覆盖功能、结构、API、依赖、配置、数据库、数据流、来源、计算、缓存、定时任务、构建部署和验证方式。删除功能清理旧描述，如实记录回退与限制，不能把计划当实现。

异步页面继续使用 Skeleton 和成功/空/失败状态。数据源和计算改动验证日期、缺失值、回退；部署完整静态资源并验证业务接口。文档示例使用占位符，不能提交凭据或用户数据。协作约束见 [AGENTS.md](AGENTS.md)。

代码架构、命名、缓存、SQL 改写、组件拆分等结构性约束统一写在 [docs/CODE_STANDARDS.md](docs/CODE_STANDARDS.md)，是改动的强约束（强于本 README 的叙述）。改动 src 或 backend 任何模块前请同步阅读。

### 已移除功能

| 功能 | 移除版本 | 原因 |
| --- | --- | --- |
| 资金轮动 / sector_fund_flow_snapshots | 早期 | 实际未启用，初始化时主动 drop 表 |
| `marktet_cache.cached_value` 缓存访问器 | 2026-09 | 被 `core.cache_market_value` 工厂模式取代，避免散落的 `time.time()+N` |
| `providers.fetch_akshare_watch_quote` | 2026-09 | 后台手动刷新场景未启用，前端从未消费 |
| `providers.select_fund123_today_nav` | 2026-09 | 与 `fetch_fund123_nav_text` 重复，无唯一调用方 |
| `services._build_position_analysis` / `position.analysis` 字段 | 2026-09 | 拼模板字符串，前端从未消费 `analysis`，删除以缩小 dashboard payload |
| `App.vue` 内联的 14 个格式化方法 | 2026-09 | 抽到 `src/utils/format.js` 与 `src/mixins/numberFormat.js`，组件不再手写格式化 |
| 可拖拽悬浮按钮的内联实现 | 2026-09 | 抽到 `src/mixins/draggableFab.js`，未来新增悬浮按钮直接 mixin |

如发现上述符号仍在 README、注释或前端代码中出现，说明还没完成清理。
