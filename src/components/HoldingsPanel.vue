<template>
  <div>
    <section :class="{ 'page-skeleton-loading': initialLoading }">
      <div class="page-heading">
        <div><h2>持仓收益</h2><p>股票、ETF 与场外基金的实时估值及收益分析。</p></div><div class="panel-actions">
          <el-button @click="seedDemoData">
            导入演示持仓
          </el-button>
        </div>
      </div>
      <metric-rail
        :items="summaryCards"
        item-key="key"
        class="stats-row holdings-summary"
      >
        <template #default="{ item }">
          <div
            class="stat-card"
            :class="{ 'stat-card--clickable': item.clickable }"
            :role="item.clickable ? 'button' : null"
            :tabindex="item.clickable ? 0 : null"
            :title="item.title"
            @click="handleCardClick(item)"
            @keyup.enter="handleCardClick(item)"
          >
            <div class="stat-label">
              {{ item.label }}
            </div><div
              class="stat-value"
              :class="item.valueClass"
            >
              {{ item.value }}
            </div><div
              class="stat-foot"
              :class="item.footClass"
            >
              {{ item.foot }}<span
                v-if="item.hint"
                class="stat-card-hint"
              >{{ item.hint }}</span>
            </div>
          </div>
        </template>
      </metric-rail>
      <el-card
        shadow="never"
        class="panel-card"
      >
        <template #header>
          <div class="panel-header">
            <span>当日持仓收益</span><div class="panel-actions">
              <span class="panel-tip">股票 / ETF / 场外基金</span><el-button
                type="primary"
                size="small"
                @click="openCreateHolding"
              >
                新增持仓
              </el-button>
            </div>
          </div>
        </template>
        <el-table
          :data="sortedHoldingPositions"
          stripe
          :class="{ 'table-skeleton table-skeleton-wide': initialLoading }"
        >
          <el-table-column
            prop="name"
            label="名称"
            min-width="170"
          >
            <template #default="{ row }">
              <el-button
                type="primary"
                link
                class="position-link"
                @click="openIntradayChart(row)"
              >
                {{ row.name }}
              </el-button>
            </template>
          </el-table-column><el-table-column
            prop="code"
            label="代码"
            width="110"
          >
            <template #default="{ row }">
              {{ formatHoldingCode(row.code) }}
            </template>
          </el-table-column><el-table-column
            prop="asset_type"
            label="类型"
            width="110"
          >
            <template #default="{ row }">
              <el-tag
                size="small"
                :type="assetTypeTag(row.asset_type)"
              >
                {{ assetTypeLabel(row.asset_type) }}
              </el-tag>
            </template>
          </el-table-column><el-table-column
            prop="quantity"
            label="持仓份额"
            width="110"
          >
            <template #default="{ row }">
              {{ formatHoldingQuantity(row.quantity) }}
            </template>
          </el-table-column><el-table-column
            prop="cost_price"
            label="成本价"
            width="110"
          >
            <template #default="{ row }">
              {{ formatHoldingCostPrice(row.cost_price) }}
            </template>
          </el-table-column><el-table-column
            prop="previous_close"
            label="昨日收盘价"
            width="110"
          >
            <template #default="{ row }">
              {{ formatHoldingNetValue(row.previous_close, row.asset_type) }}
            </template>
          </el-table-column><el-table-column
            prop="current_price"
            label="现价"
            width="110"
          >
            <template #default="{ row }">
              {{ formatHoldingNetValue(row.current_price, row.asset_type) }}
            </template>
          </el-table-column><el-table-column
            prop="estimated_price"
            label="估值"
            width="110"
          >
            <template #default="{ row }">
              {{ formatHoldingNetValue(row.estimated_price, row.asset_type) }}
            </template>
          </el-table-column><el-table-column
            prop="estimated_change_rate"
            label="预估涨幅"
            width="105"
          >
            <template #default="{ row }">
              <span :class="profitClass(row.estimated_change_rate)">{{ formatHoldingPercent(row.estimated_change_rate, true) }}</span>
            </template>
          </el-table-column><el-table-column
            prop="estimated_pnl"
            label="预估收益"
            width="120"
          >
            <template #default="{ row }">
              <span :class="profitClass(row.estimated_pnl)">{{ formatHoldingMoney(row.estimated_pnl, true) }}</span>
            </template>
          </el-table-column><el-table-column
            prop="daily_change_rate"
            label="当日涨幅"
            width="105"
          >
            <template #default="{ row }">
              <span :class="profitClass(row.daily_change_rate)">{{ formatHoldingPercent(row.daily_change_rate, true) }}</span>
            </template>
          </el-table-column><el-table-column
            prop="today_pnl"
            label="当日收益"
            width="120"
          >
            <template #default="{ row }">
              <span :class="profitClass(row.today_pnl)">{{ formatHoldingMoney(row.today_pnl, true) }}</span>
            </template>
          </el-table-column><el-table-column
            prop="holding_pnl"
            label="持有收益"
            width="120"
          >
            <template #default="{ row }">
              <span :class="profitClass(row.holding_pnl)">{{ formatHoldingMoney(row.holding_pnl) }}</span>
            </template>
          </el-table-column><el-table-column
            prop="holding_pnl_rate"
            label="持有收益率"
            width="110"
          >
            <template #default="{ row }">
              <span :class="profitClass(row.holding_pnl_rate)">{{ formatHoldingPercent(row.holding_pnl_rate) }}</span>
            </template>
          </el-table-column><el-table-column
            label="操作"
            width="130"
            fixed="right"
          >
            <template #default="{ row }">
              <el-button
                type="primary"
                link
                @click="openEditHolding(row)"
              >
                修改
              </el-button><el-button
                type="primary"
                link
                class="danger-text"
                @click="removeHolding(row.id)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </section>
  </div>
