/**
 * 移动端下拉刷新。
 *
 * 页面滚动到顶部（window.scrollY === 0）时向下拖拽超过阈值即触发回调，
 * 与原生 App 的下拉刷新一致，因而可以把顶部的刷新按钮整个去掉。
 * 桌面端不产生 touch 事件，天然不会启用，不需要额外的视口判断。
 *
 * 用法：
 *   const unregister = registerPullToRefresh({ onProgress, onRefresh, canRefresh })
 *   unregister() // 组件卸载时调用
 */

// 触发刷新所需的下拉距离（阻尼之后）
export const PULL_THRESHOLD = 60
// 指示器最大撑开高度，避免一直往下拉出整屏空白
const MAX_PULL = 96
// 阻尼系数：手指位移的一半。手感接近原生，也避免拉得太快太远
const DAMPING = 0.5

export function registerPullToRefresh({ onProgress, onRefresh, canRefresh = () => true }) {
  let startY = null
  let distance = 0

  const reset = () => {
    startY = null
    distance = 0
  }

  const handleStart = event => {
    if (window.scrollY > 0 || !canRefresh()) return
    const touch = event.touches && event.touches[0]
    if (!touch) return
    startY = touch.clientY
    distance = 0
  }

  const handleMove = event => {
    if (startY === null) return
    const touch = event.touches && event.touches[0]
    if (!touch) return
    // 中途向上滑或页面已离开顶部：立刻收手，交还给浏览器正常滚动
    if (window.scrollY > 0 || touch.clientY <= startY) {
      reset()
      onProgress(0)
      return
    }
    // 接管这一次手势，否则页面会跟着一起滚动/回弹
    if (event.cancelable) event.preventDefault()
    distance = Math.min((touch.clientY - startY) * DAMPING, MAX_PULL)
    onProgress(distance)
  }

  const handleEnd = () => {
    if (startY === null) return
    const reached = distance >= PULL_THRESHOLD
    reset()
    if (reached) onRefresh()
    else onProgress(0)
  }

  window.addEventListener('touchstart', handleStart, { passive: true })
  // touchmove 必须显式 passive: false，否则 preventDefault 无效
  window.addEventListener('touchmove', handleMove, { passive: false })
  window.addEventListener('touchend', handleEnd, { passive: true })
  window.addEventListener('touchcancel', handleEnd, { passive: true })

  return () => {
    window.removeEventListener('touchstart', handleStart)
    window.removeEventListener('touchmove', handleMove)
    window.removeEventListener('touchend', handleEnd)
    window.removeEventListener('touchcancel', handleEnd)
  }
}
