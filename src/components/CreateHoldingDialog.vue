<template>
  <div>
    <el-dialog
      v-model="dialogVisible"
      title="新增持仓"
      width="440px"
      @closed="resetHoldingForm"
    >
      <el-form
        ref="createHoldingForm"
        :model="holdingForm"
        :rules="holdingRules"
        label-width="90px"
      >
        <el-form-item label="名称">
          <el-input
            v-model.trim="holdingForm.name"
            placeholder="如：沪深300ETF"
          />
        </el-form-item>
        <el-form-item label="代码">
          <el-input
            v-model.trim="holdingForm.code"
            placeholder="如：510300 / 001632"
            @blur="lookupHoldingInstrument"
          />
        </el-form-item>
        <el-form-item label="类型">
          <el-select
            v-model="holdingForm.asset_type"
            placeholder="请选择类型"
            class="form-control"
            @change="lookupHoldingInstrument"
          >
            <el-option
              label="股票"
              value="stock"
            />
            <el-option
              label="ETF"
              value="etf"
            />
            <el-option
              label="场外基金"
              value="fund"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="现价/估值">
          <el-input
            :model-value="marketPreview.priceText"
            disabled
          >
            <template #append>
              <el-button
                :loading="lookupLoading"
                @click="lookupHoldingInstrument"
              >
                自动识别
              </el-button>
            </template>
          </el-input>
          <div
            v-if="marketPreview.source"
            class="market-source"
          >
            数据源：{{ marketPreview.source }}
          </div>
        </el-form-item>
        <el-form-item label="份额/股数">
          <el-input-number
            v-model="holdingForm.quantity"
            :min="0.0001"
            :step="100"
            class="form-control"
          />
        </el-form-item>
        <el-form-item label="成本价">
          <el-input-number
            v-model="holdingForm.cost_price"
            :min="0.0001"
            :step="0.01"
            :precision="4"
            class="form-control"
          />
        </el-form-item>
        <el-form-item label="自选">
          <el-checkbox v-model="holdingForm.add_to_watchlist">
            同时加入自选
          </el-checkbox>
        </el-form-item>
      </el-form>
      <template #footer>
        <span>
          <el-button @click="$emit('update:visible', false)">取消</el-button>
          <el-button
            type="primary"
            :loading="saving"
            @click="submitHolding"
          >保存持仓</el-button>
        </span>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { lookupInstrument } from '../api/dashboard'
import { formatNetValue } from '../utils/format'
import dialogModel from '../mixins/dialog'

const newHoldingForm = () => ({
  name: '',
  code: '',
  asset_type: 'stock',
  quantity: 100,
  cost_price: 1,
  add_to_watchlist: true
})

const IDLE_PREVIEW = { priceText: '输入代码后自动识别', source: '' }

export default {
  name: 'CreateHoldingDialog',
  mixins: [dialogModel],
  props: {
    visible: Boolean,
    saving: Boolean
  },
  emits: ["update:visible","submit"],
  data() {
    return {
      holdingForm: newHoldingForm(),
      marketPreview: { ...IDLE_PREVIEW },
      lookupLoading: false,
      holdingRules: {
        name: [{ required: true, message: '请输入持仓名称', trigger: 'blur' }],
        code: [{ required: true, message: '请输入持仓代码', trigger: 'blur' }],
        asset_type: [{ required: true, message: '请选择持仓类型', trigger: 'change' }]
      }
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
    async submitHolding() {
      try {
        await this.$refs.createHoldingForm.validate()
        this.$emit('submit', { ...this.holdingForm })
      } catch {
        // validation failed, keep the dialog open
      }
    }
  }
}
</script>
