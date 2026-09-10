<template>
  <div class="app-shell">
    <header class="workspace-nav">
      <div class="brand-mark"><span>量化工作台</span><small>Quant Workbench</small></div>
      <el-menu :default-active="activeMenu" mode="horizontal" class="workspace-menu" @select="onMenuSelect">
        <el-menu-item index="home">首页</el-menu-item>
        <el-menu-item index="holdings">持仓收益</el-menu-item>
        <el-menu-item index="watchlist">自选</el-menu-item>
        <el-menu-item index="market">市场指数</el-menu-item>
        <el-menu-item index="news">消息快讯</el-menu-item>
      </el-menu>
    </header>

    <button type="button" class="refresh-fab" :class="{ 'is-loading': loading || refreshingAll }" :disabled="refreshingAll" :style="refreshFabStyle" aria-label="刷新数据" title="重新抓取全部数据" @mousedown="startRefreshDrag" @touchstart="startRefreshDrag" @touchend.stop.prevent="finishRefreshTouch" @touchcancel="stopRefreshDrag" @click="handleRefreshFabClick"><i class="el-icon-refresh" /></button>
    <button type="button" class="privacy-fab" :class="{ 'is-visible': holdingsNumbersVisible }" :style="privacyFabStyle" :aria-label="holdingsNumbersVisible ? '隐藏数字' : '展示数字'" :title="holdingsNumbersVisible ? '隐藏数字' : '展示数字'" @mousedown="startPrivacyDrag" @touchstart="startPrivacyDrag" @touchend.stop.prevent="finishPrivacyTouch" @touchcancel="stopPrivacyDrag" @click="toggleHoldingNumbers"><i class="el-icon-view" /></button>

    <section v-if="activeMenu === 'home'" :class="{ 'page-skeleton-loading': isDashboardInitialLoading }">
      <section class="hero-card">
        <div>
          <p class="eyebrow">Quant Workbench</p>
          <h1>量化工作台</h1>
          <p class="hero-copy">持仓估值、市场脉搏与财经要闻，集中在一个清爽的投资工作界面。</p>
        </div>
        <div class="hero-actions"><el-button @click="activeMenu = 'holdings'">查看持仓收益</el-button></div>
      </section>
      <el-row :gutter="18" class="stats-row home-stats-row">
        <el-col :xs="24" :sm="12" :lg="6" v-for="card in statCards" :key="card.label">
          <div class="stat-card" :class="{ 'stat-card--timestamp': card.isTimestamp }"><div class="stat-label">{{ card.label }}</div><div class="stat-value" :class="card.className">{{ card.value }}</div><div class="stat-foot">{{ card.foot }}</div></div>
        </el-col>
      </el-row>
      <el-row :gutter="18" class="home-market-row">
        <el-col :xs="24"><el-card shadow="never" class="panel-card home-temperature-card"><div slot="header" class="panel-header"><span>市场温度</span><span class="panel-tip">{{ homeMarketTemperature.breadth.data_date ? `${homeMarketTemperature.breadth.data_date} ${homeMarketTemperature.breadth.is_realtime ? '实时' : '收盘'}` : '内地核心指数' }}</span></div><template v-if="isMarketInitialLoading"><div class="temperature-skeleton"><i /><i /><i /></div></template><template v-else><div class="temperature-main"><div><span class="temperature-label">市场情绪</span><strong :class="homeMarketTemperature.className">{{ homeMarketTemperature.label }}</strong></div><div :class="homeMarketTemperature.className" class="temperature-rate">{{ formatPercent(homeMarketTemperature.averageChange) }}</div></div><div class="temperature-metrics"><span>主要指数 {{ homeMarketTemperature.rising }} 涨 {{ homeMarketTemperature.falling }} 跌</span><span v-if="homeMarketTemperature.breadth.available">全市 {{ homeMarketTemperature.breadth.rising }} 涨 {{ homeMarketTemperature.breadth.falling }} 跌</span><span v-else>全市涨跌 暂无有效数据</span><span v-if="homeMarketTemperature.breadth.available">涨停 / 跌停 {{ homeMarketTemperature.breadth.limit_up }} : {{ homeMarketTemperature.breadth.limit_down }}</span><span v-else>涨停 / 跌停 暂无有效数据</span><span>行业领涨 {{ homeMarketTemperature.leader.name || '--' }} {{ formatPercent(homeMarketTemperature.leader.change_rate) }}</span><span>行业领跌 {{ homeMarketTemperature.laggard.name || '--' }} {{ formatPercent(homeMarketTemperature.laggard.change_rate) }}</span></div></template></el-card></el-col>
      </el-row>
      <el-row :gutter="18" class="home-content-row">
        <el-col :xs="24" :lg="14">
          <el-card shadow="never" class="panel-card home-sector-card">
            <div slot="header" class="panel-header"><span>板块排行</span><el-button type="text" @click="activeMenu = 'market'">完整复盘</el-button></div>
            <div v-if="isDashboardInitialLoading" class="home-sector-skeleton"><i v-for="row in 5" :key="row" /></div>
            <div v-else-if="dashboard.sectors.gainers.length || dashboard.sectors.losers.length" class="home-sector-columns">
              <div class="home-sector-list"><h3>涨幅榜</h3><div v-for="(item, index) in dashboard.sectors.gainers.slice(0, 5)" :key="item.name" class="home-sector-item"><span class="home-sector-rank">{{ index + 1 }}</span><span class="home-sector-name">{{ item.name }}</span><strong class="positive">{{ formatPercent(item.change_rate) }}</strong></div></div>
              <div class="home-sector-list"><h3>跌幅榜</h3><div v-for="(item, index) in dashboard.sectors.losers.slice(0, 5)" :key="item.name" class="home-sector-item"><span class="home-sector-rank">{{ index + 1 }}</span><span class="home-sector-name">{{ item.name }}</span><strong class="negative">{{ formatPercent(item.change_rate) }}</strong></div></div>
            </div>
            <div v-else class="empty-state">暂无板块排行，请稍后刷新。</div>
          </el-card>
        </el-col>
        <el-col :xs="24" :lg="10">
          <el-card shadow="never" class="panel-card news-source-card home-news-card">
            <div slot="header" class="panel-header"><span>最新消息 · 东方财富</span><el-button type="text" @click="activeMenu = 'news'">更多</el-button></div>
            <template v-if="newsLoading && !homeEastmoneyNews.length"><div v-for="row in 3" :key="row" class="news-skeleton-item"><i class="news-skeleton-title" /><i class="news-skeleton-time" /><i class="news-skeleton-body" /><i class="news-skeleton-body short" /></div></template><template v-else-if="homeEastmoneyNews.length"><div v-for="item in homeEastmoneyNews.slice(0, 3)" :key="item.id" class="news-item"><div class="news-head"><span class="news-title">{{ item.title }}</span></div><div class="news-meta">{{ item.published_at }}</div><div class="news-body">{{ item.summary }}</div><a v-if="item.url" class="news-link" :href="item.url" target="_blank" rel="noopener noreferrer">查看原文</a></div></template><div v-else class="empty-state home-news-empty">暂无东方财富实时快讯，请稍后刷新。</div>
          </el-card>
        </el-col>
      </el-row>
    </section>

    <section v-else-if="activeMenu === 'holdings'" :class="{ 'page-skeleton-loading': isDashboardInitialLoading }">
      <div class="page-heading"><div><h2>持仓收益</h2><p>股票、ETF 与场外基金的实时估值及收益分析。</p></div><div class="panel-actions"><el-button @click="seedDemoData">导入演示持仓</el-button></div></div>
      <el-row :gutter="18" class="stats-row holdings-summary">
        <el-col :xs="24" :sm="12" :lg="6"><div class="stat-card"><div class="stat-label">持仓总市值</div><div class="stat-value">{{ formatHoldingMoney(dashboard.portfolio.total_market_value) }}</div><div class="stat-foot">按现价或最新估值计入</div></div></el-col>
        <el-col :xs="24" :sm="12" :lg="6"><div class="stat-card"><div class="stat-label">累计持仓收益</div><div class="stat-value" :class="profitClass(dashboard.portfolio.total_holding_pnl)">{{ formatHoldingMoney(dashboard.portfolio.total_holding_pnl) }}</div><div class="stat-foot" :class="profitClass(dashboard.portfolio.total_holding_pnl_rate)">收益率 {{ formatHoldingPercent(dashboard.portfolio.total_holding_pnl_rate) }}</div></div></el-col>
        <el-col :xs="24" :sm="12" :lg="6"><div class="stat-card stat-card--clickable" role="button" tabindex="0" title="查看当日收益走势与指数对比" @click="openPnlTrendDialog"><div class="stat-label">累计今日预估收益</div><div class="stat-value" :class="profitClass(dashboard.portfolio.total_estimated_pnl)">{{ formatHoldingMoney(dashboard.portfolio.total_estimated_pnl) }}</div><div class="stat-foot" :class="profitClass(dashboard.portfolio.total_estimated_pnl_rate)">涨跌幅 {{ formatHoldingPercent(dashboard.portfolio.total_estimated_pnl_rate) }}<span class="stat-card-hint">走势对比</span></div></div></el-col>
        <el-col :xs="24" :sm="12" :lg="6"><div class="stat-card"><div class="stat-label">累计今日实际收益</div><div class="stat-value" :class="profitClass(dashboard.portfolio.total_today_pnl)">{{ formatHoldingMoney(dashboard.portfolio.total_today_pnl) }}</div><div class="stat-foot" :class="profitClass(dashboard.portfolio.total_today_pnl_rate)">涨跌幅 {{ formatHoldingPercent(dashboard.portfolio.total_today_pnl_rate) }}</div></div></el-col>
      </el-row>
      <el-card shadow="never" class="panel-card">
        <div slot="header" class="panel-header"><span>当日持仓收益</span><div class="panel-actions"><span class="panel-tip">股票 / ETF / 场外基金</span><el-button type="primary" size="small" @click="openCreateHolding">新增持仓</el-button></div></div>
        <el-table :data="sortedHoldingPositions" stripe :class="{ 'table-skeleton table-skeleton-wide': isDashboardInitialLoading }">
          <el-table-column prop="name" label="名称" min-width="170"><template slot-scope="{ row }"><el-button type="text" class="position-link" @click="openIntradayChart(row)">{{ row.name }}</el-button></template></el-table-column><el-table-column prop="code" label="代码" width="110"><template slot-scope="{ row }">{{ formatHoldingCode(row.code) }}</template></el-table-column><el-table-column prop="asset_type" label="类型" width="110"><template slot-scope="{ row }"><el-tag size="mini" :type="assetTypeTag(row.asset_type)">{{ assetTypeLabel(row.asset_type) }}</el-tag></template></el-table-column><el-table-column prop="quantity" label="持仓份额" width="110"><template slot-scope="{ row }">{{ formatHoldingQuantity(row.quantity) }}</template></el-table-column><el-table-column prop="cost_price" label="成本价" width="110"><template slot-scope="{ row }">{{ formatHoldingCostPrice(row.cost_price) }}</template></el-table-column><el-table-column prop="previous_close" label="昨日收盘价" width="110"><template slot-scope="{ row }">{{ formatHoldingNetValue(row.previous_close, row.asset_type) }}</template></el-table-column><el-table-column prop="current_price" label="现价" width="110"><template slot-scope="{ row }">{{ formatHoldingNetValue(row.current_price, row.asset_type) }}</template></el-table-column><el-table-column prop="estimated_price" label="估值" width="110"><template slot-scope="{ row }">{{ formatHoldingNetValue(row.estimated_price, row.asset_type) }}</template></el-table-column><el-table-column prop="estimated_change_rate" label="预估涨幅" width="105"><template slot-scope="{ row }"><span :class="profitClass(row.estimated_change_rate)">{{ formatHoldingPercent(row.estimated_change_rate, true) }}</span></template></el-table-column><el-table-column prop="estimated_pnl" label="预估收益" width="120"><template slot-scope="{ row }"><span :class="profitClass(row.estimated_pnl)">{{ formatHoldingMoney(row.estimated_pnl, true) }}</span></template></el-table-column><el-table-column prop="daily_change_rate" label="当日涨幅" width="105"><template slot-scope="{ row }"><span :class="profitClass(row.daily_change_rate)">{{ formatHoldingPercent(row.daily_change_rate, true) }}</span></template></el-table-column><el-table-column prop="today_pnl" label="当日收益" width="120"><template slot-scope="{ row }"><span :class="profitClass(row.today_pnl)">{{ formatHoldingMoney(row.today_pnl, true) }}</span></template></el-table-column><el-table-column prop="holding_pnl" label="持有收益" width="120"><template slot-scope="{ row }"><span :class="profitClass(row.holding_pnl)">{{ formatHoldingMoney(row.holding_pnl) }}</span></template></el-table-column><el-table-column prop="holding_pnl_rate" label="持有收益率" width="110"><template slot-scope="{ row }"><span :class="profitClass(row.holding_pnl_rate)">{{ formatHoldingPercent(row.holding_pnl_rate) }}</span></template></el-table-column><el-table-column label="操作" width="130" fixed="right"><template slot-scope="{ row }"><el-button type="text" @click="openEditHolding(row)">修改</el-button><el-button type="text" class="danger-text" @click="removeHolding(row.id)">删除</el-button></template></el-table-column>
        </el-table>
      </el-card>
    </section>

    <section v-else-if="activeMenu === 'watchlist'">
      <div class="page-heading"><div><h2>自选</h2><p>分组跟踪场内股票、ETF 与场外基金行情。</p></div><div class="panel-actions"><span class="panel-tip">{{ watchlist.generated_at || '--' }} 更新</span><el-button size="small" :loading="watchlistLoading" @click="loadWatchlist(true)">刷新行情</el-button></div></div>
      <el-card shadow="never" class="panel-card"><el-tabs v-model="watchlistCategory" @tab-click="ensureWatchGroup"><el-tab-pane label="场内基金与股票" name="exchange" /><el-tab-pane label="场外基金" name="fund" /></el-tabs><div class="watch-toolbar"><div class="watch-groups"><el-button v-for="group in watchGroups" :key="group.id" size="small" :type="selectedWatchGroupId === group.id ? 'primary' : 'default'" @click="selectedWatchGroupId = group.id">{{ group.name }}</el-button><el-button size="small" icon="el-icon-plus" @click="createWatchGroup">新建分组</el-button></div><div class="panel-actions"><el-button size="small" :disabled="!selectedWatchGroupId" @click="openWatchItemDialog">添加自选</el-button><el-button v-if="selectedWatchGroup" type="text" class="danger-text" @click="deleteWatchGroup">删除分组</el-button></div></div><div v-if="watchlistLoading && !watchlistLoaded" class="detail-skeleton"><div class="skeleton-table"><div class="skeleton-table-row skeleton-table-head"><i /><i /><i /><i /></div><div v-for="row in 6" :key="row" class="skeleton-table-row"><i /><i /><i /><i /></div></div></div><div v-else-if="!selectedWatchGroupId || !watchItems.length" class="empty-state">当前分组暂无自选标的，点击“添加自选”开始跟踪。</div><el-table v-else :data="watchItems" stripe><el-table-column prop="name" label="名称" min-width="170"><template slot-scope="{ row }"><el-button type="text" class="position-link" @click="openIntradayChart(row)">{{ row.name }}</el-button></template></el-table-column><el-table-column prop="code" label="代码" width="110" /><el-table-column prop="asset_type" label="类型" width="110"><template slot-scope="{ row }"><el-tag size="mini" :type="assetTypeTag(row.asset_type)">{{ assetTypeLabel(row.asset_type) }}</el-tag></template></el-table-column><el-table-column prop="previous_close" label="昨日收盘价" width="120"><template slot-scope="{ row }">{{ formatNetValue(row.previous_close, row.asset_type) }}</template></el-table-column><el-table-column prop="current_price" label="现价" width="110"><template slot-scope="{ row }">{{ formatNetValue(row.current_price, row.asset_type) }}</template></el-table-column><el-table-column v-if="watchlistCategory === 'fund'" prop="estimated_price" label="估值" width="110"><template slot-scope="{ row }">{{ formatNetValue(row.estimated_price, row.asset_type) }}</template></el-table-column><el-table-column prop="daily_change_rate" label="当日涨幅" width="110"><template slot-scope="{ row }"><span :class="profitClass(row.daily_change_rate)">{{ formatNullablePercent(row.daily_change_rate) }}</span></template></el-table-column><el-table-column v-if="watchlistCategory === 'fund'" prop="estimated_change_rate" label="预估涨幅" width="110"><template slot-scope="{ row }"><span :class="profitClass(row.estimated_change_rate)">{{ formatNullablePercent(row.estimated_change_rate) }}</span></template></el-table-column><el-table-column prop="source_label" label="数据源" min-width="130" /><el-table-column label="操作" width="75" fixed="right"><template slot-scope="{ row }"><el-button type="text" class="danger-text" @click="deleteWatchItem(row.id)">删除</el-button></template></el-table-column></el-table></el-card>
      <div v-if="selectedWatchGroup" class="watch-order-actions"><span>当前分组：{{ selectedWatchGroup.name }}</span><el-button size="mini" :disabled="watchGroups[0] && selectedWatchGroup.id === watchGroups[0].id" @click="moveCurrentWatchGroup('up')">上移</el-button><el-button size="mini" :disabled="watchGroups[watchGroups.length - 1] && selectedWatchGroup.id === watchGroups[watchGroups.length - 1].id" @click="moveCurrentWatchGroup('down')">下移</el-button></div>
    </section>

    <section v-else-if="activeMenu === 'market'">
      <div class="page-heading"><div><h2>市场指数</h2><p>主要市场指数与板块强弱复盘。</p></div><span class="panel-tip">{{ indicesUpdatedAt || '--' }} 更新</span></div>
      <el-tabs v-model="activeMarketTab" class="market-index-tabs" @tab-click="loadMarketIndices"><el-tab-pane label="内地" name="cn" /><el-tab-pane label="港股" name="hk" /><el-tab-pane label="美股" name="us" /><el-tab-pane label="韩国" name="kr" /></el-tabs><el-row v-if="isMarketInitialLoading" :gutter="18" class="stats-row market-index-row"><el-col v-for="card in 4" :key="card" :xs="6" :sm="12" :lg="6"><div class="index-card index-skeleton"><i /><i /><i /></div></el-col></el-row><el-row v-else :gutter="18" class="stats-row market-index-row"><el-col :xs="6" :sm="12" :lg="6" v-for="item in visibleMarketIndices" :key="item.code"><div class="index-card index-card--clickable" role="button" tabindex="0" @click="openIndexIntradayChart(item)" @keyup.enter="openIndexIntradayChart(item)"><div class="stat-label index-label"><span class="index-name">{{ item.name }}</span><span class="index-code"> · {{ item.code }}</span></div><div class="index-value">{{ Number(item.current_price).toFixed(2) }}</div><div :class="profitClass(item.change_rate)">{{ formatPercent(item.change_rate) }}</div></div></el-col></el-row>
      <div v-if="!marketIndicesLoading && !marketIndices.length" class="empty-state">暂无指数行情，请刷新后重试。</div>
      <el-card shadow="never" class="panel-card" :class="{ 'sector-skeleton': isDashboardInitialLoading }"><div slot="header" class="panel-header"><span>板块复盘分析</span><span class="panel-tip">{{ dashboard.sectors.source_label }} · 前 10 名</span></div><div class="sector-columns"><div class="sector-block"><h3>涨幅居前</h3><div v-for="(item, index) in dashboard.sectors.gainers" :key="item.name" class="sector-item"><div class="sector-rank">{{ index + 1 }}</div><div class="sector-content"><div class="sector-name">{{ item.name }}</div><div class="sector-reason">{{ item.reason }}</div></div><div class="positive">{{ formatPercent(item.change_rate) }}</div></div></div><div class="sector-block"><h3>跌幅居前</h3><div v-for="(item, index) in dashboard.sectors.losers" :key="item.name" class="sector-item"><div class="sector-rank">{{ index + 1 }}</div><div class="sector-content"><div class="sector-name">{{ item.name }}</div><div class="sector-reason">{{ item.reason }}</div></div><div class="negative">{{ formatPercent(item.change_rate) }}</div></div></div></div></el-card>
    </section>

    <section v-else>
      <div class="page-heading"><div><h2>消息快讯</h2><p>聚合多平台财经快讯，优先展示高影响事件。</p></div><div class="panel-actions"><span class="panel-tip">{{ newsFeed.total_count || 0 }} 条重要消息 · {{ newsFeed.generated_at || '--' }} 更新</span><el-button size="small" :loading="newsLoading" @click="loadNews(true)">刷新快讯</el-button></div></div>
      <el-row v-if="newsLoading && !newsFeed.groups.length" :gutter="18" class="news-grid" aria-label="正在加载财经快讯"><el-col v-for="card in 4" :key="card" :xs="24" :lg="12"><el-card shadow="never" class="panel-card news-source-card news-skeleton-card"><div slot="header" class="panel-header"><i class="news-skeleton-source" /><i class="news-skeleton-count" /></div><div v-for="row in 4" :key="row" class="news-skeleton-item"><i class="news-skeleton-title" /><i class="news-skeleton-time" /><i class="news-skeleton-body" /><i class="news-skeleton-body short" /></div></el-card></el-col></el-row>
      <el-row v-else :gutter="18" class="news-grid"><el-col v-for="group in newsFeed.groups" :key="group.source" :xs="24" :lg="12"><el-card shadow="never" class="panel-card news-source-card"><div slot="header" class="panel-header"><span>{{ group.source }}</span><span class="panel-tip">{{ group.items.length }} 条重点快讯</span></div><div v-for="item in group.items" :key="item.id" class="news-item"><div class="news-head"><span class="news-title">{{ item.title }}</span></div><div class="news-meta">{{ item.published_at }}</div><div class="news-body">{{ item.summary }}</div><a v-if="item.url" class="news-link" :href="item.url" target="_blank" rel="noopener noreferrer">查看原文</a></div></el-card></el-col></el-row>
    </section>

    <el-dialog :title="`${intradayChart.name || '标的'}${intradayChart.asset_type === 'fund' ? ' 基金详情' : ' 当日分时'}`" :visible.sync="intradayDialogVisible" width="760px" @opened="renderIntradayChart">
      <el-tabs v-if="intradayChart.asset_type === 'fund'" v-model="fundChartTab" class="fund-chart-tabs" @tab-click="handleFundChartTab"><el-tab-pane label="估值走势" name="intraday" /><el-tab-pane label="业绩走势" name="performance" /></el-tabs>
      <div v-if="['fund', 'stock', 'etf'].includes(intradayChart.asset_type) && fundChartTab === 'intraday'" class="chart-meta">
        <span>{{ intradayChart.asset_type === 'fund' ? '估值走势日期' : '价格走势日期' }}</span>
        <el-select v-model="estimateArchiveDate" size="small" :disabled="intradayLoading" @change="loadEstimateArchive">
          <el-option :label="intradayChart.asset_type === 'fund' ? '当日实时估值' : '当日分时价格'" value="" />
          <el-option v-for="day in estimateArchiveDates" :key="day" :label="day + ' 已归档'" :value="day" />
        </el-select>
        <span v-if="!estimateArchiveDates.length">收盘归档后可查看历史走势</span>
      </div>
      <div v-if="fundChartTab === 'intraday' && intradayLoading" class="chart-skeleton" aria-label="正在加载估值走势"><i /><i /><i /><i /><i /></div>
      <template v-else-if="fundChartTab === 'intraday'">
        <template v-if="intradayChart.points.length">
          <div class="chart-meta"><span>昨收：{{ formatIntradayPrice(intradayChart.previous_close, intradayChart.asset_type) }}</span><span>最新：{{ formatIntradayPrice(intradayChart.points[intradayChart.points.length - 1].price, intradayChart.asset_type) }}</span><span>{{ intradayChart.source_label }}</span></div>
          <div v-if="intradayChart.asset_type === 'fund'" class="chart-meta">估值更新时间：{{ intradayChart.updated_at || '--' }}</div>
          <div ref="intradayChart" class="intraday-chart" role="img" aria-label="当日分时走势"></div>
        </template>
        <div v-else class="chart-loading">暂无当日分时数据</div>
      </template>
      <div v-else-if="intradayChart.asset_type === 'fund'" class="fund-performance"><div class="performance-ranges"><el-button v-for="item in [{ key: 'ONE', label: '近1个月' }, { key: 'THREE', label: '近3个月' }, { key: 'SIX', label: '近6个月' }, { key: 'ONE_YEAR', label: '近1年' }]" :key="item.key" type="text" :class="{ active: fundPerformanceInterval === item.key }" @click="loadFundPerformance(item.key)">{{ item.label }}</el-button></div><div v-if="fundPerformanceLoading" class="chart-skeleton"><i /><i /><i /><i /><i /></div><div v-else-if="!fundPerformance.fund.length" class="chart-loading">暂无该区间业绩走势数据</div><div v-else ref="fundPerformanceChart" class="fund-performance-chart" /></div>
      <el-tabs v-if="intradayChart.asset_type === 'fund'" v-model="fundDetailTab" class="fund-detail-tabs"><el-tab-pane label="持仓股" name="holdings"><div v-if="fundHoldingsLoading" class="detail-skeleton" aria-label="正在加载基金持仓股"><div class="skeleton-meta"><i /><i /></div><div class="skeleton-table"><div class="skeleton-table-row skeleton-table-head"><i /><i /><i /><i /></div><div v-for="row in 6" :key="row" class="skeleton-table-row"><i /><i /><i /><i /></div></div></div><div v-else-if="!fundHoldings.items.length" class="holding-loading">暂无基金持仓数据</div><template v-else><div class="holding-report"><span>{{ fundHoldings.report_date || '最新披露' }}</span><span>股票：{{ formatNullablePercent(fundHoldings.stock_position) }}</span></div><div class="holding-meta">{{ fundHoldings.source_label }} · {{ fundHoldings.updated_at }} 更新</div><el-table :data="fundHoldings.items" size="small" max-height="280"><el-table-column prop="code" label="代码" width="105" /><el-table-column prop="name" label="重仓股票" min-width="150" /><el-table-column prop="change_rate" label="涨跌幅" width="115"><template slot-scope="{ row }"><span :class="profitClass(row.change_rate)">{{ formatSignedNullablePercent(row.change_rate) }}</span></template></el-table-column><el-table-column prop="weight" label="占净值比例" width="125"><template slot-scope="{ row }">{{ formatNullablePercent(row.weight) }}</template></el-table-column><el-table-column label="自选" width="80"><template slot-scope="{ row }"><el-button type="text" @click="openFundHoldingWatch(row)">加入</el-button></template></el-table-column></el-table></template></el-tab-pane><el-tab-pane label="历史净值" name="history"><div class="history-toolbar"><span>自定义时间查询</span><el-date-picker v-model="fundHistoryRange" type="daterange" size="small" value-format="yyyy-MM-dd" range-separator="至" start-placeholder="开始日期" end-placeholder="结束日期" @change="loadFundHistory" /></div><div v-if="fundHistoryLoading" class="detail-skeleton" aria-label="正在加载历史净值"><div class="skeleton-table"><div class="skeleton-table-row skeleton-table-head"><i /><i /><i /><i /></div><div v-for="row in 7" :key="row" class="skeleton-table-row"><i /><i /><i /><i /></div></div></div><div v-else-if="!fundHistory.items.length" class="holding-loading">暂无历史净值数据</div><template v-else><div class="holding-meta">{{ fundHistory.source_label }} · {{ fundHistory.updated_at }} 更新</div><el-table :data="fundHistory.items" size="small" max-height="320"><el-table-column prop="date" label="日期" min-width="130" /><el-table-column prop="unit_nav" label="单位净值" min-width="130"><template slot-scope="{ row }">{{ formatFundNav(row.unit_nav) }}</template></el-table-column><el-table-column prop="total_nav" label="累计净值" min-width="130"><template slot-scope="{ row }">{{ formatFundNav(row.total_nav) }}</template></el-table-column><el-table-column prop="daily_change_rate" label="日涨幅" min-width="120"><template slot-scope="{ row }"><span :class="profitClass(row.daily_change_rate)">{{ formatSignedNullablePercent(row.daily_change_rate) }}</span></template></el-table-column></el-table></template></el-tab-pane></el-tabs>
    </el-dialog>

    <el-dialog title="新增持仓" :visible.sync="createDialogVisible" width="440px" @closed="resetHoldingForm">
      <el-form :model="holdingForm" label-width="90px">
        <el-form-item label="名称">
          <el-input v-model.trim="holdingForm.name" placeholder="如：沪深300ETF" />
        </el-form-item>
        <el-form-item label="代码">
          <el-input v-model.trim="holdingForm.code" placeholder="如：510300 / 001632" @blur="lookupHoldingInstrument" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="holdingForm.asset_type" placeholder="请选择类型" class="form-control" @change="lookupHoldingInstrument">
            <el-option label="股票" value="stock" />
            <el-option label="ETF" value="etf" />
            <el-option label="场外基金" value="fund" />
          </el-select>
        </el-form-item>
        <el-form-item label="现价/估值">
          <el-input :value="marketPreview.priceText" disabled>
            <template slot="append">
              <el-button :loading="lookupLoading" @click="lookupHoldingInstrument">自动识别</el-button>
            </template>
          </el-input>
          <div v-if="marketPreview.source" class="market-source">数据源：{{ marketPreview.source }}</div>
        </el-form-item>
        <el-form-item label="份额/股数">
          <el-input-number v-model="holdingForm.quantity" :min="0.0001" :step="100" class="form-control" />
        </el-form-item>
        <el-form-item label="成本价">
          <el-input-number v-model="holdingForm.cost_price" :min="0.0001" :step="0.01" :precision="4" class="form-control" />
        </el-form-item>
      </el-form>
      <span slot="footer">
        <el-button @click="createDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingCreate" @click="submitHolding">保存持仓</el-button>
      </span>
    </el-dialog>

    <el-dialog title="添加自选" :visible.sync="watchItemDialogVisible" width="420px"><el-form :model="watchItemForm" label-width="80px"><el-form-item label="代码"><el-input v-model.trim="watchItemForm.code" placeholder="输入代码后自动识别" @blur="lookupWatchItem" /></el-form-item><el-form-item label="名称"><el-input v-model.trim="watchItemForm.name" placeholder="自动识别后可修改" /></el-form-item><el-form-item label="类型"><el-select v-model="watchItemForm.asset_type" class="form-control" @change="lookupWatchItem"><el-option v-if="watchlistCategory === 'exchange'" label="股票" value="stock" /><el-option v-if="watchlistCategory === 'exchange'" label="ETF" value="etf" /><el-option v-if="watchlistCategory === 'fund'" label="场外基金" value="fund" /></el-select></el-form-item><el-form-item label="分组"><el-select v-model="watchItemForm.group_id" class="form-control"><el-option v-for="group in watchGroups" :key="group.id" :label="group.name" :value="group.id" /></el-select></el-form-item></el-form><span slot="footer"><el-button @click="watchItemDialogVisible = false">取消</el-button><el-button type="primary" :loading="watchItemSaving" @click="saveWatchItem">添加</el-button></span></el-dialog>
    <el-dialog title="加入自选" :visible.sync="fundHoldingWatchDialogVisible" width="360px"><el-form label-width="70px"><el-form-item label="股票"><span>{{ fundHoldingToWatch.name }}（{{ fundHoldingToWatch.code }}）</span></el-form-item><el-form-item label="分组"><el-select v-model="fundHoldingWatchGroupId" class="form-control" placeholder="请选择分组"><el-option v-for="group in exchangeWatchGroups" :key="group.id" :label="group.name" :value="group.id" /></el-select></el-form-item></el-form><span slot="footer"><el-button @click="fundHoldingWatchDialogVisible = false">取消</el-button><el-button type="primary" :loading="fundHoldingWatchSaving" @click="saveFundHoldingWatch">加入自选</el-button></span></el-dialog>

    <el-dialog title="修改持仓" :visible.sync="editDialogVisible" width="420px">
      <el-form :model="editHoldingForm" label-width="90px">
        <el-form-item label="持仓">
          <span>{{ editHoldingForm.name }}（{{ editHoldingForm.code }}）</span>
        </el-form-item>
        <el-form-item label="份额/股数">
          <el-input-number v-model="editHoldingForm.quantity" :min="0.0001" :step="100" />
        </el-form-item>
        <el-form-item label="成本价">
          <el-input-number v-model="editHoldingForm.cost_price" :min="0.0001" :step="0.01" :precision="4" />
        </el-form-item>
      </el-form>
      <span slot="footer">
        <el-button @click="editDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="savingEdit" @click="submitHoldingEdit">保存修改</el-button>
      </span>
    </el-dialog>

    <el-dialog title="当日收益率走势 · 指数对比" :visible.sync="pnlTrendDialogVisible" width="860px" @opened="renderPnlTrendChart">
      <div class="pnl-trend-toolbar">
        <span class="pnl-trend-toolbar-label">对比指数</span>
        <el-checkbox-group v-model="pnlTrendIndexCodes" :disabled="pnlTrendLoading">
          <el-checkbox v-for="index in pnlTrend.indices" :key="index.code" :label="index.code" :disabled="!index.available">{{ index.name }}</el-checkbox>
        </el-checkbox-group>
        <el-button type="text" :loading="pnlTrendLoading" @click="loadPnlTrend(true)">重新抓取</el-button>
      </div>

      <div v-if="pnlTrendLoading" class="pnl-trend-skeleton"><i /><i /><i /><i /></div>
      <div v-else-if="pnlTrendError" class="empty-state">{{ pnlTrendError }}</div>
      <div v-else-if="!pnlTrend.portfolio.available" class="empty-state">暂无当日收益率走势，请确认持仓已录入且行情可用。</div>
      <template v-else>
        <div ref="pnlTrendChart" class="pnl-trend-chart" />
        <div class="pnl-trend-meta">
          <span>组合当日收益率与指数涨跌幅对比</span>
          <span>覆盖 {{ pnlTrend.portfolio.covered }}/{{ pnlTrend.portfolio.total }} 个持仓</span>
          <span v-if="pnlTrend.missing_holdings.length">未取到分时：{{ pnlTrend.missing_holdings.map(item => item.name).join('、') }}</span>
          <span>{{ pnlTrend.source_label }}</span>
          <span>{{ pnlTrend.generated_at }}</span>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { fetchEstimateArchive, fetchPortfolioIntradayPnl } from './api/dashboard'
