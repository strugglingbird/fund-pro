<template>
  <div>
    <el-dialog
      v-model="dialogVisible"
      :title="`${intradayChart.name || '标的'}${intradayChart.asset_type === 'fund' ? ' 基金详情' : ' 当日分时'}`"
      width="760px"
      @opened="renderIntradayChart"
    >
      <el-tabs
        v-if="intradayChart.asset_type === 'fund'"
        v-model="fundChartTab"
        class="fund-chart-tabs"
        @tab-click="handleFundChartTab"
      >
        <el-tab-pane
          label="估值走势"
          name="intraday"
        /><el-tab-pane
          label="业绩走势"
          name="performance"
        />
      </el-tabs>
      <div
        v-if="['fund', 'stock', 'etf'].includes(intradayChart.asset_type) && fundChartTab === 'intraday'"
        class="chart-meta"
      >
        <span>{{ intradayChart.asset_type === 'fund' ? '估值走势日期' : '价格走势日期' }}</span>
        <el-select
          v-model="estimateArchiveDate"
          size="small"
          :disabled="intradayLoading"
          @change="loadEstimateArchive"
        >
          <el-option
            :label="intradayChart.asset_type === 'fund' ? '当日实时估值' : '当日分时价格'"
            :value="liveValue"
          />
          <el-option
            v-for="day in estimateArchiveDates"
            :key="day"
            :label="day + ' 已归档'"
            :value="day"
          />
        </el-select>
        <span v-if="!estimateArchiveDates.length">收盘归档后可查看历史走势</span>
      </div>
      <div
        v-if="fundChartTab === 'intraday' && intradayLoading"
        class="chart-skeleton"
        aria-label="正在加载估值走势"
      >
        <i /><i /><i /><i /><i />
      </div>
      <template v-else-if="fundChartTab === 'intraday'">
        <template v-if="intradayChart.points.length">
          <div class="chart-meta">
            <span>昨收：{{ formatIntradayPrice(intradayChart.previous_close, intradayChart.asset_type) }}</span><span>最新：{{ formatIntradayPrice(intradayChart.points[intradayChart.points.length - 1].price, intradayChart.asset_type) }}</span><span>{{ intradayChart.source_label }}</span>
          </div>
          <div
            v-if="intradayChart.asset_type === 'fund'"
            class="chart-meta"
          >
            估值更新时间：{{ intradayChart.updated_at || '--' }}
          </div>
          <div
            ref="intradayChart"
            class="intraday-chart"
            role="img"
            aria-label="当日分时走势"
          />
        </template>
        <div
          v-else
          class="chart-loading"
        >
          暂无当日分时数据
        </div>
      </template>
      <div
        v-else-if="intradayChart.asset_type === 'fund'"
        class="fund-performance"
      >
        <div class="performance-ranges">
          <el-button
            v-for="item in [{ key: 'ONE', label: '近1个月' }, { key: 'THREE', label: '近3个月' }, { key: 'SIX', label: '近6个月' }, { key: 'ONE_YEAR', label: '近1年' }]"
            :key="item.key"
            type="primary"
            link
            :class="{ active: fundPerformanceInterval === item.key }"
            @click="loadFundPerformance(item.key)"
          >
            {{ item.label }}
          </el-button>
        </div><div
          v-if="fundPerformanceLoading"
          class="chart-skeleton"
        >
          <i /><i /><i /><i /><i />
        </div><div
          v-else-if="!fundPerformance.fund.length"
          class="chart-loading"
        >
          暂无该区间业绩走势数据
        </div><div
          v-else
          ref="fundPerformanceChart"
          class="fund-performance-chart"
        />
      </div>
      <el-tabs
        v-if="intradayChart.asset_type === 'fund'"
        v-model="fundDetailTab"
        class="fund-detail-tabs"
      >
        <el-tab-pane
          label="持仓股"
          name="holdings"
        >
          <div
            v-if="fundHoldingsLoading"
            class="detail-skeleton"
            aria-label="正在加载基金持仓股"
          >
            <div class="skeleton-meta">
              <i /><i />
            </div><div class="skeleton-table">
              <div class="skeleton-table-row skeleton-table-head">
                <i /><i /><i /><i />
              </div><div
                v-for="row in 6"
                :key="row"
                class="skeleton-table-row"
              >
                <i /><i /><i /><i />
              </div>
            </div>
          </div><div
            v-else-if="!fundHoldings.items.length"
            class="holding-loading"
          >
            暂无基金持仓数据
          </div><template v-else>
            <div class="holding-report">
              <span>{{ fundHoldings.report_date || '最新披露' }}</span><span>股票：{{ formatNullablePercent(fundHoldings.stock_position) }}</span>
            </div><div class="holding-meta">
              {{ fundHoldings.source_label }} · {{ fundHoldings.updated_at }} 更新
            </div><el-table
              :data="fundHoldings.items"
              size="small"
              max-height="280"
            >
              <el-table-column
                prop="code"
                label="代码"
                width="105"
              /><el-table-column
                prop="name"
                label="重仓股票"
                min-width="150"
              /><el-table-column
                prop="change_rate"
                label="涨跌幅"
                width="115"
              >
                <template #default="{ row }">
                  <span :class="profitClass(row.change_rate)">{{ formatSignedNullablePercent(row.change_rate) }}</span>
                </template>
              </el-table-column><el-table-column
                prop="weight"
                label="占净值比例"
                width="125"
              >
                <template #default="{ row }">
                  {{ formatNullablePercent(row.weight) }}
                </template>
              </el-table-column><el-table-column
                label="自选"
                width="80"
              >
                <template #default="{ row }">
                  <el-button
                    type="primary"
                    link
                    @click="openFundHoldingWatch(row)"
                  >
                    加入
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </template>
        </el-tab-pane><el-tab-pane
          label="历史净值"
          name="history"
        >
          <div class="history-toolbar">
            <span>自定义时间查询</span><el-date-picker
              v-model="fundHistoryRange"
              type="daterange"
              size="small"
              value-format="YYYY-MM-DD"
              range-separator="至"
              start-placeholder="开始日期"
              end-placeholder="结束日期"
              @change="loadFundHistory"
            />
          </div><div
            v-if="fundHistoryLoading"
            class="detail-skeleton"
            aria-label="正在加载历史净值"
          >
            <div class="skeleton-table">
              <div class="skeleton-table-row skeleton-table-head">
                <i /><i /><i /><i />
              </div><div
                v-for="row in 7"
                :key="row"
                class="skeleton-table-row"
              >
                <i /><i /><i /><i />
              </div>
            </div>
          </div><div
            v-else-if="!fundHistory.items.length"
            class="holding-loading"
          >
            暂无历史净值数据
          </div><template v-else>
            <div class="holding-meta">
              {{ fundHistory.source_label }} · {{ fundHistory.updated_at }} 更新
            </div><el-table
              :data="fundHistory.items"
              size="small"
              max-height="320"
            >
              <el-table-column
                prop="date"
                label="日期"
                min-width="130"
              /><el-table-column
                prop="unit_nav"
                label="单位净值"
                min-width="130"
              >
                <template #default="{ row }">
                  {{ formatFundNav(row.unit_nav) }}
                </template>
              </el-table-column><el-table-column
                prop="total_nav"
                label="累计净值"
                min-width="130"
              >
                <template #default="{ row }">
                  {{ formatFundNav(row.total_nav) }}
                </template>
              </el-table-column><el-table-column
                prop="daily_change_rate"
                label="日涨幅"
                min-width="120"
              >
                <template #default="{ row }">
                  <span :class="profitClass(row.daily_change_rate)">{{ formatSignedNullablePercent(row.daily_change_rate) }}</span>
                </template>
              </el-table-column>
            </el-table>
          </template>
        </el-tab-pane>
      </el-tabs>
    </el-dialog>
  </div>
