<template>
  <div class="app-shell">
    <!-- 下拉刷新指示器：静止时高度为 0，完全不占空间 -->
    <div
      class="pull-refresh"
      :class="{ 'is-animating': pullAnimating, 'is-refreshing': pullRefreshing }"
      :style="{ height: `${pullDistance}px` }"
    >
      <el-icon class="pull-refresh__icon">
        <Refresh />
      </el-icon><span>{{ pullRefreshLabel }}</span>
    </div>
    <header class="workspace-nav">
      <div class="brand-mark">
        <span>量化工作台</span><small>Quant Workbench</small>
      </div>
      <el-menu
        :default-active="activeMenu"
        mode="horizontal"
        :ellipsis="false"
        class="workspace-menu"
        @select="onMenuSelect"
      >
        <el-menu-item index="home">
          首页
        </el-menu-item>
        <el-menu-item index="holdings">
          持仓收益
        </el-menu-item>
        <el-menu-item index="watchlist">
          自选
        </el-menu-item>
        <el-menu-item index="market">
          市场指数
        </el-menu-item>
        <el-menu-item index="news">
          消息快讯
        </el-menu-item>
      </el-menu>
    </header>

    <floating-actions
      :loading="loading"
      :refreshing="refreshingAll"
      :numbers-visible="holdingsNumbersVisible"
      @refresh="refreshAll"
      @toggle-numbers="holdingsNumbersVisible = !holdingsNumbersVisible"
    />

    <home-panel
      v-if="activeMenu === 'home'"
      :dashboard="dashboard"
      :news-feed="newsFeed"
      :news-loading="newsLoading"
      :market-indices="marketIndices"
      :market-loading="marketIndicesLoading"
      :initial-loading="isDashboardInitialLoading"
      :numbers-visible="holdingsNumbersVisible"
      @navigate="onMenuSelect"
    />
    <holdings-panel
      v-else-if="activeMenu === 'holdings'"
      :dashboard="dashboard"
      :initial-loading="isDashboardInitialLoading"
      :numbers-visible="holdingsNumbersVisible"
      @open-chart="openIntradayChart"
      @open-pnl-trend="pnlTrendDialogVisible = true"
      @create="createDialogVisible = true"
      @edit="openEditHolding"
      @remove="removeHolding"
    />
    <watchlist-panel
      v-else-if="activeMenu === 'watchlist'"
      v-model:category="watchlistCategory"
      v-model:selected-group-id="selectedWatchGroupId"
      :watchlist="watchlist"
      :loading="watchlistLoading"
      :loaded="watchlistLoaded"
      @reload="loadWatchlist"
      @ensure-group="ensureWatchGroup"
      @create-group="createWatchGroup"
      @delete-group="deleteWatchGroup"
      @move-group="moveCurrentWatchGroup"
      @add-item="openWatchItemDialog"
      @delete-item="deleteWatchItem"
      @open-chart="openIntradayChart"
    />
    <market-panel
      v-else-if="activeMenu === 'market'"
      v-model:tab="activeMarketTab"
      :market-indices="marketIndices"
      :loading="marketIndicesLoading"
      :updated-at="indicesUpdatedAt"
      :dashboard="dashboard"
      :initial-loading="isDashboardInitialLoading"
      @reload="loadMarketIndices"
      @open-chart="openIndexIntradayChart"
    />
    <news-panel
      v-else
      :news-feed="newsFeed"
      :loading="newsLoading"
      @reload="loadNews"
    />

    <nav
      class="mobile-tabbar"
      aria-label="主导航"
    >
      <button
        v-for="tab in mobileTabs"
        :key="tab.key"
        type="button"
        class="mobile-tabbar__item"
        :class="{ 'is-active': activeMenu === tab.key }"
        :aria-current="activeMenu === tab.key ? 'page' : null"
        @click="onMenuSelect(tab.key)"
      >
        <el-icon><component :is="tab.icon" /></el-icon><span>{{ tab.label }}</span>
      </button>
    </nav>

    <intraday-chart-dialog
      v-model:visible="intradayDialogVisible"
      :instrument="intradayInstrument"
      @add-watch="openFundHoldingWatch"
    />
    <pnl-trend-dialog v-model:visible="pnlTrendDialogVisible" />

    <create-holding-dialog
      v-model:visible="createDialogVisible"
      :saving="savingCreate"
      @submit="submitHolding"
    />
    <edit-holding-dialog
      v-model:visible="editDialogVisible"
      :holding="editTarget"
      :saving="savingEdit"
      @submit="submitHoldingEdit"
    />
    <watch-item-dialog
      v-model:visible="watchItemDialogVisible"
      :category="watchlistCategory"
      :groups="currentWatchGroups"
      :selected-group-id="selectedWatchGroupId"
      :saving="watchItemSaving"
      @submit="saveWatchItem"
    />
    <fund-holding-watch-dialog
      v-model:visible="fundHoldingWatchDialogVisible"
      :stock="fundHoldingToWatch"
      :groups="exchangeWatchGroups"
      :saving="fundHoldingWatchSaving"
      @submit="saveFundHoldingWatch"
    />
  </div>