import * as echarts from 'echarts'
import { deleteHolding, fetchDashboard, fetchFundHistory, fetchFundHoldings, fetchFundPerformance, fetchIntradayChart, fetchMarketIndices, fetchNews, fetchWatchlist, lookupInstrument, moveWatchlistGroup, removeWatchlistGroup, removeWatchlistItem, saveHolding, saveWatchlistGroup, saveWatchlistItem, seedDemo, updateHolding } from './api/dashboard'

const emptyDashboard = () => ({
  portfolio: {
    total_market_value: 0,
    total_holding_pnl: 0,
    total_holding_pnl_rate: 0,
    total_today_pnl: 0,
    total_today_pnl_rate: 0,
    total_cost: 0,
    positions: []
  },
  news: {
    items: [],
    groups: [],
    total_count: 0
  },
  sectors: {
    gainers: [],
    losers: []
  },
  market_breadth: {
    available: false,
    rising: 0,
    falling: 0,
    flat: 0,
    limit_up: 0,
    limit_down: 0,
    total: 0,
    data_date: null,
    is_realtime: false
  },
  generated_at: ''
})

const newHoldingForm = () => ({
  name: '',
  code: '',
  asset_type: 'stock',
  quantity: 100,
  cost_price: 1
})

const defaultHistoryRange = () => {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - 92)
  const format = date => date.toISOString().slice(0, 10)
  return [format(start), format(end)]
}

