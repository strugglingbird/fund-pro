<template>
  <div
    class="metric-rail"
    :class="{ 'metric-rail--static': items.length <= perView }"
  >
    <div
      ref="viewport"
      class="metric-rail__viewport"
      @scroll.passive="syncActivePage"
    >
      <div
        class="metric-rail__track"
        :style="trackStyle"
      >
        <div
          v-for="(item, index) in items"
          :key="resolveItemKey(item, index)"
          class="metric-rail__cell"
        >
          <slot
            :item="item"
            :index="index"
          />
        </div>
      </div>
    </div>
    <div
      v-if="pageCount > 1"
      class="metric-rail__pager"
      role="group"
      aria-label="指标卡片翻页"
    >
      <button
        v-for="page in pageCount"
        :key="page"
        type="button"
        class="metric-rail__dot"
        :class="{ 'is-active': page - 1 === activePage }"
        :aria-label="`查看第 ${page} 组指标`"
        :aria-current="page - 1 === activePage ? 'true' : 'false'"
        @click="scrollToPage(page - 1)"
      />
    </div>
  </div>
</template>

<script>
/**
 * 指标卡片轨道。
 *
 * 桌面端（> 768px）退化为普通栅格，每行列数由 columns / wideColumns 控制；
 * 移动端（<= 768px）一行固定 perView 个卡片位（默认 3），多余的卡片横向滑动查看，
 * 并带 scroll-snap 与圆点指示器。是否可滑动由实际布局宽度测量得出，
 * 因此组件本身不判断屏幕宽度，避免与 CSS 断点脱节。
 */
export default {
  name: 'MetricRail',
  props: {
    items: { type: Array, default: () => [] },
    // 卡片 key：传字段名，或传 (item) => key 的函数；都没有时退回数组下标
    itemKey: { type: [String, Function], default: '' },
    // 移动端一屏可见的卡片数量
    perView: { type: Number, default: 3 },
    // 桌面端（769px ~ 1199px）每行列数
    columns: { type: Number, default: 2 },
    // 宽屏（>= 1200px）每行列数
    wideColumns: { type: Number, default: 4 },
    // 移动端相邻卡片间距（px）
    gap: { type: Number, default: 10 }
  },
  emits: [],
  data() {
    return {
      pageCount: 1,
      activePage: 0,
      step: 0
    }
  },
  computed: {
    trackStyle() {
      return {
        '--metric-rail-per-view': this.perView,
        '--metric-rail-columns': this.columns,
        '--metric-rail-columns-lg': this.wideColumns,
        '--metric-rail-gap': `${this.gap}px`
      }
    }
  },
  watch: {
    items() {
      this.measureOnNextTick()
    },
    perView() {
      this.measureOnNextTick()
    }
  },
  mounted() {
    this.measureOnNextTick()
    if (typeof ResizeObserver !== 'undefined') {
      this.resizeObserver = new ResizeObserver(() => this.measure())
      this.resizeObserver.observe(this.$refs.viewport)
    }
    window.addEventListener('resize', this.measure, { passive: true })
  },
  beforeUnmount() {
    if (this.resizeObserver) {
      this.resizeObserver.disconnect()
      this.resizeObserver = null
    }
    window.removeEventListener('resize', this.measure)
  },
  methods: {
    resolveItemKey(item, index) {
      if (typeof this.itemKey === 'function') {
        const key = this.itemKey(item)
        return key === undefined || key === null ? index : key
      }
      if (this.itemKey && item && item[this.itemKey] !== undefined && item[this.itemKey] !== null) {
        return item[this.itemKey]
      }
      return index
    },
    measureOnNextTick() {
      this.$nextTick(() => this.measure())
    },
    measure() {
      const viewport = this.$refs.viewport
      if (!viewport) return
      const cells = viewport.querySelectorAll('.metric-rail__cell')
      const width = viewport.clientWidth
      // jsdom 与隐藏容器下没有布局，直接判定为「不可滑动」
      if (!cells.length || !width) {
        this.step = 0
        this.pageCount = 1
        this.activePage = 0
        return
      }
      this.step = cells.length > 1
        ? cells[1].offsetLeft - cells[0].offsetLeft
        : cells[0].getBoundingClientRect().width + this.gap
      const overflow = viewport.scrollWidth - width
      if (overflow <= 2 || this.step <= 0) {
        this.pageCount = 1
        this.activePage = 0
        return
      }
      const reachable = Math.round(overflow / this.step) + 1
      const positions = Math.max(1, this.items.length - this.perView + 1)
      this.pageCount = Math.min(reachable, positions)
      this.syncActivePage()
    },
    syncActivePage() {
      const viewport = this.$refs.viewport
      if (!viewport || this.step <= 0) return
      const page = Math.round(viewport.scrollLeft / this.step)
      this.activePage = Math.min(Math.max(page, 0), this.pageCount - 1)
    },
    scrollToPage(page) {
      const viewport = this.$refs.viewport
      if (!viewport || this.step <= 0) return
      const target = Math.min(Math.max(page, 0), this.pageCount - 1)
      const left = target * this.step
      this.activePage = target
      if (typeof viewport.scrollTo === 'function') {
        viewport.scrollTo({ left, behavior: 'smooth' })
      } else {
        viewport.scrollLeft = left
      }
    }
  }
}
</script>
