import { executeStep } from '../jobhunter';

declare const global: any;

describe('content script executeStep', () => {
  beforeAll(() => {
    // Mock chrome.runtime.sendMessage
    global.chrome = { runtime: { sendMessage: jest.fn() } };
  });

  afterEach(() => {
    document.body.innerHTML = '';
    jest.clearAllMocks();
  });

  test('type action fills an input', async () => {
    document.body.innerHTML = `<input id="name" />`;
    const result = await executeStep('task1', { id: 's1', action: 'type', payload: { selector: '#name', text: 'Alice' } });
    expect(result.success).toBeTruthy();
    const input = document.querySelector('#name') as HTMLInputElement;
    expect(input.value).toBe('Alice');
  });

  test('click action clicks a button by selector', async () => {
    document.body.innerHTML = `<button id="btn">Click</button>`;
    const btn = document.querySelector('#btn') as HTMLButtonElement;
    jest.spyOn(btn, 'click');
    const result = await executeStep('task1', { id: 's2', action: 'click', payload: { selector: '#btn' } });
    expect(result.success).toBeTruthy();
    expect(btn.click).toHaveBeenCalled();
  });

  test('extract returns text content', async () => {
    document.body.innerHTML = `<div id="jd">Job description here</div>`;
    const res = await executeStep('task1', { id: 's3', action: 'extract', payload: { selector: '#jd' } });
    expect(res.success).toBeTruthy();
    expect(res.data.extracted).toBe('Job description here');
  });

  test('search on indeed navigates', async () => {
    // Set window.location.hostname to indeed.com
    Object.defineProperty(window, 'location', {
      value: { hostname: 'www.indeed.com', href: 'https://www.indeed.com/' },
      writable: true,
    });
    const res = await executeStep('task1', { id: 's4', action: 'search', payload: { query: 'python developer' } });
    expect(res.success).toBeTruthy();
    expect(window.location.href).toContain('indeed.com/jobs');
  });

  test('loop over items executes substeps', async () => {
    document.body.innerHTML = `<div class="item">A</div><div class="item">B</div>`;

    const substep = { action: 'extract', payload: { selector: '$this .title' } };

    // Add child .title to each item
    document.querySelectorAll('.item').forEach((el, idx) => {
      const span = document.createElement('span');
      span.className = 'title';
      span.textContent = `title-${idx}`;
      el.appendChild(span);
    });

    const res = await executeStep('task1', { id: 's5', action: 'loop', payload: { items_selector: '.item', substeps: [substep], clickOnItem: false } });
    expect(res.success).toBeTruthy();
    expect(res.data.results.length).toBe(2);
  });

  test('parse linkedin results extracts items', async () => {
    document.body.innerHTML = `
      <ul>
        <li class="jobs-search-results__list-item"><a href="/job/1"><h3 class="base-search-card__title">Engineer</h3><h4 class="base-search-card__subtitle">ACME</h4><div class="job-search-card__location">Remote</div></a></li>
        <li class="jobs-search-results__list-item"><a href="/job/2"><h3 class="base-search-card__title">PM</h3><h4 class="base-search-card__subtitle">Beta</h4><div class="job-search-card__location">NY</div></a></li>
      </ul>
    `;
    Object.defineProperty(window, 'location', { value: { hostname: 'www.linkedin.com', href: 'https://www.linkedin.com/' }, writable: true });
    const res = await executeStep('task1', { id: 's6', action: 'parse', payload: {} });
    expect(res.success).toBeTruthy();
    expect(res.data.items.length).toBe(2);
    expect(res.data.items[0].title).toBe('Engineer');
  });

  test('parse indeed results extracts items', async () => {
    document.body.innerHTML = `
      <div class="jobsearch-SerpJobCard"><div class="title"><a href="/job/1">Dev</a></div><div class="company">ACME</div><div class="location">Remote</div></div>
      <div class="jobsearch-SerpJobCard"><div class="title"><a href="/job/2">DevOps</a></div><div class="company">Beta</div><div class="location">NY</div></div>
    `;
    Object.defineProperty(window, 'location', { value: { hostname: 'www.indeed.com', href: 'https://www.indeed.com/' }, writable: true });
    const res = await executeStep('task1', { id: 's7', action: 'parse', payload: {} });
    expect(res.success).toBeTruthy();
    expect(res.data.items.length).toBe(2);
    expect(res.data.items[0].title).toBe('Dev');
  });

  test('apply linkedin easy apply', async () => {
    document.body.innerHTML = `<button>Easy Apply</button>`;
    Object.defineProperty(window, 'location', { value: { hostname: 'www.linkedin.com', href: 'https://www.linkedin.com/' }, writable: true });
    const sendSpy = jest.spyOn(global.chrome.runtime, 'sendMessage');
    const res = await executeStep('task1', { id: 's8', action: 'apply', payload: {} });
    expect(res.success).toBeTruthy();
    expect(res.data.applied).toBe('easy_apply_clicked');
    expect(sendSpy).toHaveBeenCalled();
  });

  test('apply linkedin fallback to apply_dialog', async () => {
    document.body.innerHTML = `<button data-control-name="apply_dialog">Apply</button>`;
    Object.defineProperty(window, 'location', { value: { hostname: 'www.linkedin.com', href: 'https://www.linkedin.com/' }, writable: true });
    const res = await executeStep('task1', { id: 's9', action: 'apply', payload: {} });
    expect(res.success).toBeTruthy();
    expect(res.data.applied).toBe('apply_dialog_clicked');
  });

  test('apply indeed clicks apply', async () => {
    document.body.innerHTML = `<button>Apply</button>`;
    Object.defineProperty(window, 'location', { value: { hostname: 'www.indeed.com', href: 'https://www.indeed.com/' }, writable: true });
    const res = await executeStep('task1', { id: 's10', action: 'apply', payload: {} });
    expect(res.success).toBeTruthy();
    expect(res.data.applied).toBe('apply_clicked');
  });

  test('apply on unsupported site fails', async () => {
    document.body.innerHTML = `<div>No apply here</div>`;
    Object.defineProperty(window, 'location', { value: { hostname: 'www.example.com', href: 'https://www.example.com/' }, writable: true });
    const res = await executeStep('task1', { id: 's11', action: 'apply', payload: {} });
    expect(res.success).toBeFalsy();
    expect(res.error).toMatch(/Apply action not implemented|No apply/);
  });

  test('executeSteps sequence end-to-end (unit)', async () => {
    document.body.innerHTML = `<input id="q"/><button id="search">Search</button><div class="results"><a class="job" href="/job/1">Job A</a></div>`;
    Object.defineProperty(window, 'location', { value: { hostname: 'www.example.com', href: 'https://www.example.com/' }, writable: true });

    const steps = [
      { id: 's1', action: 'type', payload: { selector: '#q', text: 'Python' } },
      { id: 's2', action: 'click', payload: { selector: '#search' } },
      { id: 's3', action: 'extract', payload: { selector: '.results .job' } },
    ];

    for (const step of steps) {
      const r = await executeStep('task2', step);
      expect(r.success).toBeTruthy();
    }
  });
});