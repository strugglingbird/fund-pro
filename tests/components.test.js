import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { h, nextTick } from 'vue'
import ElementPlus, { ElCheckbox, ElDatePicker, ElDialog, ElInput, ElInputNumber, ElTabPane } from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import CreateHoldingDialog from '../src/components/CreateHoldingDialog.vue'
import EditHoldingDialog from '../src/components/EditHoldingDialog.vue'
import WatchItemDialog from '../src/components/WatchItemDialog.vue'
import FundHoldingWatchDialog from '../src/components/FundHoldingWatchDialog.vue'
import WatchlistPanel from '../src/components/WatchlistPanel.vue'
import HoldingsPanel from '../src/components/HoldingsPanel.vue'
import HomePanel from '../src/components/HomePanel.vue'
import NewsPanel from '../src/components/NewsPanel.vue'
import MarketPanel from '../src/components/MarketPanel.vue'
import IntradayChartDialog from '../src/components/IntradayChartDialog.vue'
import PnlTrendDialog from '../src/components/PnlTrendDialog.vue'
import FloatingActions from '../src/components/FloatingActions.vue'
import MetricRail from '../src/components/MetricRail.vue'
import App from '../src/App.vue'
import viewport from '../src/mixins/viewport'
import * as api from '../src/api/dashboard'

vi.mock('../src/api/dashboard', () => ({
  lookupInstrument: vi.fn(), fetchEstimateArchive: vi.fn(), fetchFundHistory: vi.fn(),
  fetchFundHoldings: vi.fn(), fetchFundPerformance: vi.fn(), fetchIntradayChart: vi.fn(),
  fetchPortfolioIntradayPnl: vi.fn(), fetchDashboard: vi.fn(), fetchMarketIndices: vi.fn(), fetchNews: vi.fn(),
  fetchWatchlist: vi.fn(), deleteHolding: vi.fn(), moveWatchlistGroup: vi.fn(), removeWatchlistGroup: vi.fn(),
  removeWatchlistItem: vi.fn(), saveHolding: vi.fn(), saveWatchlistGroup: vi.fn(), saveWatchlistItem: vi.fn(),
  updateHolding: vi.fn()
}))
vi.mock('echarts', () => ({
  init: vi.fn(container => ({ getDom: () => container, setOption: vi.fn(), resize: vi.fn(), dispose: vi.fn() }))
}))

