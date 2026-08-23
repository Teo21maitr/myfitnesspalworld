import '@testing-library/jest-dom/vitest'

import { beforeAll } from 'vitest'

beforeAll(() => {
  // jsdom n'implémente pas matchMedia, utilisé par le ThemeProvider.
  if (!window.matchMedia) {
    Object.defineProperty(window, 'matchMedia', {
      writable: true,
      value: (query: string) => ({
        matches: false,
        media: query,
        onchange: null,
        addEventListener: () => {},
        removeEventListener: () => {},
        dispatchEvent: () => false,
      }),
    })
  }
})
