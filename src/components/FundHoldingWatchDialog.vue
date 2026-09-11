<template>
  <div>
    <el-dialog
      v-model="dialogVisible"
      title="加入自选"
      width="360px"
    >
      <el-form label-width="70px">
        <el-form-item label="股票">
          <span>{{ stock.name }}（{{ stock.code }}）</span>
        </el-form-item><el-form-item label="分组">
          <el-select
            v-model="groupId"
            class="form-control"
            placeholder="请选择分组"
          >
            <el-option
              v-for="group in groups"
              :key="group.id"
              :label="group.name"
              :value="group.id"
            />
          </el-select>
        </el-form-item>
      </el-form><template #footer>
        <span><el-button @click="$emit('update:visible', false)">取消</el-button><el-button
          type="primary"
          :loading="saving"
          @click="saveFundHoldingWatch"
        >加入自选</el-button></span>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import dialogModel from '../mixins/dialog'

export default {
  name: 'FundHoldingWatchDialog',
  mixins: [dialogModel],
  props: {
    visible: Boolean,
    stock: { type: Object, default: () => ({ name: '', code: '' }) },
    groups: { type: Array, default: () => [] },
    saving: Boolean
  },
  emits: ["update:visible","submit"],
  data() {
    return {
      groupId: null
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
