# In-Tab Execution (Content Script) — Design Notes

This document explains the in-tab execution behavior and content-script responsibilities.

## Overview
- The extension in-tab mode allows the content script (`src/contents/jobhunter.ts`) to execute plan steps inside the user's active browser tab.
- Steps are created by the backend planner and may include actions like: `navigate`, `click`, `type`, `extract`, `wait`, `search`, `scrape`, `parse`, `loop`, `verify`, `submit`, `apply`.

## Content script features
- `executeStep(taskId, step)`: Core exported function that performs a single step and returns `{ success, data?, error? }`.
- Robust error reporting and retry support: steps can specify `payload.retries` to attempt multiple times with backoff.
- `sendStepResult(...)`: Sends structured step results (including `meta` with timestamp/attempt) to the background service which forwards to the backend.
- Site-specific helpers: `parseLinkedInResults`, `parseIndeedResults`, `handleLinkedInApply`, `handleIndeedApply`.

## Site permissions
- For safety, extension content script injections are restricted to a curated list of job sites in `.plasmo/chrome-mv3.plasmo.manifest.json` (LinkedIn, Indeed, Glassdoor, Greenhouse, Lever, Workday) and localhost for testing.

## Tests
- Unit tests added under `extension/src/contents/__tests__/jobhunter.test.ts` using `jest` + `ts-jest` (jsdom environment) to validate `executeStep` behavior for common actions.

## Next improvements
- Add richer site-specific apply & form flows for each target site.
- Add Playwright-based e2e tests that run the extension in a Chromium profile and validate an end-to-end in-tab flow on test accounts.
- Add runtime feature-detection to gracefully degrade when selectors change.

If you'd like, I can implement deeper site-specific flows for LinkedIn and Indeed next and add Playwright e2e tests to automate end-to-end verification.