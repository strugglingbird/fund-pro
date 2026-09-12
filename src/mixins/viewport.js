/**
 * 视口断点 mixin：暴露响应式 isMobile（与 workspace.css 的 768px 断点保持一致）。
 *
 * 用途：结构性差异（例如表格 vs 卡片列表）必须在模板层切换，纯 CSS 隐藏会同时
 * 渲染两套 DOM，既浪费又会重复触发子组件的测量逻辑。仅样式差异继续走 CSS。
 */
const MOBILE_MEDIA_QUERY = '(max-width: 768px)'

function readMobileQuery() {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return null
  return window.matchMedia(MOBILE_MEDIA_QUERY)
}

export function isMobileViewport() {
  const query = readMobileQuery()
  return query ? query.matches : false
}

export default {
  data() {
    return { isMobile: isMobileViewport() }
  },
  created() {
    const query = readMobileQuery()
    if (!query || typeof query.addEventListener !== 'function') return
    this.mobileQuery = query
    this.onMobileQueryChange = event => {
      this.isMobile = event.matches
    }
    query.addEventListener('change', this.onMobileQueryChange)
  },
  beforeUnmount() {
    if (this.mobileQuery && this.onMobileQueryChange) {
      this.mobileQuery.removeEventListener('change', this.onMobileQueryChange)
    }
    this.mobileQuery = null
    this.onMobileQueryChange = null
  }
}
