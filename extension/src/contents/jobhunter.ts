/**
 * JobHunter Extension - Content Script
 * Plasmo Content Script with DOM manipulation
 * 
 * Features:
 * - Form scraping (FR-01, FR-02)
 * - Event simulation (FR-03)
 * - Iterative DOM re-scan (NFR-03)
 * - JD scraping (FR-07)
 * - Feedback capture (AIR-03)
 */

import type { PlasmoCSConfig } from 'plasmo';
import { scrapeForm, scrapeJobDescription, fillForm, captureCorrections } from '../lib/form-utils';
import type { FormField, FieldAnswer, AutoFillResponse, GenerateAnswersRequest } from '../types';

// Plasmo content script config
export const config: PlasmoCSConfig = {
  matches: ['<all_urls>'],
  all_frames: true,
  run_at: 'document_idle',
};

const API_BASE_URL = 'http://localhost:8001/api/v1';
const RESCAN_INTERVAL = 2000; // NFR-03: 2 seconds

console.log('[JobHunter] Content script loaded on:', window.location.href);

// State
let isFillingActive = false;
let rescanTimer: ReturnType<typeof setInterval> | null = null;
let previousFieldCount = 0;

/**
 * Start DOM monitoring for dynamic forms (NFR-03)
 */
function startDOMMonitor(): void {
  if (rescanTimer) {
    clearInterval(rescanTimer);
  }

  isFillingActive = true;
  previousFieldCount = scrapeForm().length;

  rescanTimer = setInterval(() => {
    if (!isFillingActive) {
      stopDOMMonitor();
      return;
    }

    const currentFields = scrapeForm();
    const currentCount = currentFields.length;

    if (currentCount !== previousFieldCount) {
      console.log(`[JobHunter] DOM changed: ${previousFieldCount} → ${currentCount} fields`);

      // Notify about new fields
      chrome.runtime.sendMessage({
        action: 'newFieldsDetected',
        fields: currentFields.filter((f) => true), // New fields
        totalFields: currentCount,
      });

      previousFieldCount = currentCount;
    }
  }, RESCAN_INTERVAL);

  console.log('[JobHunter] DOM monitor started');
}

/**
 * Stop DOM monitoring
 */
function stopDOMMonitor(): void {
  isFillingActive = false;
  if (rescanTimer) {
    clearInterval(rescanTimer);
    rescanTimer = null;
  }
  console.log('[JobHunter] DOM monitor stopped');
}

/**
 * Get answers from backend API
 */
async function getAnswersFromBackend(fields: FormField[]): Promise<any> {
  const jobDescription = scrapeJobDescription();

  const request: GenerateAnswersRequest = {
    fields,
    job_description: jobDescription,
    page_url: window.location.href,
    use_hallucination_guard: true,
  };

  const response = await fetch(`${API_BASE_URL}/generate-answers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to get answers');
  }

  return response.json();
}

/**
 * Full auto-fill flow
 */
async function autoFillForm(): Promise<AutoFillResponse> {
  console.log('[JobHunter] Starting auto-fill...');

  // Step 1: Scrape form fields
  const fields = scrapeForm();
  console.log(`[JobHunter] Found ${fields.length} fields:`, fields);

  if (fields.length === 0) {
    return { success: false, message: 'No form fields found' };
  }

  // Step 2: Get answers from backend
  console.log('[JobHunter] Sending to backend...');
  const response = await getAnswersFromBackend(fields);
  console.log('[JobHunter] Received answers:', response);

  if (!response.success) {
    return { success: false, message: response.message || 'Failed to generate answers' };
  }

  // Step 3: Fill the form
  console.log('[JobHunter] Filling form...');
  const fillResults = fillForm(response.answers);
  console.log('[JobHunter] Fill results:', fillResults);

  // Step 4: Start DOM monitor
  startDOMMonitor();

  // Step 5: Setup feedback capture
  setupFeedbackCapture();

  return {
    success: true,
    fieldsFound: fields.length,
    fieldsFilled: fillResults.filled,
    fieldsSkipped: fillResults.skipped,
    fieldsFlagged: fillResults.flagged,
    errors: fillResults.errors,
    jobContext: response.job_context,
    message: `Filled ${fillResults.filled} of ${fields.length} fields${
      fillResults.flagged > 0 ? ` (${fillResults.flagged} need review)` : ''
    }`,
  };
}

/**
 * Capture and send feedback
 */
async function captureFeedback(): Promise<any[]> {
  const corrections = captureCorrections();

  if (corrections.length > 0) {
    console.log(`[JobHunter] Sending ${corrections.length} corrections...`);

    for (const correction of corrections) {
      try {
        await fetch(`${API_BASE_URL}/feedback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            question: correction.question,
            original_answer: correction.original_answer,
            corrected_answer: correction.corrected_answer,
            field_type: 'text',
            job_context: window.location.href,
          }),
        });
      } catch (error) {
        console.error('[JobHunter] Feedback error:', error);
      }
    }

    console.log('[JobHunter] Feedback sent');
  }

  return corrections;
}

