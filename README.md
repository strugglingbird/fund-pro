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
- [本地开发](#本地开发)
- [构建与部署](#构建与部署)
- [Android APK](#android-apk)
- [数据迁移与备份](#数据迁移与备份)
- [验证与排障](#验证与排障)
- [文档维护](#文档维护)

## 功能介绍

| 页面 | 功能 |
| --- | --- |
| 首页 | 市值、当日盈亏、消息数量、更新时间、持仓摘要；市场温度、涨跌家数和涨跌停比；东方财富最新消息与更多入口 |
| 持仓收益 | 股票、ETF、场外基金新增/修改/删除；自动识别名称和行情；份额及成本管理；市值、累计持有收益、今日预估/实际收益及对应收益率 |
| 自选 | 股票/ETF 与场外基金分开分组；创建/删除组、添加/删除标的；后端提供分组上移/下移接口；浏览器记住分类下最后选中的组 |
| 市场指数 | 内地、港股、美股、韩国 TAB；指数分时图；行业涨幅前十和跌幅前十 |
| 消息快讯 | 财联社、东方财富、新浪、富途、同花顺渠道卡片；重要关键词筛选、各渠道内时间倒序 |
| 场外基金详情 | 估值/业绩走势 TAB；估值更新时间、归档日期选择；持仓股/历史净值 TAB；持仓股加入自选时选择分组 |

持仓表默认按预估涨幅降序，含份额、成本、昨收、现价、估值、预估涨幅/收益、当日涨幅/收益，最后为持有收益及收益率。成本价与基金净值展示四位小数。首页和持仓敏感数字默认以 `****` 隐藏，悬浮眼睛切换，悬浮刷新重新请求数据；按钮支持拖动和移动端操作。

业绩区间为近一个月、三个月、六个月、一年，同时显示基金与对比指数。持仓股展示代码、名称、涨跌幅、占净值比例；历史净值展示日期、单位净值、累计净值、日涨幅，支持日期范围查询。异步区域使用 Skeleton、空状态及失败提示，保存按钮有等待状态。脱敏仅作用于展示，接口仍返回真实数值。

## 软件架构

| 层 | 实现 |
| --- | --- |
| 前端 | Vue 2.7、Vue CLI 5、Element UI 2、ECharts 5、Axios 1；具体安装版本由 package-lock.json 锁定 |
| 后端 | Python 3.11、标准库 ThreadingHTTPServer；没有 Flask/FastAPI、ORM 或独立任务队列 |
| 数据适配 | AkShare 1.18.94、urllib，部分回退请求使用系统 curl |
| 存储 | SQLite / PyMySQL 1.1.1；Docker MySQL 8.4；cryptography 46.0.5 支持数据库认证 |
| 网关 | Caddy 2.8，HTTPS、静态文件与 API 反向代理 |
| Android | Capacitor 8.5、JDK 21、Gradle；minSdk 24、compileSdk/targetSdk 36 |

```text
浏览器 / Android WebView
  -> App.vue -> Axios (/api)
  -> Vue CLI 开发代理 / 服务器 Caddy
  -> app.py HTTP 路由
     -> services.py 持仓、自选、汇总计算
        -> database.py -> SQLite / MySQL
        -> providers.py -> 进程内缓存 -> 外部行情/基金/新闻
     -> fund_archives.py -> 数据库历史估值

后端启动 -> 收盘归档线程 -> 交易日判断 -> 持仓/自选基金去重
  -> fund123 当日分时 -> 日期及收盘点校验 -> 数据库
```

`App.vue` 用 activeMenu 切换菜单，没有 Vue Router 或 Vuex。菜单、弹窗、图表和请求状态集中管理。后端每个 HTTP 请求在线程中执行，部分指数并发抓取；归档和韩国指数刷新使用进程内后台线程。

## 代码结构

```text
fund-pro/
  src/
    main.js                 Vue/Element UI 初始化和全局 CSS
    App.vue                 菜单、表单、ECharts、隐私和定时刷新
    api/dashboard.js        Axios 地址、超时及全部 API 函数
    styles/global.css       PC/移动端布局、Skeleton、悬浮按钮
  public/
    index.html              HTML 入口模板
    runtime-config.js       浏览器运行时 API 地址
  backend/
    run.py                  后端启动入口
    app.py                  HTTP 路由、JSON、归档线程生命周期
    services.py             持仓/自选 CRUD、收益和市场汇总、降级数据
    providers.py            外部接口、解析、缓存、行情时间判断
    database.py             SQLite/MySQL 连接、建表及兼容 SQL
    fund_archives.py        收盘采集、归档校验、历史日期及读取
  scripts/
    deploy.sh               Linux 构建、复制静态资源、Compose 和校验
    verify-deployment.py    首页同源 JS/CSS 状态、MIME、HTML 误返回检查
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

### 看板与自选

1. 页面调用 dashboard，服务从 holdings 读份额、成本和类型，逐个取得行情。
2. providers 根据缓存与回退策略返回数据，services 计算单项及组合收益。
3. 同一看板请求还取得行业排名、市场宽度后返回 JSON。因此全市场抓取也会影响看板响应速度。
4. 指数、快讯由页面通过各自 API 并行请求；自选先查询 groups/items，再按类型附加报价。
5. Vue 更新页面；点击名称打开详情并渲染 ECharts。新增持仓先写数据库，再请求看板，保存成功不等于随后行情刷新成功。

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

后端启动后每轮判断北京时间是否达到 15:05，并用 AkShare 交易日历确认。SQL UNION 合并持仓和自选中 fund 类型代码，跳过当天已有记录，直接抓取 fund123 分时。

所有点必须属于当天，最晚时间不早于 15:00，才保存 JSON。每轮结束等待 300 秒，失败下轮重试；异常写日志，空或不完整曲线跳过。午夜后只处理新日期，没有跨日补采。读取日期列表和选定日期的历史曲线只访问数据库。

归档是上游返回的估值点，不保证逐分钟齐全，不是正式净值；不要求当日正式净值已经发布。数据长期保留，成功后不覆盖，删除持仓/自选也不删归档。服务需在当天收盘后运行；错过整晚、日历不可用或缺少收盘点会形成空档。

## 外部数据源

适配实现见 [providers.py](backend/providers.py)，日历见 [fund_archives.py](backend/fund_archives.py)。以下描述当前调用关系，不保证上游更新频率。

| 使用位置 | 来源 | 回退/说明 |
| --- | --- | --- |
| 持仓股票/ETF、场内识别 | 腾讯 qt.gtimg.cn/q=... | 持仓并非统一使用 AkShare |
| 自选股票/ETF | AkShare stock_zh_a_spot_em / fund_etf_spot_em | 按代码匹配，失败回退腾讯 |
| 内地、港股、美股指数 | 腾讯报价，并发请求 | 内地四指数、恒生、恒生科技 hkHSTECH、道琼斯、纳斯达克、标普500 |
| 韩国 KOSPI | AkShare index_global_spot_em | Yahoo query1.finance.yahoo.com/v8/finance/chart/%5EKS11；普通请求后台更新 |
| 场内及内地/港股分时 | 腾讯 web.ifzq.gtimg.cn/appstock/app/minute/query | 不可用显示空状态 |
| 美股、韩国分时 | Yahoo chart API | range=1d、interval=5m，并非逐笔行情 |
| 行业前十排名 | AkShare stock_board_industry_summary_ths | 东方财富 push2 /api/qt/clist/get，最终静态榜单 |
| 全市涨跌家数 | AkShare stock_zh_a_spot_em | 同花顺行业上涨/下跌家数汇总 |
| 涨跌停 | 实时快照阈值计数 | 回退 stock_zt_pool_em / stock_zt_pool_dtgc_em |
| 归档交易日 | AkShare tool_trade_date_hist_sina | 日历不覆盖或失败时不归档，重试 |

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

基金报价回退顺序：可选 FUND123_ESTIMATE_URL → fund123 盘中估值 → fundgz.1234567.com.cn/js/{code}.js → 天天基金/东方财富 FundValuationLast → fund.eastmoney.com/pingzhongdata/{code}.js 最新净值 → fund123 页面文本解析。自定义地址支持 `{code}` 占位符，JSON 格式需符合 fetch_fund123_valuation。

### 消息来源

| 渠道 | AkShare API | 最多条数 |
| --- | --- | --- |
| 财联社 | stock_info_global_cls(symbol='重点') | 6 |
| 东方财富 | stock_info_global_em | 4 |
| 新浪 | stock_info_global_sina | 4 |
| 富途 | stock_info_global_futu | 4 |
| 同花顺 | stock_info_global_ths | 4 |

按政策、央行、财报等关键词筛选，无命中时使用普通消息。按来源时间字符串降序，单渠道失败跳过，全部失败为空消息结构。当前没有央视/财经早餐等其他渠道，也没有 LLM 多空分析服务。

### 降级边界

- services.py 保留 FALLBACK_SECTORS 静态榜单及“本地回退榜单”标签，不能当作实时排名。
- 持仓所有来源失败时以成本价和零涨幅返回“本地回退数据”；东方财富最新净值回退尚未做与 fund123 相同的当天日期校验。
- 实时涨跌停采用 ±9.9% 近似阈值，没有按证券区分 5%、10%、20%、30% 制度；回退日期主要按工作日推算。
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
| 历史估值 | 数据库长期保存 |

开盘函数按北京时间 09:30 跳过周末，未使用节假日日历，海外报价也共用该规则。仅收盘归档采用实际交易日历。缓存位于进程内，重启清空，没有 Redis 或跨进程共享缓存。

页面每 60000 毫秒刷新看板、指数和消息，自选菜单下额外刷新自选。页面隐藏或手动全量刷新时跳过，已有 loading 的请求不重叠。详情图、持仓股、历史净值不在自动刷新范围。浏览器后台定时器受系统调度限制。

悬浮手动刷新传 force=true，由 ContextVar 控制适用缓存绕过；自动刷新复用有效缓存。force 不会生成上游新报价、覆盖历史归档或刷新所有已打开的详情。看板超时 120 秒；普通指数 15 秒、消息/自选 45 秒，这几类强制请求为 120 秒。看板/指数失败保留已有页面数据。

## 数据库结构

定义见 [database.py](backend/database.py)。没有 ORM/migration 工具，启动创建缺失表并执行少量兼容迁移；目前初始化仍删除旧 sector_fund_flow_snapshots 表，这是移除资金轮动后的清理行为。

| 表 | 字段 | 约束/用途 |
| --- | --- | --- |
| holdings | id, name, code, asset_type, quantity, cost_price, created_at | id 自增；代码字符串保留前导零；同代码可多条持仓 |
| watchlist_groups | id, name, category, sort_order, created_at | name+category 唯一；category=exchange/fund |
| watchlist_items | id, group_id, name, code, asset_type, created_at | group_id+code+asset_type 唯一；外键级联删除 |
| app_settings | key, value | key 主键，当前存默认分组初始化标记 |
| fund_estimate_archives | code, trade_date, payload, saved_at | code+trade_date 联合主键，独立于持仓/自选生命周期 |

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
| GET /health | 无 | status=ok，仅进程健康 |
| GET /dashboard | force 可选 | portfolio、sectors、market_breadth、generated_at |
| GET /holdings | 无 | items 原始持仓 |
| POST /holdings | name, code, asset_type, quantity, cost_price | 新建，201 |
| PUT /holdings/{id} | quantity, cost_price | 修改持仓 |
| DELETE /holdings/{id} | 无 | deleted |
| POST /seed-demo | 无 | 仅空持仓时插入三条演示持仓 |
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
| GET /instruments/estimate-archive | code | 日期倒序 dates |
| GET /instruments/estimate-archive | code, date=YYYY-MM-DD | 归档曲线，不存在 404 |

业务类型为 stock/etf/fund，分时接口额外支持 index。当前没有登录、权限隔离、多用户表；响应允许 Access-Control-Allow-Origin: *。部分 GET 异常尚无统一 JSON 错误封装，公网访问控制需由部署环境补充。

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
| FUND123_ESTIMATE_URL | 默认空 | 自建估值适配地址 |
| WEB_DOMAIN / API_DOMAIN | .env.deploy 必填 | 站点/API 域名 |
| SERVER_IP | Compose 有默认，部署应显式改写 | Caddy HTTP IP 入口 |
| MYSQL_IMAGE / PYTHON_IMAGE / CADDY_IMAGE | mysql:8.4 / python:3.11-slim / caddy:2.8-alpine | 镜像覆盖 |
| DEPLOY_URL | deploy.sh 必填 | 部署后资源校验地址 |
| VUE_APP_API_BASE_URL | 构建时可选 | API 基址，包含 /api |
| window.__QUANT_API_BASE_URL__ | runtime-config.js 默认空 | 浏览器运行时 API 基址 |
| VUE_APP_TARGET | Android 脚本设 capacitor | publicPath 切换 |

API 基址优先级：构建变量 → 运行时变量 → 同源 /api。改构建变量要重建；运行时变量在输出目录 runtime-config.js 中设置。普通 build 不加载 .env.android，Android 用 --mode android。

Python 不自动加载 dotenv，本地需在 shell 设置变量；.env.deploy 由 Compose --env-file 读取。market_now 显式用 UTC+8，关键净值和归档不依赖容器系统时区，但并非所有来源的历史显示时间都已统一转换。

## 本地开发

要求 Node.js 22+（当前 Capacitor CLI 要求 >=22）、npm、Python 3.11。Linux 部署另需 Bash、Docker Engine/Compose；部分回退可用系统 curl。

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
npm run lint -- --no-fix
python -m compileall -q backend
```

build 产出 dist。单独执行 npm run lint 可能自动修复；现有构建含模板格式和大包警告，不是零警告。当前没有统一后端自动化测试套件，计算、日期、归档等变更应做针对性验证。

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
FUND123_ESTIMATE_URL=
```

域名 A 记录指向服务器，开放 80/443。默认不向宿主机映射 3306/5000。证书签发依赖 DNS、端口和证书服务可达；HTTP IP 入口不使用自动 TLS。

```bash
DEPLOY_URL=https://example.com bash scripts/deploy.sh
```

实际流程：npm ci → build → 停 Caddy → 清理 frontend 并复制完整 dist → Compose up -d --build → 最多 12 次资源校验。存在短暂停机，没有蓝绿、自动回滚或原子发布保证。构建失败发生在停 Caddy 前。不要只传 index.html 或单个 app.*.js。

| 服务 | 内容与存储 |
| --- | --- |
| db | MySQL/mysql_data 卷；健康检查通过后 API 启动 |
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
| 韩国暂缺数据 | AkShare/Yahoo 可达性、后台刷新结果 |
| 归档日期为空 | 场外持仓/自选是否存在；日历、15:05 后服务运行、15:00 点是否返回 |
| 个别归档缺失 | 异常日志；日期混杂/缺收盘点会跳过，不伪造也不跨日补采 |
| IP 正常域名异常 | DNS、80/443、安全组、TLS 和网关分别检查 |

适配器部分使用关闭证书校验的 SSL 上下文，系统尚无完整生产级认证、访问控制、分布式调度及监控。页面脱敏不能替代 API 权限。以上限制是代码现状说明，不代表本次文档更新同时修复这些问题。

## 文档维护

每次代码调整必须在同一变更中更新 README 受影响/新增内容，覆盖功能、结构、API、依赖、配置、数据库、数据流、来源、计算、缓存、定时任务、构建部署和验证方式。删除功能清理旧描述，如实记录回退与限制，不能把计划当实现。

异步页面继续使用 Skeleton 和成功/空/失败状态。数据源和计算改动验证日期、缺失值、回退；部署完整静态资源并验证业务接口。文档示例使用占位符，不能提交凭据或用户数据。协作约束见 [AGENTS.md](AGENTS.md)。
