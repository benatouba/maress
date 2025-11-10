import { fileURLToPath } from 'node:url'
import { mergeConfig, defineConfig, configDefaults } from 'vitest/config'
import viteConfig from './vite.config.mts'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      exclude: [...configDefaults.exclude, 'e2e/*'],
      root: fileURLToPath(new URL('./', import.meta.url)),
      globals: true,
      coverage: {
        provider: 'v8',
        reporter: ['text', 'json', 'html', 'lcov'],
        exclude: [
          'node_modules/',
          'src/tests/',
          '**/*.spec.ts',
          '**/*.test.ts',
          '**/mocks/',
          '**/utils/test-utils.ts',
          'vite.config.mts',
          'vitest.config.ts',
        ],
        include: [
          'src/**/*.ts',
          'src/**/*.vue',
        ],
        statements: 80,
        branches: 80,
        functions: 80,
        lines: 80
      },
      setupFiles: ['./src/tests/setup.ts']
    }
  })
)
