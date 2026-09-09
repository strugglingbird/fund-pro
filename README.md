# 量化工作台

面向个人投资跟踪的全栈工作台，集中展示持仓估值、市场指数、板块复盘和财经快讯。项目同时支持浏览器访问与 Android APK 打包。

> 本项目仅用于信息展示与研究，不构成任何投资建议。行情和消息来自公开数据源，可能存在延迟、缺失或接口变动。

## 功能概览

- **持仓收益**：管理股票、ETF 与场外基金持仓，支持新增、修改份额与成本价、删除；展示昨日收盘价、现价、估值、当日/预估收益、持有收益和收益率。成本价按 4 位小数显示。
- **场外基金详情**：支持基金分时估值、历史净值、基金持仓股、业绩走势及自选分组。
- **隐私保护**：金额和份额默认以 `****` 脱敏，可通过悬浮小眼睛切换显示；悬浮刷新与小眼睛按钮支持移动端短按和拖动。
- **市场指数**：内地、港股、美股和韩国市场标签；指数卡片可打开 ECharts 分时图。指数抓取采用并发与内存缓存，避免移动端首屏超时。
- **板块复盘**：同花顺行业涨跌幅前 10 名，快速观察行业强弱。
- **消息快讯**：通过 AkShare 聚合财经消息，按渠道和时间倒序展示重要资讯；首页默认展示东方财富消息入口。
- **自选**：支持场内股票/ETF 与场外基金分别分组、调整组顺序和从基金持仓股快速加入自选。
- **体验**：异步区域使用 Skeleton 骨架屏，兼顾 PC 和移动端布局。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | Vue 2、Vue CLI、Element UI、Axios、ECharts |
| 后端 | Python 3.11、标准库 HTTP 服务、AkShare、PyMySQL |
| 数据库 | 本地开发默认 SQLite；Docker 部署使用 MySQL 8.4 |
| 网关 | Caddy，自动申请和续期 HTTPS 证书 |
| Android | Capacitor 8、Gradle、JDK 21、Android SDK API 36 |

## 目录结构

```text
.
├─ android/                 # Capacitor Android 原生工程
├─ backend/
│  ├─ app.py                # HTTP API 路由与 JSON 输出
│  ├─ database.py           # SQLite / MySQL 连接与初始化
│  ├─ providers.py          # AkShare、基金和公开行情数据适配
│  ├─ services.py           # 持仓、看板、自选和轮动业务逻辑
│  └─ run.py                # 本地后端入口
├─ public/                  # 静态运行时配置
├─ src/                     # Vue 页面与 API 客户端
├─ Caddyfile                # 浏览器站点与 API 反向代理
├─ docker-compose.yml       # MySQL、API、Caddy 部署编排
├─ Dockerfile               # Python API 镜像
├─ requirements.txt         # Python 依赖
└─ capacitor.config.json    # Android 配置
```

## 本地开发

### 前置条件

- Node.js 18 或更高版本
- Python 3.11
- 可选：Android APK 构建需要 JDK 21 与 Android SDK API 36

### 启动后端

本地默认使用 `backend/fund_pro.db` SQLite 数据库，无需额外数据库服务。

```bash
pip install -r requirements.txt
python backend/run.py
```

默认监听 `http://127.0.0.1:5000`。

### 启动前端

```bash
npm install
npm run serve
```

Vue 开发服务器默认地址为 `http://localhost:8080`，并通过 `vue.config.js` 转发 `/api` 请求到本地后端。

### 常用命令

```bash
# 生产前端构建
npm run build

# ESLint 检查
npm run lint

# 生成并同步 Android Web 资源
npm run build:android
```

## Docker Compose 部署

部署后由 Caddy 提供两个 HTTPS 域名：

- `WEB_DOMAIN`：前端浏览器站点，例如 `https://example.com`
- `API_DOMAIN`：独立 API 域名，例如 `https://api.example.com/api`

同样可通过前端域名的 `/api` 路径访问后端，避免浏览器跨域问题。

### 1. 配置环境变量

```bash
cp .env.deploy.example .env.deploy
```

编辑 `.env.deploy`：

```dotenv
WEB_DOMAIN=example.com
API_DOMAIN=api.example.com
MYSQL_DATABASE=quant_workbench
MYSQL_USER=quant
MYSQL_PASSWORD=use-a-long-random-password
MYSQL_ROOT_PASSWORD=use-another-long-random-password
FUND123_ESTIMATE_URL=
```

将两个域名的 DNS A 记录指向服务器公网 IP，并在云安全组和系统防火墙放行 `80`、`443`。如网络无法访问 Docker Hub，可在 `.env.deploy` 指定镜像地址，示例文件中已列出变量。

### 2. 启动服务

```bash
docker compose --env-file .env.deploy up -d --build
docker compose --env-file .env.deploy ps
```

MySQL 数据保存在 `mysql_data` Docker 数据卷，Caddy 会自动签发 HTTPS 证书。查看日志：

```bash
docker compose --env-file .env.deploy logs -f quant-api caddy
```

## Android APK

### 配置 API

复制示例文件并填写公网 HTTPS API：

```bash
cp .env.android.example .env.android
```

```dotenv
VUE_APP_API_BASE_URL=https://api.example.com/api
```

`.env.android` 仅供本机构建使用，不应提交到 Git。

### 构建调试包

```bash
npm run build:android
cd android
gradlew.bat assembleDebug
```

Windows 下若系统存在多个 Java 版本，请确保 `JAVA_HOME` 指向 JDK 21。生成文件位于：

```text
android/app/build/outputs/apk/debug/app-debug.apk
```

首次创建 Android 原生工程时才需要运行：

```bash
npm run android:add
```

## 运行时配置与数据源

- 场内标的与主要指数使用公开行情源；市场指数接口会缓存最近有效结果，并将耗时较长的韩国指数放到后台刷新，保障首屏响应。
- 板块排名、资金流、市场宽度和财经快讯主要通过 AkShare 获取。
- 场外基金使用 fund123 相关公开接口获取净值、预估涨幅、历史净值、持仓股和业绩曲线；`FUND123_ESTIMATE_URL` 可按需接入自建适配地址。
- 第三方接口不可用时，页面会保留已有数据或展示空状态，不会把模拟数据伪装成实时行情。

## API 简表

| 接口 | 用途 |
| --- | --- |
| `GET /api/health` | 健康检查 |
| `GET /api/dashboard` | 持仓看板、板块和市场宽度 |
| `GET /api/holdings` | 原始持仓列表 |
| `POST /api/holdings` | 新增持仓 |
| `PUT /api/holdings/{id}` | 修改份额和成本价 |
| `DELETE /api/holdings/{id}` | 删除持仓 |
| `GET /api/market-indices` | 多市场指数 |
| `GET /api/news` | 财经快讯 |
| `GET /api/watchlist` | 自选及分组 |

完整路由实现在 `backend/app.py`。

## 协作与安全约定

- 不提交 `.env.android`、`.env.deploy`、`backend/fund_pro.db`、`node_modules`、`dist`、APK 和 Android 构建目录。
- 新增异步页面时必须同时处理加载、成功、空状态和失败状态，加载阶段优先复用 Skeleton 骨架屏，避免布局跳动。
- 行情、基金与新闻接口会变动；修改数据源时应保留超时、缓存和降级策略，并避免阻塞 HTTP 请求线程。
- 生产环境数据库以 MySQL 数据卷为准；迁移电脑只需克隆源码，生产数据仍保留在服务器。
