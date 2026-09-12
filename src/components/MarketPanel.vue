<template>
  <div>
    <section>
      <div class="page-heading">
        <span class="panel-tip">{{ updatedAt || '--' }} 更新</span>
      </div>
      <el-tabs
        v-model="activeMarketTab"
        class="market-index-tabs"
        @tab-click="loadMarketIndices"
      >
        <el-tab-pane
          label="内地"
          name="cn"
        /><el-tab-pane
          label="港股"
          name="hk"
        /><el-tab-pane
          label="美股"
          name="us"
        />
      </el-tabs>
      <metric-rail
        v-if="isMarketInitialLoading"
        :items="skeletonCards"
        item-key="key"
        class="stats-row market-index-row"
      >
        <template #default>
          <div class="index-card index-skeleton">
            <i /><i /><i />
          </div>
        </template>
      </metric-rail><metric-rail
        v-else
        :items="visibleMarketIndices"
        item-key="code"
        class="stats-row market-index-row"
      >
        <template #default="{ item }">
          <div
            class="index-card index-card--clickable"
            role="button"
            tabindex="0"
            @click="openIndexIntradayChart(item)"
            @keyup.enter="openIndexIntradayChart(item)"
          >
            <div class="stat-label index-label">
              <span class="index-name">{{ item.name }}</span><span class="index-code"> · {{ item.code }}</span>
            </div><div class="index-value">
              {{ Number(item.current_price).toFixed(2) }}
            </div><div :class="profitClass(item.change_rate)">
              {{ formatPercent(item.change_rate) }}
            </div>
          </div>
        </template>
      </metric-rail>
      <div
        v-if="!loading && !marketIndices.length"
        class="empty-state"
      >
        暂无指数行情，请刷新后重试。
      </div>
      <el-card
        shadow="never"
        class="panel-card"
        :class="{ 'sector-skeleton': initialLoading }"
      >
        <template #header>
          <div class="panel-header">
            <span>板块复盘分析</span><span class="panel-tip">{{ dashboard.sectors.source_label }} · 前 10 名</span>
          </div>
        </template><div class="sector-columns">
          <div class="sector-block">
            <h3>涨幅居前</h3><div
              v-for="(item, index) in dashboard.sectors.gainers"
              :key="item.name"
              class="sector-item"
            >
              <div class="sector-rank">
                {{ index + 1 }}
              </div><div class="sector-content">
                <div class="sector-name">
                  {{ item.name }}
                </div><div class="sector-reason">
                  {{ item.reason }}
                </div>
              </div><div class="positive">
                {{ formatPercent(item.change_rate) }}
              </div>
            </div>
          </div><div class="sector-block">
            <h3>跌幅居前</h3><div
              v-for="(item, index) in dashboard.sectors.losers"
              :key="item.name"
              class="sector-item"
            >
              <div class="sector-rank">
                {{ index + 1 }}
              </div><div class="sector-content">
                <div class="sector-name">
                  {{ item.name }}
                </div><div class="sector-reason">
                  {{ item.reason }}
                </div>
              </div><div class="negative">
                {{ formatPercent(item.change_rate) }}
              </div>
            </div>
          </div>
        </div>
      </el-card>
    </section>
  </div>
</template>

<script>
import { formatPercent, profitClass } from '../utils/format'
import MetricRail from './MetricRail.vue'

const SKELETON_COUNT = 4

export default {
  name: 'MarketPanel',
  components: { MetricRail },
  props: {
    marketIndices: { type: Array, default: () => [] },
    loading: Boolean,
    updatedAt: { type: String, default: '' },
    dashboard: { type: Object, required: true },
    initialLoading: Boolean,
    tab: { type: String, default: 'cn' }
  },
  emits: ["update:tab","reload","open-chart"],
  computed: {
    activeMarketTab: {
      get() {
        return this.tab
      },
      set(value) {
        this.$emit('update:tab', value)
      }
    },
    isMarketInitialLoading() {
      return this.loading && !this.marketIndices.length
    },
    visibleMarketIndices() {
      return this.marketIndices.filter(item => (item.market || 'cn') === this.tab)
    },
    skeletonCards() {
      return Array.from({ length: SKELETON_COUNT }, (_, index) => ({ key: `skeleton-${index}` }))
    }
  },
  methods: {
    formatPercent,
    profitClass,
    loadMarketIndices() {
      this.$emit('reload')
    },
    openIndexIntradayChart(index) {
      this.$emit('open-chart', index)
    }
  }
}
</script>
