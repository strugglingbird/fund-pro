import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import ElementPlus, { ElCheckbox, ElDatePicker, ElDialog, ElInput, ElInputNumber, ElTabPane } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import CreateHoldingDialog from '../src/components/CreateHoldingDialog.vue'
import EditHoldingDialog from '../src/components/EditHoldingDialog.vue'
import WatchItemDialog from '../src/components/WatchItemDialog.vue'
import FundHoldingWatchDialog from '../src/components/FundHoldingWatchDialog.vue'
import WatchlistPanel from '../src/components/WatchlistPanel.vue'
import MarketPanel from '../src/components/MarketPanel.vue'
import IntradayChartDialog from '../src/components/IntradayChartDialog.vue'
import PnlTrendDialog from '../src/components/PnlTrendDialog.vue'
import FloatingActions from '../src/components/FloatingActions.vue'
import MetricRail from '../src/components/MetricRail.vue'
import App from '../src/App.vue'
import * as api from '../src/api/dashboard'

vi.mock('../src/api/dashboard', () => ({
  lookupInstrument: vi.fn(), fetchEstimateArchive: vi.fn(), fetchFundHistory: vi.fn(),
  fetchFundHoldings: vi.fn(), fetchFundPerformance: vi.fn(), fetchIntradayChart: vi.fn(),
  fetchPortfolioIntradayPnl: vi.fn(), fetchDashboard: vi.fn(), fetchMarketIndices: vi.fn(), fetchNews: vi.fn(),
  fetchWatchlist: vi.fn(), deleteHolding: vi.fn(), moveWatchlistGroup: vi.fn(), removeWatchlistGroup: vi.fn(),
  removeWatchlistItem: vi.fn(), saveHolding: vi.fn(), saveWatchlistGroup: vi.fn(), saveWatchlistItem: vi.fn(),
  seedDemo: vi.fn(), updateHolding: vi.fn()
}))
vi.mock('echarts', () => ({
  init: vi.fn(container => ({ getDom: () => container, setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() }))
}))

const wrappers = []
function render(component, props = {}) {
  const wrapper = mount(component, { props, attachTo: document.body, global: { plugins: [[ElementPlus, { locale: zhCn }]] } })
  wrappers.push(wrapper)
  return wrapper
}
async function open(component, props = {}) {
  const wrapper = render(component, { visible: false, ...props })
  await wrapper.setProps({ visible: true })
  await flushPromises()
  return wrapper
}
async function clickButton(wrapper, text) {
  const button = wrapper.findAll('button').find(item => item.text() === text)
  expect(button, text).toBeTruthy()
  await button.trigger('click')
  await flushPromises()
}
function buttonByText(wrapper, text) {
  return wrapper.findAll('button').find(item => item.text() === text) || null
}
afterEach(() => {
  wrappers.splice(0).forEach(wrapper => wrapper.unmount())
  document.body.innerHTML = ''
  vi.clearAllMocks()
})