/**
 * Setup feedback capture on form submit
 */
function setupFeedbackCapture(): void {
  document.querySelectorAll('form').forEach((form) => {
    form.addEventListener('submit', async () => {
      await captureFeedback();
    }, { once: true });
  });

  document.querySelectorAll('button[type="submit"], input[type="submit"]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      await captureFeedback();
    }, { once: true });
  });

  console.log('[JobHunter] Feedback capture setup');
}

// Helper to send step results in a consistent structure
function sendStepResult(taskId: string, stepId: string, stepName: string, success: boolean, payload: any = {}, meta: any = {}) {
  const msg = {
    action: 'stepResult',
    taskId,
    stepId,
    stepName,
    success,
    data: payload,
    meta: {
      timestamp: Date.now(),
      ...meta,
    },
  };
  try {
    chrome.runtime.sendMessage(msg);
  } catch (err) {
    // Best-effort; log locally
    console.error('[JobHunter] Failed to send step result to background:', err, msg);
  }
}

// Execute a single step (exported for testing)
export async function executeStep(taskId: string, step: any): Promise<{ success: boolean; data?: any; error?: string }>{
  const stepId = step.id || step.name || 'step';
  const stepName = step.name || step.action;

  async function attemptAction(act: string, payload: any) {
    switch ((act || '').toLowerCase()) {
      case 'navigate':
        if (payload && payload.url) {
          window.location.href = payload.url;
          await Promise.race([
            new Promise((res) => window.addEventListener('load', () => res(null), { once: true })),
            new Promise((res) => setTimeout(res, payload.timeout || 5000)),
          ]);
          return { url: window.location.href };
        }
        throw new Error('No URL provided');

      case 'click': {
        const selector = payload?.selector || payload?.target;
        if (!selector) throw new Error('No selector provided for click');
        const el = document.querySelector(selector) as HTMLElement | null;
        if (el) {
          el.click();
          await new Promise((r) => setTimeout(r, payload?.postDelay || 800));
          return { clicked: selector };
        }
        // Try text-based find
        const text = payload?.target_text;
        if (text) {
          const el2 = Array.from(document.querySelectorAll('button, a')).find(e => (e.textContent||'').trim().includes(text));
          if (el2) {
            (el2 as HTMLElement).click();
            await new Promise((r) => setTimeout(r, payload?.postDelay || 800));
            return { clicked: 'by_text', text };
          }
        }
        throw new Error('Element not found');
      }

      case 'type': {
        const selector = payload?.selector || payload?.target;
        const text = payload?.text || payload?.value || payload?.query || '';
        if (!selector) throw new Error('No selector for type');
        const input = document.querySelector(selector) as HTMLInputElement | HTMLTextAreaElement | null;
        if (!input) throw new Error('Input element not found');
        input.focus();
        input.value = text;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        await new Promise((r) => setTimeout(r, 400));
        return { typed: text };
      }

      case 'extract': {
        const selector = payload?.selector;
        if (!selector) throw new Error('No selector for extract');
        const el = document.querySelector(selector);
        const text = el ? (el.textContent || '').trim() : null;
        return { extracted: text };
      }

      case 'wait': {
        const ms = payload?.ms || 1000;
        await new Promise((r) => setTimeout(r, ms));
        return { waited: ms };
      }

      case 'search': {
        // Generic search fallback: try to type into a search box or construct site-specific url
        const q = payload?.query || payload?.text || '';
        if (!q) throw new Error('No query provided for search');

        const host = window.location.hostname;
        // LinkedIn jobs search
        if (host.includes('linkedin.com')) {
          const url = `https://www.linkedin.com/jobs/search?keywords=${encodeURIComponent(q)}`;
          window.location.href = url;
          await new Promise((r) => setTimeout(r, 1500));
          return { navigated: url };
        }

        // Indeed search
        if (host.includes('indeed.com')) {
          const url = `https://www.indeed.com/jobs?q=${encodeURIComponent(q)}`;
          window.location.href = url;
          await new Promise((r) => setTimeout(r, 1500));
          return { navigated: url };
        }

        // Generic: try to find input[type=search] or input[name=q]
        const input = document.querySelector('input[type="search"], input[name="q"], input[aria-label*="search"]') as HTMLInputElement | null;
        if (input) {
          input.focus();
          input.value = q;
          input.dispatchEvent(new Event('input', { bubbles: true }));
          input.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', bubbles: true } as any));
          await new Promise((r) => setTimeout(r, 1200));
          return { typed: q };
        }

        // As last resort, use Google site search
        const googleUrl = `https://www.google.com/search?q=site:${host}+${encodeURIComponent(q)}`;
        window.location.href = googleUrl;
        await new Promise((r) => setTimeout(r, 1500));
        return { navigated: googleUrl };
      }

      case 'scrape': {
        const selector = payload?.selector;
        if (!selector) throw new Error('No selector for scrape');
        const nodes = Array.from(document.querySelectorAll(selector));
        const items = nodes.map((n) => ({ text: (n.textContent || '').trim(), html: (n as HTMLElement).outerHTML }));
        return { items, total: items.length };
      }

      case 'parse': {
        // High-level parse for job result pages. Delegates to site-specific parsers if available.
        const host = window.location.hostname;
        if (host.includes('linkedin.com')) {
          return { items: parseLinkedInResults(), total: document.querySelectorAll('.jobs-search-results__list-item').length };
        }
        if (host.includes('indeed.com')) {
          return { items: parseIndeedResults(), total: document.querySelectorAll('.jobsearch-SerpJobCard').length };
        }
        // Generic parse: attempt to find job titles and links
        const titles = Array.from(document.querySelectorAll('a[href*="job"]')).slice(0, 20).map((a: any) => ({ title: (a.textContent||'').trim(), href: a.href }));
        return { items: titles, total: titles.length };
      }

      case 'loop': {
        // Steps: payload.items_selector, payload.substeps
        const sel = payload?.items_selector;
        const substeps = payload?.substeps || [];
        if (!sel) throw new Error('No items_selector for loop');
        const nodes = Array.from(document.querySelectorAll(sel));
        const results: any[] = [];
        for (let i = 0; i < nodes.length; i++) {
          const el = nodes[i] as HTMLElement;
          try {
            // Bring into view
            el.scrollIntoView({ behavior: 'auto', block: 'center' });
            // Optionally click to open
            if (payload?.clickOnItem !== false) {
              (el as HTMLElement).click();
              await new Promise((r) => setTimeout(r, 600));
            }

            // Execute substeps in the context of the item
            for (const sub of substeps) {
              // If sub has selector starting with $this, replace it
              const cloned = JSON.parse(JSON.stringify(sub));
              if (cloned.payload?.selector && cloned.payload.selector.startsWith('$this')) {
                cloned.payload.selector = `${sel} :scope ${cloned.payload.selector.replace(/^\$this\s*/, '')}`;
              }
              await attemptAction(cloned.action, cloned.payload);
            }

            results.push({ index: i, success: true });
          } catch (e: any) {
            results.push({ index: i, success: false, error: e.message });
          }
        }
        return { results };
      }

      case 'verify': {
        const selector = payload?.selector;
        if (!selector) throw new Error('No selector for verify');
        const el = document.querySelector(selector);
        if (!el) throw new Error('Element not found for verify');
        if (payload?.text) {
          const txt = (el.textContent||'').trim();
          if (!txt.includes(payload.text)) throw new Error('Text mismatch in verify');
          return { verified: true, text: txt };
        }
        return { exists: true };
      }

      case 'submit': {
        const selector = payload?.selector;
        if (selector) {
          const form = document.querySelector(selector) as HTMLFormElement | null;
          if (form) {
            form.submit();
            return { submitted: selector };
          }
        }
        // Try generic submit buttons
        const btn = document.querySelector('button[type="submit"], input[type="submit"]') as HTMLButtonElement | null;
        if (btn) {
          btn.click();
          return { submitted: 'button' };
        }
        throw new Error('No submit target found');
      }

      case 'apply': {
        // High-level apply action for job pages (site-specific)
        const host = window.location.hostname;
        if (host.includes('linkedin.com')) {
          return handleLinkedInApply(payload || {});
        }
        if (host.includes('indeed.com')) {
          return handleIndeedApply(payload || {});
        }
        throw new Error('Apply action not implemented for this site');
      }

      default:
        throw new Error(`Unsupported action in content script: ${act}`);
    }
  }

  // Site-specific parsers
  function parseLinkedInResults() {
    const items = [] as any[];
    document.querySelectorAll('.jobs-search-results__list-item').forEach((el) => {
      const title = (el.querySelector('.base-search-card__title')?.textContent || '').trim();
      const company = (el.querySelector('.base-search-card__subtitle')?.textContent || '').trim();
      const location = (el.querySelector('.job-search-card__location')?.textContent || (el.querySelector('.base-search-card__meta')?.textContent))?.trim() || '';
      const link = (el.querySelector('a') as HTMLAnchorElement | null)?.href || '';
      items.push({ title, company, location, link });
    });
    return items;
  }

  function parseIndeedResults() {
    const items: any[] = [];
    document.querySelectorAll('.jobsearch-SerpJobCard').forEach((el) => {
      const title = (el.querySelector('.title a')?.textContent || '').trim();
      const company = (el.querySelector('.company')?.textContent || '').trim();
      const location = (el.querySelector('.location')?.textContent || '').trim() || '';
      const link = (el.querySelector('.title a') as HTMLAnchorElement | null)?.href || '';
      items.push({ title, company, location, link });
    });
    return items;
  }

  // Site-specific apply helpers
  function handleLinkedInApply(opts: any) {
    // Try to find "Easy Apply" button
    const easy = Array.from(document.querySelectorAll('button, a')).find((e:any) => (e.textContent||'').trim().toLowerCase().includes('easy apply')) as HTMLElement | undefined;
    if (easy) {
      easy.click();
      return { applied: 'easy_apply_clicked' };
    }
    // fallback: try to click apply button
    const applyBtn = document.querySelector('button[data-control-name="apply_dialog"]') as HTMLElement | null;
    if (applyBtn) { applyBtn.click(); return { applied: 'apply_dialog_clicked' }; }
    throw new Error('LinkedIn apply button not found');
  }

  function handleIndeedApply(opts: any) {
    // Indeed: look for applyNow or apply buttons
    const applyBtn = Array.from(document.querySelectorAll('button, a')).find((e:any) => /(apply|apply now)/i.test((e.textContent||'')));
    if (applyBtn) { (applyBtn as HTMLElement).click(); return { applied: 'apply_clicked' }; }
    throw new Error('Indeed apply button not found');
  }

  // Retry logic support
  const retries = step.payload?.retries || 1;
  for (let attempt = 1; attempt <= retries; attempt++) {
    try {
      const res = await attemptAction(step.action, step.payload || {});
      sendStepResult(taskId, stepId, stepName, true, res, { attempt });
      return { success: true, data: res };
    } catch (error: any) {
      console.warn(`[JobHunter] Step attempt ${attempt}/${retries} failed:`, error.message);
      sendStepResult(taskId, stepId, stepName, false, {}, { attempt, error: error.message });
      if (attempt === retries) return { success: false, error: error.message };
      // Backoff
      await new Promise((r) => setTimeout(r, 300 * attempt));
    }
  }

  return { success: false, error: 'Unknown failure' };
}

