# Using Playwright CDP Attach (Advanced)

This document explains how to allow the backend Playwright runner to attach to an already-running Chrome instance using the Chrome DevTools Protocol (CDP).

⚠️ Security note: exposing a debugging port allows remote control of your browser. Only enable this on trusted machines/networks.

## Steps (Linux / macOS)
1. Close all running Chrome instances.
2. Start Chrome with remote debugging enabled:

   ```bash
   # Example (Linux / macOS)
   google-chrome --remote-debugging-port=9222 --user-data-dir=/tmp/chrome-profile
   ```

3. Confirm CDP is reachable:
   - Visit http://localhost:9222/json in your browser. You should see a JSON list of open pages and a "webSocketDebuggerUrl" field.

4. In the JobHunter popup, enable **Isolated browser** mode and toggle **Enable Playwright CDP attach (advanced)**. Then execute your task; the backend will attempt to use CDP to attach to the running browser.

E2E testing note: Our E2E tests launch a persistent Chromium profile with `--load-extension` to deterministically load the extension before page navigation. This avoids fragile in-test shims and aligns with how we validate in-tab flows in CI.

## Steps (Windows)
1. Close Chrome.
2. Start Chrome from PowerShell or a shortcut with:

   ```powershell
   "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="C:\temp\chrome-profile"
   ```

## Notes
- If your Chrome is started with multiple profiles, point to a dedicated `--user-data-dir` to avoid profile corruption.
- If the backend cannot connect to the CDP endpoint, it will fall back to launching an isolated browser (if implemented) or fail with an explanatory error.
- For more details see Playwright docs: https://playwright.dev/docs/chrome-cdp

If you want, I can add a small popup tooltip that shows the `ws://` endpoint detected from `http://localhost:9222/json` once the backend implements endpoint discovery.