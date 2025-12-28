/**
 * JobHunter Extension - Form Utilities
 * DOM traversal, scraping, and form filling logic
 */

import type { FormField, FieldAnswer, FillResults } from '~/types';

// Element map for filling
const elementMap = new Map<string, HTMLElement>();

// Original values for feedback capture
const originalValues = new Map<string, { originalAnswer: string; label: string; element: HTMLElement }>();

/**
 * Scrape all form fields from the page
 */
export function scrapeForm(): FormField[] {
  const fields: FormField[] = [];
  elementMap.clear();

  // Find all input elements
  const inputs = document.querySelectorAll<HTMLInputElement>(
    'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"])'
  );
  const textareas = document.querySelectorAll<HTMLTextAreaElement>('textarea');
  const selects = document.querySelectorAll<HTMLSelectElement>('select');

  // Process inputs
  inputs.forEach((el) => {
    const field = extractField(el);
    if (field) {
      fields.push(field);
      elementMap.set(field.id, el);
    }
  });

  // Process textareas
  textareas.forEach((el) => {
    const field = extractField(el);
    if (field) {
      fields.push(field);
      elementMap.set(field.id, el);
    }
  });

  // Process selects
  selects.forEach((el) => {
    const field = extractField(el);
    if (field) {
      field.options = Array.from(el.options).map((opt) => opt.text);
      fields.push(field);
      elementMap.set(field.id, el);
    }
  });

  // Traverse Shadow DOMs
  document.querySelectorAll('*').forEach((el) => {
    if ((el as any).shadowRoot) {
      traverseShadowDOM((el as any).shadowRoot, fields);
    }
  });

  return fields;
}

/**
 * Traverse Shadow DOM to find form elements
 */
function traverseShadowDOM(shadowRoot: ShadowRoot, fields: FormField[]): void {
  const inputs = shadowRoot.querySelectorAll<HTMLInputElement>(
    'input:not([type="hidden"]):not([type="submit"]):not([type="button"])'
  );
  const textareas = shadowRoot.querySelectorAll<HTMLTextAreaElement>('textarea');
  const selects = shadowRoot.querySelectorAll<HTMLSelectElement>('select');

  [...inputs, ...textareas, ...selects].forEach((el) => {
    const field = extractField(el);
    if (field) {
      fields.push(field);
      elementMap.set(field.id, el);
    }
  });

  // Recursively check nested Shadow DOMs
  shadowRoot.querySelectorAll('*').forEach((el) => {
    if ((el as any).shadowRoot) {
      traverseShadowDOM((el as any).shadowRoot, fields);
    }
  });
}

/**
 * Extract field info from an element
 */
function extractField(el: HTMLElement): FormField | null {
  // Skip hidden elements
  if (el.offsetParent === null) {
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') {
      return null;
    }
  }

  const id = el.id || (el as HTMLInputElement).name || generateId(el);

  return {
    id,
    label: guessLabel(el),
    type: getType(el),
  };
}

/**
 * Get field type
 */
function getType(el: HTMLElement): string {
  const tag = el.tagName.toLowerCase();
  if (tag === 'textarea') return 'textarea';
  if (tag === 'select') return 'select';
  return (el as HTMLInputElement).type || 'text';
}

/**
 * Guess label using heuristics
 */
function guessLabel(el: HTMLElement): string {
  // 1. aria-label
  const ariaLabel = el.getAttribute('aria-label');
  if (ariaLabel) return ariaLabel.trim();

  // 2. aria-labelledby
  const ariaLabelledBy = el.getAttribute('aria-labelledby');
  if (ariaLabelledBy) {
    const labelEl = document.getElementById(ariaLabelledBy);
    if (labelEl) return labelEl.textContent?.trim() || '';
  }

  // 3. Explicit label[for]
  if (el.id) {
    const label = document.querySelector(`label[for="${el.id}"]`);
    if (label) return label.textContent?.trim() || '';
  }

  // 4. Parent label
  const parentLabel = el.closest('label');
  if (parentLabel) {
    const clone = parentLabel.cloneNode(true) as HTMLElement;
    clone.querySelectorAll('input, textarea, select').forEach((inp) => inp.remove());
    const text = clone.textContent?.trim();
    if (text) return text;
  }

  // 5. Preceding siblings
  let prevEl = el.previousElementSibling;
  while (prevEl) {
    if (prevEl.tagName === 'LABEL') {
      return prevEl.textContent?.trim() || '';
    }
    if (['SPAN', 'DIV', 'P'].includes(prevEl.tagName)) {
      const text = prevEl.textContent?.trim();
      if (text && text.length < 100) return text;
    }
    prevEl = prevEl.previousElementSibling;
  }

  // 6. Name attribute
  const name = (el as HTMLInputElement).name;
  if (name) {
    return name.replace(/([A-Z])/g, ' $1').replace(/[_-]/g, ' ').trim();
  }

  // 7. Placeholder
  const placeholder = (el as HTMLInputElement).placeholder;
  if (placeholder) return placeholder;

  return '(unknown)';
}

/**
 * Generate unique ID
 */
function generateId(el: HTMLElement): string {
  const tag = el.tagName.toLowerCase();
  const type = (el as HTMLInputElement).type || 'field';
  const id = `${tag}_${type}_${Math.random().toString(36).substr(2, 6)}`;
  if (!el.id) {
    el.setAttribute('data-jobhunter-id', id);
  }
  return id;
}

/**
 * Scrape job description from page
 */
