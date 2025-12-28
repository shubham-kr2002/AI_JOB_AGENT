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
  }

  return true;
});

console.log('[JobHunter] Content script ready');
