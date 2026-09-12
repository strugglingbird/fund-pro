<template>
  <div>
    <section :class="{ 'page-skeleton-loading': initialLoading }">
      <section class="hero-card">
        <div>
          <p class="eyebrow">
            Quant Workbench
          </p>
          <h1>量化工作台</h1>
          <p class="hero-copy">
            持仓估值、市场脉搏与财经要闻，集中在一个清爽的投资工作界面。
          </p>
        </div>
        <div class="hero-actions">
          <el-button @click="$emit('navigate', 'holdings')">
            查看持仓收益
          </el-button>
        </div>
      </section>
      <metric-rail
        :items="statCards"
        item-key="label"
        class="stats-row home-stats-row"
      >
        <template #default="{ item }">
          <div
            class="stat-card"
            :class="{ 'stat-card--timestamp': item.isTimestamp }"
          >
            <div class="stat-label">
              {{ item.label }}
            </div><div
              class="stat-value"
              :class="item.className"
            >
              {{ item.value }}
            </div><div class="stat-foot">
              {{ item.foot }}
            </div>
          </div>
        </template>
      </metric-rail>
      <el-row
        :gutter="18"
        class="home-market-row"
      >
        <el-col :xs="24">
          <el-card
            shadow="never"
            class="panel-card home-temperature-card"
          >
            <template #header>
              <div class="panel-header">
                <span>市场温度</span><span class="panel-tip">{{ homeMarketTemperature.breadth.data_date ? `${homeMarketTemperature.breadth.data_date} ${homeMarketTemperature.breadth.is_realtime ? '实时' : '收盘'}` : '内地核心指数' }}</span>
              </div>
            </template><template v-if="isMarketInitialLoading">
              <div class="temperature-skeleton">
                <i /><i /><i />
              </div>
            </template><template v-else>
              <div class="temperature-main">
                <div><span class="temperature-label">市场情绪</span><strong :class="homeMarketTemperature.className">{{ homeMarketTemperature.label }}</strong></div><div
                  :class="homeMarketTemperature.className"
                  class="temperature-rate"
                >
                  {{ formatPercent(homeMarketTemperature.averageChange) }}
                </div>
              </div><div class="temperature-metrics">
                <span>主要指数 {{ homeMarketTemperature.rising }} 涨 {{ homeMarketTemperature.falling }} 跌</span><span v-if="homeMarketTemperature.breadth.available">全市 {{ homeMarketTemperature.breadth.rising }} 涨 {{ homeMarketTemperature.breadth.falling }} 跌</span><span v-else>全市涨跌 暂无有效数据</span><span>行业领涨 {{ homeMarketTemperature.leader.name || '--' }} {{ formatPercent(homeMarketTemperature.leader.change_rate) }}</span><span>行业领跌 {{ homeMarketTemperature.laggard.name || '--' }} {{ formatPercent(homeMarketTemperature.laggard.change_rate) }}</span>
              </div>
            </template>
          </el-card>
        </el-col>
      </el-row>
      <el-row
        :gutter="18"
        class="home-content-row"
      >
        <el-col
          :xs="24"
          :lg="14"
        >
          <el-card
            shadow="never"
            class="panel-card home-sector-card"
          >
            <template #header>
              <div class="panel-header">
                <span>板块排行</span><el-button
                  type="primary"
                  link
                  @click="$emit('navigate', 'market')"
                >
                  完整复盘
                </el-button>
              </div>
            </template>
            <div
              v-if="initialLoading"
              class="home-sector-skeleton"
            >
              <i
                v-for="row in 5"
                :key="row"
              />
            </div>
            <div
              v-else-if="dashboard.sectors.gainers.length || dashboard.sectors.losers.length"
              class="home-sector-columns"
            >
              <div class="home-sector-list">
                <h3>涨幅榜</h3><div
                  v-for="(item, index) in dashboard.sectors.gainers.slice(0, 5)"
                  :key="item.name"
                  class="home-sector-item"
                >
                  <span class="home-sector-rank">{{ index + 1 }}</span><span class="home-sector-name">{{ item.name }}</span><strong class="positive">{{ formatPercent(item.change_rate) }}</strong>
                </div>
              </div>
              <div class="home-sector-list">
                <h3>跌幅榜</h3><div
                  v-for="(item, index) in dashboard.sectors.losers.slice(0, 5)"
                  :key="item.name"
                  class="home-sector-item"
                >
                  <span class="home-sector-rank">{{ index + 1 }}</span><span class="home-sector-name">{{ item.name }}</span><strong class="negative">{{ formatPercent(item.change_rate) }}</strong>
                </div>
              </div>
            </div>
            <div
              v-else
              class="empty-state"
            >
              暂无板块排行，请稍后刷新。
            </div>
          </el-card>
        </el-col>
        <el-col
          :xs="24"
          :lg="10"
        >
          <el-card
            shadow="never"
            class="panel-card news-source-card home-news-card"
          >
            <template #header>
              <div class="panel-header">
                <span>最新消息</span><el-button
                  type="primary"
                  link
                  @click="$emit('navigate', 'news')"
                >
                  更多
                </el-button>
              </div>
            </template>
            <template v-if="newsLoading && !homeNewsItems.length">
              <div
                v-for="row in 3"
                :key="row"
                class="news-skeleton-item"
              >
                <i class="news-skeleton-title" /><i class="news-skeleton-time" /><i class="news-skeleton-body" /><i class="news-skeleton-body short" />
              </div>
            </template><template v-else-if="homeNewsItems.length">
              <div
                v-for="item in homeNewsItems.slice(0, 3)"
                :key="item.id"
                class="news-item"
              >
                <div class="news-head">
                  <span class="news-title">{{ item.title }}</span>
                </div><div class="news-meta">
                  {{ item.published_at }}
                </div><div class="news-body">
                  {{ item.summary }}
                </div><a
                  v-if="item.url"
                  class="news-link"
                  :href="item.url"
                  target="_blank"
                  rel="noopener noreferrer"
                >查看原文</a>
              </div>
            </template><div
              v-else
              class="empty-state home-news-empty"
            >
              暂无实时快讯，请稍后刷新。
            </div>
          </el-card>
        </el-col>
      </el-row>
    </section>
  </div>