</template>

<script>
import numberFormat from '../mixins/numberFormat'
import { assetTypeLabel, assetTypeTag, profitClass, sortableRate } from '../utils/format'
import MetricRail from './MetricRail.vue'

export default {
  name: 'HoldingsPanel',
  components: { MetricRail },
  mixins: [numberFormat],
  props: {
    dashboard: { type: Object, required: true },
    initialLoading: Boolean,
    numbersVisible: Boolean
  },
  emits: ["open-chart","open-pnl-trend","create","edit","remove","seed-demo"],
  computed: {
    sortedHoldingPositions() {
      return [...this.dashboard.portfolio.positions].sort((left, right) => {
        const rate = sortableRate(left.estimated_change_rate)
        const other = sortableRate(right.estimated_change_rate)
        return rate === other ? 0 : other - rate
      })
    },
    summaryCards() {
      const portfolio = this.dashboard.portfolio
      return [
        {
          key: 'market-value',
          label: '持仓总市值',
          value: this.formatHoldingMoney(portfolio.total_market_value),
          foot: '按现价或最新估值计入'
        },
        {
          key: 'holding-pnl',
          label: '累计持仓收益',
          value: this.formatHoldingMoney(portfolio.total_holding_pnl),
          valueClass: profitClass(portfolio.total_holding_pnl),
          foot: `收益率 ${this.formatHoldingPercent(portfolio.total_holding_pnl_rate)}`,
          footClass: profitClass(portfolio.total_holding_pnl_rate)
        },
        {
          key: 'estimated-pnl',
          label: '累计今日预估收益',
          value: this.formatHoldingMoney(portfolio.total_estimated_pnl),
          valueClass: profitClass(portfolio.total_estimated_pnl),
          foot: `涨跌幅 ${this.formatHoldingPercent(portfolio.total_estimated_pnl_rate)}`,
          footClass: profitClass(portfolio.total_estimated_pnl_rate),
          clickable: true,
          hint: '走势对比',
          title: '查看当日收益走势与指数对比'
        },
        {
          key: 'today-pnl',
          label: '累计今日实际收益',
          value: this.formatHoldingMoney(portfolio.total_today_pnl),
          valueClass: profitClass(portfolio.total_today_pnl),
          foot: `涨跌幅 ${this.formatHoldingPercent(portfolio.total_today_pnl_rate)}`,
          footClass: profitClass(portfolio.total_today_pnl_rate)
        }
      ]
    }
  },
  methods: {
    profitClass,
    assetTypeLabel,
    assetTypeTag,
    handleCardClick(card) {
      if (card.clickable) {
        this.openPnlTrendDialog()
      }
    },
    openIntradayChart(row) {
      this.$emit('open-chart', row)
    },
    openPnlTrendDialog() {
      this.$emit('open-pnl-trend')
    },
    openCreateHolding() {
      this.$emit('create')
    },
    openEditHolding(row) {
      this.$emit('edit', row)
    },
    removeHolding(id) {
      this.$emit('remove', id)
    },
    seedDemoData() {
      this.$emit('seed-demo')
    }
  }
}
</script>
