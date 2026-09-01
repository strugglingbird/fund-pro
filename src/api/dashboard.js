import axios from 'axios'

const runtimeApiBase = typeof window === 'undefined' ? '' : window.__QUANT_API_BASE_URL__
const apiBaseUrl = process.env.VUE_APP_API_BASE_URL || runtimeApiBase || '/api'

const request = axios.create({
  baseURL: apiBaseUrl,
  timeout: 15000
})

export function fetchDashboard() {
  return request.get('/dashboard')
}

export function fetchHoldings() {
  return request.get('/holdings')
}

export function fetchMarketIndices() {
  return request.get('/market-indices')
}

export function fetchSectorFundFlow() {
  return request.get('/sector-fund-flow')
}

export function fetchNews() {
  return request.get('/news', { timeout: 45000 })
}

export function lookupInstrument(code, assetType) {
  return request.get('/instruments/lookup', {
    params: { code, asset_type: assetType }
  })
}

export function fetchIntradayChart(code, assetType) {
  return request.get('/instruments/intraday', {
    params: { code, asset_type: assetType }
  })
}

export function fetchFundHoldings(code) {
  return request.get('/instruments/fund-holdings', { params: { code }, timeout: 30000 })
}

export function fetchFundHistory(code, startDate, endDate) {
  return request.get('/instruments/fund-history', {
    params: { code, start_date: startDate, end_date: endDate },
    timeout: 30000
  })
}
export function fetchFundPerformance(code, interval) { return request.get('/instruments/fund-performance', { params: { code, interval }, timeout: 30000 }) }

export function fetchWatchlist() { return request.get('/watchlist', { timeout: 45000 }) }
export function saveWatchlistGroup(payload) { return request.post('/watchlist/groups', payload) }
export function removeWatchlistGroup(id) { return request.delete(`/watchlist/groups/${id}`) }
export function moveWatchlistGroup(id, direction) { return request.post(`/watchlist/groups/${id}/move`, { direction }) }
export function saveWatchlistItem(payload) { return request.post('/watchlist/items', payload) }
export function removeWatchlistItem(id) { return request.delete(`/watchlist/items/${id}`) }

export function saveHolding(payload) {
  return request.post('/holdings', payload)
}

export function deleteHolding(id) {
  return request.delete(`/holdings/${id}`)
}

export function updateHolding(id, payload) {
  return request.put(`/holdings/${id}`, payload)
}

export function seedDemo() {
  return request.post('/seed-demo')
}