const DEFAULT_PNL_TREND_INDICES = ['sh000001', 'sz399006', 'sh000688']

const PNL_TREND_INDEX_COLORS = {
  sh000001: '#f0a13c',
  sz399006: '#7c5cff',
  sh000688: '#2aa7c4'
}

const emptyPnlTrend = () => ({
  trade_date: '',
  times: [],
  portfolio: { available: false, name: '', pnl: [], rate: [], base_value: 0, covered: 0, total: 0 },
  indices: [],
  missing_holdings: [],
  source_label: '',
  generated_at: ''
})

export default {
  name: 'App',
  data() {
    return {
      loading: false,
      refreshingAll: false,
      dashboardLoaded: false,
      activeMenu: 'home',
      holdingsNumbersVisible: false,
      dashboard: emptyDashboard(),
      newsFeed: { items: [], groups: [], total_count: 0, source_label: '', generated_at: '' },
      newsLoading: false,
      newsRefreshTimer: null,
      refreshFab: { left: null, top: null, offsetX: 0, offsetY: 0, moved: false },
      privacyFab: { left: null, top: null, offsetX: 0, offsetY: 0, startX: 0, startY: 0, moved: false },
      marketIndices: [],
      marketIndicesLoading: false,
      activeMarketTab: 'cn',
      watchlistLoading: false,
      watchlistLoaded: false,
      watchlistCategory: 'exchange',
      selectedWatchGroupId: null,
      watchlist: { groups: [], items: [], generated_at: '' },
      watchItemDialogVisible: false,
      watchItemSaving: false,
      watchItemForm: { group_id: null, name: '', code: '', asset_type: 'stock' },
      fundHoldingWatchDialogVisible: false,
      fundHoldingWatchSaving: false,
      fundHoldingToWatch: { name: '', code: '' },
      fundHoldingWatchGroupId: null,
      indicesUpdatedAt: '',
      intradayDialogVisible: false,
      estimateArchiveDates: [],
      archiveInstrumentCode: '',
      estimateArchiveDate: '',
      intradayLoading: false,
      intradayChart: { name: '', previous_close: null, points: [], source_label: '' },
      fundHoldingsLoading: false,
      fundHoldings: { items: [], source_label: '', updated_at: '' },
      fundHistoryLoading: false,
      fundHistory: { items: [], source_label: '', updated_at: '' },
      fundHistoryRange: defaultHistoryRange(),
      fundHistoryCode: '',
      fundDetailTab: 'holdings',
      fundPerformanceLoading: false,
      fundPerformanceCode: '',
      fundPerformanceInterval: 'THREE',
      fundPerformance: { fund: [], index: [] },
      pnlTrendDialogVisible: false,
      pnlTrendLoading: false,
      pnlTrendError: '',
      pnlTrend: emptyPnlTrend(),
      pnlTrendIndexCodes: DEFAULT_PNL_TREND_INDICES.slice(),
      fundChartTab: 'intraday',
      holdingForm: newHoldingForm(),
      createDialogVisible: false,
      savingCreate: false,
      lookupLoading: false,
      marketPreview: {
        priceText: '输入代码后自动识别',
        source: ''
      },
      editDialogVisible: false,
      savingEdit: false,
      editHoldingForm: {
        id: null,
        name: '',
        code: '',
        quantity: 0,
        cost_price: 0
      }
    }
  },
  computed: {
    sortedHoldingPositions() {
      const rate = item => {
        const value = item.estimated_change_rate
        return value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value))
          ? Number(value) : -Infinity
      }
      return [...this.dashboard.portfolio.positions].sort((left, right) => {
        const a = rate(left)
        const b = rate(right)
        return a === b ? 0 : b - a
      })
    },
    statCards() {
      return [
        {
          label: '总持仓市值',
          value: this.formatHoldingMoney(this.dashboard.portfolio.total_market_value),
          foot: `成本 ${this.formatHoldingMoney(this.dashboard.portfolio.total_cost)}`,
          className: ''
        },
        {
          label: '当日预估盈亏金额',
          value: this.formatHoldingMoney(this.dashboard.portfolio.total_estimated_pnl),
          foot: `收益率 ${this.formatHoldingPercent(this.dashboard.portfolio.total_estimated_pnl_rate)}`,
          className: this.profitClass(this.dashboard.portfolio.total_estimated_pnl)
        },
        {
          label: '消息数量',
          value: String(this.homeEastmoneyNews.length),
          foot: '东方财富实时重点快讯',
          className: ''
        },
        {
          label: '更新时间',
          value: this.dashboard.generated_at || '--',
          foot: '由后端聚合生成',
          className: '',
          isTimestamp: true
        }
      ]
    },
    chartScale() {
      const prices = this.intradayChart.points.map(item => Number(item.price)).filter(Number.isFinite)
      const min = Math.min(...prices)
      const max = Math.max(...prices)
      const padding = Math.max((max - min) * 0.1, max * 0.002, 0.001)
      return { min: min - padding, max: max + padding }
    },
    refreshFabStyle() {
      return this.refreshFab.left === null ? {} : {
        left: `${this.refreshFab.left}px`,
        top: `${this.refreshFab.top}px`,
        right: 'auto',
        bottom: 'auto'
      }
    },
    privacyFabStyle() {
      return this.privacyFab.left === null ? {} : {
        left: `${this.privacyFab.left}px`,
        top: `${this.privacyFab.top}px`,
        right: 'auto',
        bottom: 'auto'
      }
    },
    isDashboardInitialLoading() {
      return this.loading && !this.dashboardLoaded
    },
    isMarketInitialLoading() {
      return this.marketIndicesLoading && !this.marketIndices.length
    },
    visibleMarketIndices() {
      return this.marketIndices.filter(item => (item.market || 'cn') === this.activeMarketTab)
    },
    homeEastmoneyNews() {
      const group = this.newsFeed.groups.find(item => item.source === '东方财富')
      return group ? group.items : []
    },
    homeMarketTemperature() {
      const mainland = this.marketIndices.filter(item => (item.market || 'cn') === 'cn')
      const changes = mainland.map(item => Number(item.change_rate)).filter(Number.isFinite)
      const averageChange = changes.length ? changes.reduce((total, value) => total + value, 0) / changes.length : 0
      const leader = this.dashboard.sectors.gainers[0] || {}
      const laggard = this.dashboard.sectors.losers[0] || {}
      const breadth = this.dashboard.market_breadth || { available: false, rising: 0, falling: 0, limit_up: 0, limit_down: 0, data_date: null, is_realtime: false }
      const label = averageChange >= 0.35 ? '偏暖' : averageChange <= -0.35 ? '偏弱' : '震荡'
      return {
        averageChange,
        rising: changes.filter(value => value > 0).length,
        falling: changes.filter(value => value < 0).length,
        breadth,
        leader,
        laggard,
        label,
        className: averageChange > 0 ? 'positive' : averageChange < 0 ? 'negative' : 'neutral'
      }
    },
    watchGroups() {
      return this.watchlist.groups.filter(group => group.category === this.watchlistCategory)
    },
    selectedWatchGroup() {
      return this.watchGroups.find(group => group.id === this.selectedWatchGroupId) || null
    },
    watchItems() {
      return this.watchlist.items.filter(item => item.group_id === this.selectedWatchGroupId)
    },
    exchangeWatchGroups() {
      return this.watchlist.groups.filter(group => group.category === 'exchange')
    }
  },
  watch: {
    selectedWatchGroupId(groupId) {
      if (groupId) localStorage.setItem(`quant-workbench-watchlist-${this.watchlistCategory}`, String(groupId))
    },
    watchlistCategory() {
      this.$nextTick(() => this.ensureWatchGroup())
    },
    pnlTrendIndexCodes() {
      this.$nextTick(() => this.renderPnlTrendChart())
    }
  },
  mounted() {
    window.addEventListener('resize', this.resizeIntradayChart)
    this.newsRefreshTimer = window.setInterval(() => {
      this.autoRefreshData()
    }, 60000)
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.resizeIntradayChart)
    this.stopRefreshDrag()
    this.stopPrivacyDrag()
    window.clearInterval(this.newsRefreshTimer)
    if (this.intradayInstance) this.intradayInstance.dispose()
    if (this.pnlTrendInstance) this.pnlTrendInstance.dispose()
  },
  created() {
    this.bootstrap()
  },
  methods: {
    async loadEstimateArchive() {
      const code = this.archiveInstrumentCode
      const assetType = this.intradayChart.asset_type
      this.intradayLoading = true
      this.intradayChart = { ...this.intradayChart, points: [] }
      try {
        const { data } = this.estimateArchiveDate
          ? await fetchEstimateArchive(code, this.estimateArchiveDate, assetType)
          : await fetchIntradayChart(code, assetType)
        if (code === this.archiveInstrumentCode) this.intradayChart = { ...data, asset_type: assetType }
      } catch (error) {
        this.$message.warning(error.response?.data?.error || '估值走势加载失败')
      } finally {
        this.intradayLoading = false
        this.$nextTick(() => this.renderIntradayChart())
      }
    },
    async autoRefreshData() {
      if (document.hidden || this.refreshingAll) return
      await Promise.all([
        ...(!this.loading ? [this.refreshDashboard()] : []),
        ...(!this.marketIndicesLoading ? [this.loadMarketIndices()] : []),
        this.loadNews(false, true),
        ...(this.activeMenu === 'watchlist' ? [this.loadWatchlist(false, true)] : [])
      ])
    },
    async bootstrap(force = false) {
      await Promise.all([this.refreshDashboard(force), this.loadMarketIndices(force), this.loadNews(force), ...(force ? [this.loadWatchlist(true)] : [])])
    },
    async refreshAll() {
      if (this.refreshingAll) return
      this.refreshingAll = true
      try { await this.bootstrap(true) } finally { this.refreshingAll = false }
    },
    handleRefreshFabClick() {
      if (this.refreshFab.moved) return
      this.refreshAll()
    },
    finishRefreshTouch() {
      const wasMoved = this.refreshFab.moved
      this.stopRefreshDrag()
      if (!wasMoved) this.refreshAll()
    },
    toggleHoldingNumbers() {
      if (this.privacyFab.moved) return
      this.holdingsNumbersVisible = !this.holdingsNumbersVisible
    },
    finishPrivacyTouch() {
      const wasMoved = this.privacyFab.moved
      this.stopPrivacyDrag()
      if (!wasMoved) this.holdingsNumbersVisible = !this.holdingsNumbersVisible
    },
    startRefreshDrag(event) {
      const point = this.getPointer(event)
      const rect = event.currentTarget.getBoundingClientRect()
      this.refreshFab.offsetX = point.clientX - rect.left
      this.refreshFab.offsetY = point.clientY - rect.top
      this.refreshFab.moved = false
      window.addEventListener('mousemove', this.moveRefreshDrag)
      window.addEventListener('mouseup', this.stopRefreshDrag)
      window.addEventListener('touchmove', this.moveRefreshDrag, { passive: false })
      window.addEventListener('touchend', this.stopRefreshDrag)
    },
    moveRefreshDrag(event) {
      const point = this.getPointer(event)
      const size = 54
      const left = Math.min(Math.max(8, point.clientX - this.refreshFab.offsetX), window.innerWidth - size - 8)
      const top = Math.min(Math.max(8, point.clientY - this.refreshFab.offsetY), window.innerHeight - size - 8)
      this.refreshFab.left = left
      this.refreshFab.top = top
      this.refreshFab.moved = true
      if (event.cancelable) event.preventDefault()
    },
    stopRefreshDrag() {
      window.removeEventListener('mousemove', this.moveRefreshDrag)
      window.removeEventListener('mouseup', this.stopRefreshDrag)
      window.removeEventListener('touchmove', this.moveRefreshDrag)
      window.removeEventListener('touchend', this.stopRefreshDrag)
      if (this.refreshFab.moved) setTimeout(() => { this.refreshFab.moved = false }, 250)
    },
    startPrivacyDrag(event) {
      const point = this.getPointer(event)
      const rect = event.currentTarget.getBoundingClientRect()
      this.privacyFab.offsetX = point.clientX - rect.left
      this.privacyFab.offsetY = point.clientY - rect.top
      this.privacyFab.startX = point.clientX
      this.privacyFab.startY = point.clientY
      this.privacyFab.moved = false
      window.addEventListener('mousemove', this.movePrivacyDrag)
      window.addEventListener('mouseup', this.stopPrivacyDrag)
      window.addEventListener('touchmove', this.movePrivacyDrag, { passive: false })
      window.addEventListener('touchend', this.stopPrivacyDrag)
    },
    movePrivacyDrag(event) {
      const point = this.getPointer(event)
      const size = 50
      const distance = Math.hypot(point.clientX - this.privacyFab.startX, point.clientY - this.privacyFab.startY)
      if (distance < 6) return
      this.privacyFab.left = Math.min(Math.max(8, point.clientX - this.privacyFab.offsetX), window.innerWidth - size - 8)
      this.privacyFab.top = Math.min(Math.max(8, point.clientY - this.privacyFab.offsetY), window.innerHeight - size - 8)
      this.privacyFab.moved = true
      if (event.cancelable) event.preventDefault()
    },
    stopPrivacyDrag() {
      window.removeEventListener('mousemove', this.movePrivacyDrag)
      window.removeEventListener('mouseup', this.stopPrivacyDrag)
      window.removeEventListener('touchmove', this.movePrivacyDrag)
      window.removeEventListener('touchend', this.stopPrivacyDrag)
      if (this.privacyFab.moved) setTimeout(() => { this.privacyFab.moved = false }, 250)
    },
    getPointer(event) {
      return event.touches ? event.touches[0] : event
    },
    onMenuSelect(menu) {
      this.activeMenu = menu
      if (menu === 'news') this.loadNews()
      if (menu === 'watchlist') this.loadWatchlist()
    },
    ensureWatchGroup() {
      const storedId = Number(localStorage.getItem(`quant-workbench-watchlist-${this.watchlistCategory}`))
      const target = this.watchGroups.find(group => group.id === storedId) || this.watchGroups[0]
      if (!this.selectedWatchGroup || this.selectedWatchGroup.category !== this.watchlistCategory) this.selectedWatchGroupId = target ? target.id : null
    },
    async loadWatchlist(force = false, reload = false) {
      if (this.watchlistLoading || (!force && !reload && this.watchlistLoaded)) return
      this.watchlistLoading = true
      try {
        const { data } = await fetchWatchlist(force)
        this.watchlist = data
        this.watchlistLoaded = true
        this.ensureWatchGroup()
      } catch (error) {
        this.$message.error(error.response?.data?.error || '自选行情加载失败')
      } finally { this.watchlistLoading = false }
    },
    async createWatchGroup() {
      try {
        const { value } = await this.$prompt('请输入分组名称', '新建自选分组', { inputPattern: /\S+/, inputErrorMessage: '分组名称不能为空' })
        await saveWatchlistGroup({ name: value, category: this.watchlistCategory })
        await this.loadWatchlist(true)
        this.selectedWatchGroupId = this.watchGroups.find(group => group.name === value)?.id || this.selectedWatchGroupId
      } catch (error) { if (error !== 'cancel' && error !== 'close') this.$message.error(error.response?.data?.error || '新建分组失败') }
    },
    async deleteWatchGroup() {
      try {
        await this.$confirm(`删除“${this.selectedWatchGroup.name}”及其中所有自选？`, '确认删除', { type: 'warning' })
        await removeWatchlistGroup(this.selectedWatchGroupId)
        this.selectedWatchGroupId = null
        await this.loadWatchlist(true)
      } catch (error) { if (error !== 'cancel' && error !== 'close') this.$message.error(error.response?.data?.error || '删除分组失败') }
    },
    async moveCurrentWatchGroup(direction) {
      if (!this.selectedWatchGroupId) return
      try {
        await moveWatchlistGroup(this.selectedWatchGroupId, direction)
        await this.loadWatchlist(true)
      } catch (error) { this.$message.error(error.response?.data?.error || '移动分组失败') }
    },
    openWatchItemDialog() {
      this.watchItemForm = { group_id: this.selectedWatchGroupId, name: '', code: '', asset_type: this.watchlistCategory === 'fund' ? 'fund' : 'stock' }
      this.watchItemDialogVisible = true
    },
    async lookupWatchItem() {
      if (!this.watchItemForm.code) return
      try {
        const { data } = await lookupInstrument(this.watchItemForm.code, this.watchItemForm.asset_type)
        this.watchItemForm.name = data.name || this.watchItemForm.name
      } catch (error) { this.$message.warning(error.response?.data?.error || '标的识别失败') }
    },
    async saveWatchItem() {
      this.watchItemSaving = true
      try {
        await saveWatchlistItem(this.watchItemForm)
        this.watchItemDialogVisible = false
        await this.loadWatchlist(true)
      } catch (error) { this.$message.error(error.response?.data?.error || '添加自选失败') } finally { this.watchItemSaving = false }
    },
    async deleteWatchItem(id) {
      try { await removeWatchlistItem(id); await this.loadWatchlist(true) } catch (error) { this.$message.error(error.response?.data?.error || '删除自选失败') }
    },
    async openFundHoldingWatch(row) {
      if (!this.watchlistLoaded) await this.loadWatchlist()
      if (!this.exchangeWatchGroups.length) {
        this.$message.warning('请先在自选页面创建场内分组')
        return
      }
      this.fundHoldingToWatch = { name: row.name, code: row.code }
      this.fundHoldingWatchGroupId = this.exchangeWatchGroups[0].id
      this.fundHoldingWatchDialogVisible = true
    },
    async saveFundHoldingWatch() {
      if (!this.fundHoldingWatchGroupId) return
      this.fundHoldingWatchSaving = true
      try {
        await saveWatchlistItem({
          group_id: this.fundHoldingWatchGroupId,
          name: this.fundHoldingToWatch.name,
          code: this.fundHoldingToWatch.code,
          asset_type: 'stock'
        })
        this.fundHoldingWatchDialogVisible = false
        await this.loadWatchlist(true)
        this.$message.success('已加入自选')
      } catch (error) {
        this.$message.error(error.response?.data?.error || '加入自选失败')
      } finally { this.fundHoldingWatchSaving = false }
    },
    async loadNews(force = false, reload = false) {
      if (this.newsLoading || (!force && !reload && this.newsFeed.groups.length)) return
      this.newsLoading = true
      try {
        const { data } = await fetchNews(force)
        this.newsFeed = data
      } catch (error) {
        this.$message.error(error.response?.data?.error || '财经快讯加载失败')
      } finally {
        this.newsLoading = false
      }
    },
    async refreshDashboard(force = false) {
      if (this.loading) return
      this.loading = true
      try {
        const { data } = await fetchDashboard(force)
        this.dashboard = data
        this.dashboardLoaded = true
      } catch (error) {
        this.$message.error(error.response?.data?.error || (error.code === 'ECONNABORTED'
          ? '看板数据源响应超时，已保留原数据，请稍后刷新'
          : '看板刷新失败，请检查网络后重试'))
      } finally {
        this.loading = false
      }
    },
    async loadMarketIndices(force = false) {
      if (this.marketIndicesLoading) return
      this.marketIndicesLoading = true
      try {
        const { data } = await fetchMarketIndices(force === true)
        this.marketIndices = data.items || []
        this.indicesUpdatedAt = data.generated_at || ''
      } catch (error) {
        // Retain the last successful quotes when a background refresh fails.
      } finally {
        this.marketIndicesLoading = false
      }
    },
    async openIntradayChart(holding) {
      this.archiveInstrumentCode = holding.code
      this.estimateArchiveDate = ''
      this.estimateArchiveDates = []
      if (['fund', 'stock', 'etf'].includes(holding.asset_type)) {
        fetchEstimateArchive(holding.code, '', holding.asset_type).then(({ data }) => {
          if (this.archiveInstrumentCode === holding.code) this.estimateArchiveDates = data.dates || []
        }).catch(() => this.$message.warning('历史走势日期加载失败'))
      }
      this.intradayDialogVisible = true
      this.intradayLoading = true
      this.intradayChart = { name: holding.name, asset_type: holding.asset_type, previous_close: holding.previous_close, points: [], source_label: '' }
      this.fundHoldings = { items: [], source_label: '', updated_at: '' }
      this.fundHistory = { items: [], source_label: '', updated_at: '' }
      this.fundPerformance = { fund: [], index: [] }
      this.fundPerformanceCode = holding.asset_type === 'fund' ? holding.code : ''
      this.fundPerformanceLoading = holding.asset_type === 'fund'
      this.fundDetailTab = 'holdings'
      this.fundChartTab = 'intraday'
      this.fundHoldingsLoading = holding.asset_type === 'fund'
      this.fundHistoryLoading = holding.asset_type === 'fund'
      this.fundHistoryCode = holding.asset_type === 'fund' ? holding.code : ''
      const fundHoldingsRequest = holding.asset_type === 'fund' ? fetchFundHoldings(holding.code) : null
      const fundHistoryRequest = holding.asset_type === 'fund' ? fetchFundHistory(holding.code, ...this.fundHistoryRange) : null
      const fundPerformanceRequest = holding.asset_type === 'fund' ? fetchFundPerformance(holding.code, this.fundPerformanceInterval) : null
      try {
        const { data } = await fetchIntradayChart(holding.code, holding.asset_type)
        this.intradayChart = { ...data, asset_type: holding.asset_type }
      } catch (error) {
        this.$message.warning(error.response?.data?.error || '分时数据加载失败')
      } finally {
        this.intradayLoading = false
        this.$nextTick(() => this.renderIntradayChart())
      }
      if (fundHoldingsRequest) {
        try {
          const { data } = await fundHoldingsRequest
          this.fundHoldings = data
        } catch (error) {
          this.$message.warning(error.response?.data?.error || '基金持仓加载失败')
        } finally {
          this.fundHoldingsLoading = false
        }
      }
      if (fundHistoryRequest) {
        try {
          const { data } = await fundHistoryRequest
          this.fundHistory = data
        } catch (error) {
          this.$message.warning(error.response?.data?.error || '历史净值加载失败')
        } finally {
          this.fundHistoryLoading = false
        }
      }
      if (fundPerformanceRequest) {
        try { const { data } = await fundPerformanceRequest; this.fundPerformance = data } catch (error) { this.$message.warning(error.response?.data?.error || '业绩走势加载失败') } finally { this.fundPerformanceLoading = false; this.$nextTick(() => this.renderFundPerformance()) }
      }
    },
    openIndexIntradayChart(index) {
      this.openIntradayChart({
        name: index.name,
        code: index.intraday_symbol || index.code,
        asset_type: 'index',
        previous_close: index.previous_close
      })
    },
    async loadFundPerformance(interval) {
      if (!this.fundPerformanceCode) return
      this.fundPerformanceInterval = interval; this.fundPerformanceLoading = true
      try { const { data } = await fetchFundPerformance(this.fundPerformanceCode, interval); this.fundPerformance = data } catch (error) { this.$message.warning(error.response?.data?.error || '业绩走势加载失败') } finally { this.fundPerformanceLoading = false; this.$nextTick(() => this.renderFundPerformance()) }
    },
    handleFundChartTab(tab) {
      if (tab.name === 'performance') this.$nextTick(() => this.renderFundPerformance())
      else this.$nextTick(() => this.renderIntradayChart())
    },
    renderFundPerformance() {
      if (!this.$refs.fundPerformanceChart || !this.fundPerformance.fund.length) return
      const fund = this.fundPerformance.fund; const index = this.fundPerformance.index
      if (this.fundPerformanceInstance && this.fundPerformanceInstance.getDom() !== this.$refs.fundPerformanceChart) {
        this.fundPerformanceInstance.dispose()
        this.fundPerformanceInstance = null
      }
      this.fundPerformanceInstance = this.fundPerformanceInstance || echarts.init(this.$refs.fundPerformanceChart)
      this.fundPerformanceInstance.setOption({ tooltip: { trigger: 'axis', formatter: params => `${params[0].axisValue}<br/>${params.map(item => `${item.seriesName}：${Number(item.data).toFixed(2)}%`).join('<br/>')}` }, legend: { data: ['本基金', '沪深300'] }, grid: { left: 48, right: 22, top: 38, bottom: 28 }, xAxis: { type: 'category', boundaryGap: false, data: fund.map(item => item.date.slice(5)), axisLabel: { interval: Math.max(Math.floor(fund.length / 4), 1) } }, yAxis: { type: 'value', axisLabel: { formatter: '{value}%' }, splitLine: { lineStyle: { type: 'dashed' } } }, series: [{ name: '本基金', type: 'line', showSymbol: false, smooth: true, data: fund.map(item => item.rate), lineStyle: { color: '#6f9dff', width: 2 } }, { name: '沪深300', type: 'line', showSymbol: false, smooth: true, data: index.map(item => item.rate), lineStyle: { color: '#f0a13c', width: 2 } }] }, true)
      this.fundPerformanceInstance.resize()
    },
    async loadFundHistory() {
      if (!this.fundHistoryCode || !this.fundHistoryRange || this.fundHistoryRange.length !== 2) return
      this.fundHistoryLoading = true
      try {
        const { data } = await fetchFundHistory(this.fundHistoryCode, ...this.fundHistoryRange)
        this.fundHistory = data
      } catch (error) {
        this.$message.warning(error.response?.data?.error || '历史净值加载失败')
      } finally {
        this.fundHistoryLoading = false
      }
    },
    renderIntradayChart() {
      if (!this.intradayDialogVisible || this.intradayLoading || this.fundChartTab !== 'intraday' || !this.$refs.intradayChart || !this.intradayChart.points.length) return
      // v-if recreates the container after loading or switching chart tabs.
      if (this.intradayInstance && this.intradayInstance.getDom() !== this.$refs.intradayChart) {
        this.intradayInstance.dispose()
        this.intradayInstance = null
      }
      const points = this.intradayChart.points
      const previousClose = Number(this.intradayChart.previous_close)
      const lastPrice = Number(points[points.length - 1].price)
      const positive = lastPrice >= previousClose
      const lineColor = positive ? '#d64541' : '#0f9960'
      this.intradayInstance = this.intradayInstance || echarts.init(this.$refs.intradayChart)
      this.intradayInstance.setOption({
        animationDuration: 350,
        backgroundColor: '#f8fbff',
        grid: { left: 60, right: 26, top: 28, bottom: 48 },
        tooltip: {
          trigger: 'axis',
          backgroundColor: 'rgba(16, 35, 63, 0.92)',
          borderWidth: 0,
          textStyle: { color: '#fff' },
          formatter: params => `${params[0].axisValue}<br/>估值：${Number(params[0].data).toFixed(4)}`
        },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: points.map(item => item.time),
          axisLine: { lineStyle: { color: '#ccd9e8' } },
          axisLabel: { color: '#6b7a90', interval: Math.max(Math.floor(points.length / 5), 1) }
        },
        yAxis: {
          type: 'value',
          min: this.chartScale.min,
          max: this.chartScale.max,
          scale: true,
          axisLabel: { color: '#6b7a90', formatter: value => Number(value).toFixed(3) },
          splitLine: { lineStyle: { color: '#e5edf6', type: 'dashed' } }
        },
        series: [{
          name: '当日分时',
          type: 'line',
          smooth: true,
          showSymbol: false,
          data: points.map(item => Number(item.price)),
          lineStyle: { color: lineColor, width: 2.5 },
          areaStyle: { color: positive ? 'rgba(214, 69, 65, 0.12)' : 'rgba(15, 153, 96, 0.12)' },
          markLine: previousClose ? { symbol: 'none', lineStyle: { color: '#8394aa', type: 'dashed' }, label: { formatter: `昨收 ${previousClose.toFixed(4)}` }, data: [{ yAxis: previousClose }] } : undefined
        }]
      }, true)
      this.intradayInstance.resize()
    },
    openPnlTrendDialog() {
      this.pnlTrendDialogVisible = true
      this.loadPnlTrend()
    },
    async loadPnlTrend(force = false) {
      if (this.pnlTrendLoading) return
      this.pnlTrendLoading = true
      this.pnlTrendError = ''
      try {
        const { data } = await fetchPortfolioIntradayPnl(force)
        this.pnlTrend = data
        if (!this.pnlTrendIndexCodes.length && data.indices.length) {
          this.pnlTrendIndexCodes = data.indices.map(item => item.code)
        }
        this.$nextTick(() => this.renderPnlTrendChart())
      } catch (error) {
        this.pnlTrendError = error.response?.data?.error || '当日收益走势加载失败，请稍后重试'
      } finally {
        this.pnlTrendLoading = false
      }
    },
    renderPnlTrendChart() {
      const container = this.$refs.pnlTrendChart
      if (!this.pnlTrendDialogVisible || this.pnlTrendLoading || !container || !this.pnlTrend.portfolio.available) return
      if (this.pnlTrendInstance && this.pnlTrendInstance.getDom() !== container) {
        this.pnlTrendInstance.dispose()
        this.pnlTrendInstance = null
      }
      const times = this.pnlTrend.times
      const rate = this.pnlTrend.portfolio.rate
      const lastRate = [...rate].reverse().find(value => value !== null && value !== undefined)
      const positive = Number(lastRate || 0) >= 0
      const portfolioColor = positive ? '#d64541' : '#0f9960'
      const visible = this.pnlTrend.indices.filter(item => item.available && this.pnlTrendIndexCodes.includes(item.code))

      const series = [{
        name: '我的持仓当日收益率',
        type: 'line',
        yAxisIndex: 0,
        showSymbol: false,
        smooth: true,
        data: rate,
        lineStyle: { color: portfolioColor, width: 2.5 },
        areaStyle: { color: positive ? 'rgba(214, 69, 65, 0.12)' : 'rgba(15, 153, 96, 0.12)' },
        markLine: { symbol: 'none', lineStyle: { color: '#8394aa', type: 'dashed' }, label: { formatter: '盈亏平衡' }, data: [{ yAxis: 0 }] }
      }]
      visible.forEach(item => {
        series.push({
          name: item.name,
          type: 'line',
          yAxisIndex: 0,
          showSymbol: false,
          smooth: true,
          data: item.rate,
          lineStyle: { color: PNL_TREND_INDEX_COLORS[item.code] || '#8394aa', width: 1.6 }
        })
      })

      this.pnlTrendInstance = this.pnlTrendInstance || echarts.init(container)
      this.pnlTrendInstance.setOption({
        animationDuration: 350,
        backgroundColor: '#f8fbff',
        grid: { left: 60, right: 54, top: 52, bottom: 48 },
        legend: {
          top: 8,
          textStyle: { color: '#6b7a90' },
          data: series.map(item => item.name)
        },
        tooltip: {
          trigger: 'axis',
          backgroundColor: 'rgba(16, 35, 63, 0.92)',
          borderWidth: 0,
          textStyle: { color: '#fff' },
          formatter: params => {
            const head = params[0].axisValue
            const lines = params
              .filter(item => item.value !== null && item.value !== undefined)
              .map(item => `${item.marker}${item.seriesName}：${Number(item.value).toFixed(2)}%`)
            return [head, ...lines].join('<br/>')
          }
        },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: times,
          axisLine: { lineStyle: { color: '#ccd9e8' } },
          axisLabel: { color: '#6b7a90', interval: Math.max(Math.floor(times.length / 6), 1) }
        },
        yAxis: {
          type: 'value',
          name: '当日收益率(%)',
          nameTextStyle: { color: '#6b7a90' },
          scale: true,
          axisLabel: { color: '#6b7a90', formatter: value => `${Number(value).toFixed(2)}%` },
          splitLine: { lineStyle: { color: '#e5edf6', type: 'dashed' } }
        },
        series
      }, true)
      this.pnlTrendInstance.resize()
    },
    resizeIntradayChart() {
      if (this.intradayInstance) this.intradayInstance.resize()
      if (this.fundPerformanceInstance) this.fundPerformanceInstance.resize()
      if (this.pnlTrendInstance) this.pnlTrendInstance.resize()
    },
    async submitHolding() {
      this.savingCreate = true
      try {
        await saveHolding(this.holdingForm)
        this.createDialogVisible = false
        this.$message.success('持仓已保存')
        await this.bootstrap()
      } catch (error) {
        this.$message.error(error.response?.data?.error || '新增持仓失败')
      } finally {
        this.savingCreate = false
      }
    },
    openCreateHolding() {
      this.resetHoldingForm()
      this.createDialogVisible = true
    },
    resetHoldingForm() {
      this.holdingForm = newHoldingForm()
      this.marketPreview = {
        priceText: '输入代码后自动识别',
        source: ''
      }
    },
    async lookupHoldingInstrument() {
      if (!this.holdingForm.code) return
      this.lookupLoading = true
      try {
        const { data } = await lookupInstrument(this.holdingForm.code, this.holdingForm.asset_type)
        this.holdingForm.name = data.name
        this.marketPreview = {
          priceText: (data.current_price === null || data.current_price === undefined) && (data.estimated_price === null || data.estimated_price === undefined)
            ? '暂无实时估值'
            : this.formatNetValue(data.current_price ?? data.estimated_price, this.holdingForm.asset_type),
          source: data.source_label || '公开行情'
        }
      } catch (error) {
        this.marketPreview = {
          priceText: '未查询到实时价格',
          source: ''
        }
        this.$message.warning(error.response?.data?.error || '标的识别失败，请检查代码')
      } finally {
        this.lookupLoading = false
      }
    },
    async removeHolding(id) {
      try {
        await deleteHolding(id)
        this.$message.success('持仓已删除')
        await this.bootstrap()
      } catch (error) {
        this.$message.error(error.response?.data?.error || '删除持仓失败')
      }
    },
    openEditHolding(holding) {
      this.editHoldingForm = {
        id: holding.id,
        name: holding.name,
        code: holding.code,
        quantity: Number(holding.quantity),
        cost_price: Number(holding.cost_price)
      }
      this.editDialogVisible = true
    },
    async submitHoldingEdit() {
      this.savingEdit = true
      try {
        await updateHolding(this.editHoldingForm.id, {
          quantity: this.editHoldingForm.quantity,
          cost_price: this.editHoldingForm.cost_price
        })
        this.editDialogVisible = false
        this.$message.success('持仓份额和成本价已更新')
        await this.bootstrap()
      } catch (error) {
        this.$message.error(error.response?.data?.error || '修改持仓失败')
      } finally {
        this.savingEdit = false
      }
    },
    async seedDemoData() {
      try {
        await seedDemo()
        this.$message.success('已导入演示持仓')
        await this.bootstrap()
      } catch (error) {
        this.$message.error(error.response?.data?.error || '导入失败')
      }
    },
    formatMoney(value) {
      const numeric = Number(value || 0)
      return `¥${numeric.toFixed(2)}`
    },
    formatNetValue(value, assetType) {
      if (value === null || value === undefined) return '--'
      const numeric = Number(value)
      return assetType === 'fund' ? `¥${numeric.toFixed(4)}` : this.formatMoney(numeric)
    },
    formatIntradayPrice(value, assetType) {
      if (value === null || value === undefined) return '--'
      if (assetType === 'index') return Number(value).toFixed(2)
      return this.formatNetValue(value, assetType)
    },
    formatFundNav(value) {
      return value === null || value === undefined ? '--' : Number(value).toFixed(4)
    },
    formatHoldingMoney(value, nullable = false) {
      if (nullable && (value === null || value === undefined)) return '--'
      return this.holdingsNumbersVisible ? this.formatMoney(value) : '****'
    },
    formatHoldingCostPrice(value) {
      return this.holdingsNumbersVisible ? `¥${Number(value || 0).toFixed(4)}` : '****'
    },
    formatHoldingPercent(value, nullable = false) {
      if (nullable && (value === null || value === undefined)) return '--'
      return this.holdingsNumbersVisible ? this.formatPercent(value) : '****'
    },
    formatHoldingNetValue(value, assetType) {
      if (value === null || value === undefined) return '--'
      return this.holdingsNumbersVisible ? this.formatNetValue(value, assetType) : '****'
    },
    formatHoldingQuantity(value) {
      return this.holdingsNumbersVisible ? Number(value).toFixed(2) : '****'
    },
    formatHoldingCode(value) {
      return this.holdingsNumbersVisible ? value : '******'
    },
    formatPercent(value) {
      const numeric = Number(value || 0)
      return `${numeric.toFixed(2)}%`
    },
    formatNullablePercent(value) {
      return value === null || value === undefined ? '--' : this.formatPercent(value)
    },
    formatSignedNullablePercent(value) {
      if (value === null || value === undefined) return '--'
      const numeric = Number(value)
      return `${numeric > 0 ? '+' : ''}${numeric.toFixed(2)}%`
    },
    formatNullableMoney(value) {
      return value === null || value === undefined ? '--' : this.formatMoney(value)
    },
    profitClass(value) {
      if (Number(value) > 0) return 'positive'
      if (Number(value) < 0) return 'negative'
      return 'neutral'
    },
    tagType(sentiment) {
      if (sentiment === 'bullish') return 'danger'
      if (sentiment === 'bearish') return 'success'
      return 'warning'
    },
    sentimentLabel(sentiment) {
      if (sentiment === 'bullish') return '偏多'
      if (sentiment === 'bearish') return '偏空'
      return '中性'
    },
    assetTypeLabel(assetType) {
      if (assetType === 'stock') return '股票'
      if (assetType === 'etf') return 'ETF'
      if (assetType === 'fund') return '场外基金'
      return '未知'
    },
    assetTypeTag(assetType) {
      if (assetType === 'stock') return 'danger'
      if (assetType === 'etf') return 'warning'
      if (assetType === 'fund') return 'success'
      return 'info'
    }
  }
}
</script>

