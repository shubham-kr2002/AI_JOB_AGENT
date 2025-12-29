# E2E Strategy & Test Guidelines

This document describes how our Playwright E2E tests load and validate the Chrome extension and in-tab flows.

## Goals
- Run deterministic end-to-end tests against a Chromium instance with the extension loaded.
- Avoid flaky in-test script injection shims by ensuring the extension content script executes in-page.
- Provide reproducible CI runs and a documented strategy for future contributors.

## How tests load the extension
- Tests use Playwright's `launchPersistentContext()` with a `userDataDir` and the Chromium args:
  - `--disable-extensions-except=<build-dir>`
  - `--load-extension=<build-dir>`
- This ensures the extension is loaded into the profile before pages are opened and content scripts run.

## Deterministic checks
- Tests wait for the content script to expose `window.JobHunter.executeStep` using Playwright's `page.waitForFunction(...)`.
- If `JobHunter` is not present after a short timeout, the test fails explicitly — this keeps failures deterministic and obvious.

## When to use a shim (only for debugging)
- Small in-page shims were used temporarily during development to unblock the CI while we stabilized loading — these are not used in committed tests.

## CDP notes (dev/advanced use)
- For attaching to a running browser via CDP (advanced workflows): see `design/CDP.md` — tests and the backend can optionally use Playwright CDP attach to work with a user browser session.
- CDP attach is **not** used in CI but is useful for local debugging against logged-in sessions.

## CI
- Playwright tests run in GitHub Actions (`.github/workflows/e2e-playwright.yml`). The workflow installs Playwright browsers and runs `npm run test:e2e` in `extension/`.

## Adding tests
- Prefer launching Chromium with `--load-extension` rather than injecting shims.
- Keep tests site-agnostic where possible; use simple static pages for verifying basic actions (type/click/scrape/loop/parse/apply scaffolding).
