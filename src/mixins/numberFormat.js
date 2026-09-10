/** Masked number formatting for holdings views.

Consumers must expose a ``numbersVisible`` value (data, prop or computed). When it
is false every sensitive figure collapses to a mask; the underlying API payload is
never changed.
*/
import {
  MASK,
  EMPTY,
  formatCostPrice,
  formatMoney,
  formatNetValue,
  formatPercent,
  isNil
} from '../utils/format'

export default {
  methods: {
    formatMoney,
    formatNetValue,
    formatPercent,
    formatHoldingMoney(value, nullable = false) {
      if (nullable && isNil(value)) return EMPTY
      return this.numbersVisible ? formatMoney(value) : MASK
    },
    formatHoldingCostPrice(value) {
      return this.numbersVisible ? formatCostPrice(value) : MASK
    },
    formatHoldingPercent(value, nullable = false) {
      if (nullable && isNil(value)) return EMPTY
      return this.numbersVisible ? formatPercent(value) : MASK
    },
    formatHoldingNetValue(value, assetType) {
      if (isNil(value)) return EMPTY
      return this.numbersVisible ? formatNetValue(value, assetType) : MASK
    },
    formatHoldingQuantity(value) {
      return this.numbersVisible ? Number(value).toFixed(2) : MASK
    },
    formatHoldingCode(value) {
      return this.numbersVisible ? value : '******'
    }
  }
}