describe('Element Plus migration: forms and events', () => {
  it('renders lookup preview and footer, submits numeric holding fields and closes', async () => {
    api.lookupInstrument.mockResolvedValue({ data: { name: '测试基金', estimated_price: 1.2345, source_label: '测试源' } })
    const wrapper = await open(CreateHoldingDialog)
    const inputs = wrapper.findAllComponents(ElInput)
    await inputs[1].find('input').setValue('001632')
    await inputs[1].find('input').trigger('blur')
    await flushPromises()
    expect(wrapper.text()).toContain('测试源')
    expect(wrapper.find('input[disabled]').element.value).toBe('¥1.23')
    const numbers = wrapper.findAllComponents(ElInputNumber)
    numbers[0].vm.$emit('update:modelValue', 100)
    numbers[1].vm.$emit('update:modelValue', 1.1111)
    await nextTick()
    await clickButton(wrapper, '保存持仓')
    expect(wrapper.emitted('submit')[0][0]).toMatchObject({ code: '001632', name: '测试基金', quantity: 100, cost_price: 1.1111, add_to_watchlist: true })
    await clickButton(wrapper, '取消')
    expect(wrapper.emitted('update:visible')).toEqual([[false]])
    wrapper.findComponent(ElDialog).vm.$emit('update:modelValue', false)
    expect(wrapper.emitted('update:visible')).toHaveLength(2)
  })

  it('preserves edit values and emits edits through the footer', async () => {
    const holding = { id: 7, name: '测试ETF', code: '510300', quantity: 200, cost_price: 3.1415 }
    const wrapper = await open(EditHoldingDialog, { holding })
    expect(wrapper.text()).toContain('测试ETF')
    await clickButton(wrapper, '保存修改')
    expect(wrapper.emitted('submit')[0][0]).toMatchObject({ id: 7, quantity: 200, cost_price: 3.1415 })
  })

  it('keeps fund watchlist defaults and selected group on add', async () => {
    const wrapper = await open(WatchItemDialog, { category: 'fund', groups: [{ id: 2, name: '基金组' }], selectedGroupId: 2 })
    await wrapper.findComponent(ElInput).find('input').setValue('001632')
    await clickButton(wrapper, '添加')
    expect(wrapper.emitted('submit')[0][0]).toMatchObject({ code: '001632', asset_type: 'fund', group_id: 2 })
  })

  it('selects an exchange group when adding a fund holding stock', async () => {
    const wrapper = await open(FundHoldingWatchDialog, { groups: [{ id: 3, name: '股票组' }], stock: { name: '测试股票', code: '600000' } })
    await clickButton(wrapper, '加入自选')
    expect(wrapper.emitted('submit')[0][0]).toEqual({ group_id: 3, name: '测试股票', code: '600000', asset_type: 'stock' })
  })

  it('renders table scoped slots, SVG add icon and group/category updates', async () => {
    const wrapper = render(WatchlistPanel, { loaded: true, category: 'exchange', selectedGroupId: 1,
      watchlist: { groups: [{ id: 1, name: '股票组', category: 'exchange' }, { id: 2, name: '第二组', category: 'exchange' }],
        items: [{ id: 1, group_id: 1, code: '510300', name: '测试ETF', asset_type: 'etf', current_price: 3.1 }] } })
    await flushPromises()
    expect(wrapper.text()).toContain('测试ETF')
    expect(wrapper.find('svg').exists()).toBe(true)
    await clickButton(wrapper, '第二组')
    expect(wrapper.emitted('update:selectedGroupId')).toEqual([[2]])
    await wrapper.findAll('[role="tab"]')[1].trigger('click')
    expect(wrapper.emitted('update:category')).toEqual([['fund']])
    await clickButton(wrapper, '测试ETF')
    expect(wrapper.emitted('open-chart')[0][0].code).toBe('510300')
  })

  it('hides the delete action for the default watchlist group', async () => {
    const wrapper = render(WatchlistPanel, { loaded: true, category: 'exchange', selectedGroupId: 1,
      watchlist: { groups: [{ id: 1, name: '场内自选', category: 'exchange', is_default: 1 }], items: [] } })
    await flushPromises()
    expect(buttonByText(wrapper, '删除分组')).toBeNull()
    wrapper.setProps({ watchlist: { groups: [{ id: 1, name: '自定义组', category: 'exchange', is_default: 0 }], items: [] } })
    await nextTick()
    expect(buttonByText(wrapper, '删除分组')).not.toBeNull()
  })

  it('retains floating refresh/privacy actions with SVG icons', async () => {
    const wrapper = render(FloatingActions)
    expect(wrapper.findAll('svg')).toHaveLength(2)
    await wrapper.find('[aria-label="刷新数据"]').trigger('click')
    await wrapper.find('[aria-label="展示数字"]').trigger('click')
    expect(wrapper.emitted('refresh')).toHaveLength(1)
    expect(wrapper.emitted('toggle-numbers')).toHaveLength(1)
  })
})

describe('Element Plus migration: charts and dates', () => {
  it('loads fund detail tabs, keeps API date format and safely clears the date range', async () => {
    api.fetchIntradayChart.mockResolvedValue({ data: { name: '测试基金', asset_type: 'fund', points: [], previous_close: 1 } })
    api.fetchEstimateArchive.mockResolvedValue({ data: { dates: [] } })
    api.fetchFundHistory.mockResolvedValue({ data: { items: [], source_label: '测试' } })
    api.fetchFundHoldings.mockResolvedValue({ data: { items: [] } })
    api.fetchFundPerformance.mockResolvedValue({ data: { fund: [], indices: [] } })
    const wrapper = await open(IntradayChartDialog, { instrument: { code: '001632', asset_type: 'fund' } })
    expect(wrapper.findAllComponents(ElTabPane).map(tab => tab.props('label'))).toEqual(expect.arrayContaining(['持仓股', '历史净值']))
    const picker = wrapper.findComponent(ElDatePicker)
    expect(picker.props('valueFormat')).toBe('YYYY-MM-DD')
    picker.vm.$emit('update:modelValue', ['2026-09-01', '2026-09-11'])
    await nextTick()
    picker.vm.$emit('change', ['2026-09-01', '2026-09-11'])
    await flushPromises()
    expect(api.fetchFundHistory).toHaveBeenLastCalledWith('001632', '2026-09-01', '2026-09-11')
    picker.vm.$emit('update:modelValue', null)
    await nextTick()
    picker.vm.$emit('change', null)
    await flushPromises()
    expect(api.fetchFundHistory).toHaveBeenCalledTimes(2)
  })

  it('checkbox values select benchmark codes and unmount disposes chart instances', async () => {
    api.fetchPortfolioIntradayPnl.mockResolvedValue({ data: {
      times: ['09:30'], portfolio: { available: true, rate: [1], covered: 1, total: 1 },
      indices: [{ code: 'sh000001', name: '上证指数', available: true, rate: [0.5] }], missing_holdings: []
    } })
    const wrapper = await open(PnlTrendDialog)
    expect(wrapper.findComponent(ElCheckbox).props('value')).toBe('sh000001')
    await wrapper.findComponent(ElCheckbox).find('input').setValue(false)
    expect(wrapper.vm.pnlTrendIndexCodes).not.toContain('sh000001')
    const instance = wrapper.vm.trendInstance
    expect(instance).toBeTruthy()
    wrapper.unmount()
    wrappers.splice(wrappers.indexOf(wrapper), 1)
    expect(instance.dispose).toHaveBeenCalledOnce()
  })
})

