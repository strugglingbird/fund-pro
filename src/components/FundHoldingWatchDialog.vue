<template>
  <div>
    <el-dialog title="加入自选" :visible.sync="dialogVisible" width="360px"><el-form label-width="70px"><el-form-item label="股票"><span>{{ fundHoldingToWatch.name }}（{{ fundHoldingToWatch.code }}）</span></el-form-item><el-form-item label="分组"><el-select v-model="fundHoldingWatchGroupId" class="form-control" placeholder="请选择分组"><el-option v-for="group in exchangeWatchGroups" :key="group.id" :label="group.name" :value="group.id" /></el-select></el-form-item></el-form><span slot="footer"><el-button @click="$emit('update:visible', false)">取消</el-button><el-button type="primary" :loading="fundHoldingWatchSaving" @click="saveFundHoldingWatch">加入自选</el-button></span></el-dialog>
  </div>
</template>

<script>
export default {
  name: 'FundHoldingWatchDialog',
  props: {
    visible: Boolean,
    stock: { type: Object, default: () => ({ name: '', code: '' }) },
    groups: { type: Array, default: () => [] },
    saving: Boolean
  },
  data() {
    return {
      groupId: null
    }
  },
  computed: {
    fundHoldingToWatch() {
      return this.stock
    },
    exchangeWatchGroups() {
      return this.groups
    },
    fundHoldingWatchSaving() {
      return this.saving
    },
    fundHoldingWatchGroupId: {
      get() {
        return this.groupId
      },
      set(value) {
        this.groupId = value
      }
    },
    dialogVisible: {
      get() { return this.visible },
      set(value) { this.$emit('update:visible', value) }
    }
  },
  watch: {
    visible(open) {
      if (open) this.groupId = this.groups.length ? this.groups[0].id : null
    }
  },
  methods: {
    saveFundHoldingWatch() {
      if (!this.groupId) return
      this.$emit('submit', {
        group_id: this.groupId,
        name: this.stock.name,
        code: this.stock.code,
        asset_type: 'stock'
      })
    }
  }
}
</script>