</template>

<script>
import { markRaw } from 'vue'
import { Bell, DataLine, HomeFilled, Refresh, Star, TrendCharts } from '@element-plus/icons-vue'
import {
  deleteHolding,
  fetchDashboard,
  fetchMarketIndices,
  fetchNews,
  fetchWatchlist,
  moveWatchlistGroup,
  removeWatchlistGroup,
  removeWatchlistItem,
  saveHolding,
  saveWatchlistGroup,
  saveWatchlistItem,
  updateHolding
} from './api/dashboard'
import CreateHoldingDialog from './components/CreateHoldingDialog.vue'
import EditHoldingDialog from './components/EditHoldingDialog.vue'
import FloatingActions from './components/FloatingActions.vue'
import FundHoldingWatchDialog from './components/FundHoldingWatchDialog.vue'
import HoldingsPanel from './components/HoldingsPanel.vue'
import HomePanel from './components/HomePanel.vue'
import IntradayChartDialog from './components/IntradayChartDialog.vue'
import MarketPanel from './components/MarketPanel.vue'
import NewsPanel from './components/NewsPanel.vue'
import PnlTrendDialog from './components/PnlTrendDialog.vue'
import WatchItemDialog from './components/WatchItemDialog.vue'
import WatchlistPanel from './components/WatchlistPanel.vue'
import { registerBackButton } from './utils/backButton'
import { PULL_THRESHOLD, registerPullToRefresh } from './utils/pullToRefresh'

const REFRESH_INTERVAL_MS = 60000

// 刷新进行中时下拉指示器保持的高度（px）
const PULL_HOLD_HEIGHT = 52

// 点击即可切换脱敏的区域：汇总卡数值 + 移动端卡片里的数值。
// 排除 .stat-card--clickable（整卡可点会打开走势弹窗，点数值会两个动作打架）。
const MASK_TOGGLE_SELECTOR = [
  '.stat-card:not(.stat-card--clickable) .stat-value',
  '.data-card__cell strong',
  '.data-card__rate'
].join(', ')

// 移动端底部导航（与 workspace-menu 的 el-menu-item 一一对应）
const MOBILE_TABS = [
  { key: 'home', label: '首页', icon: markRaw(HomeFilled) },
  { key: 'holdings', label: '持仓', icon: markRaw(TrendCharts) },
  { key: 'watchlist', label: '自选', icon: markRaw(Star) },
  { key: 'market', label: '指数', icon: markRaw(DataLine) },
  { key: 'news', label: '快讯', icon: markRaw(Bell) }
]

// 打开时需要被物理返回键优先关闭的弹窗
const DISMISSABLE_DIALOGS = [
  'intradayDialogVisible',
  'pnlTrendDialogVisible',
  'createDialogVisible',
  'editDialogVisible',
  'watchItemDialogVisible',
  'fundHoldingWatchDialogVisible'
]

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
  news: { items: [], groups: [], total_count: 0 },
  sectors: { gainers: [], losers: [] },
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

const emptyNewsFeed = () => ({ items: [], groups: [], total_count: 0, source_label: '', generated_at: '' })

