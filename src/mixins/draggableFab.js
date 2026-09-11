/** Drag behaviour for the floating action buttons.

Shared by both FABs through a ``name`` argument so the ~60 lines of pointer,
clamping and click-suppression logic live in one place.
*/
const MARGIN = 8
const FAB_SIZES = { refresh: 54, privacy: 50 }
// The privacy button only starts moving after the finger travels a few pixels.
const DRAG_THRESHOLDS = { refresh: 0, privacy: 6 }
const CLICK_SUPPRESS_MS = 250

const IDLE_DRAG = { name: null, offsetX: 0, offsetY: 0, startX: 0, startY: 0, moved: false }

export default {
  data() {
    return {
      fabPositions: {},
      // Kept true briefly after a drag so the trailing click does not fire the action.
      fabJustDragged: {},
      drag: { ...IDLE_DRAG }
    }
  },
  beforeUnmount() {
    this.stopDrag()
  },
  methods: {
    getPointer(event) {
      return event.touches ? event.touches[0] : event
    },
    startDrag(name, event) {
      const point = this.getPointer(event)
      const rect = event.currentTarget.getBoundingClientRect()
      this.drag = {
        name,
        offsetX: point.clientX - rect.left,
        offsetY: point.clientY - rect.top,
        startX: point.clientX,
        startY: point.clientY,
        moved: false
      }
      window.addEventListener('mousemove', this.moveDrag)
      window.addEventListener('mouseup', this.stopDrag)
      window.addEventListener('touchmove', this.moveDrag, { passive: false })
      window.addEventListener('touchend', this.stopDrag)
    },
    moveDrag(event) {
      const { name } = this.drag
      if (!name) return
      const point = this.getPointer(event)
      const travelled = Math.hypot(point.clientX - this.drag.startX, point.clientY - this.drag.startY)
      if (travelled < (DRAG_THRESHOLDS[name] || 0)) return
      const size = FAB_SIZES[name] || 54
      const left = Math.min(Math.max(MARGIN, point.clientX - this.drag.offsetX), window.innerWidth - size - MARGIN)
      const top = Math.min(Math.max(MARGIN, point.clientY - this.drag.offsetY), window.innerHeight - size - MARGIN)
      this.fabPositions = { ...this.fabPositions, [name]: { left, top } }
      this.drag.moved = true
      if (event.cancelable) event.preventDefault()
    },
    stopDrag() {
      window.removeEventListener('mousemove', this.moveDrag)
      window.removeEventListener('mouseup', this.stopDrag)
      window.removeEventListener('touchmove', this.moveDrag)
      window.removeEventListener('touchend', this.stopDrag)
      const { name, moved } = this.drag
      this.drag = { ...IDLE_DRAG }
      if (name && moved) {
        this.fabJustDragged = { ...this.fabJustDragged, [name]: true }
        setTimeout(() => { this.fabJustDragged = { ...this.fabJustDragged, [name]: false } }, CLICK_SUPPRESS_MS)
      }
    },
    fabStyle(name) {
      const position = this.fabPositions[name]
      if (!position) return {}
      return { left: `${position.left}px`, top: `${position.top}px`, right: 'auto', bottom: 'auto' }
    },
    isDragged(name) {
      return Boolean(this.fabJustDragged[name])
    }
  }
}