export function scrapeJobDescription(): string {
  let jdText = '';

  const jdSelectors = [
    '.job-description',
    '.jobDescription',
    '[data-testid="job-description"]',
    '.description__text',
    '.job-details',
    '#job-details',
    '[class*="jobDescription"]',
    '[class*="job-description"]',
    'article',
    '.posting-requirements',
  ];

  for (const selector of jdSelectors) {
    const el = document.querySelector(selector);
    if (el && el.textContent && el.textContent.length > 200) {
      jdText = el.textContent;
      break;
    }
  }

  // Fallback: look for keywords
  if (!jdText) {
    const paragraphs = document.querySelectorAll('p, div, section');
    for (const p of paragraphs) {
      const text = p.textContent?.toLowerCase() || '';
      if (
        text.length > 500 &&
        (text.includes('requirements') ||
          text.includes('qualifications') ||
          text.includes('responsibilities'))
      ) {
        jdText = p.textContent || '';
        break;
      }
    }
  }

  return jdText.replace(/\s+/g, ' ').trim().substring(0, 5000);
}

/**
 * Fill form with answers
 */
export function fillForm(answers: FieldAnswer[]): FillResults {
  const results: FillResults = {
    filled: 0,
    skipped: 0,
    flagged: 0,
    errors: [],
  };

  for (const answerObj of answers) {
    try {
      if (!answerObj.answer || answerObj.answer.trim() === '') {
        results.skipped++;
        continue;
      }

      let el = elementMap.get(answerObj.id);
      if (!el) {
        el =
          (document.getElementById(answerObj.id) ||
          document.querySelector(`[name="${answerObj.id}"]`) ||
          document.querySelector(`[data-jobhunter-id="${answerObj.id}"]`)) as HTMLElement | undefined;
      }

      if (!el) {
        results.errors.push({ id: answerObj.id, error: 'Element not found' });
        continue;
      }

      // Store for feedback
      originalValues.set(answerObj.id, {
        originalAnswer: answerObj.answer,
        label: answerObj.id,
        element: el,
      });

      const success = fillField(el, answerObj.answer);

      if (success) {
        results.filled++;
        if (!answerObj.verified) {
          highlightField(el, 'warning');
          results.flagged++;
        } else {
          highlightField(el, 'success');
        }
      } else {
        results.errors.push({ id: answerObj.id, error: 'Failed to fill' });
      }
    } catch (error: any) {
      results.errors.push({ id: answerObj.id, error: error.message });
    }
  }

  return results;
}

/**
 * Fill a single field with synthetic events
 */
function fillField(el: HTMLElement, value: string): boolean {
  try {
    el.focus();
    el.dispatchEvent(new FocusEvent('focus', { bubbles: true }));

    const tagName = el.tagName.toLowerCase();

    if (tagName === 'select') {
      const select = el as HTMLSelectElement;
      const options = Array.from(select.options);
      const match = options.find(
        (opt) =>
          opt.value.toLowerCase() === value.toLowerCase() ||
          opt.text.toLowerCase().includes(value.toLowerCase())
      );
      if (match) {
        select.value = match.value;
      }
      select.dispatchEvent(new Event('change', { bubbles: true }));
    } else if ((el as HTMLInputElement).type === 'checkbox') {
      const checkbox = el as HTMLInputElement;
      const shouldCheck = ['true', 'yes', '1', 'on'].includes(value.toLowerCase());
      if (checkbox.checked !== shouldCheck) {
        checkbox.checked = shouldCheck;
        checkbox.dispatchEvent(new Event('change', { bubbles: true }));
      }
    } else if ((el as HTMLInputElement).type === 'radio') {
      const radio = el as HTMLInputElement;
      const name = radio.name;
      if (name) {
        document.querySelectorAll<HTMLInputElement>(`input[type="radio"][name="${name}"]`).forEach((r) => {
          if (r.value.toLowerCase() === value.toLowerCase()) {
            r.checked = true;
            r.dispatchEvent(new Event('change', { bubbles: true }));
          }
        });
      }
    } else {
      const input = el as HTMLInputElement | HTMLTextAreaElement;
      input.value = value;
      input.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertText', data: value }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }

    el.blur();
    el.dispatchEvent(new FocusEvent('blur', { bubbles: true }));

    return true;
  } catch (error) {
    console.error('[JobHunter] Fill error:', error);
    return false;
  }
}

/**
 * Highlight field with status color
 */
function highlightField(el: HTMLElement, status: 'success' | 'warning' | 'error'): void {
  const colors = {
    success: 'rgba(34, 197, 94, 0.2)',
    warning: 'rgba(251, 191, 36, 0.3)',
    error: 'rgba(239, 68, 68, 0.2)',
  };

  const borders = {
    success: '2px solid #22c55e',
    warning: '2px solid #fbbf24',
    error: '2px solid #ef4444',
  };

  el.style.transition = 'all 0.3s ease';
  el.style.backgroundColor = colors[status];
  el.style.border = borders[status];

  if (status === 'warning') {
    el.title = '⚠️ This answer may need review';
  }

  setTimeout(() => {
    el.style.backgroundColor = '';
    el.style.border = '';
  }, 5000);
}

/**
 * Capture user corrections for feedback
 */
export function captureCorrections(): Array<{ question: string; original_answer: string; corrected_answer: string }> {
  const corrections: Array<{ question: string; original_answer: string; corrected_answer: string }> = [];

  for (const [fieldId, data] of originalValues.entries()) {
    const el = data.element as HTMLInputElement | HTMLTextAreaElement;
    if (!el) continue;

    const currentValue = el.value;
    if (currentValue !== data.originalAnswer) {
      corrections.push({
        question: data.label,
        original_answer: data.originalAnswer,
        corrected_answer: currentValue,
      });
    }
  }

  return corrections;
}

export { elementMap, originalValues };
