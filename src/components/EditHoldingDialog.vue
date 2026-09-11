<template>
  <div>
    <el-dialog
      v-model="dialogVisible"
      title="修改持仓"
      width="420px"
    >
      <el-form
        :model="editHoldingForm"
        label-width="90px"
      >
        <el-form-item label="持仓">
          <span>{{ editHoldingForm.name }}（{{ editHoldingForm.code }}）</span>
        </el-form-item>
        <el-form-item label="份额/股数">
          <el-input-number
            v-model="editHoldingForm.quantity"
            :min="0.0001"
            :step="100"
          />
        </el-form-item>
        <el-form-item label="成本价">
          <el-input-number
            v-model="editHoldingForm.cost_price"
            :min="0.0001"
            :step="0.01"
            :precision="4"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="$emit('update:visible', false)">取消</el-button>
          <el-button
            type="primary"
            :loading="saving"
            @click="submitHoldingEdit"
          >保存修改</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import dialogModel from '../mixins/dialog'

const emptyForm = () => ({ id: null, name: '', code: '', quantity: 0, cost_price: 0 })

export default {
  name: 'EditHoldingDialog',
  mixins: [dialogModel],
  props: {
    visible: Boolean,
    holding: { type: Object, default: null },
    saving: Boolean
  },
  emits: ["update:visible","submit"],
  data() {
    return {
      editHoldingForm: emptyForm()
    }
  },
  watch: {
    holding: {
      immediate: true,
      handler(value) {
        this.editHoldingForm = value
          ? {
            id: value.id,
            name: value.name,
            code: value.code,
            quantity: Number(value.quantity),
            cost_price: Number(value.cost_price)
          }
          : emptyForm()
      }
    }
  },
  methods: {
    submitHoldingEdit() {
      this.$emit('submit', {
        id: this.editHoldingForm.id,
        quantity: this.editHoldingForm.quantity,
        cost_price: this.editHoldingForm.cost_price
      })
    }
  }
}
</script>
