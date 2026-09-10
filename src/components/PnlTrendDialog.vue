<template>
  <div>
    <el-dialog title="当日收益率走势 · 指数对比" :visible.sync="dialogVisible" width="860px" @opened="renderPnlTrendChart">
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
import * as echarts from 'echarts'
import { fetchPortfolioIntradayPnl } from '../api/dashboard'

const DEFAULT_INDEX_CODES = ['sh000001', 'sz399006', 'sh000688']
const INDEX_COLORS = { sh000001: '#f0a13c', sz399006: '#7c5cff', sh000688: '#2aa7c4' }

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
  name: 'PnlTrendDialog',
  props: {
    visible: Boolean
  },
  data() {
    return {
      pnlTrendLoading: false,
      pnlTrendError: '',
      pnlTrend: emptyPnlTrend(),
      pnlTrendIndexCodes: DEFAULT_INDEX_CODES.slice()
    }
  },
  computed: {
    dialogVisible: {
      get() { return this.visible },
      set(value) { this.$emit('update:visible', value) }
    }
  },
  watch: {
    visible(open) {
      if (open) this.loadPnlTrend()
      else this.disposeChart()
    },
    pnlTrendIndexCodes() {
      this.$nextTick(() => this.renderPnlTrendChart())
    }
  },
  mounted() {
    window.addEventListener('resize', this.resizeChart)
  },
  beforeDestroy() {
    window.removeEventListener('resize', this.resizeChart)
    this.disposeChart()
  },
  methods: {
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
      if (!this.visible || this.pnlTrendLoading || !container || !this.pnlTrend.portfolio.available) return
      if (this.trendInstance && this.trendInstance.getDom() !== container) {
        this.trendInstance.dispose()
        this.trendInstance = null
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
          lineStyle: { color: INDEX_COLORS[item.code] || '#8394aa', width: 1.6 }
        })
      })

      this.trendInstance = this.trendInstance || echarts.init(container)
      this.trendInstance.setOption({
        animationDuration: 350,
        backgroundColor: '#f8fbff',
        grid: { left: 60, right: 54, top: 52, bottom: 48 },
        legend: { top: 8, textStyle: { color: '#6b7a90' }, data: series.map(item => item.name) },
        tooltip: {
          trigger: 'axis',
          backgroundColor: 'rgba(16, 35, 63, 0.92)',
          borderWidth: 0,
          textStyle: { color: '#fff' },
          formatter: params => {
            const lines = params
              .filter(item => item.value !== null && item.value !== undefined)
              .map(item => `${item.marker}${item.seriesName}：${Number(item.value).toFixed(2)}%`)
            return [params[0].axisValue, ...lines].join('<br/>')
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
      this.trendInstance.resize()
    },
    resizeChart() {
      if (this.trendInstance) this.trendInstance.resize()
    },
    disposeChart() {
      if (this.trendInstance) {
        this.trendInstance.dispose()
        this.trendInstance = null
      }
    }
  }
}
</script>
