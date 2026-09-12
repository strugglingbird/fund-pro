/**
 * 移动端布局诊断：用本机 Chrome 的无头模式 + CDP 在指定视口渲染页面，
 * 输出关键元素的计算样式与几何信息，并可截图。
 *
 * 用途：jsdom 没有布局，vitest 无法验证响应式行为（媒体查询、固定定位、
 * 横向溢出）。改动移动端样式后用它确认真实渲染结果，避免靠肉眼猜。
 *
 * 用法：node scripts/probe-layout.mjs <url> <width> <height> [outPng] [portOffset] [menuLabel]
 * 示例：node scripts/probe-layout.mjs http://localhost:8080 390 844 shot.png 0 持仓
 *
 * menuLabel 会先点击同名导航项（底部 Tab Bar 或桌面菜单）再测量，
 * 用于逐页检查页头是否残留标题/介绍。
 */
const url = process.argv[2] || 'http://localhost:8080'
const width = Number(process.argv[3] || 390)
const height = Number(process.argv[4] || 844)
const outPng = process.argv[5] || ''
const port = 9223 + (Number(process.argv[6]) || 0)
const menuLabel = process.argv[7] || ''

const CHROME_CANDIDATES = [
  'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
  'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe'
]

const { spawn } = await import('node:child_process')
const fs = await import('node:fs')

let chromePath = ''
for (const candidate of CHROME_CANDIDATES) {
  if (fs.existsSync(candidate)) {
    chromePath = candidate
    break
  }
}
if (!chromePath) throw new Error('未找到 Chrome/Edge 可执行文件')

const chrome = spawn(chromePath, [
  '--headless=new',
  '--disable-gpu',
  '--no-first-run',
  '--no-default-browser-check',
  `--remote-debugging-port=${port}`,
  `--user-data-dir=${process.cwd()}\\.workbuddy\\chrome-profile-cdp`
], { stdio: 'ignore' })

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))

async function getWsUrl() {
  for (let i = 0; i < 40; i += 1) {
    try {
      const res = await fetch(`http://127.0.0.1:${port}/json/version`)
      const data = await res.json()
      if (data.webSocketDebuggerUrl) return data.webSocketDebuggerUrl
    } catch (error) {
      /* 端口还没起来，继续重试 */
    }
    await sleep(250)
  }
  throw new Error('CDP 未就绪')
}

const ws = new WebSocket(await getWsUrl())
await new Promise((resolve, reject) => {
  ws.addEventListener('open', resolve, { once: true })
  ws.addEventListener('error', reject, { once: true })
})

let messageId = 0
const pending = new Map()
ws.addEventListener('message', event => {
  const msg = JSON.parse(event.data)
  if (!msg.id || !pending.has(msg.id)) return
  const { resolve, reject } = pending.get(msg.id)
  pending.delete(msg.id)
  if (msg.error) reject(new Error(JSON.stringify(msg.error)))
  else resolve(msg.result)
})

function send(method, params = {}, sessionId) {
  messageId += 1
  const payload = { id: messageId, method, params }
  if (sessionId) payload.sessionId = sessionId
  ws.send(JSON.stringify(payload))
  return new Promise((resolve, reject) => pending.set(messageId, { resolve, reject }))
}

try {
  const { targetId } = await send('Target.createTarget', { url: 'about:blank' })
  const { sessionId } = await send('Target.attachToTarget', { targetId, flatten: true })
  await send('Page.enable', {}, sessionId)
  await send('Runtime.enable', {}, sessionId)
  await send('Emulation.setDeviceMetricsOverride', {
    width,
    height,
    deviceScaleFactor: 1,
    mobile: width <= 768
  }, sessionId)
  await send('Page.navigate', { url }, sessionId)
  await sleep(6000)

  async function clickMenu(label) {
    const clicked = await send('Runtime.evaluate', {
      expression: `
      (() => {
        const items = [...document.querySelectorAll('.mobile-tabbar__item, [role="menuitem"]')]
        const target = items.find(el => el.textContent.trim() === ${JSON.stringify(label)})
        if (!target) return false
        target.click()
        return true
      })()
      `,
      returnByValue: true
    }, sessionId)
    if (!clicked.result.value) console.log('MENU_MISS ' + label)
    await sleep(2500)
  }

  const expression = `
  (() => {
    const pick = (selector) => {
      const el = document.querySelector(selector)
      if (!el) return null
      const cs = getComputedStyle(el)
      const r = el.getBoundingClientRect()
      return {
        display: cs.display,
        position: cs.position,
        width: Math.round(r.width),
        height: Math.round(r.height),
        top: Math.round(r.top),
        left: Math.round(r.left)
      }
    }
    return JSON.stringify({
      innerWidth: window.innerWidth,
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      mediaMatch: window.matchMedia('(max-width: 768px)').matches,
      tabbar: pick('.mobile-tabbar'),
      tabbarItems: document.querySelectorAll('.mobile-tabbar__item').length,
      hero: pick('.hero-card'),
      h1Count: document.querySelectorAll('h1').length,
      pageHeading: pick('.page-heading'),
      pageHeadingCount: document.querySelectorAll('.page-heading').length,
      pageHeadingH2: document.querySelectorAll('.page-heading h2').length,
      pageHeadingP: document.querySelectorAll('.page-heading p').length,
      pageHeadingText: (document.querySelector('.page-heading') || { textContent: '' }).textContent.trim(),
      pageHeadingButtons: [...document.querySelectorAll('.page-heading .el-button')].map(el => ({
        text: el.textContent.trim(),
        display: getComputedStyle(el).display,
        width: Math.round(el.getBoundingClientRect().width)
      })),
      firstBlockTop: (() => {
        const el = document.querySelector('.metric-rail, .stats-row, .panel-card, .index-card')
        return el ? Math.round(el.getBoundingClientRect().top) : null
      })(),
      nav: pick('.workspace-nav'),
      menu: pick('.workspace-menu'),
      pullRefresh: pick('.pull-refresh'),
      rail: pick('.metric-rail'),
      dataCards: document.querySelectorAll('.data-card').length,
      tables: document.querySelectorAll('.el-table').length
    })
  })()
  `
  const labels = menuLabel ? menuLabel.split(',').map(item => item.trim()).filter(Boolean) : []
  async function measure(tag) {
    const { result } = await send('Runtime.evaluate', { expression, returnByValue: true }, sessionId)
    console.log('RESULT[' + tag + '] ' + result.value)
  }

  await measure('default')
  for (const label of labels) {
    await clickMenu(label)
    await measure(label)
  }

  if (outPng) {
    const shot = await send('Page.captureScreenshot', { format: 'png' }, sessionId)
    fs.writeFileSync(outPng, Buffer.from(shot.data, 'base64'))
    console.log('SHOT ' + outPng)
  }
} finally {
  ws.close()
  chrome.kill()
}
process.exit(0)
