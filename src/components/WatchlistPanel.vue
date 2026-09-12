<template>
  <div>
    <section>
      <div class="page-heading">
        <div class="panel-actions">
          <span class="panel-tip">{{ watchlist.generated_at || '--' }} 更新</span><el-button
            size="small"
            :loading="loading"
            @click="loadWatchlist(true)"
          >
            刷新行情
          </el-button>
        </div>
      </div>
      <el-card
        shadow="never"
        class="panel-card watchlist-card"
      >
        <el-tabs
          v-model="watchlistCategory"
          @tab-click="ensureWatchGroup"
        >
          <el-tab-pane
            label="场内基金与股票"
            name="exchange"
          /><el-tab-pane
            label="场外基金"
            name="fund"
          />
        </el-tabs><div class="watch-toolbar">
          <div class="watch-groups">
            <el-button
              v-for="group in watchGroups"
              :key="group.id"
              size="small"
              :type="selectedWatchGroupId === group.id ? 'primary' : 'default'"
              @click="selectedWatchGroupId = group.id"
            >
              {{ group.name }}
            </el-button><el-button
              size="small"
              @click="createWatchGroup"
            >
              <el-icon><Plus /></el-icon><span>新建分组</span>
            </el-button>
          </div><div class="panel-actions">
            <el-button
              size="small"
              :disabled="!selectedWatchGroupId"
              @click="openWatchItemDialog"
            >
              添加自选
            </el-button>            <el-button
              v-if="selectedWatchGroup && !selectedWatchGroup.is_default"
              type="primary"
              link
              class="danger-text"
              @click="deleteWatchGroup"
            >
              删除分组
            </el-button>
          </div>
        </div><div
          v-if="loading && !loaded"
          class="detail-skeleton"
        >
          <div class="skeleton-table">
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
          v-else-if="!selectedWatchGroupId || !watchItems.length"
          class="empty-state"
        >
          当前分组暂无自选标的，点击“添加自选”开始跟踪。
        </div><div
          v-else-if="isMobile"
          class="data-card-list"
        >
          <div
            v-for="row in watchItems"
            :key="row.id"
            class="data-card"
          >
            <div class="data-card__head">
              <button
                type="button"
                class="data-card__name"
                @click="openIntradayChart(row)"
              >
                {{ row.name }}
              </button><span
                class="data-card__rate"
                :class="profitClass(row.daily_change_rate)"
              >
                {{ formatNullablePercent(row.daily_change_rate) }}
              </span>
            </div><div class="data-card__meta">
              <span>{{ row.code }}</span><el-tag
                size="small"
                :type="assetTypeTag(row.asset_type)"
              >
                {{ assetTypeLabel(row.asset_type) }}
              </el-tag><span v-if="row.source_label">{{ row.source_label }}</span><div class="data-card__actions">
                <el-button
                  type="primary"
                  link
                  class="danger-text"
                  @click="deleteWatchItem(row.id)"
                >
                  删除
                </el-button>
              </div>
            </div><div class="data-card__grid">
              <div
                v-for="cell in watchCardCells(row)"
                :key="cell.label"
                class="data-card__cell"
              >
                <span>{{ cell.label }}</span><strong :class="cell.className">{{ cell.value }}</strong>
              </div>
            </div>
          </div>
        </div><el-table
          v-else
          :data="watchItems"
          stripe
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
          /><el-table-column
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
            prop="previous_close"
            label="昨日收盘价"
            width="120"
          >
            <template #default="{ row }">
              {{ formatNetValue(row.previous_close, row.asset_type) }}
            </template>
          </el-table-column><el-table-column
            prop="current_price"
            label="现价"
            width="110"
          >
            <template #default="{ row }">
              {{ formatNetValue(row.current_price, row.asset_type) }}
            </template>
          </el-table-column><el-table-column
            v-if="watchlistCategory === 'fund'"
            prop="estimated_price"
            label="估值"
            width="110"
          >
            <template #default="{ row }">
              {{ formatNetValue(row.estimated_price, row.asset_type) }}
            </template>
          </el-table-column><el-table-column
            prop="daily_change_rate"
            label="当日涨幅"
            width="110"
          >
            <template #default="{ row }">
              <span :class="profitClass(row.daily_change_rate)">{{ formatNullablePercent(row.daily_change_rate) }}</span>
            </template>
          </el-table-column><el-table-column
            v-if="watchlistCategory === 'fund'"
            prop="estimated_change_rate"
            label="预估涨幅"
            width="110"
          >
            <template #default="{ row }">
              <span :class="profitClass(row.estimated_change_rate)">{{ formatNullablePercent(row.estimated_change_rate) }}</span>
            </template>
          </el-table-column><el-table-column
            prop="source_label"
            label="数据源"
            min-width="130"
          /><el-table-column
            label="操作"
            width="75"
            fixed="right"
          >
            <template #default="{ row }">
              <el-button
                type="primary"
                link
                class="danger-text"
                @click="deleteWatchItem(row.id)"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
      <div
        v-if="selectedWatchGroup"
        class="watch-order-actions"
      >
        <span>当前分组：{{ selectedWatchGroup.name }}</span><el-button
          size="small"
          :disabled="watchGroups[0] && selectedWatchGroup.id === watchGroups[0].id"
          @click="moveCurrentWatchGroup('up')"
        >
          上移
        </el-button><el-button
          size="small"
          :disabled="watchGroups[watchGroups.length - 1] && selectedWatchGroup.id === watchGroups[watchGroups.length - 1].id"
          @click="moveCurrentWatchGroup('down')"
        >
          下移
        </el-button>
      </div>
    </section>
  </div>
