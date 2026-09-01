# 炒股工作台

基于 `vue-cli + element-ui` 的前端与 `Python + SQLite` 的后端实现，覆盖三类核心能力：

1. 股票、ETF、场外基金的当日持仓收益展示与分析。
2. 盘前、盘后重大消息汇总与多空观点展示。
3. 板块涨跌幅排名与复盘分析。

## 目录结构

```text
.
├─ backend
│  ├─ app.py
│  ├─ database.py
│  ├─ providers.py
│  ├─ run.py
│  └─ services.py
├─ public
├─ src
└─ package.json
```

## 前端启动

```bash
npm install
npm run serve
```

默认启动在 `http://localhost:8080`，并通过 `vue.config.js` 代理到本地 Python API。

## 后端启动

```bash
python backend/run.py
```

默认启动在 `http://127.0.0.1:5000`。

## 已实现能力

- SQLite 持仓存储，支持新增、删除、演示数据初始化。
- 股票 / ETF 通过腾讯行情接口拉取实时价格。
- 场外基金估值优先支持配置化 `fund123` 抓取，回退到天天基金公开估值接口。
- 看板汇总总市值、当日盈亏、消息面与板块复盘。

## 前端加载规范

- 所有需要等待异步数据的首屏区域，必须使用与最终内容高度、列数相匹配的 Skeleton 骨架屏，不能仅展示空白区域或“加载中”文字。
- 已有内容的后台刷新应保留当前数据，使用按钮加载态或局部提示，避免页面闪烁和布局跳动。
- 新增页面、卡片、表格和图表时，须同步实现加载、成功、空数据、失败四种状态；其中加载状态优先复用 `src/App.vue` 的 `skeleton-shimmer` 动画和通用骨架样式。

## fund123 估值接入说明

后端会优先读取环境变量 `FUND123_ESTIMATE_URL`。你可以把它配置成自己确认可用的 `fund123.cn` 抓取地址，例如：

```bash
set FUND123_ESTIMATE_URL=https://your-fund123-adapter.example/api/fund/{code}
```

返回值既可以是 JSON，也可以是带有 `GSZ`、`GSZZL`、`NAV` 等字段的文本内容。后端已经内置了简单解析逻辑。

## 下一步建议

- 接入你自己的新闻源和板块榜单源，把 `FALLBACK_NEWS` 与 `FALLBACK_SECTORS` 替换为真实聚合接口。
- 增加定时任务，把每日盘前和盘后摘要写入 SQLite，支持历史复盘。
- 增加持仓成本分批买入、止盈止损提醒、板块联动分析。

## Android APK 与云端部署

Android 客户端通过 Capacitor 打包，后端以 Docker Compose 部署，MySQL 为唯一部署数据库。实时行情与消息依赖网络，请为 API 配置 HTTPS 域名。

1. 在服务器安装 Docker Compose，复制 `.env.deploy.example` 为 `.env.deploy` 并填写域名与强密码。
2. 将 `API_DOMAIN` 的 DNS A 记录指向服务器公网 IP，并放行 `80`、`443` 端口。
3. 执行 `docker compose --env-file .env.deploy up -d --build`。Caddy 会自动签发 HTTPS 证书，MySQL 数据会保存在 `mysql_data` 数据卷。
3. 复制 `.env.android.example` 为 `.env.android`，填写实际 HTTPS API 地址。
4. 仅首次执行 `npm run android:add` 创建 Android 原生工程。
5. 执行 `npm run build:android` 同步前端资源，然后执行 `npm run android:open`，在 Android Studio 中生成签名 APK。

`.env.android` 不应提交到版本库；每次更换 API 域名后需重新执行 Android 构建。