</template>

<script>
import { markRaw } from 'vue'
import * as echarts from 'echarts'
import { fetchEstimateArchive, fetchFundHistory, fetchFundHoldings, fetchFundPerformance, fetchIntradayChart } from '../api/dashboard'
import {
  defaultHistoryRange,
  formatFundNav,
  formatIntradayPrice,
  formatNullablePercent,
  formatSignedNullablePercent,
  profitClass
} from '../utils/format'
import dialogModel from '../mixins/dialog'

const ARCHIVABLE_TYPES = ['fund', 'stock', 'etf']
// Element Plus 的 el-select 把空字符串视为"未选择"（显示占位符"请选择"），
// 所以"当日实时估值"选项必须用哨兵值，不能用 ''
const LIVE_DATE_VALUE = '__live__'

export default {
  name: 'IntradayChartDialog',
  mixins: [dialogModel],
  props: {
    visible: Boolean,
    instrument: { type: Object, default: null }
  },
  emits: ["update:visible","add-watch"],
  data() {
    return {
      activeCode: '',
      intradayLoading: false,
      intradayChart: { name: '', asset_type: '', previous_close: null, points: [], source_label: '' },
      estimateArchiveDates: [],
      estimateArchiveDate: LIVE_DATE_VALUE,
      fundChartTab: 'intraday',
      fundDetailTab: 'holdings',
      fundHoldings: { items: [], source_label: '', updated_at: '' },
      fundHoldingsLoading: false,
      fundHistory: { items: [], source_label: '', updated_at: '' },
      fundHistoryLoading: false,
      fundHistoryRange: defaultHistoryRange(),
      fundPerformance: { fund: [], index: [] },
      fundPerformanceLoading: false,
      fundPerformanceInterval: 'THREE'
    }
  },
  computed: {
    liveValue() {
      return LIVE_DATE_VALUE
    },
    chartScale() {
      const prices = this.intradayChart.points.map(item => Number(item.price)).filter(Number.isFinite)
      if (!prices.length) return { min: 0, max: 0 }
      const min = Math.min(...prices)
      const max = Math.max(...prices)
      const padding = Math.max((max - min) * 0.1, max * 0.002, 0.001)
      return { min: min - padding, max: max + padding }
    }
  },
  watch: {
    visible(open) {
      if (open) this.open()
      else this.disposeCharts()
    }
  },
  mounted() {
    window.addEventListener('resize', this.resizeCharts)
  },
  beforeUnmount() {
    window.removeEventListener('resize', this.resizeCharts)
    this.disposeCharts()
  },
  methods: {
    formatIntradayPrice,
    formatNullablePercent,
    formatSignedNullablePercent,
    formatFundNav,
    profitClass,
    open() {
      const instrument = this.instrument
      if (!instrument) return
      const isFund = instrument.asset_type === 'fund'
      this.activeCode = instrument.code
      this.estimateArchiveDate = LIVE_DATE_VALUE
      this.estimateArchiveDates = []
      this.fundChartTab = 'intraday'
      this.fundDetailTab = 'holdings'
      this.fundHoldings = { items: [], source_label: '', updated_at: '' }
      this.fundHistory = { items: [], source_label: '', updated_at: '' }
      this.fundPerformance = { fund: [], index: [] }
      this.fundHoldingsLoading = isFund
      this.fundHistoryLoading = isFund
      this.fundPerformanceLoading = isFund
      this.intradayChart = {
        name: instrument.name,
        asset_type: instrument.asset_type,
        previous_close: instrument.previous_close,
        points: [],
        source_label: ''
      }
      if (ARCHIVABLE_TYPES.includes(instrument.asset_type)) this.loadArchiveDates(instrument)
      this.loadChart(instrument)
      if (isFund) {
        this.loadFundHoldings(instrument.code)
        this.loadFundHistory()
        this.loadFundPerformance(this.fundPerformanceInterval)
      }
    },
    loadArchiveDates(instrument) {
      fetchEstimateArchive(instrument.code, '', instrument.asset_type)
        .then(({ data }) => {
          if (this.activeCode === instrument.code) this.estimateArchiveDates = data.dates || []
        })
        .catch(() => this.$message.warning('历史走势日期加载失败'))
    },
    async loadChart(instrument) {
      this.intradayLoading = true
      try {
        const { data } = await fetchIntradayChart(instrument.code, instrument.asset_type)
        this.intradayChart = { ...data, asset_type: instrument.asset_type }
      } catch (error) {
        this.$message.warning(error.response?.data?.error || '分时数据加载失败')
      } finally {
        this.intradayLoading = false
        this.$nextTick(() => this.renderIntradayChart())
      }
    },
    async loadEstimateArchive() {
      const code = this.activeCode
      const assetType = this.intradayChart.asset_type
      const selectedDay = this.estimateArchiveDate === LIVE_DATE_VALUE ? '' : this.estimateArchiveDate
      this.intradayLoading = true
      this.intradayChart = { ...this.intradayChart, points: [] }
      try {
        const { data } = selectedDay
          ? await fetchEstimateArchive(code, selectedDay, assetType)
          : await fetchIntradayChart(code, assetType)
        if (code === this.activeCode) this.intradayChart = { ...data, asset_type: assetType }
      } catch (error) {
        this.$message.warning(error.response?.data?.error || '估值走势加载失败')
      } finally {
        this.intradayLoading = false
        this.$nextTick(() => this.renderIntradayChart())
      }
    },
    async loadFundHoldings(code) {
      try {
        const { data } = await fetchFundHoldings(code)
        this.fundHoldings = data
      } catch (error) {
        this.$message.warning(error.response?.data?.error || '基金持仓加载失败')
      } finally {
        this.fundHoldingsLoading = false
      }
    },
    async loadFundHistory() {
      if (!this.activeCode || !Array.isArray(this.fundHistoryRange) || this.fundHistoryRange.length !== 2) return
      this.fundHistoryLoading = true
      try {
        const { data } = await fetchFundHistory(this.activeCode, ...this.fundHistoryRange)
        this.fundHistory = data
      } catch (error) {
        this.$message.warning(error.response?.data?.error || '历史净值加载失败')
      } finally {
        this.fundHistoryLoading = false
      }
    },
    async loadFundPerformance(interval) {
      if (!this.activeCode) return
      this.fundPerformanceInterval = interval
      this.fundPerformanceLoading = true
      try {
        const { data } = await fetchFundPerformance(this.activeCode, interval)
        this.fundPerformance = data
      } catch (error) {
        this.$message.warning(error.response?.data?.error || '业绩走势加载失败')
      } finally {
        this.fundPerformanceLoading = false
        this.$nextTick(() => this.renderFundPerformance())
      }
    },
    handleFundChartTab(tab) {
      if (tab.name === 'performance') this.$nextTick(() => this.renderFundPerformance())
      else this.$nextTick(() => this.renderIntradayChart())
    },
    openFundHoldingWatch(row) {
      this.$emit('add-watch', row)
    },
    renderIntradayChart() {
      const container = this.$refs.intradayChart
      if (!this.visible || this.intradayLoading || this.fundChartTab !== 'intraday' || !container || !this.intradayChart.points.length) return
      // v-if recreates the container after loading or switching chart tabs.
      if (this.intradayInstance && this.intradayInstance.getDom() !== container) {
        this.intradayInstance.dispose()
        this.intradayInstance = null
      }
      const points = this.intradayChart.points
      const previousClose = Number(this.intradayChart.previous_close)
      const lastPrice = Number(points[points.length - 1].price)
      const positive = lastPrice >= previousClose
      const lineColor = positive ? '#d64541' : '#0f9960'
      this.intradayInstance = this.intradayInstance || markRaw(echarts.init(container))
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
    renderFundPerformance() {
      const container = this.$refs.fundPerformanceChart
      if (!container || !this.fundPerformance.fund.length) return
      const fund = this.fundPerformance.fund
      const index = this.fundPerformance.index
      if (this.performanceInstance && this.performanceInstance.getDom() !== container) {
        this.performanceInstance.dispose()
        this.performanceInstance = null
      }
      this.performanceInstance = this.performanceInstance || markRaw(echarts.init(container))
      this.performanceInstance.setOption({
        tooltip: {
          trigger: 'axis',
          formatter: params => `${params[0].axisValue}<br/>${params.map(item => `${item.seriesName}：${Number(item.data).toFixed(2)}%`).join('<br/>')}`
        },
        legend: { data: ['本基金', '沪深300'] },
        grid: { left: 48, right: 22, top: 38, bottom: 28 },
        xAxis: {
          type: 'category',
          boundaryGap: false,
          data: fund.map(item => item.date.slice(5)),
          axisLabel: { interval: Math.max(Math.floor(fund.length / 4), 1) }
        },
        yAxis: { type: 'value', axisLabel: { formatter: '{value}%' }, splitLine: { lineStyle: { type: 'dashed' } } },
        series: [
          { name: '本基金', type: 'line', showSymbol: false, smooth: true, data: fund.map(item => item.rate), lineStyle: { color: '#6f9dff', width: 2 } },
          { name: '沪深300', type: 'line', showSymbol: false, smooth: true, data: index.map(item => item.rate), lineStyle: { color: '#f0a13c', width: 2 } }
        ]
      }, true)
      this.performanceInstance.resize()
    },
    resizeCharts() {
      if (this.intradayInstance) this.intradayInstance.resize()
      if (this.performanceInstance) this.performanceInstance.resize()
    },
    disposeCharts() {
      if (this.intradayInstance) {
        this.intradayInstance.dispose()
        this.intradayInstance = null
      }
      if (this.performanceInstance) {
        this.performanceInstance.dispose()
        this.performanceInstance = null
      }
    }
  }
}
</script>
