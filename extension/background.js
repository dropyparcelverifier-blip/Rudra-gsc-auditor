const DEFAULT_PROPERTY = 'https://rudraretails.com/';
const GSC_BASE = 'https://search.google.com/search-console';
const DEFAULT_DASHBOARD_URL = 'http://localhost:5001';

let PROPERTY = DEFAULT_PROPERTY;
let DASHBOARD_URL = DEFAULT_DASHBOARD_URL;
let lastScrapedData = null;
let dashboardSyncPending = false;

function getApiUrl() {
  if (DASHBOARD_URL.includes('localhost:3001') || DASHBOARD_URL.includes('localhost:3000') || DASHBOARD_URL.includes('localhost:5000')) {
    DASHBOARD_URL = 'http://localhost:5001';
    chrome.storage.sync.set({ dashboardUrl: DASHBOARD_URL });
  }
  return DASHBOARD_URL;
}

let queue = { state: 'idle', urls: [], results: [], processed: 0, errors: 0, total: 0, currentUrl: '' };
let gscTabId = null;
let processingTimeout = null;
let isProcessing = false;

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function broadcastState() {
  chrome.runtime.sendMessage({ type: 'STATE_UPDATE', queue }).catch(() => {});
}

function saveQueue() {
  chrome.storage.local.set({ queue });
}

function loadQueue() {
  // Settings sync across Chrome profiles/PCs via chrome.storage.sync
  chrome.storage.sync.get(['dashboardUrl', 'property'], (s) => {
    // Migrate settings from local → sync on first run after upgrade
    chrome.storage.local.get(['dashboardUrl', 'property', 'queue', 'gscTabId', 'lastScrapedData', 'dashboardSyncPending'], (d) => {
      if (!s.dashboardUrl && d.dashboardUrl) {
        DASHBOARD_URL = d.dashboardUrl;
        chrome.storage.sync.set({ dashboardUrl: DASHBOARD_URL });
      } else if (s.dashboardUrl) {
        DASHBOARD_URL = s.dashboardUrl;
      }
      if (!s.property && d.property) {
        PROPERTY = d.property;
        chrome.storage.sync.set({ property: PROPERTY });
      } else if (s.property) {
        PROPERTY = s.property;
      }

      if (DASHBOARD_URL.includes('localhost:3001') || DASHBOARD_URL.includes('localhost:3000') || DASHBOARD_URL.includes('localhost:5000')) {
        console.warn('[GSC-EXT] Dashboard URL was pointing to React dev server, fixing to Flask API port 5001');
        DASHBOARD_URL = 'http://localhost:5001';
        chrome.storage.sync.set({ dashboardUrl: DASHBOARD_URL });
      }

      // Runtime data stays local (device-specific, larger quota)
      if (d.queue) {
        queue = d.queue;
        if (queue.state === 'running') queue.state = 'paused';
      }
      if (d.gscTabId) gscTabId = d.gscTabId;
      if (d.lastScrapedData) lastScrapedData = d.lastScrapedData;
      if (d.dashboardSyncPending) dashboardSyncPending = true;

      if (dashboardSyncPending && queue.results.length > 0) {
        console.log('[GSC-EXT] Retrying pending dashboard sync...');
        sendBulkResultsToDashboard();
      }
    });
  });
}

async function ensureGSCTab() {
  if (gscTabId) {
    try {
      const tab = await chrome.tabs.get(gscTabId);
      if (tab && tab.url?.startsWith('https://search.google.com/')) return gscTabId;
      gscTabId = null;
    } catch {
      gscTabId = null;
    }
  }
  const tabs = await chrome.tabs.query({ url: 'https://search.google.com/*' });
  if (tabs.length) {
    gscTabId = tabs[0].id;
    chrome.storage.local.set({ gscTabId });
    return gscTabId;
  }
  const tab = await chrome.tabs.create({
    url: `${GSC_BASE}?resource_id=${encodeURIComponent(PROPERTY)}`,
    active: false,
  });
  gscTabId = tab.id;
  chrome.storage.local.set({ gscTabId });
  await sleep(4000);
  return gscTabId;
}

