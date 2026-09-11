import { vi } from 'vitest'

// jsdom has no layout observer; keep the actual Element Plus components mounted.
globalThis.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
}
window.matchMedia = vi.fn(() => ({ matches: false, addEventListener() {}, removeEventListener() {} }))