</template>

<script>
import { Plus } from '@element-plus/icons-vue'
import viewport from '../mixins/viewport'
import { assetTypeLabel, assetTypeTag, formatNetValue, formatNullablePercent, profitClass } from '../utils/format'

export default {
  name: 'WatchlistPanel',
  components: { Plus },
  mixins: [viewport],
  props: {
    watchlist: { type: Object, required: true },
    loading: Boolean,
    loaded: Boolean,
    category: { type: String, default: 'exchange' },
    selectedGroupId: { type: Number, default: null }
  },
  emits: ["update:category","update:selectedGroupId","reload","ensure-group","create-group","delete-group","move-group","add-item","delete-item","open-chart"],
  computed: {
    watchlistCategory: {
      get() {
        return this.category
      },
      set(value) {
        this.$emit('update:category', value)
      }
    },
    selectedWatchGroupId: {
      get() {
        return this.selectedGroupId
      },
      set(value) {
        this.$emit('update:selectedGroupId', value)
      }
    },
    watchGroups() {
      return this.watchlist.groups.filter(group => group.category === this.category)
    },
    selectedWatchGroup() {
      return this.watchGroups.find(group => group.id === this.selectedGroupId) || null
    },
    watchItems() {
      return this.watchlist.items.filter(item => item.group_id === this.selectedGroupId)
    }
  },
  methods: {
    formatNetValue,
    formatNullablePercent,
    profitClass,
    assetTypeLabel,
    assetTypeTag,
    // 移动端卡片：场外基金多出「估值 / 预估涨幅」两格
    watchCardCells(row) {
      const isFund = row.asset_type === 'fund'
      const cells = []
      if (isFund) {
        cells.push({ label: '估值', value: formatNetValue(row.estimated_price, row.asset_type) })
      }
      cells.push({ label: '现价', value: formatNetValue(row.current_price, row.asset_type) })
      cells.push({ label: '昨日收盘', value: formatNetValue(row.previous_close, row.asset_type) })
      cells.push({
        label: '当日涨幅',
        value: formatNullablePercent(row.daily_change_rate),
        className: profitClass(row.daily_change_rate)
      })
      if (isFund) {
        cells.push({
          label: '预估涨幅',
          value: formatNullablePercent(row.estimated_change_rate),
          className: profitClass(row.estimated_change_rate)
        })
      }
      return cells
    },
    loadWatchlist(force) {
      this.$emit('reload', force)
    },
    ensureWatchGroup() {
      this.$emit('ensure-group')
    },
    createWatchGroup() {
      this.$emit('create-group')
    },
    deleteWatchGroup() {
      this.$emit('delete-group')
    },
    moveCurrentWatchGroup(direction) {
      this.$emit('move-group', direction)
    },
    openWatchItemDialog() {
      this.$emit('add-item')
    },
    deleteWatchItem(id) {
      this.$emit('delete-item', id)
    },
    openIntradayChart(row) {
      this.$emit('open-chart', row)
    }
  }
}
</script>
