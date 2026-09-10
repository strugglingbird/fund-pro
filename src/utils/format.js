/** Pure display helpers shared by every panel and dialog. */

export const MASK = '****'
export const EMPTY = '--'

export function isNil(value) {
  return value === null || value === undefined || value === ''
}

export function formatMoney(value) {
  return `¥${Number(value || 0).toFixed(2)}`
}

export function formatPercent(value) {
  return `${Number(value || 0).toFixed(2)}%`
}

export function formatNullablePercent(value) {
  return isNil(value) ? EMPTY : formatPercent(value)
}

export function formatSignedNullablePercent(value) {
  if (isNil(value)) return EMPTY
  const numeric = Number(value)
  return `${numeric > 0 ? '+' : ''}${numeric.toFixed(2)}%`
}

export function formatNetValue(value, assetType) {
  if (isNil(value)) return EMPTY
  return assetType === 'fund' ? `¥${Number(value).toFixed(4)}` : formatMoney(value)
}

export function formatIntradayPrice(value, assetType) {
  if (isNil(value)) return EMPTY
  if (assetType === 'index') return Number(value).toFixed(2)
  return formatNetValue(value, assetType)
}

export function formatFundNav(value) {
  return isNil(value) ? EMPTY : Number(value).toFixed(4)
}

export function formatCostPrice(value) {
  return `¥${Number(value || 0).toFixed(4)}`
}

export function profitClass(value) {
  const numeric = Number(value)
  if (numeric > 0) return 'positive'
  if (numeric < 0) return 'negative'
  return 'neutral'
}

export function assetTypeLabel(assetType) {
  if (assetType === 'stock') return '股票'
  if (assetType === 'etf') return 'ETF'
  if (assetType === 'fund') return '场外基金'
  return '未知'
}

export function assetTypeTag(assetType) {
  if (assetType === 'stock') return 'danger'
  if (assetType === 'etf') return 'warning'
  if (assetType === 'fund') return 'success'
  return 'info'
}

/** Wrap a numeric rate so the holdings table can sort rows without estimates last. */
export function sortableRate(value) {
  return isNil(value) || !Number.isFinite(Number(value)) ? -Infinity : Number(value)
}

export function defaultHistoryRange(days = 92) {
  const end = new Date()
  const start = new Date()
  start.setDate(start.getDate() - days)
  const format = date => date.toISOString().slice(0, 10)
  return [format(start), format(end)]
}
