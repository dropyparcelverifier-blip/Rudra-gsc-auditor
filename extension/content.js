console.log('[Rudra GSC] Content script loaded', new Date().toLocaleTimeString());

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

const POLL_MS = 1000;
const INSPECT_TIMEOUT_MS = 90000;
const OUTCOME_TIMEOUT_MS = 240000;
const DIALOG_CLOSE_MS = 8000;

// ─── Dialog Detection (GSC uses role="dialog" / aria-modal for all popups) ───

const DIALOG_KIND = {
  QUOTA: 'QUOTA',
  ACCEPTED: 'ACCEPTED',
  REJECTED: 'REJECTED',
  NOT_IN_PROPERTY: 'NOT_IN_PROPERTY',
  OOPS: 'OOPS',
  BUSY: 'BUSY',
};

const DIALOG_PATTERNS = [
  [DIALOG_KIND.QUOTA, /quota/i],
  [DIALOG_KIND.REJECTED, /indexing request rejected/i],
  [DIALOG_KIND.ACCEPTED, /indexing requested/i],
  [DIALOG_KIND.NOT_IN_PROPERTY, /not in property/i],
  [DIALOG_KIND.OOPS, /something went wrong/i],
  [DIALOG_KIND.BUSY, /testing if live url|retrieving data from google/i],
];

function classifyText(text) {
  if (!text) return null;
  const m = DIALOG_PATTERNS.find(([, re]) => re.test(text));
  return m ? m[0] : null;
}

function isVisible(el) {
  if (!el || !el.isConnected || el.getClientRects().length === 0) return false;
  const s = getComputedStyle(el);
  return s.visibility !== 'hidden' && s.display !== 'none';
}

function findDialog() {
  const els = document.querySelectorAll('[role="dialog"], [role="alertdialog"], [aria-modal="true"], div[aria-label]');
  for (const el of els) {
    if (!isVisible(el)) continue;
    let kind = classifyText(el.getAttribute('aria-label'));
    if (!kind && (el.hasAttribute('role') || el.hasAttribute('aria-modal'))) {
      kind = classifyText((el.innerText || '').slice(0, 600));
    }
    if (kind) return { element: el, kind };
  }
  return null;
}

async function dismissDialog(dialogEl) {
  const buttons = Array.from(dialogEl.querySelectorAll('button, [role="button"]')).filter(isVisible);
  const btn = dialogEl.querySelector('button[data-mdc-dialog-action="ok"]')
    || buttons.find(b => /^(dismiss|got it|ok|close)$/i.test((b.innerText || '').trim()))
    || (buttons.length === 1 ? buttons[0] : null);
  if (!btn) return false;
  btn.click();
  const deadline = Date.now() + DIALOG_CLOSE_MS;
  while (Date.now() < deadline) {
    if (!isVisible(dialogEl)) return true;
    await sleep(250);
  }
  return false;
}

async function waitForIdlePage() {
  const deadline = Date.now() + 30000;
  while (Date.now() < deadline) {
    const d = findDialog();
    if (!d) return true;
    if (d.kind !== DIALOG_KIND.BUSY) await dismissDialog(d.element);
    await sleep(POLL_MS);
  }
  return false;
}

// ─── Button Finder ───

function findRequestButton() {
  const els = document.querySelectorAll('div[role="button"], button');
  for (const el of els) {
    const t = (el.innerText || '').trim().toLowerCase();
    if (t.length < 80 && (t.includes('request indexing') || t.includes('request again')) && isVisible(el)) return el;
  }
  return null;
}

function isDisabled(btn) {
  return btn.getAttribute('aria-disabled') === 'true' || btn.disabled === true;
}

// ─── Inspection Result Scraper ───

function scrapeInspectionResults() {
  const text = document.body?.innerText || '';
  const data = {
    indexStatus: 'unknown', coverage: '', lastCrawl: '',
    richResults: [], mobileUsability: '', canRequestIndexing: false,
    robotsTxt: '', canonical: '',
  };

  if (text.includes('URL is on Google')) data.indexStatus = 'indexed';
  else if (text.includes('URL is not on Google')) data.indexStatus = 'not_indexed';
  else if (text.includes('URL cannot be indexed')) data.indexStatus = 'cannot_index';
  else if (text.includes('URL is an alternate version')) data.indexStatus = 'alternate';
  else if (text.includes('URL is unknown to Google')) data.indexStatus = 'not_indexed';

  const coverages = [
    'Submitted and indexed', 'Crawled - currently not indexed',
    'Discovered - currently not indexed', 'URL is unknown to Google',
    'Blocked by robots.txt', 'Blocked due to other 4xx issue',
    'Server error', 'Redirect error', 'Soft 404',
    'Duplicate without user-selected canonical',
    'Duplicate, Google chose different canonical',
    'Excluded by noindex tag', 'Page with redirect',
    'Not found (404)', 'Blocked due to unauthorized request',
    'Blocked due to access forbidden',
  ];
  for (const c of coverages) {
    if (text.includes(c)) { data.coverage = c; break; }
  }

  const richSection = document.querySelector('[data-feature="RICH_RESULTS"], [data-feature="ENHANCEMENTS"]');
  const richText = richSection ? richSection.innerText || '' : '';
  const richTypes = [
    'Product snippet', 'Merchant listing', 'Review snippet',
    'Sitelinks search box', 'FAQ', 'HowTo', 'Recipe', 'Event',
    'Article', 'Breadcrumb', 'Shopping', 'Organization', 'Offer',
  ];
  const searchText = richText || text;
  for (const rt of richTypes) {
    if (searchText.includes(rt)) data.richResults.push(rt);
  }

  if (text.includes('Page is mobile friendly')) data.mobileUsability = 'mobile_friendly';
  else if (text.includes('Page is not mobile friendly')) data.mobileUsability = 'not_mobile_friendly';

  const crawlMatch = text.match(/Last crawl[:\s]*([\w\s,.:]+\d{4})/i);
  if (crawlMatch) data.lastCrawl = crawlMatch[1].trim();

  if (text.includes('Blocked by robots.txt: No')) data.robotsTxt = 'allowed';
  else if (text.includes('Blocked by robots.txt: Yes')) data.robotsTxt = 'blocked';

  const canonicalMatch = text.match(/Google-selected canonical[:\s]*(https?:\/\/[^\s]+)/i);
  if (canonicalMatch) data.canonical = canonicalMatch[1];

  data.canRequestIndexing = !!findRequestButton();
  return data;
}

