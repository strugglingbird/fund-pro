<template>
  <div>
    <button
      type="button"
      class="refresh-fab"
      :class="{ 'is-loading': loading || refreshing }"
      :disabled="refreshing"
      :style="fabStyle('refresh')"
      aria-label="刷新数据"
      title="重新抓取全部数据"
      @mousedown="startDrag('refresh', $event)"
      @touchstart="startDrag('refresh', $event)"
      @touchend.stop.prevent="refreshFromTouch"
      @touchcancel="stopDrag"
      @click="refreshFromClick"
    ><i class="el-icon-refresh" /></button>
    <button
      type="button"
      class="privacy-fab"
      :class="{ 'is-visible': numbersVisible }"
      :style="fabStyle('privacy')"
      :aria-label="numbersVisible ? '隐藏数字' : '展示数字'"
      :title="numbersVisible ? '隐藏数字' : '展示数字'"
      @mousedown="startDrag('privacy', $event)"
      @touchstart="startDrag('privacy', $event)"
      @touchend.stop.prevent="toggleFromTouch"
      @touchcancel="stopDrag"
      @click="toggleFromClick"
    ><i class="el-icon-view" /></button>
  </div>
</template>

<script>
import draggableFab from '../mixins/draggableFab'

export default {
  name: 'FloatingActions',
  mixins: [draggableFab],
  props: {
    loading: Boolean,
    refreshing: Boolean,
    numbersVisible: Boolean
  },
  methods: {
    refreshFromClick() {
      if (this.isDragged('refresh')) return
      this.$emit('refresh')
    },
    refreshFromTouch() {
      const wasDragged = this.isDragged('refresh')
      this.stopDrag()
      if (!wasDragged) this.$emit('refresh')
    },
    toggleFromClick() {
      if (this.isDragged('privacy')) return
      this.$emit('toggle-numbers')
    },
    toggleFromTouch() {
      const wasDragged = this.isDragged('privacy')
      this.stopDrag()
      if (!wasDragged) this.$emit('toggle-numbers')
    }
  }
}
</script>