// Message listener
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  console.log('[JobHunter] Message received:', request.action);

  switch (request.action) {
    case 'scrapeForm':
      try {
        const fields = scrapeForm();
        sendResponse({ success: true, fields });
      } catch (error: any) {
        sendResponse({ success: false, error: error.message });
      }
      break;

    case 'scrapeJD':
      try {
        const jd = scrapeJobDescription();
        sendResponse({ success: true, jobDescription: jd });
      } catch (error: any) {
        sendResponse({ success: false, error: error.message });
      }
      break;

    case 'autoFill':
      autoFillForm()
        .then((result) => sendResponse(result))
        .catch((error) => sendResponse({ success: false, error: error.message }));
      return true; // Async response

    case 'fillForm':
      try {
        const results = fillForm(request.answers);
        sendResponse({ success: true, results });
      } catch (error: any) {
        sendResponse({ success: false, error: error.message });
      }
      break;

    case 'stopMonitor':
      stopDOMMonitor();
      sendResponse({ success: true });
      break;

    case 'captureFeedback':
      captureFeedback()
        .then((corrections) => sendResponse({ success: true, corrections }))
        .catch((error) => sendResponse({ success: false, error: error.message }));
      return true; // Async response

    case 'executeSteps':
      (async () => {
        const { taskId, steps } = request as { taskId: string; steps: any[] };
        console.log('[JobHunter] executeSteps called for task', taskId, steps);

        for (const step of steps) {
          const result = await executeStep(taskId, step);
          if (!result.success) break; // stop on first failure
          // slight pacing
          await new Promise((r) => setTimeout(r, 300));
        }

        sendResponse({ success: true, message: 'Execution finished' });
      })();
      return true;
  }

  return true;
});

// Expose helpers for e2e tests and debugging
;(window as any).JobHunter = { executeStep, parseLinkedInResults, parseIndeedResults };

console.log('[JobHunter] Content script ready');