describe('移动端指标卡片轨道', () => {
  const metricItems = ['A', 'B', 'C', 'D', 'E'].map((label, index) => ({ code: `code-${index}`, label }))

  it('每个指标渲染一个卡片位，未溢出时不显示翻页点', () => {
    const wrapper = render(MetricRail, { items: metricItems, itemKey: 'code' })
    expect(wrapper.findAll('.metric-rail__cell')).toHaveLength(5)
    expect(wrapper.find('.metric-rail__pager').exists()).toBe(false)
    expect(wrapper.classes()).not.toContain('metric-rail--static')
  })

  it('卡片不足一屏时等分铺满，溢出后才出现可点击的翻页点', async () => {
    const fitted = render(MetricRail, { items: metricItems.slice(0, 2), itemKey: 'code' })
    expect(fitted.classes()).toContain('metric-rail--static')
    // jsdom 没有布局，等挂载后的首次测量结束，再注入测量结果模拟移动端溢出
    const wrapper = render(MetricRail, { items: metricItems, itemKey: 'code' })
    await flushPromises()
    wrapper.vm.step = 120
    wrapper.vm.pageCount = 3
    await nextTick()
    const dots = wrapper.findAll('.metric-rail__dot')
    expect(dots).toHaveLength(3)
    expect(dots[0].classes()).toContain('is-active')
    await dots[2].trigger('click')
    expect(wrapper.vm.activePage).toBe(2)
    expect(wrapper.findAll('.metric-rail__dot')[2].classes()).toContain('is-active')
  })

  it('市场指数卡片改走轨道渲染后仍保留点击与骨架屏', async () => {
    const wrapper = render(MarketPanel, {
      marketIndices: [{ code: 'sh000001', name: '上证指数', market: 'cn', current_price: 3200, change_rate: 0.5 }],
      dashboard: { sectors: { gainers: [], losers: [], source_label: '测试' } },
      tab: 'cn'
    })
    expect(wrapper.findAll('.metric-rail__cell')).toHaveLength(1)
    expect(wrapper.text()).toContain('上证指数')
    await wrapper.find('.index-card--clickable').trigger('click')
    expect(wrapper.emitted('open-chart')[0][0].code).toBe('sh000001')
    const skeleton = render(MarketPanel, {
      marketIndices: [],
      loading: true,
      dashboard: { sectors: { gainers: [], losers: [], source_label: '测试' } },
      tab: 'cn'
    })
    expect(skeleton.findAll('.index-skeleton')).toHaveLength(4)
  })
})

it('preserves whole-page navigation, privacy, refresh data and timer cleanup', async () => {
  api.fetchDashboard.mockResolvedValue({ data: {
    portfolio: { positions: [], total_market_value: 1234, total_cost: 1000 },
    sectors: { gainers: [], losers: [] }, generated_at: '2026-09-11 10:00:00'
  } })
  api.fetchMarketIndices.mockResolvedValue({ data: { items: [] } })
  api.fetchNews.mockResolvedValue({ data: { items: [], groups: [], total_count: 0 } })
  api.fetchWatchlist.mockResolvedValue({ data: { items: [], groups: [] } })
  const wrapper = render(App)
  await flushPromises()
  expect(wrapper.text()).toContain('****')
  await wrapper.find('[aria-label="展示数字"]').trigger('click')
  expect(wrapper.text()).toContain('1234.00')
  for (const label of ['持仓收益', '自选', '市场指数', '消息快讯', '首页']) {
    await wrapper.findAll('[role="menuitem"]').find(item => item.text() === label).trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="menuitem"].is-active').text()).toBe(label)
  }
  const previous = wrapper.vm.dashboard
  api.fetchDashboard.mockRejectedValueOnce(new Error('offline'))
  await wrapper.find('[aria-label="刷新数据"]').trigger('click')
  await flushPromises()
  expect(api.fetchDashboard).toHaveBeenLastCalledWith(true)
  expect(wrapper.vm.dashboard).toBe(previous)
  const clearTimer = vi.spyOn(window, 'clearInterval')
  const timer = wrapper.vm.newsRefreshTimer
  wrapper.unmount()
  wrappers.splice(wrappers.indexOf(wrapper), 1)
  expect(clearTimer).toHaveBeenCalledWith(timer)
  clearTimer.mockRestore()
})
