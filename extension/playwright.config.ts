import { defineConfig, devices } from '@playwright/test';
import path from 'path';

const extPath = path.resolve(__dirname, 'build', 'chrome-mv3-dev');

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: {
          headless: false,
          args: [
            `--disable-extensions-except=${extPath}`,
            `--load-extension=${extPath}`,
          ],
        },
      },
    },
  ],
});
