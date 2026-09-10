<template>
  <div>
    <el-dialog title="添加自选" :visible="visible" width="420px"><el-form :model="watchItemForm" label-width="80px"><el-form-item label="代码"><el-input v-model.trim="watchItemForm.code" placeholder="输入代码后自动识别" @blur="lookupWatchItem" /></el-form-item><el-form-item label="名称"><el-input v-model.trim="watchItemForm.name" placeholder="自动识别后可修改" /></el-form-item><el-form-item label="类型"><el-select v-model="watchItemForm.asset_type" class="form-control" @change="lookupWatchItem"><el-option v-if="watchlistCategory === 'exchange'" label="股票" value="stock" /><el-option v-if="watchlistCategory === 'exchange'" label="ETF" value="etf" /><el-option v-if="watchlistCategory === 'fund'" label="场外基金" value="fund" /></el-select></el-form-item><el-form-item label="分组"><el-select v-model="watchItemForm.group_id" class="form-control"><el-option v-for="group in watchGroups" :key="group.id" :label="group.name" :value="group.id" /></el-select></el-form-item></el-form><span slot="footer"><el-button @click="$emit('update:visible', false)">取消</el-button><el-button type="primary" :loading="watchItemSaving" @click="saveWatchItem">添加</el-button></span></el-dialog>
  </div>
</template>

<script>
import { lookupInstrument } from '../api/dashboard'

export default {
  name: 'WatchItemDialog',
  props: {
    visible: Boolean,
    category: { type: String, default: 'exchange' },
    groups: { type: Array, default: () => [] },
    selectedGroupId: { type: Number, default: null },
    saving: Boolean
  },
  data() {
    return {
      watchItemForm: { group_id: null, name: '', code: '', asset_type: 'stock' }
    }
  },
  computed: {
    watchlistCategory() {
      return this.category
    },
    watchGroups() {
      return this.groups
    },
    watchItemSaving() {
      return this.saving
    }
  },
  watch: {
    visible(open) {
      if (!open) return
      this.watchItemForm = {
        group_id: this.selectedGroupId,
        name: '',
        code: '',
        asset_type: this.category === 'fund' ? 'fund' : 'stock'
      }
    }
  },
  methods: {
    async lookupWatchItem() {
      if (!this.watchItemForm.code) return
      try {
        const { data } = await lookupInstrument(this.watchItemForm.code, this.watchItemForm.asset_type)
        this.watchItemForm.name = data.name || this.watchItemForm.name
      } catch (error) {
        this.$message.warning(error.response?.data?.error || '标的识别失败')
      }
    },
    saveWatchItem() {
      this.$emit('submit', { ...this.watchItemForm })
    }
  }
}
</script>
