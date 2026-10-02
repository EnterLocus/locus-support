const { defineConfig } = require('@playwright/test');
module.exports = defineConfig({
  testDir: './tests/search',
  use: { baseURL: 'http://127.0.0.1:4186', browserName: 'chromium', channel: process.env.BROWSER_CHANNEL || undefined },
  webServer: { command: 'python3 tools/serve_site.py', url: 'http://127.0.0.1:4186', reuseExistingServer: false },
});