export default {
  name: 'App',
  components: {
    CreateHoldingDialog,
    EditHoldingDialog,
    FloatingActions,
    FundHoldingWatchDialog,
    HoldingsPanel,
    HomePanel,
    IntradayChartDialog,
    MarketPanel,
    NewsPanel,
    PnlTrendDialog,
    Refresh,
    WatchItemDialog,
    WatchlistPanel
  },
  data() {
    return {
      activeMenu: 'home',
      mobileTabs: MOBILE_TABS,
      unregisterBackButton: null,
      unregisterPullToRefresh: null,
      pullDistance: 0,
      pullAnimating: false,
      pullRefreshing: false,
      loading: false,
      refreshingAll: false,
      dashboardLoaded: false,
      holdingsNumbersVisible: false,
      dashboard: emptyDashboard(),
      newsFeed: emptyNewsFeed(),
      newsLoading: false,
      newsRefreshTimer: null,
      marketIndices: [],
      marketIndicesLoading: false,
      activeMarketTab: 'cn',
      indicesUpdatedAt: '',
      watchlist: { groups: [], items: [], generated_at: '' },
      watchlistLoading: false,
      watchlistLoaded: false,
      watchlistCategory: 'exchange',
      selectedWatchGroupId: null,
      watchItemDialogVisible: false,
      watchItemSaving: false,
      fundHoldingWatchDialogVisible: false,
      fundHoldingWatchSaving: false,
      fundHoldingToWatch: { name: '', code: '' },
      intradayDialogVisible: false,
      intradayInstrument: null,
      pnlTrendDialogVisible: false,
      createDialogVisible: false,
      savingCreate: false,
      editDialogVisible: false,
      editTarget: null,
      savingEdit: false
    }
  },
  computed: {
    isDashboardInitialLoading() {
      return this.loading && !this.dashboardLoaded
    },
    pullRefreshLabel() {
      if (this.pullRefreshing) return '正在刷新…'
      return this.pullDistance >= PULL_THRESHOLD ? '松开刷新' : '下拉刷新'
    },
    currentWatchGroups() {
      return this.watchlist.groups.filter(group => group.category === this.watchlistCategory)
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
    }
  },
  created() {
    this.bootstrap()
  },
  async mounted() {
    this.newsRefreshTimer = window.setInterval(() => this.autoRefreshData(), REFRESH_INTERVAL_MS)
    this.unregisterBackButton = await registerBackButton(() => this.handleNativeBack())
    this.unregisterPullToRefresh = registerPullToRefresh({
      onProgress: this.handlePullProgress,
      onRefresh: this.handlePullRefresh,
      canRefresh: () => !this.pullRefreshing && !this.refreshingAll
    })
    // 顶部不再有刷新/脱敏按钮：刷新走下拉手势，脱敏改为点击页面上的数值
    document.addEventListener('click', this.handleMaskToggle)
  },
  async beforeUnmount() {
    window.clearInterval(this.newsRefreshTimer)
    if (this.unregisterBackButton) this.unregisterBackButton()
    if (this.unregisterPullToRefresh) this.unregisterPullToRefresh()
    document.removeEventListener('click', this.handleMaskToggle)
  },
  methods: {
    async bootstrap(force = false) {
      await Promise.all([
        this.refreshDashboard(force),
        this.loadMarketIndices(force),
        this.loadNews(force),
        ...(force ? [this.loadWatchlist(true)] : [])
      ])
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
    async refreshAll() {
      if (this.refreshingAll) return
      this.refreshingAll = true
      try {
        await this.bootstrap(true)
      } finally {
        this.refreshingAll = false
      }
    },
    // 下拉过程中跟随手指撑开指示器；松手回弹时才要过渡，拖拽中不能有
    handlePullProgress(distance) {
      if (this.pullRefreshing) return
      this.pullAnimating = false
      this.pullDistance = distance
    },
    async handlePullRefresh() {
      if (this.pullRefreshing || this.refreshingAll) return
      this.pullRefreshing = true
      this.pullAnimating = true
      this.pullDistance = PULL_HOLD_HEIGHT
      try {
        await this.refreshAll()
      } finally {
        this.pullRefreshing = false
        this.pullDistance = 0
      }
    },
    // 点击数值切换脱敏。可点击范围限定在汇总卡数值与卡片数值上（见 MASK_TOGGLE_SELECTOR），
    // 不让整页数字都能点，避免列表里随手一划就切换
    handleMaskToggle(event) {
      const target = event.target && event.target.closest ? event.target.closest(MASK_TOGGLE_SELECTOR) : null
      if (!target) return
      this.holdingsNumbersVisible = !this.holdingsNumbersVisible
    },
    handleNativeBack() {
      if (this.closeTopDialog()) return true
      if (this.activeMenu !== 'home') {
        this.onMenuSelect('home')
        return true
      }
      return false
    },
    closeTopDialog() {
      const opened = DISMISSABLE_DIALOGS.find(flag => this[flag])
      if (!opened) return false
      this[opened] = false
      return true
    },
    onMenuSelect(menu) {
      this.activeMenu = menu
      if (menu === 'news') this.loadNews()
      if (menu === 'watchlist') this.loadWatchlist()
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
      } finally {
        this.watchlistLoading = false
      }
    },
    ensureWatchGroup() {
      const storedId = Number(localStorage.getItem(`quant-workbench-watchlist-${this.watchlistCategory}`))
      const groups = this.currentWatchGroups
      const target = groups.find(group => group.id === storedId) || groups[0]
      const selected = groups.find(group => group.id === this.selectedWatchGroupId)
      if (!selected) this.selectedWatchGroupId = target ? target.id : null
    },
    async createWatchGroup() {
      try {
        const { value } = await this.$prompt('请输入分组名称', '新建自选分组', { inputPattern: /\S+/, inputErrorMessage: '分组名称不能为空' })
        await saveWatchlistGroup({ name: value, category: this.watchlistCategory })
        await this.loadWatchlist(true)
        const created = this.currentWatchGroups.find(group => group.name === value)
        if (created) this.selectedWatchGroupId = created.id
      } catch (error) {
        if (error !== 'cancel' && error !== 'close') this.$message.error(error.response?.data?.error || '新建分组失败')
      }
    },
    async deleteWatchGroup() {
      const group = this.currentWatchGroups.find(item => item.id === this.selectedWatchGroupId)
      if (!group) return
      try {
        await this.$confirm(`删除“${group.name}”及其中所有自选？`, '确认删除', { type: 'warning' })
        await removeWatchlistGroup(group.id)
        this.selectedWatchGroupId = null
        await this.loadWatchlist(true)
      } catch (error) {
        if (error !== 'cancel' && error !== 'close') this.$message.error(error.response?.data?.error || '删除分组失败')
      }
    },
    async moveCurrentWatchGroup(direction) {
      if (!this.selectedWatchGroupId) return
      try {
        await moveWatchlistGroup(this.selectedWatchGroupId, direction)
        await this.loadWatchlist(true)
      } catch (error) {
        this.$message.error(error.response?.data?.error || '移动分组失败')
      }
    },
    openWatchItemDialog() {
      this.watchItemDialogVisible = true
    },
    async saveWatchItem(payload) {
      this.watchItemSaving = true
      try {
        await saveWatchlistItem(payload)
        this.watchItemDialogVisible = false
        await this.loadWatchlist(true)
      } catch (error) {
        this.$message.error(error.response?.data?.error || '添加自选失败')
      } finally {
        this.watchItemSaving = false
      }
    },
    async deleteWatchItem(id) {
      try {
        await removeWatchlistItem(id)
        await this.loadWatchlist(true)
      } catch (error) {
        this.$message.error(error.response?.data?.error || '删除自选失败')
      }
    },
    async openFundHoldingWatch(row) {
      if (!this.watchlistLoaded) await this.loadWatchlist()
      if (!this.exchangeWatchGroups.length) {
        this.$message.warning('请先在自选页面创建场内分组')
        return
      }
      this.fundHoldingToWatch = { name: row.name, code: row.code }
      this.fundHoldingWatchDialogVisible = true
    },
    async saveFundHoldingWatch(payload) {
      this.fundHoldingWatchSaving = true
      try {
        await saveWatchlistItem(payload)
        this.fundHoldingWatchDialogVisible = false
        await this.loadWatchlist(true)
        this.$message.success('已加入自选')
      } catch (error) {
        this.$message.error(error.response?.data?.error || '加入自选失败')
      } finally {
        this.fundHoldingWatchSaving = false
      }
    },
    openIntradayChart(instrument) {
      this.intradayInstrument = {
        name: instrument.name,
        code: instrument.code,
        asset_type: instrument.asset_type,
        previous_close: instrument.previous_close
      }
      this.intradayDialogVisible = true
    },
    openIndexIntradayChart(index) {
      this.openIntradayChart({
        name: index.name,
        code: index.intraday_symbol || index.code,
        asset_type: 'index',
        previous_close: index.previous_close
      })
    },
    async submitHolding(payload) {
      this.savingCreate = true
      try {
        const { data } = await saveHolding(payload)
        this.createDialogVisible = false
        this.$message.success(data && data.watchlist_added
          ? `持仓已保存，已自动加入自选「${data.watchlist_group_name}」`
          : '持仓已保存')
        await this.bootstrap()
        // The new holding may have been mirrored into the watchlist, refresh it
        // only when it is already loaded so the menu stays in sync.
        if (this.watchlistLoaded) await this.loadWatchlist(false, true)
      } catch (error) {
        this.$message.error(error.response?.data?.error || '新增持仓失败')
      } finally {
        this.savingCreate = false
      }
    },
    openEditHolding(holding) {
      this.editTarget = { ...holding }
      this.editDialogVisible = true
    },
    async submitHoldingEdit(payload) {
      this.savingEdit = true
      try {
        await updateHolding(payload.id, { quantity: payload.quantity, cost_price: payload.cost_price })
        this.editDialogVisible = false
        this.$message.success('持仓份额和成本价已更新')
        await this.bootstrap()
      } catch (error) {
        this.$message.error(error.response?.data?.error || '修改持仓失败')
      } finally {
        this.savingEdit = false
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
    }
  }
}
</script>