// ─── Wait for Inspection Results ───

async function waitForInspection(url, before) {
  const deadline = Date.now() + INSPECT_TIMEOUT_MS;
  let started = false;
  let stableBtn = null;

  while (Date.now() < deadline) {
    const dialog = findDialog();
    if (dialog) {
      stableBtn = null;
      if (dialog.kind === DIALOG_KIND.BUSY) {
        started = true;
      } else {
        await dismissDialog(dialog.element);
        if (dialog.kind === DIALOG_KIND.NOT_IN_PROPERTY) return { status: 'error', reason: 'URL not in this GSC property' };
        if (dialog.kind === DIALOG_KIND.QUOTA) return { status: 'quota', reason: 'Daily quota exceeded' };
        if (dialog.kind === DIALOG_KIND.OOPS) return { status: 'error', reason: 'GSC error: Something went wrong' };
      }
    } else {
      if (!started && (location.href !== before.href || (before.button && !before.button.isConnected))) {
        started = true;
      }
      if (started) {
        const btn = findRequestButton();
        if (btn && btn === stableBtn) return { status: 'ready', button: btn };
        stableBtn = btn;
      }
    }
    await sleep(POLL_MS);
  }

  if (!started) return { status: 'error', reason: 'GSC did not start inspection (90s timeout)' };
  return { status: 'error', reason: 'Request Indexing button did not appear (90s timeout)' };
}

// ─── Wait for Indexing Outcome ───

async function waitForOutcome(url) {
  const deadline = Date.now() + OUTCOME_TIMEOUT_MS;
  while (Date.now() < deadline) {
    const dialog = findDialog();
    if (dialog && dialog.kind !== DIALOG_KIND.BUSY) {
      await dismissDialog(dialog.element);
      return dialog.kind;
    }
    await sleep(POLL_MS);
  }
  return null;
}

// ─── Main: Process One URL ───

async function processUrl(url) {
  try {
    if (!(await waitForIdlePage())) {
      return { status: 'error', reason: 'Page blocked by undismissable dialog' };
    }

    // Find the inspect input
    const urlInput = document.querySelector('input[aria-label*="Inspect any URL"]')
      || document.querySelector('input[role="combobox"][jsname="dSO9oc"]')
      || document.querySelector('input.Ax4B8.ZAGvjd');
    if (!urlInput) return { status: 'error', reason: 'Inspect input not found on page' };

    const before = { href: location.href, button: findRequestButton() };

    // Type URL and trigger inspection
    urlInput.focus();
    urlInput.value = url;
    urlInput.dispatchEvent(new Event('input', { bubbles: true }));
    await sleep(500);
    urlInput.dispatchEvent(new KeyboardEvent('keydown', {
      key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true,
    }));

    // Wait for inspection results
    const inspection = await waitForInspection(url, before);
    if (inspection.status !== 'ready') {
      const data = scrapeInspectionResults();
      return { status: inspection.status, reason: inspection.reason, data };
    }

    // Scrape the inspection data
    const data = scrapeInspectionResults();

    // If already indexed, no need to request
    if (data.indexStatus === 'indexed') {
      return { status: 'indexed', reason: 'Already indexed', data };
    }

    // Check if button is disabled
    if (isDisabled(inspection.button)) {
      return { status: 'error', reason: 'Request Indexing button is disabled', data };
    }

    // Click Request Indexing
    inspection.button.click();

    // Wait for outcome (can take 1-2 minutes for live test)
    const outcome = await waitForOutcome(url);

    if (outcome === DIALOG_KIND.ACCEPTED) {
      return { status: 'requested', reason: 'Indexing requested', data };
    }
    if (outcome === DIALOG_KIND.QUOTA) {
      return { status: 'quota', reason: 'Daily quota exceeded', data };
    }
    if (outcome === DIALOG_KIND.REJECTED) {
      return { status: 'rejected', reason: 'Indexing request rejected — issues detected', data };
    }
    if (outcome === DIALOG_KIND.OOPS) {
      return { status: 'error', reason: 'GSC error: Something went wrong', data };
    }
    return { status: 'error', reason: 'No confirmation from GSC within 4 minutes', data };

  } catch (e) {
    return { status: 'error', reason: `Script error: ${e.message}` };
  }
}

// ─── Message Handler ───

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  if (msg.type === 'PROCESS_URL') {
    processUrl(msg.url).then(sendResponse);
    return true;
  }

  if (msg.type === 'SCRAPE_INSPECTION') {
    sendResponse({ success: true, data: scrapeInspectionResults() });
    return false;
  }

  if (msg.type === 'SCRAPE_PAGE_TEXT') {
    sendResponse({ text: document.body?.innerText || '' });
    return false;
  }
});
