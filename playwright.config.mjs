import { defineConfig, devices } from '@playwright/test';

const buildRoot = 'build/playwright';

export default defineConfig({
  testDir: './tests/browser',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  timeout: 90_000,
  expect: {
    timeout: 15_000,
  },
  reporter: [
    ['list'],
    ['html', { outputFolder: `${buildRoot}/report`, open: 'never' }],
  ],
  outputDir: `${buildRoot}/results`,
  use: {
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'off',
  },
  webServer: {
    command: 'tools/serve_local_stack.sh',
    url: 'http://127.0.0.1:8767/',
    reuseExistingServer: false,
    timeout: 240_000,
    gracefulShutdown: {
      signal: 'SIGTERM',
      timeout: 15_000,
    },
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'webkit',
      testIgnore: '**/authenticated-editor.spec.mjs',
      use: { ...devices['Desktop Safari'] },
    },
  ],
});
