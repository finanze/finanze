import "@testing-library/jest-dom/vitest"

global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
}
