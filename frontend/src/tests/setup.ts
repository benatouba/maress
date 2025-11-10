import { vi } from 'vitest'
import { config } from '@vue/test-utils'

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation(query => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Mock IntersectionObserver
global.IntersectionObserver = class IntersectionObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  takeRecords() {
    return []
  }
  unobserve() {}
} as any

// Mock ResizeObserver
global.ResizeObserver = class ResizeObserver {
  constructor() {}
  disconnect() {}
  observe() {}
  unobserve() {}
} as any

// Mock scrollTo
window.scrollTo = vi.fn()

// Global Vue Test Utils config
config.global.stubs = {
  transition: false,
  'transition-group': false
}

// Suppress console warnings in tests
global.console.warn = vi.fn()

// Mock environment variables
process.env.VITE_API_BASE_URL = 'http://localhost:3000'
process.env.VITE_API_V1_URL = 'http://localhost:3000/api/v1'