async function injectAndRun(tabId, func, ...args) {
  const results = await chrome.scripting.executeScript({ target: { tabId }, func, args });
  return results?.[0]?.result;
}

async function waitForPageLoad(tabId, ms = 8000) {
  await sleep(ms);
  for (let i = 0; i < 5; i++) {
    try {
      const ready = await injectAndRun(tabId, () => document.readyState);
      if (ready === 'complete') {
        await sleep(1500);
        return;
      }
    } catch {}
    await sleep(1000);
  }
}

// ─── URL Inspection (delegated to content script) ───

async function sendToContentScript(tabId, message) {
  return new Promise((resolve) => {
    chrome.tabs.sendMessage(tabId, message, (response) => {
      if (chrome.runtime.lastError) {
        resolve({ status: 'error', reason: 'Content script not responding: ' + chrome.runtime.lastError.message });
      } else {
        resolve(response);
      }
    });
  });
}

async function processUrlViaContentScript(url, retries = 2) {
  const tabId = await ensureGSCTab();
  console.log(`[GSC-EXT] Processing URL via content script: ${url} (tab ${tabId})`);

  await chrome.tabs.update(tabId, {
    url: `${GSC_BASE}/index?resource_id=${encodeURIComponent(PROPERTY)}`
  });
  await waitForPageLoad(tabId, 6000);

  let result = await sendToContentScript(tabId, { type: 'PROCESS_URL', url });

  if (result.status === 'error' && result.reason?.includes('Content script not responding') && retries > 0) {
    console.warn(`[GSC-EXT] Content script not responding, injecting and retrying (${retries} left)`);
    try {
      await chrome.scripting.executeScript({ target: { tabId }, files: ['content.js'] });
      await sleep(1000);
      result = await sendToContentScript(tabId, { type: 'PROCESS_URL', url });
    } catch (e) {
      console.error('[GSC-EXT] Manual injection failed:', e.message);
    }
    if (result.status === 'error' && result.reason?.includes('Content script not responding') && retries > 0) {
      gscTabId = null;
      return processUrlViaContentScript(url, retries - 1);
    }
  }

  console.log(`[GSC-EXT] Content script result for ${url}:`, JSON.stringify(result).slice(0, 200));
  return result;
}

async function processNext() {
  if (isProcessing) return;
  if (queue.state !== 'running') return;
  if (queue.processed >= queue.total) {
    if (queue.state !== 'done') {
      queue.state = 'done';
      queue.currentUrl = '';
      broadcastState(); saveQueue();
      sendBulkResultsToDashboard();
    }
    return;
  }
  isProcessing = true;

  const idx = queue.processed;
  const url = queue.urls[idx];
  queue.currentUrl = url;
  broadcastState();

  const result = {
    url, status: 'pending', coverage: '', action: '', error: '',
    richResults: [], indexStatus: '', lastCrawl: '', mobileUsability: '',
  };

  try {
    const response = await processUrlViaContentScript(url);

    if (response.data) {
      result.coverage = response.data.coverage || 'unknown';
      result.indexStatus = response.data.indexStatus || 'unknown';
      result.richResults = response.data.richResults || [];
      result.lastCrawl = response.data.lastCrawl || '';
      result.mobileUsability = response.data.mobileUsability || '';
    }

    switch (response.status) {
      case 'indexed':
        result.status = 'indexed';
        result.action = 'Already indexed';
        if (result.richResults.length) result.action += ` · Rich: ${result.richResults.join(', ')}`;
        break;
      case 'requested':
        result.status = 'requested';
        result.action = 'Indexing requested via GSC';
        break;
      case 'rejected':
        result.status = 'not_indexed';
        result.action = `Indexing rejected — ${response.reason || 'issues detected'}`;
        break;
      case 'quota':
        result.status = 'not_indexed';
        result.action = 'Quota exceeded — pausing queue';
        queue.state = 'paused';
        if (processingTimeout) clearTimeout(processingTimeout);
        break;
      case 'error':
      default:
        result.status = 'error';
        result.error = (response.reason || 'Unknown error').slice(0, 120);
        queue.errors++;
        break;
    }
  } catch (e) {
    result.status = 'error';
    result.error = e.message?.slice(0, 120) || 'Unknown error';
    queue.errors++;
  }

  queue.results.push(result);
  queue.processed++;
  queue.currentUrl = '';
  broadcastState(); saveQueue();

  isProcessing = false;

  if (queue.state === 'running' && queue.processed < queue.total) {
    // Random 20-30s delay between URLs to avoid rate limiting
    const delay = 20000 + Math.random() * 10000;
    console.log(`[GSC-EXT] Next URL in ${Math.round(delay / 1000)}s`);
    processingTimeout = setTimeout(processNext, delay);
  } else if (queue.processed >= queue.total && queue.state !== 'done') {
    queue.state = 'done';
    queue.currentUrl = '';
    broadcastState(); saveQueue();
    sendBulkResultsToDashboard();
  }
}

