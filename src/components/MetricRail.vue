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
    gap: { type: Number, default: 10 },
    // 需要自适应字号的元素，默认覆盖卡片里的标题 / 数值 / 脚注
    fitSelector: {
      type: String,
      default: '.stat-label, .stat-value, .stat-foot, .index-label, .index-value'
    }
  },
  emits: [],
  data() {
    return {
      pageCount: 1,
      activePage: 0,
      step: 0,
      fitFrame: 0
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
  updated() {
    // 数值随行情刷新变长（如 ¥1.00 → ¥136149.25）时不会改变容器尺寸，
    // ResizeObserver 收不到通知，所以在每次更新后再校验一次。
    this.scheduleFitText()
  },
  beforeUnmount() {
    if (this.resizeObserver) {
      this.resizeObserver.disconnect()
      this.resizeObserver = null
    }
    if (this.fitFrame && typeof window !== 'undefined' && window.cancelAnimationFrame) {
      window.cancelAnimationFrame(this.fitFrame)
      this.fitFrame = 0
    }
    window.removeEventListener('resize', this.measure)
  },
  methods: {
    /**
     * 让卡片里的文字自适应字号而不是被省略号截断。
     * 先清掉上一次写入的行内字号（回到 CSS 基准），再测量是否溢出；
     * 溢出时按「可用宽度 / 实际宽度」等比缩小，下限取元素上的 --fit-min。
     */
    fitText() {
      const viewport = this.$refs.viewport
      if (!viewport) return
      const nodes = viewport.querySelectorAll(this.fitSelector)
      nodes.forEach(node => {
        // 先清掉上一次的覆盖，回到 CSS 基准再判断（窗口变宽后字号要还原）
        node.style.fontSize = ''
        node.style.whiteSpace = ''
        node.style.lineHeight = ''
        const style = window.getComputedStyle(node)
        const base = parseFloat(style.fontSize)
        if (!base) return
        const available = node.getBoundingClientRect().width
        // jsdom 与隐藏容器下宽度为 0，跳过以免写出错误字号
        if (!available) return
        const required = node.scrollWidth
        if (required <= available + 0.5) return
        const min = parseFloat(style.getPropertyValue('--fit-min')) || 0
        // 减 1px 作为四舍五入的余量，避免刚好卡在边界仍显示省略号
        const next = base * ((available - 1) / required)
        if (next < min) {
          // 缩到下限仍放不下（如时间戳、长句脚注）：改成折行，多占一行也好过省略号
          node.style.fontSize = `${min}px`
          node.style.whiteSpace = 'normal'
          node.style.lineHeight = '1.25'
          return
        }
        node.style.fontSize = `${next.toFixed(2)}px`
      })
    },
    scheduleFitText() {
      if (this.fitFrame) return
      if (typeof window === 'undefined' || !window.requestAnimationFrame) {
        this.fitText()
        return
      }
      this.fitFrame = window.requestAnimationFrame(() => {
        this.fitFrame = 0
        this.fitText()
      })
    },
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
      // 卡片宽度变化时字号要重新算（清掉行内字号再按新宽度判断，既会缩也会放回去）
      this.fitText()
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