<style scoped>
.app-shell {
  padding: 28px;
}

.workspace-nav {
  display: flex;
  align-items: center;
  gap: 24px;
  margin-bottom: 22px;
  padding: 10px 16px;
  border: 1px solid var(--border);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 8px 28px rgba(16, 35, 63, 0.05);
}

.brand-mark {
  display: flex;
  flex-direction: column;
  min-width: 104px;
  color: var(--text);
  font-weight: 700;
}

.brand-mark small {
  margin-top: 2px;
  color: var(--muted);
  font-size: 11px;
  font-weight: 400;
}

.workspace-menu {
  flex: 1;
  border-bottom: 0;
  background: transparent;
}

.workspace-menu.el-menu--horizontal > .el-menu-item {
  height: 42px;
  line-height: 42px;
}

.refresh-fab {
  position: fixed;
  z-index: 20;
  right: 26px;
  bottom: 28px;
  display: grid;
  width: 54px;
  height: 54px;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: linear-gradient(145deg, #0e6fb4, #063e78);
  box-shadow: 0 12px 26px rgba(6, 62, 120, 0.3);
  color: #fff;
  cursor: grab;
  font-size: 23px;
  transition: box-shadow 0.2s ease, transform 0.2s ease;
  user-select: none;
  touch-action: none;
}

.refresh-fab:hover {
  box-shadow: 0 16px 32px rgba(6, 62, 120, 0.4);
  transform: translateY(-2px);
}

.refresh-fab:active {
  cursor: grabbing;
  transform: scale(0.94);
}

.refresh-fab.is-loading i {
  animation: refresh-spin 0.8s linear infinite;
}

.privacy-fab {
  position: fixed;
  z-index: 20;
  right: 28px;
  bottom: 96px;
  display: grid;
  width: 50px;
  height: 50px;
  place-items: center;
  border: 0;
  border-radius: 50%;
  background: linear-gradient(145deg, #475569, #1e293b);
  box-shadow: 0 10px 24px rgba(30, 41, 59, 0.28);
  color: #fff;
  cursor: grab;
  font-size: 21px;
  transition: box-shadow 0.2s ease, transform 0.2s ease, background 0.2s ease;
  user-select: none;
  touch-action: none;
}

.privacy-fab.is-visible {
  background: linear-gradient(145deg, #0ea5a4, #087f7b);
}

.privacy-fab:hover {
  box-shadow: 0 15px 30px rgba(30, 41, 59, 0.38);
  transform: translateY(-2px);
}

.privacy-fab:active {
  cursor: grabbing;
  transform: scale(0.94);
}

@keyframes refresh-spin {
  to { transform: rotate(360deg); }
}

.page-heading {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  margin: 4px 0 18px;
}

.page-heading h2 {
  margin: 0;
  font-size: 26px;
}

.page-heading p {
  margin: 7px 0 0;
  color: var(--muted);
}

.index-card {
  min-height: 132px;
  padding: 22px;
  border: 1px solid var(--border);
  border-radius: 20px;
  background: linear-gradient(145deg, #fff, #edf6fb);
  box-shadow: 0 8px 28px rgba(16, 35, 63, 0.06);
}

.index-card--clickable {
  cursor: pointer;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, transform 0.2s ease;
}

.index-card--clickable:hover,
.index-card--clickable:focus {
  border-color: #8eb9e5;
  box-shadow: 0 14px 30px rgba(18, 89, 155, 0.14);
  outline: 0;
  transform: translateY(-2px);
}

.index-value {
  margin: 9px 0 7px;
  font-size: 28px;
  font-weight: 700;
}

.empty-state {
  margin-bottom: 18px;
  padding: 28px;
  border: 1px dashed var(--border);
  border-radius: 16px;
  color: var(--muted);
  text-align: center;
}

.position-link {
  padding: 0;
  color: var(--text);
  font-weight: 600;
}

.position-link:hover {
  color: #0e6fb4;
}

.chart-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  margin-bottom: 12px;
  color: var(--muted);
  font-size: 13px;
}

.intraday-chart {
  display: block;
  width: 100%;
  height: 310px;
  border-radius: 12px;
  background: #f8fbff;
}

.chart-loading {
  padding: 72px 16px;
  color: var(--muted);
  text-align: center;
}

.holding-loading {
  padding: 22px 16px;
  color: var(--muted);
  text-align: center;
}

.holding-meta {
  margin: -4px 0 10px;
  color: var(--muted);
  font-size: 12px;
}

.holding-report {
  display: flex;
  justify-content: space-between;
  margin: 0 0 10px;
  color: var(--text);
  font-size: 13px;
}

.fund-detail-tabs {
  margin-top: 18px;
}

.fund-chart-tabs .el-tabs__header { margin-bottom: 12px; }
.market-index-tabs .el-tabs__header { margin-bottom: 12px; }
.fund-performance-chart { width: 100%; height: 310px; }
.performance-ranges { display: flex; justify-content: space-around; margin: 4px 0 10px; }
.performance-ranges .active { color: #2f74e9; border-bottom: 2px solid #2f74e9; }

.detail-skeleton {
  min-height: 286px;
}

.skeleton-meta {
  display: flex;
  justify-content: space-between;
  margin: 0 0 16px;
}

.skeleton-meta i {
  width: 96px;
  height: 14px;
}

.skeleton-table {
  overflow: hidden;
  border: 1px solid #edf1f5;
  border-radius: 8px;
}

.skeleton-table-row {
  display: grid;
  grid-template-columns: 1fr 1.5fr 1fr 1.1fr;
  gap: 24px;
  align-items: center;
  min-height: 38px;
  padding: 0 18px;
  border-top: 1px solid #edf1f5;
}

.skeleton-table-row:first-child {
  border-top: 0;
}

.skeleton-table-head {
  background: #f7f9fb;
}

.skeleton-table-row i,
.skeleton-meta i {
  display: block;
  border-radius: 4px;
  background: linear-gradient(90deg, #edf2f7 25%, #f7f9fc 37%, #edf2f7 63%);
  background-size: 400% 100%;
  animation: skeleton-shimmer 1.35s ease infinite;
}

.skeleton-table-row i {
  height: 12px;
}

@keyframes skeleton-shimmer {
  0% { background-position: 100% 50%; }
  100% { background-position: 0 50%; }
}

.page-skeleton-loading .stat-value,
.page-skeleton-loading .stat-foot {
  display: block;
  width: 72%;
  color: transparent !important;
  border-radius: 5px;
  background: linear-gradient(90deg, #edf2f7 25%, #f7f9fc 37%, #edf2f7 63%);
  background-size: 400% 100%;
  animation: skeleton-shimmer 1.35s ease infinite;
}

.page-skeleton-loading .stat-value {
  height: 32px;
}

.page-skeleton-loading .stat-foot {
  height: 13px;
}

.table-skeleton {
  min-height: 245px;
}

.table-skeleton.table-skeleton-wide {
  min-height: 290px;
}

.table-skeleton .el-table__empty-block {
  display: none;
}

.table-skeleton .el-table__body-wrapper {
  min-height: 195px;
  background:
    repeating-linear-gradient(to bottom, transparent 0, transparent 37px, #edf1f5 38px),
    linear-gradient(90deg, #edf2f7 20%, #f7f9fc 37%, #edf2f7 63%);
  background-size: 100% 38px, 400% 100%;
  animation: skeleton-shimmer 1.35s ease infinite;
}

.table-skeleton-wide .el-table__body-wrapper {
  min-height: 240px;
}

.index-skeleton {
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 14px;
}

.index-skeleton i,
.chart-skeleton i {
  display: block;
  border-radius: 5px;
  background: linear-gradient(90deg, #edf2f7 25%, #f7f9fc 37%, #edf2f7 63%);
  background-size: 400% 100%;
  animation: skeleton-shimmer 1.35s ease infinite;
}

.index-skeleton i:nth-child(1) { width: 58%; height: 13px; }
.index-skeleton i:nth-child(2) { width: 76%; height: 29px; }
.index-skeleton i:nth-child(3) { width: 34%; height: 13px; }

.sector-skeleton .sector-columns {
  min-height: 355px;
  border-radius: 10px;
  background:
    repeating-linear-gradient(to bottom, transparent 0, transparent 47px, #edf1f5 48px),
    linear-gradient(90deg, #edf2f7 25%, #f7f9fc 37%, #edf2f7 63%);
  background-size: 100% 48px, 400% 100%;
  animation: skeleton-shimmer 1.35s ease infinite;
}

.sector-skeleton .sector-block {
  visibility: hidden;
}

.chart-skeleton {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  height: 310px;
  padding: 30px;
  border-radius: 12px;
  background: #f8fbff;
}

.chart-skeleton i {
  flex: 1;
}

.chart-skeleton i:nth-child(1) { height: 28%; }
.chart-skeleton i:nth-child(2) { height: 46%; }
.chart-skeleton i:nth-child(3) { height: 36%; }
.chart-skeleton i:nth-child(4) { height: 68%; }
.chart-skeleton i:nth-child(5) { height: 54%; }

@media (prefers-reduced-motion: reduce) {
  .detail-skeleton *,
  .news-skeleton-card *,
  .page-skeleton-loading *,
  .index-skeleton *,
  .sector-skeleton *,
  .chart-skeleton * {
    animation: none !important;
  }
}

.history-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 14px;
  margin: 0 0 12px;
  color: var(--muted);
  font-size: 13px;
}

.watch-toolbar,
.watch-groups {
  display: flex;
  align-items: center;
  gap: 8px;
}

.watch-toolbar {
  justify-content: space-between;
  margin: 0 0 16px;
}

.watch-groups {
  flex-wrap: wrap;
}

.watch-order-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: -6px;
  color: var(--muted);
  font-size: 12px;
}

.hero-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 24px;
  padding: 28px 32px;
  border-radius: 24px;
  background: var(--panel-soft);
  color: #fff;
  box-shadow: 0 18px 48px rgba(12, 56, 112, 0.15);
}

.eyebrow {
  margin: 0 0 10px;
  font-size: 12px;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  opacity: 0.78;
}

h1 {
  margin: 0;
  font-size: 34px;
}

.hero-copy {
  max-width: 700px;
  margin: 12px 0 0;
  line-height: 1.7;
  opacity: 0.92;
}

.hero-actions {
  display: flex;
  gap: 12px;
}

.stats-row {
  margin: 18px 0;
}

.home-stats-row > .el-col {
  display: flex;
}

.home-market-row {
  margin-bottom: 18px;
}

.home-market-row > .el-col {
  display: flex;
}

.home-market-row .panel-card {
  width: 100%;
  margin-bottom: 0;
}

@media (min-width: 769px) {
  .home-market-row,
  .home-content-row {
    display: flex;
    flex-wrap: wrap;
    align-items: stretch;
  }

  .home-market-row > .el-col,
  .home-content-row > .el-col {
    float: none;
  }

  .home-stats-row .stat-card {
    width: 100%;
    min-height: 136px;
  }

  .home-market-row > .el-col,
  .home-content-row > .el-col {
    display: flex;
  }

  .home-market-row .panel-card,
  .home-content-row .panel-card {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
  }

  .home-market-row .panel-card ::v-deep .el-card__body {
    display: flex;
    flex: 1;
    flex-direction: column;
  }

  .home-temperature-card ::v-deep .el-card__body {
    justify-content: space-between;
  }

  .home-content-row .panel-card {
    height: 410px;
  }

  .home-content-row .home-news-card ::v-deep .el-card__body {
    overflow-y: auto;
  }

  .home-content-row .home-news-card .news-item {
    padding: 10px 0;
  }

  .home-content-row .home-news-card .news-body {
    display: -webkit-box;
    overflow: hidden;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }
}

.temperature-main {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  padding: 4px 0 18px;
  border-bottom: 1px solid #eef3f8;
}

.temperature-label {
  display: block;
  margin-bottom: 7px;
  color: var(--muted);
  font-size: 12px;
}

.temperature-main strong {
  font-size: 30px;
  letter-spacing: -0.04em;
}

.temperature-rate {
  font-size: 20px;
  font-weight: 700;
}

.temperature-metrics {
  display: grid;
  gap: 10px;
  padding-top: 16px;
  color: #62758e;
  font-size: 12px;
}

.temperature-skeleton {
  display: grid;
  gap: 12px;
}

.temperature-skeleton i {
  display: block;
  height: 18px;
  border-radius: 5px;
  background: linear-gradient(90deg, #edf2f7 25%, #f7f9fc 37%, #edf2f7 63%);
  background-size: 400% 100%;
  animation: skeleton-shimmer 1.35s ease infinite;
}

.temperature-skeleton i:first-child {
  width: 56%;
  height: 38px;
}

.temperature-skeleton i:last-child {
  width: 72%;
}

.stat-card,
.panel-card {
  border-radius: 20px;
  border: 1px solid var(--border);
  background: var(--panel);
  box-shadow: 0 8px 28px rgba(16, 35, 63, 0.06);
}

.stat-card {
  box-sizing: border-box;
  width: 100%;
  min-height: 128px;
  padding: 22px;
}

.stat-label {
  font-size: 13px;
  color: var(--muted);
}

.stat-value {
  margin-top: 8px;
  font-size: 30px;
  font-weight: 700;
}

.stat-foot {
  margin-top: 10px;
  font-size: 12px;
  color: var(--muted);
}

.stat-card--timestamp .stat-value {
  font-size: 21px;
  letter-spacing: -0.02em;
  white-space: nowrap;
}

.stat-card--clickable {
  cursor: pointer;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
}

.stat-card--clickable:hover,
.stat-card--clickable:focus-visible {
  border-color: var(--accent);
  box-shadow: 0 12px 32px rgba(16, 35, 63, 0.12);
  transform: translateY(-2px);
  outline: none;
}

.stat-card-hint {
  float: right;
  color: var(--accent);
}

.pnl-trend-toolbar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 14px;
  margin-bottom: 14px;
}

.pnl-trend-toolbar-label {
  font-size: 13px;
  color: var(--muted);
}

.pnl-trend-chart {
  width: 100%;
  height: 380px;
}

.pnl-trend-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  margin-top: 10px;
  font-size: 12px;
  color: var(--muted);
}

.pnl-trend-skeleton {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 380px;
  justify-content: center;
}

.pnl-trend-skeleton i {
  display: block;
  height: 18px;
  border-radius: 10px;
  background: linear-gradient(90deg, rgba(16, 35, 63, 0.06), rgba(16, 35, 63, 0.12), rgba(16, 35, 63, 0.06));
  background-size: 200% 100%;
  animation: pnlTrendShimmer 1.3s ease-in-out infinite;
}

.pnl-trend-skeleton i:nth-child(2) { height: 46px; }
.pnl-trend-skeleton i:nth-child(3) { height: 68px; }
.pnl-trend-skeleton i:nth-child(4) { height: 34px; }

@keyframes pnlTrendShimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.panel-card {
  margin-bottom: 18px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.panel-tip {
  font-size: 12px;
  color: var(--muted);
}

.panel-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.form-control {
  width: 100%;
}

.market-source {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.3;
  color: var(--muted);
}

.news-item {
  padding: 14px 0;
  border-bottom: 1px solid #eef3f8;
}

.news-item:last-child {
  border-bottom: 0;
}

.news-grid .el-col {
  margin-bottom: 18px;
}

.news-source-card {
  height: calc(100% - 18px);
}

.news-skeleton-card .el-card__header {
  min-height: 51px;
}

.news-skeleton-item {
  padding: 14px 0;
  border-bottom: 1px solid #eef3f8;
}

.news-skeleton-item:last-child {
  border-bottom: 0;
}

.news-skeleton-item i,
.news-skeleton-source,
.news-skeleton-count {
  display: block;
  border-radius: 4px;
  background: linear-gradient(90deg, #edf2f7 25%, #f7f9fc 37%, #edf2f7 63%);
  background-size: 400% 100%;
  animation: skeleton-shimmer 1.35s ease infinite;
}

.news-skeleton-source {
  width: 96px;
  height: 15px;
}

.news-skeleton-count {
  width: 56px;
  height: 12px;
}

.news-skeleton-title {
  width: 78%;
  height: 14px;
}

.news-skeleton-time {
  width: 34%;
  height: 11px;
  margin-top: 10px;
}

.news-skeleton-body {
  width: 100%;
  height: 11px;
  margin-top: 10px;
}

.news-skeleton-body.short {
  width: 62%;
  margin-top: 7px;
}

.news-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.news-title,
.sector-name {
  font-weight: 600;
}

.news-meta,
.sector-reason {
  margin-top: 8px;
  font-size: 12px;
  color: var(--muted);
}

.news-body,
.news-impact {
  margin-top: 8px;
  line-height: 1.7;
}

.news-link {
  display: inline-block;
  margin-top: 8px;
  color: #0e6fb4;
  font-size: 12px;
  text-decoration: none;
}

.news-link:hover {
  text-decoration: underline;
}

.home-sector-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 26px;
}

.home-sector-list h3 {
  margin: 0 0 8px;
  color: #18324d;
  font-size: 15px;
}

.home-sector-item {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) auto;
  align-items: center;
  gap: 8px;
  min-height: 38px;
  border-bottom: 1px solid rgba(105, 130, 158, 0.13);
}

.home-sector-item:last-child {
  border-bottom: 0;
}

.home-sector-rank {
  width: 24px;
  height: 24px;
  border-radius: 8px;
  background: #edf4fb;
  color: #607891;
  font-size: 12px;
  line-height: 24px;
  text-align: center;
}

.home-sector-name {
  overflow: hidden;
  color: #243b53;
  font-size: 14px;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.home-sector-item strong {
  font-size: 14px;
  font-weight: 600;
}

.home-sector-skeleton {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px 26px;
}

.home-sector-skeleton i {
  height: 26px;
  border-radius: 8px;
  background: linear-gradient(90deg, #eef3f8 25%, #f8fafc 45%, #eef3f8 65%);
  background-size: 300% 100%;
  animation: skeleton-loading 1.4s ease infinite;
}

.sector-columns {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.sector-block h3 {
  margin: 0 0 14px;
}

.sector-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid #eef3f8;
}

.sector-rank {
  display: grid;
  flex: 0 0 22px;
  width: 22px;
  height: 22px;
  place-items: center;
  border-radius: 50%;
  background: #eef4fa;
  color: var(--muted);
  font-size: 12px;
  font-weight: 700;
}

.sector-content {
  flex: 1;
}

.positive {
  color: var(--danger);
}

.negative {
  color: var(--success);
}

.neutral {
  color: var(--muted);
}

.danger-text {
  color: var(--danger);
}

@media (max-width: 1200px) {
  .hero-card {
    flex-direction: column;
    align-items: flex-start;
  }
}

@media (max-width: 768px) {
  .app-shell {
    padding: 12px;
  }

  .hero-card {
    padding: 20px;
    border-radius: 18px;
  }

  h1 {
    font-size: 28px;
  }

  .page-heading h2 {
    font-size: 23px;
  }

  .history-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .watch-toolbar {
    align-items: flex-start;
    flex-direction: column;
  }

  .history-toolbar .el-date-editor {
    width: 100%;
  }

  .sector-columns {
    grid-template-columns: 1fr;
  }

  .home-sector-columns,
  .home-sector-skeleton {
    grid-template-columns: 1fr;
  }

  .home-sector-columns {
    gap: 18px;
  }

  .hero-actions {
    width: 100%;
    flex-wrap: wrap;
  }

  .workspace-nav {
    align-items: flex-start;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 16px;
    padding: 10px 12px;
  }

  .workspace-menu {
    order: 3;
    width: 100%;
    overflow-x: auto;
    white-space: nowrap;
  }

  .workspace-menu.el-menu--horizontal > .el-menu-item {
    float: none;
    display: inline-block;
    padding: 0 13px;
  }

  .refresh-fab {
    right: 16px;
    bottom: 20px;
    width: 50px;
    height: 50px;
    font-size: 21px;
  }

  .privacy-fab {
    right: 16px;
    bottom: 82px;
    width: 46px;
    height: 46px;
    font-size: 20px;
  }

  .page-heading {
    align-items: flex-start;
    flex-direction: column;
  }

  .panel-header,
  .panel-actions {
    align-items: flex-start;
    gap: 8px;
  }

  .panel-header {
    flex-direction: column;
  }

  .panel-actions {
    width: 100%;
    justify-content: space-between;
  }

  .stats-row {
    margin: 14px 0;
  }

  .stats-row .el-col {
    margin-bottom: 12px;
  }

  .home-market-row {
    margin-bottom: 2px;
  }

  .home-market-row .el-col {
    margin-bottom: 12px;
  }

  .temperature-main strong {
    font-size: 26px;
  }

  .market-index-row .el-col {
    margin-bottom: 0;
    padding-right: 4px !important;
    padding-left: 4px !important;
  }

  .market-index-row {
    margin-right: -4px !important;
    margin-left: -4px !important;
  }

  .market-index-row .index-card {
    min-height: 124px;
    padding: 14px 8px 12px;
  }

  .market-index-row .index-label {
    min-height: 30px;
    overflow: visible;
    font-size: 12px;
    line-height: 1.35;
    white-space: normal;
  }

  .market-index-row .index-name {
    display: -webkit-box;
    overflow: hidden;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
  }

  .market-index-row .index-code {
    display: none;
  }

  .market-index-row .index-value {
    margin: 8px 0 7px;
    font-size: clamp(16px, 4.4vw, 22px);
    letter-spacing: -0.025em;
    white-space: nowrap;
  }

  .stat-card,
  .index-card {
    min-height: auto;
    padding: 18px;
    border-radius: 16px;
  }

  .stat-value,
  .index-value {
    font-size: 25px;
  }

  .panel-card {
    border-radius: 16px;
  }

  .panel-card ::v-deep .el-card__header,
  .panel-card ::v-deep .el-card__body {
    padding: 14px;
  }

  .panel-card ::v-deep .el-table__body-wrapper {
    overflow-x: auto;
  }

  .panel-card ::v-deep .el-table .cell {
    white-space: nowrap;
  }

  .chart-meta {
    gap: 8px 14px;
  }

  .intraday-chart {
    height: 230px;
  }

  ::v-deep .el-dialog {
    width: calc(100vw - 24px) !important;
    margin-top: 8vh !important;
  }

  .news-head {
    align-items: flex-start;
  }
}
</style>