async function sendBulkResultsToDashboard() {
  console.log(`[GSC-EXT] Sending ${queue.results.length} bulk results to ${getApiUrl()}/api/extension/bulk-results`);
  dashboardSyncPending = true;
  chrome.storage.local.set({ dashboardSyncPending: true });
  try {
    const payload = {
      results: queue.results,
      total: queue.total,
      processed: queue.processed,
      errors: queue.errors,
      completedAt: new Date().toISOString(),
    };
    const resp = await fetch(`${getApiUrl()}/api/extension/bulk-results`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const ok = resp.ok;
    const body = ok ? await resp.json() : await resp.text().catch(() => resp.status);
    console.log('[GSC-EXT] Bulk results sent to dashboard:', ok ? 'success' : resp.status, body);
    if (ok) {
      dashboardSyncPending = false;
      chrome.storage.local.set({ dashboardSyncPending: false });
    }
    chrome.runtime.sendMessage({ type: 'BULK_SYNC_STATUS', ok }).catch(() => {});
  } catch (e) {
    console.error('[GSC-EXT] Bulk results send FAILED:', DASHBOARD_URL, e.message);
    chrome.runtime.sendMessage({ type: 'BULK_SYNC_STATUS', ok: false }).catch(() => {});
  }
}

// ─── Generic Enhancement Scraper (for /r/ pages) ───

async function scrapeEnhancementPage(path) {
  const tabId = await ensureGSCTab();
  const url = `${GSC_BASE}/${path}?resource_id=${encodeURIComponent(PROPERTY)}`;
  await chrome.tabs.update(tabId, { url });
  await waitForPageLoad(tabId, 8000);

  // Check if the page 404'd or redirected away from the expected path
  const pageCheck = await injectAndRun(tabId, () => {
    const text = (document.body?.innerText || '').toLowerCase();
    if (text.includes('page not found') || text.includes('404') || text.includes('not available'))
      return 'not_found';
    return 'ok';
  });
  if (pageCheck === 'not_found') {
    return { valid: '', error: '', warning: '', issues: [], rawSnippet: '', notAvailable: true };
  }

  return await injectAndRun(tabId, () => {
    const text = document.body?.innerText || '';
    const data = { valid: '', error: '', warning: '', issues: [], rawSnippet: '' };

    const validMatch = text.match(/Valid\s*[\n\r:]\s*([\d,]+)/i);
    if (validMatch) data.valid = validMatch[1].replace(/,/g, '');

    const errMatch = text.match(/Error\s*[\n\r:]\s*([\d,]+)/i);
    if (errMatch) data.error = errMatch[1].replace(/,/g, '');

    const warnMatch = text.match(/Warning\s*[\n\r:]\s*([\d,]+)/i);
    if (warnMatch) data.warning = warnMatch[1].replace(/,/g, '');

    if (!data.valid && !data.error) {
      const nums = text.match(/(\d[\d,]*)\s+(valid|error|warning|item)/gi);
      if (nums) {
        nums.forEach(m => {
          const n = m.match(/(\d[\d,]*)/)?.[1]?.replace(/,/g, '');
          if (m.toLowerCase().includes('valid')) data.valid = data.valid || n;
          else if (m.toLowerCase().includes('error')) data.error = data.error || n;
          else if (m.toLowerCase().includes('warning')) data.warning = data.warning || n;
        });
      }
    }

    const rows = document.querySelectorAll('table tr, [role="row"]');
    rows.forEach(row => {
      const cells = row.querySelectorAll('td, [role="cell"]');
      if (cells.length >= 2) {
        const issue = cells[0]?.innerText?.trim() || '';
        const count = cells[cells.length - 1]?.innerText?.trim() || '';
        if (issue && issue !== 'Issue' && issue !== 'Status') {
          data.issues.push({ issue, count });
        }
      }
    });

    data.rawSnippet = text.split('\n').filter(l => l.trim()).slice(0, 30).join('\n');
    return data;
  });
}

// ─── Specific Scrapers ───

async function scrapePerformance() {
  const tabId = await ensureGSCTab();
  const url = `${GSC_BASE}/performance/search-analytics?resource_id=${encodeURIComponent(PROPERTY)}`;
  await chrome.tabs.update(tabId, { url });
  await waitForPageLoad(tabId, 8000);

  return await injectAndRun(tabId, () => {
    const text = document.body?.innerText || '';
    const data = { clicks: '', impressions: '', ctr: '', position: '', queries: [], pages: [] };

    const clicksMatch = text.match(/Total clicks[\s\n]*([\d,.KMB]+)/i);
    if (clicksMatch) data.clicks = clicksMatch[1];
    const impMatch = text.match(/Total impressions[\s\n]*([\d,.KMB]+)/i);
    if (impMatch) data.impressions = impMatch[1];
    const ctrMatch = text.match(/Average CTR[\s\n]*([\d.]+%)/i);
    if (ctrMatch) data.ctr = ctrMatch[1];
    const posMatch = text.match(/Average position[\s\n]*([\d.]+)/i);
    if (posMatch) data.position = posMatch[1];

    document.querySelectorAll('table tr').forEach((row, i) => {
      if (i === 0) return;
      const cells = row.querySelectorAll('td');
      if (cells.length >= 2) {
        const entry = {
          label: cells[0]?.innerText?.trim() || '',
          clicks: cells[1]?.innerText?.trim() || '',
          impressions: cells[2]?.innerText?.trim() || '',
        };
        if (entry.label.startsWith('http')) data.pages.push(entry);
        else data.queries.push(entry);
      }
    });
    return data;
  });
}

async function scrapePagesReport() {
  const tabId = await ensureGSCTab();
  const url = `${GSC_BASE}/index?resource_id=${encodeURIComponent(PROPERTY)}`;
  await chrome.tabs.update(tabId, { url });
  await waitForPageLoad(tabId, 8000);

  return await injectAndRun(tabId, () => {
    const text = document.body?.innerText || '';
    const data = { indexed: '', notIndexed: '', reasons: [] };

    const notIdxMatch = text.match(/Not indexed\s*[:\n]?\s*([\d,]+)/i);
    if (notIdxMatch) data.notIndexed = notIdxMatch[1];
    const idxMatch = text.match(/(?:^|\n)\s*([\d,]+)\s*indexed/im);
    if (idxMatch) data.indexed = idxMatch[1];
    if (!data.indexed) {
      const altMatch = text.match(/Indexed\s*[:\n]?\s*([\d,]+)/i);
      if (altMatch) data.indexed = altMatch[1];
    }

    const reasonPatterns = [
      'Crawled - currently not indexed', 'Discovered - currently not indexed',
      'Excluded by noindex tag', 'Blocked by robots.txt',
      'Duplicate without user-selected canonical', 'Duplicate, Google chose different canonical',
      'Not found (404)', 'Soft 404', 'Server error (5xx)', 'Redirect error',
      'Blocked due to other 4xx issue', 'Page with redirect',
      'Alternate page with proper canonical tag',
      'Blocked due to unauthorized request (401)', 'Blocked due to access forbidden (403)',
    ];

    document.querySelectorAll('table tr, [role="row"]').forEach(row => {
      const cellText = row.innerText?.trim() || '';
      for (const p of reasonPatterns) {
        if (cellText.includes(p)) {
          const numMatch = cellText.match(/(\d[\d,]*)\s*$/);
          data.reasons.push({ reason: p, count: numMatch?.[1] || '' });
          break;
        }
      }
    });
    return data;
  });
}

async function scrapeEnhancements() {
  const tabId = await ensureGSCTab();
  const url = `${GSC_BASE}/enhancements?resource_id=${encodeURIComponent(PROPERTY)}`;
  await chrome.tabs.update(tabId, { url });
  await waitForPageLoad(tabId, 8000);

  return await injectAndRun(tabId, () => {
    const text = document.body?.innerText || '';
    const data = { enhancements: [] };

    document.querySelectorAll('a[href*="/r/"], [data-type], table tr, [role="row"]').forEach(row => {
      const label = row.querySelector('td, [class*="label"], [class*="name"]');
      const count = row.querySelector('[class*="count"], [class*="number"]');
      if (label && count) {
        data.enhancements.push({ type: label.innerText?.trim() || '', count: count.innerText?.trim() || '' });
      }
    });

    const enhTypes = [
      'Product snippet', 'Merchant listing', 'Review snippet',
      'FAQ', 'Breadcrumb', 'Sitelinks search box', 'Logo',
      'Video', 'Event', 'How-to', 'Recipe',
    ];
    for (const et of enhTypes) {
      const regex = new RegExp(et + '[\\s\\n:]*(\\d[\\d,]*)', 'i');
      const m = text.match(regex);
      if (m && !data.enhancements.find(e => e.type.includes(et))) {
        data.enhancements.push({ type: et, count: m[1] });
      }
    }
    return data;
  });
}

async function scrapeMerchantListings() { return scrapeEnhancementPage('r/merchant-listings'); }
async function scrapeProductSnippets() { return scrapeEnhancementPage('r/product'); }
async function scrapeReviewSnippets() { return scrapeEnhancementPage('r/review-snippet'); }
async function scrapeVideos() { return scrapeEnhancementPage('r/videos'); }

async function scrapeLinks() {
  const tabId = await ensureGSCTab();
  const url = `${GSC_BASE}/links?resource_id=${encodeURIComponent(PROPERTY)}`;
  await chrome.tabs.update(tabId, { url });
  await waitForPageLoad(tabId, 8000);

  return await injectAndRun(tabId, () => {
    const text = document.body?.innerText || '';
    const data = { externalLinks: '', internalLinks: '', topLinkingDomains: [], topLinkedPages: [] };

    const extMatch = text.match(/External links[\s\n]*([\d,.KMB]+)/i);
    if (extMatch) data.externalLinks = extMatch[1];
    const intMatch = text.match(/Internal links[\s\n]*([\d,.KMB]+)/i);
    if (intMatch) data.internalLinks = intMatch[1];

    const tables = document.querySelectorAll('table');
    if (tables.length >= 1) {
      tables[0].querySelectorAll('tr').forEach((row, i) => {
        if (i === 0) return;
        const cells = row.querySelectorAll('td');
        if (cells.length >= 2) {
          data.topLinkingDomains.push({
            domain: cells[0]?.innerText?.trim() || '',
            count: cells[1]?.innerText?.trim() || '',
          });
        }
      });
    }
    if (tables.length >= 2) {
      tables[1].querySelectorAll('tr').forEach((row, i) => {
        if (i === 0) return;
        const cells = row.querySelectorAll('td');
        if (cells.length >= 2) {
          data.topLinkedPages.push({
            page: cells[0]?.innerText?.trim() || '',
            count: cells[1]?.innerText?.trim() || '',
          });
        }
      });
    }

    data.rawSnippet = text.split('\n').filter(l => l.trim()).slice(0, 40).join('\n');
    return data;
  });
}

async function scrapeSitemaps() {
  const tabId = await ensureGSCTab();
  const url = `${GSC_BASE}/sitemaps?resource_id=${encodeURIComponent(PROPERTY)}`;
  await chrome.tabs.update(tabId, { url });
  await waitForPageLoad(tabId, 8000);

  return await injectAndRun(tabId, () => {
    const text = document.body?.innerText || '';
    const data = { sitemaps: [] };

    document.querySelectorAll('table tr, [role="row"]').forEach((row, i) => {
      if (i === 0) return;
      const cells = row.querySelectorAll('td, [role="cell"]');
      if (cells.length >= 2) {
        data.sitemaps.push({
          url: cells[0]?.innerText?.trim() || '',
          type: cells[1]?.innerText?.trim() || '',
          submitted: cells[2]?.innerText?.trim() || '',
          lastRead: cells[3]?.innerText?.trim() || '',
          status: cells[4]?.innerText?.trim() || '',
          discovered: cells[5]?.innerText?.trim() || '',
        });
      }
    });

    data.rawSnippet = text.split('\n').filter(l => l.trim()).slice(0, 30).join('\n');
    return data;
  });
}

// ─── Fetch All & Send to Dashboard ───

const ALL_SCRAPERS = [
  { key: 'pages', fn: scrapePagesReport, label: 'Pages Report' },
  { key: 'performance', fn: scrapePerformance, label: 'Performance' },
  { key: 'enhancements', fn: scrapeEnhancements, label: 'Enhancements' },
  { key: 'merchantListings', fn: scrapeMerchantListings, label: 'Merchant Listings' },
  { key: 'productSnippets', fn: scrapeProductSnippets, label: 'Product Snippets' },
  { key: 'reviewSnippets', fn: scrapeReviewSnippets, label: 'Review Snippets' },
  { key: 'videos', fn: scrapeVideos, label: 'Videos' },
  { key: 'links', fn: scrapeLinks, label: 'Links' },
  { key: 'sitemaps', fn: scrapeSitemaps, label: 'Sitemaps' },
];

async function fetchAllReports() {
  const reports = {};
  for (let i = 0; i < ALL_SCRAPERS.length; i++) {
    const s = ALL_SCRAPERS[i];
    chrome.runtime.sendMessage({
      type: 'FETCH_ALL_PROGRESS',
      current: s.label,
      done: i,
      total: ALL_SCRAPERS.length,
    }).catch(() => {});

    try {
      reports[s.key] = await s.fn();
    } catch (e) {
      reports[s.key] = { error: e.message || 'Failed' };
    }
  }

  chrome.runtime.sendMessage({
    type: 'FETCH_ALL_PROGRESS',
    current: 'Sending to dashboard...',
    done: ALL_SCRAPERS.length,
    total: ALL_SCRAPERS.length,
  }).catch(() => {});

  const sendResult = await sendToDashboard(reports);
  reports._dashboardSync = sendResult;

  lastScrapedData = reports;
  chrome.storage.local.set({ lastScrapedData: reports });

  return reports;
}

async function sendToDashboard(data) {
  console.log(`[GSC-EXT] Sending GSC data to ${getApiUrl()}/api/extension/gsc-data (keys: ${Object.keys(data).join(', ')})`);
  try {
    const resp = await fetch(`${getApiUrl()}/api/extension/gsc-data`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!resp.ok) {
      console.error('[GSC-EXT] Dashboard sync failed:', resp.status, resp.statusText);
      return { ok: false, status: resp.status, error: resp.statusText };
    }
    const result = await resp.json();
    console.log('[GSC-EXT] Dashboard sync success:', result);
    return result;
  } catch (e) {
    console.error('[GSC-EXT] Dashboard sync FAILED:', DASHBOARD_URL, e.message);
    return { ok: false, error: e.message || 'Dashboard not reachable' };
  }
}

// ─── Message Handler ───

chrome.runtime.onMessage.addListener((msg, sender, sendResponse) => {
  const handle = async () => {
    switch (msg.type) {
      case 'GET_STATE': return { queue };

      case 'START_QUEUE': {
        const urls = (msg.urls || []).filter(u => u.startsWith('http'));
        if (!urls.length) return { error: 'No valid URLs' };
        if (processingTimeout) clearTimeout(processingTimeout);
        isProcessing = false;
        queue = { state: 'running', urls, results: [], processed: 0, errors: 0, total: urls.length, currentUrl: '' };
        saveQueue(); broadcastState(); processNext();
        return { ok: true, queued: urls.length };
      }

      case 'PAUSE_QUEUE':
        if (queue.state === 'running') {
          queue.state = 'paused';
          if (processingTimeout) clearTimeout(processingTimeout);
          broadcastState(); saveQueue();
        }
        return { ok: true };

      case 'RESUME_QUEUE':
        if (queue.state === 'paused') {
          queue.state = 'running';
          broadcastState(); saveQueue(); processNext();
        }
        return { ok: true };

      case 'STOP_QUEUE':
        queue.state = 'stopped'; queue.currentUrl = '';
        if (processingTimeout) clearTimeout(processingTimeout);
        broadcastState(); saveQueue();
        return { ok: true };

      case 'CLEAR_QUEUE':
        queue = { state: 'idle', urls: [], results: [], processed: 0, errors: 0, total: 0, currentUrl: '' };
        if (processingTimeout) clearTimeout(processingTimeout);
        broadcastState(); saveQueue();
        return { ok: true };

      case 'SCRAPE_PERFORMANCE': return await scrapePerformance();
      case 'SCRAPE_PAGES': return await scrapePagesReport();
      case 'SCRAPE_ENHANCEMENTS': return await scrapeEnhancements();
      case 'SCRAPE_MERCHANT': return await scrapeMerchantListings();
      case 'SCRAPE_PRODUCT_SNIPPETS': return await scrapeProductSnippets();
      case 'SCRAPE_REVIEW_SNIPPETS': return await scrapeReviewSnippets();
      case 'SCRAPE_VIDEOS': return await scrapeVideos();
      case 'SCRAPE_LINKS': return await scrapeLinks();
      case 'SCRAPE_SITEMAPS': return await scrapeSitemaps();
      case 'FETCH_ALL': return await fetchAllReports();
      case 'SEND_TO_DASHBOARD': return await sendToDashboard(msg.data || {});
      case 'EXPORT_DATA': return { queue, scraped: true };

      case 'GET_SETTINGS': return { dashboardUrl: DASHBOARD_URL, property: PROPERTY, syncPending: dashboardSyncPending };
      case 'SET_DASHBOARD_URL':
        DASHBOARD_URL = msg.url || DEFAULT_DASHBOARD_URL;
        chrome.storage.sync.set({ dashboardUrl: DASHBOARD_URL });
        return { ok: true, dashboardUrl: DASHBOARD_URL };
      case 'SET_PROPERTY':
        PROPERTY = msg.property || DEFAULT_PROPERTY;
        chrome.storage.sync.set({ property: PROPERTY });
        return { ok: true, property: PROPERTY };
      case 'GET_SCRAPED_DATA':
        return { data: lastScrapedData };
      case 'RETRY_SYNC':
        if (queue.results.length > 0) {
          sendBulkResultsToDashboard();
          return { ok: true, retrying: true };
        }
        return { ok: false, error: 'No results to sync' };

      default:
        return { error: 'Unknown message type: ' + msg.type };
    }
  };

  handle().then(sendResponse).catch(e => sendResponse({ error: e.message }));
  return true;
});

loadQueue();

// Live-sync settings from other Chrome instances
chrome.storage.onChanged.addListener((changes, area) => {
  if (area !== 'sync') return;
  if (changes.dashboardUrl) DASHBOARD_URL = changes.dashboardUrl.newValue || DEFAULT_DASHBOARD_URL;
  if (changes.property) PROPERTY = changes.property.newValue || DEFAULT_PROPERTY;
});
