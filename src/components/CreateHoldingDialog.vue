<template>
  <div>
    <el-dialog title="新增持仓" :visible.sync="dialogVisible" width="440px" @closed="resetHoldingForm">
      <el-form :model="holdingForm" label-width="90px">
        <el-form-item label="名称">
          <el-input v-model.trim="holdingForm.name" placeholder="如：沪深300ETF" />
        </el-form-item>
        <el-form-item label="代码">
          <el-input v-model.trim="holdingForm.code" placeholder="如：510300 / 001632" @blur="lookupHoldingInstrument" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="holdingForm.asset_type" placeholder="请选择类型" class="form-control" @change="lookupHoldingInstrument">
            <el-option label="股票" value="stock" />
            <el-option label="ETF" value="etf" />
            <el-option label="场外基金" value="fund" />
          </el-select>
        </el-form-item>
        <el-form-item label="现价/估值">
          <el-input :value="marketPreview.priceText" disabled>
            <template slot="append">
              <el-button :loading="lookupLoading" @click="lookupHoldingInstrument">自动识别</el-button>
            </template>
          </el-input>
          <div v-if="marketPreview.source" class="market-source">数据源：{{ marketPreview.source }}</div>
        </el-form-item>
        <el-form-item label="份额/股数">
          <el-input-number v-model="holdingForm.quantity" :min="0.0001" :step="100" class="form-control" />
        </el-form-item>
        <el-form-item label="成本价">
          <el-input-number v-model="holdingForm.cost_price" :min="0.0001" :step="0.01" :precision="4" class="form-control" />
        </el-form-item>
      </el-form>
      <span slot="footer">
        <el-button @click="$emit('update:visible', false)">取消</el-button>
        <el-button type="primary" :loading="savingCreate" @click="submitHolding">保存持仓</el-button>
      </span>
    </el-dialog>
  </div>
</template>

<script>
import { lookupInstrument } from '../api/dashboard'
import { formatNetValue } from '../utils/format'

const newHoldingForm = () => ({
  name: '',
  code: '',
  asset_type: 'stock',
  quantity: 100,
  cost_price: 1
})

const IDLE_PREVIEW = { priceText: '输入代码后自动识别', source: '' }

export default {
  name: 'CreateHoldingDialog',
  props: {
    visible: Boolean,
    saving: Boolean
  },
  data() {
    return {
      holdingForm: newHoldingForm(),
      marketPreview: { ...IDLE_PREVIEW },
      lookupLoading: false
    }
  },
  computed: {
    savingCreate() {
      return this.saving
    },
    dialogVisible: {
      get() { return this.visible },
      set(value) { this.$emit('update:visible', value) }
    }
  },
  methods: {
    resetHoldingForm() {
      this.holdingForm = newHoldingForm()
      this.marketPreview = { ...IDLE_PREVIEW }
    },
    async lookupHoldingInstrument() {
      if (!this.holdingForm.code) return
      this.lookupLoading = true
      try {
        const { data } = await lookupInstrument(this.holdingForm.code, this.holdingForm.asset_type)
        this.holdingForm.name = data.name
        const hasPrice = data.current_price !== null && data.current_price !== undefined
        const hasEstimate = data.estimated_price !== null && data.estimated_price !== undefined
        this.marketPreview = {
          priceText: !hasPrice && !hasEstimate
            ? '暂无实时估值'
            : formatNetValue(data.current_price ?? data.estimated_price, this.holdingForm.asset_type),
          source: data.source_label || '公开行情'
        }
      } catch (error) {
        this.marketPreview = { priceText: '未查询到实时价格', source: '' }
        this.$message.warning(error.response?.data?.error || '标的识别失败，请检查代码')
      } finally {
        this.lookupLoading = false
      }
    },
    submitHolding() {
      this.$emit('submit', { ...this.holdingForm })
    }
  }
}
</script>