</template>

<script>
import numberFormat from '../mixins/numberFormat'
import { formatPercent, profitClass } from '../utils/format'
import MetricRail from './MetricRail.vue'

const EMPTY_BREADTH = {
  available: false,
  rising: 0,
  falling: 0,
  limit_up: 0,
  limit_down: 0,
  data_date: null,
  is_realtime: false
}

export default {
  name: 'HomePanel',
  components: { MetricRail },
  mixins: [numberFormat],
  props: {
    dashboard: { type: Object, required: true },
    newsFeed: { type: Object, required: true },
    newsLoading: Boolean,
    marketIndices: { type: Array, default: () => [] },
    marketLoading: Boolean,
    initialLoading: Boolean,
    numbersVisible: Boolean
  },
  emits: ["navigate"],
  computed: {
    isMarketInitialLoading() {
      return this.marketLoading && !this.marketIndices.length
    },
    homeNewsItems() {
      return this.newsFeed.items || []
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
          className: profitClass(this.dashboard.portfolio.total_estimated_pnl)
        },
        {
          label: '消息数量',
          value: String(this.newsFeed.total_count || 0),
          foot: '多路财经快讯实时聚合',
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
    homeMarketTemperature() {
      const mainland = this.marketIndices.filter(item => (item.market || 'cn') === 'cn')
      const changes = mainland.map(item => Number(item.change_rate)).filter(Number.isFinite)
      const averageChange = changes.length ? changes.reduce((total, value) => total + value, 0) / changes.length : 0
      const leader = this.dashboard.sectors.gainers[0] || {}
      const laggard = this.dashboard.sectors.losers[0] || {}
      const breadth = this.dashboard.market_breadth || EMPTY_BREADTH
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
    }
  },
  methods: {
    formatPercent,
    profitClass
  }
}
</script>