const wrappers = []
function render(component, props = {}, slots = null) {
  const options = { props, attachTo: document.body, global: { plugins: [[ElementPlus, { locale: zhCn }]] } }
  if (slots) options.slots = slots
  const wrapper = mount(component, options)
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

// setup.js 里的默认 mockMedia 固定返回桌面视口，移动端用例需要临时切换
const desktopMatchMedia = window.matchMedia
function mockViewport(matches) {
  window.matchMedia = vi.fn(() => ({
    matches,
    addEventListener() {},
    removeEventListener() {}
  }))
}

// 模拟一次下拉刷新手势。jsdom 没有 TouchEvent，手动挂 touches/changedTouches。
async function pullToRefreshGesture({ from = 100, to = 300 } = {}) {
  const touch = (type, clientY) => {
    const event = new Event(type, { bubbles: true, cancelable: true })
    event.touches = type === 'touchend' ? [] : [{ clientY }]
    event.changedTouches = [{ clientY }]
    window.dispatchEvent(event)
  }
  touch('touchstart', from)
  touch('touchmove', to)
  touch('touchend', to)
  await flushPromises()
}

afterEach(() => {
  wrappers.splice(0).forEach(wrapper => wrapper.unmount())
  document.body.innerHTML = ''
  window.matchMedia = desktopMatchMedia
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

  // jsdom 没有布局，clientWidth/scrollWidth 恒为 0，这里注入测量值来驱动自适应字号
  function mockTextWidth(wrapper, { available, required }) {
    const el = wrapper.find('.stat-value').element
    el.getBoundingClientRect = () => ({ width: available })
    Object.defineProperty(el, 'scrollWidth', { value: required, configurable: true })
    const spy = vi.spyOn(window, 'getComputedStyle').mockReturnValue({
      fontSize: '20px',
      getPropertyValue: () => '11px'
    })
    wrapper.vm.fitText()
    spy.mockRestore()
    return el
  }

  it('卡片文字超宽时按比例缩小字号而不是截断', () => {
    const wrapper = render(MetricRail, { items: metricItems.slice(0, 1) }, {
      default: '<div class="stat-value">¥136149.25</div>'
    })
    // 20 * (90 - 1) / 150 ≈ 11.87，高于下限，保持单行
    const el = mockTextWidth(wrapper, { available: 90, required: 150 })
    expect(el.style.fontSize).toBe('11.87px')
    expect(el.style.whiteSpace).toBe('')
  })

  it('缩到下限仍放不下时改为折行，宁可多一行也不省略', () => {
    const wrapper = render(MetricRail, { items: metricItems.slice(0, 1) }, {
      default: '<div class="stat-value">2026-09-12 14:48:05</div>'
    })
    const el = mockTextWidth(wrapper, { available: 90, required: 320 })
    expect(el.style.fontSize).toBe('11px')
    expect(el.style.whiteSpace).toBe('normal')
    expect(el.style.lineHeight).toBe('1.25')
  })

  it('宽度够用时不动字号', () => {
    const wrapper = render(MetricRail, { items: metricItems.slice(0, 1) }, {
      default: '<div class="stat-value">¥32.09</div>'
    })
    const el = mockTextWidth(wrapper, { available: 90, required: 80 })
    expect(el.style.fontSize).toBe('')
    expect(el.style.whiteSpace).toBe('')
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
  // 顶部不再有脱敏按钮：点击汇总卡上的数值即可切换显示/隐藏
  await wrapper.find('.stat-card .stat-value').trigger('click')
  expect(wrapper.text()).toContain('1234.00')
  for (const label of ['持仓收益', '自选', '市场指数', '消息快讯', '首页']) {
    await wrapper.findAll('[role="menuitem"]').find(item => item.text() === label).trigger('click')
    await flushPromises()
    expect(wrapper.find('[role="menuitem"].is-active').text()).toBe(label)
  }
  const previous = wrapper.vm.dashboard
  api.fetchDashboard.mockRejectedValueOnce(new Error('offline'))
  await pullToRefreshGesture()
  expect(api.fetchDashboard).toHaveBeenLastCalledWith(true)
  expect(wrapper.vm.dashboard).toBe(previous)
  const clearTimer = vi.spyOn(window, 'clearInterval')
  const timer = wrapper.vm.newsRefreshTimer
  wrapper.unmount()
  wrappers.splice(wrappers.indexOf(wrapper), 1)
  expect(clearTimer).toHaveBeenCalledWith(timer)
  clearTimer.mockRestore()
})

describe('移动端导航、返回键与卡片视图', () => {
  function mockAppApis() {
    api.fetchDashboard.mockResolvedValue({ data: {
      portfolio: { positions: [], total_market_value: 1234, total_cost: 1000 },
      sectors: { gainers: [], losers: [] }, generated_at: '2026-09-12 10:00:00'
    } })
    api.fetchMarketIndices.mockResolvedValue({ data: { items: [] } })
    api.fetchNews.mockResolvedValue({ data: { items: [], groups: [], total_count: 0 } })
    api.fetchWatchlist.mockResolvedValue({ data: { items: [], groups: [] } })
  }

  it('viewport mixin 按 768px 断点初始化并响应变化', async () => {
    let changeHandler = null
    window.matchMedia = vi.fn(() => ({
      matches: true,
      addEventListener(type, callback) { changeHandler = callback },
      removeEventListener() { changeHandler = null }
    }))
    const Probe = { mixins: [viewport], render: () => h('div') }
    const wrapper = render(Probe)
    expect(wrapper.vm.isMobile).toBe(true)
    changeHandler({ matches: false })
    await nextTick()
    expect(wrapper.vm.isMobile).toBe(false)
  })

  it('底部 Tab Bar 常驻 5 个入口并切换页面', async () => {
    mockAppApis()
    const wrapper = render(App)
    await flushPromises()
    const tabs = wrapper.findAll('.mobile-tabbar__item')
    expect(tabs.map(tab => tab.text())).toEqual(['首页', '持仓', '自选', '指数', '快讯'])
    expect(tabs[0].classes()).toContain('is-active')
    await tabs[1].trigger('click')
    await flushPromises()
    expect(wrapper.vm.activeMenu).toBe('holdings')
    const switched = wrapper.findAll('.mobile-tabbar__item')
    expect(switched[1].classes()).toContain('is-active')
    expect(switched[0].classes()).not.toContain('is-active')
  })

  it('顶部不再有常驻操作按钮，刷新改由下拉手势触发', async () => {
    mockAppApis()
    const wrapper = render(App)
    await flushPromises()
    expect(wrapper.find('.nav-actions').exists()).toBe(false)
    expect(wrapper.find('.nav-icon-btn').exists()).toBe(false)
    expect(wrapper.find('.pull-refresh').text()).toContain('下拉刷新')
    api.fetchDashboard.mockClear()
    await pullToRefreshGesture()
    expect(api.fetchDashboard).toHaveBeenCalledWith(true)
    expect(wrapper.vm.pullRefreshing).toBe(false)
    expect(wrapper.vm.pullDistance).toBe(0)
  })

  it('下拉距离不足时不触发刷新', async () => {
    mockAppApis()
    const wrapper = render(App)
    await flushPromises()
    api.fetchDashboard.mockClear()
    await pullToRefreshGesture({ from: 100, to: 160 })
    expect(api.fetchDashboard).not.toHaveBeenCalledWith(true)
    expect(wrapper.vm.pullDistance).toBe(0)
  })

  it('点击汇总卡数值即可切换脱敏', async () => {
    mockAppApis()
    const wrapper = render(App)
    await flushPromises()
    expect(wrapper.text()).toContain('****')
    await wrapper.find('.stat-card .stat-value').trigger('click')
    expect(wrapper.vm.holdingsNumbersVisible).toBe(true)
    expect(wrapper.text()).toContain('1234.00')
    await wrapper.find('.stat-card .stat-value').trigger('click')
    expect(wrapper.vm.holdingsNumbersVisible).toBe(false)
  })

  it('物理返回键先关弹窗、再回首页，位于首页时才交还系统', async () => {
    mockAppApis()
    const wrapper = render(App)
    await flushPromises()
    await wrapper.findAll('.mobile-tabbar__item')[1].trigger('click')
    await flushPromises()
    expect(wrapper.vm.activeMenu).toBe('holdings')
    wrapper.vm.createDialogVisible = true
    await nextTick()
    expect(wrapper.vm.handleNativeBack()).toBe(true)
    expect(wrapper.vm.createDialogVisible).toBe(false)
    expect(wrapper.vm.activeMenu).toBe('holdings')
    expect(wrapper.vm.handleNativeBack()).toBe(true)
    expect(wrapper.vm.activeMenu).toBe('home')
    expect(wrapper.vm.handleNativeBack()).toBe(false)
  })

  it('移动端持仓改渲染卡片列表，保留走势与增删入口', async () => {
    mockViewport(true)
    const dashboard = { portfolio: {
      total_market_value: 0,
      total_holding_pnl: 0,
      total_holding_pnl_rate: 0,
      total_estimated_pnl: 0,
      total_estimated_pnl_rate: 0,
      total_today_pnl: 0,
      total_today_pnl_rate: 0,
      positions: [{
        id: 1, name: '测试ETF', code: '510300', asset_type: 'etf', quantity: 200, cost_price: 3.1,
        current_price: 3.4, estimated_price: null, previous_close: 3.3, estimated_change_rate: 1.2,
        estimated_pnl: 60, today_pnl: 20, holding_pnl: 60, holding_pnl_rate: 3.2, daily_change_rate: 3.03
      }]
    } }
    const wrapper = render(HoldingsPanel, { dashboard, numbersVisible: true })
    await flushPromises()
    expect(wrapper.find('table').exists()).toBe(false)
    expect(wrapper.findAll('.data-card')).toHaveLength(1)
    expect(wrapper.text()).toContain('测试ETF')
    for (const label of ['现价', '成本价', '昨日收盘', '预估收益', '当日收益', '持有收益', '实际涨幅', '预估涨幅']) {
      expect(wrapper.text()).toContain(label)
    }
    // 顶部大号取预估涨幅，底部首项改取实际（当日）涨幅，两者引用的数值互换
    expect(wrapper.find('.data-card__rate').text()).toBe('1.20%')
    // 底部三项复用 .data-card__cell：标签在上、数值在下，与上方网格同构
    const foot = wrapper.find('.data-card__foot')
    expect(foot.findAll('.data-card__cell span').map(node => node.text()))
      .toEqual(['实际涨幅', '预估涨幅', '持有收益率'])
    expect(foot.findAll('.data-card__cell strong').map(node => node.text()))
      .toEqual(['3.03%', '1.20%', '3.20%'])
    await wrapper.find('.data-card__name').trigger('click')
    expect(wrapper.emitted('open-chart')[0][0].code).toBe('510300')
    await clickButton(wrapper, '删除')
    expect(wrapper.emitted('remove')).toEqual([[1]])
  })

  it('移动端自选基金卡片补齐估值与预估涨幅两格', async () => {
    mockViewport(true)
    const wrapper = render(WatchlistPanel, {
      loaded: true,
      category: 'fund',
      selectedGroupId: 2,
      watchlist: {
        groups: [{ id: 2, name: '场外基金', category: 'fund', is_default: 1 }],
        items: [{
          id: 9, group_id: 2, code: '001632', name: '测试基金', asset_type: 'fund',
          current_price: 2.49, estimated_price: 2.5, previous_close: 2.51,
          daily_change_rate: -0.8, estimated_change_rate: -0.4, source_label: '基金123'
        }]
      }
    })
    await flushPromises()
    expect(wrapper.find('table').exists()).toBe(false)
    expect(wrapper.findAll('.data-card')).toHaveLength(1)
    expect(wrapper.findAll('.data-card__cell span').map(node => node.text()))
      .toEqual(['估值', '现价', '昨日收盘', '当日涨幅', '预估涨幅'])
    expect(wrapper.text()).toContain('基金123')
    await clickButton(wrapper, '删除')
    expect(wrapper.emitted('delete-item')).toEqual([[9]])
  })
})

describe('页面顶部精简：移除标题、介绍与演示数据入口', () => {
  const dashboard = {
    portfolio: {
      positions: [],
      total_market_value: 0,
      total_cost: 0,
      total_holding_pnl: 0,
      total_holding_pnl_rate: 0,
      total_estimated_pnl: 0,
      total_estimated_pnl_rate: 0,
      total_today_pnl: 0,
      total_today_pnl_rate: 0
    },
    sectors: { gainers: [], losers: [], source_label: '测试' },
    generated_at: '2026-09-12 10:00:00'
  }
  const newsFeed = { groups: [], items: [], total_count: 0, generated_at: '2026-09-12 10:00:00' }

  it('持仓页整块页头与「导入演示持仓」入口一并移除', async () => {
    const wrapper = render(HoldingsPanel, { dashboard })
    await flushPromises()
    expect(wrapper.find('.page-heading').exists()).toBe(false)
    expect(buttonByText(wrapper, '导入演示持仓')).toBeNull()
    expect(wrapper.find('h2').exists()).toBe(false)
  })

  it('自选 / 快讯 / 指数页头只保留更新时间与刷新操作', async () => {
    const watchlist = render(WatchlistPanel, {
      loaded: true,
      watchlist: { groups: [], items: [], generated_at: '2026-09-12 10:00:00' }
    })
    const news = render(NewsPanel, { newsFeed })
    const market = render(MarketPanel, { dashboard, marketIndices: [], tab: 'cn', updatedAt: '2026-09-12 10:00:00' })
    for (const wrapper of [watchlist, news, market]) {
      const heading = wrapper.find('.page-heading')
      expect(heading.exists()).toBe(true)
      expect(heading.find('h2').exists()).toBe(false)
      expect(heading.find('p').exists()).toBe(false)
      expect(heading.text()).toContain('更新')
    }
  })

  it('首页不再渲染 hero 主视觉，由指标轨道直接开场', async () => {
    const wrapper = render(HomePanel, { dashboard, newsFeed })
    await flushPromises()
    expect(wrapper.find('.hero-card').exists()).toBe(false)
    expect(wrapper.find('h1').exists()).toBe(false)
    expect(wrapper.findAll('.metric-rail__cell').length).toBeGreaterThan(0)
  })
})

describe('滚动吸顶：切页控件的挂载点', () => {
  // jsdom 没有布局，「是否真的吸附在视口顶部」只能用无头 Chrome 实测
  // （见 docs/CODE_STANDARDS.md）；这里只锁住 CSS 选择器依赖的结构，
  // 避免以后改模板时把吸顶规则悄悄断开。
  const dashboard = {
    portfolio: {
      positions: [],
      total_market_value: 0,
      total_cost: 0,
      total_holding_pnl: 0,
      total_holding_pnl_rate: 0,
      total_estimated_pnl: 0,
      total_estimated_pnl_rate: 0,
      total_today_pnl: 0,
      total_today_pnl_rate: 0
    },
    sectors: { gainers: [], losers: [], source_label: '测试' },
    generated_at: '2026-09-12 10:00:00'
  }
  const newsFeed = {
    total_count: 1,
    generated_at: '2026-09-12 10:00:00',
    groups: [
      {
        source: '财联社电报',
        items: [{ id: 1, title: '标题', summary: '摘要', published_at: '2026-09-12 10:00:00', url: '' }]
      }
    ]
  }

  it('自选页选项卡位于带吸顶标记的卡片内', () => {
    const wrapper = render(WatchlistPanel, {
      loaded: true,
      watchlist: {
        generated_at: '2026-09-12 10:00:00',
        groups: [{ id: 1, name: '场内自选', category: 'exchange', is_default: 1 }],
        items: []
      },
      selectedGroupId: 1
    })
    const card = wrapper.find('.panel-card.watchlist-card')
    expect(card.exists()).toBe(true)
    expect(card.find('.el-tabs').exists()).toBe(true)
  })

  it('指数页选项卡自带吸顶标记 class', () => {
    const wrapper = render(MarketPanel, {
      dashboard,
      marketIndices: [],
      tab: 'cn',
      updatedAt: '2026-09-12 10:00:00'
    })
    expect(wrapper.find('.el-tabs.market-index-tabs').exists()).toBe(true)
  })

  it('快讯页每个来源卡片都带吸顶标记，标题行即吸附元素', () => {
    const wrapper = render(NewsPanel, { newsFeed })
    expect(wrapper.findAll('.news-source-card').length).toBe(1)
    expect(wrapper.findAll('.news-source-card .el-card__header').length).toBe(1)
    expect(wrapper.find('.news-source-card .el-card__header').text()).toContain('财联社电报')
  })
})
