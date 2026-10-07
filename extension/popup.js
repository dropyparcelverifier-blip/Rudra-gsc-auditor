const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

let pollInterval = null;

function sendMsg(msg) {
  return new Promise((resolve) => {
    chrome.runtime.sendMessage(msg, (resp) => {
      if (chrome.runtime.lastError) {
        console.warn('[GSC-EXT] sendMsg error:', chrome.runtime.lastError.message);
      }
      resolve(resp);
    });
  });
}

// ─── Tabs ───
$$('.tab').forEach(tab => {
  tab.addEventListener('click', () => {
    $$('.tab').forEach(t => t.classList.remove('active'));
    $$('.tab-content').forEach(t => t.classList.remove('active'));
    tab.classList.add('active');
    $(`#tab-${tab.dataset.tab}`).classList.add('active');
  });
});

// ─── Queue UI ───
function updateUI(queue) {
  if (!queue) return;
  const { state, total, processed, errors, results, currentUrl } = queue;
  const queued = Math.max(0, total - processed);
  const pct = total > 0 ? Math.round((processed / total) * 100) : 0;

  const badge = $('#statusBadge');
  badge.className = `badge badge-${state}`;
  const labels = { idle: 'Ready', running: 'Running', paused: 'Paused', done: 'Complete', stopped: 'Stopped' };
  $('#statusText').textContent = labels[state] || state;

  const isActive = state === 'running' || state === 'paused';
  $('#urlInput').disabled = isActive;
  $('#btnStart').style.display = isActive ? 'none' : '';
  $('#btnPause').style.display = state === 'running' ? '' : 'none';
  $('#btnResume').style.display = state === 'paused' ? '' : 'none';
  $('#btnStop').style.display = isActive ? '' : 'none';
  $('#btnAdd').disabled = isActive;
  $('#btnImport').disabled = isActive;
  $('#btnClear').disabled = isActive;

  if (total > 0) {
    $('#statsSection').style.display = '';
    $('#statQueued').textContent = queued > 0 ? queued : total;
    $('#statProcessed').textContent = processed;
    $('#statErrors').textContent = errors;
    $('#progressFill').style.width = `${pct}%`;
    $('#progressLabel').textContent = `${processed} of ${total} URLs finished · ${queued} still in queue`;
    $('#progressPct').textContent = `${pct}%`;

    if (currentUrl && state === 'running') {
      $('#currentUrl').style.display = '';
      $('#currentUrlText').textContent = currentUrl;
    } else {
      $('#currentUrl').style.display = 'none';
    }
  } else {
    $('#statsSection').style.display = 'none';
  }

  if (results && results.length > 0) {
    $('#resultsSection').style.display = '';
    const indexed = results.filter(r => r.status === 'indexed').length;
    const submitted = results.filter(r => ['submitted', 'requested'].includes(r.status)).length;
    const errs = results.filter(r => r.status === 'error').length;
    $('#rcIndexed').textContent = `${indexed} indexed`;
    $('#rcSubmitted').textContent = `${submitted} submitted`;
    $('#rcErrors').textContent = `${errs} errors`;

    const tbody = $('#resultsBody');
    tbody.innerHTML = results.map((r, i) => {
      const richHtml = (r.richResults || []).map(rt => `<span class="rich-tag">${esc(rt)}</span>`).join('');
      return `<tr>
        <td style="color:#94a3b8">${i + 1}</td>
        <td class="url-cell" title="${esc(r.url)}">${esc(r.url.replace(/^https?:\/\//, '').slice(0, 45))}</td>
        <td style="font-size:10px">${esc(r.coverage || '—')}</td>
        <td><span class="pill pill-${r.status}">${statusLabel(r.status)}</span></td>
        <td><div class="rich-tags">${richHtml || '—'}</div></td>
        <td style="color:#64748b;font-size:10px;max-width:100px">${esc(r.action || r.error || '—')}</td>
      </tr>`;
    }).join('');
  } else {
    $('#resultsSection').style.display = 'none';
  }

  if (state === 'running' && !pollInterval) {
    pollInterval = setInterval(fetchState, 1500);
  } else if (state !== 'running' && pollInterval) {
    clearInterval(pollInterval);
    pollInterval = null;
  }
}

function statusLabel(s) {
  const map = { indexed: 'Indexed', submitted: 'Submitted', requested: 'Requested', not_indexed: 'Not Indexed', error: 'Error', pending: 'Pending' };
  return map[s] || s;
}

function esc(s) {
  const d = document.createElement('div');
  d.textContent = s || '';
  return d.innerHTML;
}

async function fetchState() {
  const resp = await sendMsg({ type: 'GET_STATE' });
  if (resp?.queue) updateUI(resp.queue);
}

// Queue buttons
$('#btnStart').addEventListener('click', async () => {
  const urls = $('#urlInput').value.split('\n').map(u => u.trim()).filter(u => u.startsWith('http'));
  if (!urls.length) return;
  await sendMsg({ type: 'START_QUEUE', urls });
  fetchState();
});

$('#btnAdd').addEventListener('click', () => {
  const urls = $('#urlInput').value.split('\n').map(u => u.trim()).filter(u => u.startsWith('http'));
  if (urls.length) {
    $('#urlInput').value = urls.join('\n');
    showToast(`${urls.length} URL${urls.length > 1 ? 's' : ''} ready — click Start Queue`, 'ok');
  } else {
    showToast('No valid URLs found — paste URLs starting with http', 'err');
  }
});

$('#btnPause').addEventListener('click', async () => { await sendMsg({ type: 'PAUSE_QUEUE' }); fetchState(); });
$('#btnResume').addEventListener('click', async () => { await sendMsg({ type: 'RESUME_QUEUE' }); fetchState(); });
$('#btnStop').addEventListener('click', async () => { await sendMsg({ type: 'STOP_QUEUE' }); fetchState(); });
$('#btnClear').addEventListener('click', async () => {
  await sendMsg({ type: 'CLEAR_QUEUE' });
  $('#urlInput').value = '';
  $('#btnStart').textContent = 'Start Queue';
  fetchState();
  showToast('Queue cleared', 'ok');
});

$('#urlInput').addEventListener('input', () => {
  const count = $('#urlInput').value.split('\n').filter(u => u.trim().startsWith('http')).length;
  $('#btnStart').textContent = count > 0 ? `Start Queue (${count})` : 'Start Queue';
});

$('#btnImport').addEventListener('click', () => $('#fileInput').click());
$('#fileInput').addEventListener('change', (e) => {
  const file = e.target.files[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (ev) => {
    const urls = ev.target.result.split(/[\r\n,]+/).map(u => u.trim()).filter(u => u.startsWith('http'));
    const cur = $('#urlInput').value;
    $('#urlInput').value = cur ? cur + '\n' + urls.join('\n') : urls.join('\n');
  };
  reader.readAsText(file);
  e.target.value = '';
});

$('#btnSample').addEventListener('click', (e) => {
  e.preventDefault();
  const csv = 'url\nhttps://rudraretails.com/products/example-1\nhttps://rudraretails.com/products/example-2\n';
  const blob = new Blob([csv], { type: 'text/csv' });
  const a = document.createElement('a');
  const url = URL.createObjectURL(blob);
  a.href = url;
  a.download = 'sample_urls.csv';
  a.click();
  URL.revokeObjectURL(url);
});

// ─── GSC Data Scrapers ───
function showDataLoading(title) {
  $('#dataResults').style.display = '';
  $('#dataResultsTitle').textContent = title;
  $('#dataResultsContent').innerHTML = '<div class="loading-msg"><span class="spinner"></span> Fetching data from GSC... please wait</div>';
}

function showDataError(err) {
  $('#dataResultsContent').innerHTML = `<div style="color:#ef4444;padding:8px">Error: ${esc(err)}</div>`;
}

let lastScrapedData = null;

function renderEnhancementData(data, title) {
  if (data.notAvailable) {
    return '<p style="color:#94a3b8;font-size:11px;padding:8px">Not available for this property</p>';
  }
  let html = '<div class="data-kv">';
  html += `<div class="data-kv-item"><div class="data-kv-label">Valid</div><div class="data-kv-value" style="color:#16a34a">${esc(data.valid || '—')}</div></div>`;
  html += `<div class="data-kv-item"><div class="data-kv-label">Errors</div><div class="data-kv-value" style="color:#ef4444">${esc(data.error || '—')}</div></div>`;
  html += `<div class="data-kv-item"><div class="data-kv-label">Warnings</div><div class="data-kv-value" style="color:#f59e0b">${esc(data.warning || '—')}</div></div>`;
  html += '</div>';
  if (data.issues?.length) {
    html += '<table><thead><tr><th>Issue</th><th>Count</th></tr></thead><tbody>';
    data.issues.forEach(i => { html += `<tr><td>${esc(i.issue)}</td><td style="font-weight:600">${esc(i.count)}</td></tr>`; });
    html += '</tbody></table>';
  }
  if (!data.valid && !data.error && !data.warning && !data.issues?.length && data.rawSnippet) {
    html += `<pre style="font-size:10px;color:#64748b;white-space:pre-wrap;max-height:200px;overflow:auto;margin-top:8px">${esc(data.rawSnippet)}</pre>`;
  }
  return html;
}

function renderScrapedData(msgType, data) {
  if (data?.error) {
    showDataError(data.error);
    return;
  }

  let html = '';

  if (msgType === 'SCRAPE_PAGES') {
    html = '<div class="data-kv">';
    html += `<div class="data-kv-item"><div class="data-kv-label">Indexed</div><div class="data-kv-value" style="color:#16a34a">${esc(data.indexed || '—')}</div></div>`;
    html += `<div class="data-kv-item"><div class="data-kv-label">Not Indexed</div><div class="data-kv-value" style="color:#ef4444">${esc(data.notIndexed || '—')}</div></div>`;
    html += '</div>';
    if (data.reasons?.length) {
      html += '<table><thead><tr><th>Reason</th><th>Count</th></tr></thead><tbody>';
      data.reasons.forEach(r => { html += `<tr><td>${esc(r.reason)}</td><td style="font-weight:600">${esc(r.count)}</td></tr>`; });
      html += '</tbody></table>';
    }
  } else if (msgType === 'SCRAPE_PERFORMANCE') {
    html = '<div class="data-kv">';
    html += `<div class="data-kv-item"><div class="data-kv-label">Total Clicks</div><div class="data-kv-value" style="color:#2563eb">${esc(data.clicks || '—')}</div></div>`;
    html += `<div class="data-kv-item"><div class="data-kv-label">Total Impressions</div><div class="data-kv-value" style="color:#7c3aed">${esc(data.impressions || '—')}</div></div>`;
    html += `<div class="data-kv-item"><div class="data-kv-label">Average CTR</div><div class="data-kv-value">${esc(data.ctr || '—')}</div></div>`;
    html += `<div class="data-kv-item"><div class="data-kv-label">Average Position</div><div class="data-kv-value">${esc(data.position || '—')}</div></div>`;
    html += '</div>';
    if (data.queries?.length) {
      html += '<h3 style="font-size:11px;font-weight:700;margin:8px 0 4px;color:#475569">Top Queries</h3>';
      html += '<table><thead><tr><th>Query</th><th>Clicks</th><th>Impressions</th></tr></thead><tbody>';
      data.queries.slice(0, 20).forEach(q => { html += `<tr><td>${esc(q.label)}</td><td>${esc(q.clicks)}</td><td>${esc(q.impressions)}</td></tr>`; });
      html += '</tbody></table>';
    }
  } else if (msgType === 'SCRAPE_ENHANCEMENTS') {
    html = '';
    if (data.enhancements?.length) {
      html += '<table><thead><tr><th>Enhancement Type</th><th>Count</th></tr></thead><tbody>';
      data.enhancements.forEach(e => { html += `<tr><td>${esc(e.type)}</td><td style="font-weight:600">${esc(e.count)}</td></tr>`; });
      html += '</tbody></table>';
    } else {
      html += '<p style="color:#94a3b8;font-size:11px;padding:8px">No enhancement data found</p>';
    }
  } else if (msgType === 'SCRAPE_LINKS') {
    html = '<div class="data-kv">';
    html += `<div class="data-kv-item"><div class="data-kv-label">External Links</div><div class="data-kv-value" style="color:#2563eb">${esc(data.externalLinks || '—')}</div></div>`;
    html += `<div class="data-kv-item"><div class="data-kv-label">Internal Links</div><div class="data-kv-value" style="color:#7c3aed">${esc(data.internalLinks || '—')}</div></div>`;
    html += '</div>';
    if (data.topLinkingDomains?.length) {
      html += '<h3 style="font-size:11px;font-weight:700;margin:8px 0 4px;color:#475569">Top Linking Domains</h3>';
      html += '<table><thead><tr><th>Domain</th><th>Count</th></tr></thead><tbody>';
      data.topLinkingDomains.slice(0, 15).forEach(d => { html += `<tr><td>${esc(d.domain)}</td><td style="font-weight:600">${esc(d.count)}</td></tr>`; });
      html += '</tbody></table>';
    }
    if (data.topLinkedPages?.length) {
      html += '<h3 style="font-size:11px;font-weight:700;margin:8px 0 4px;color:#475569">Top Linked Pages</h3>';
      html += '<table><thead><tr><th>Page</th><th>Count</th></tr></thead><tbody>';
      data.topLinkedPages.slice(0, 15).forEach(p => { html += `<tr><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(p.page)}</td><td style="font-weight:600">${esc(p.count)}</td></tr>`; });
      html += '</tbody></table>';
    }
    if (data.rawSnippet && !data.externalLinks && !data.topLinkingDomains?.length) {
      html += `<pre style="font-size:10px;color:#64748b;white-space:pre-wrap;max-height:200px;overflow:auto;margin-top:8px">${esc(data.rawSnippet)}</pre>`;
    }
  } else if (msgType === 'SCRAPE_SITEMAPS') {
    if (data.sitemaps?.length) {
      html = '<table><thead><tr><th>Sitemap URL</th><th>Type</th><th>Submitted</th><th>Status</th></tr></thead><tbody>';
      data.sitemaps.forEach(s => {
        html += `<tr><td style="max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-family:monospace;font-size:10px">${esc(s.url)}</td><td>${esc(s.type)}</td><td>${esc(s.submitted)}</td><td>${esc(s.status)}</td></tr>`;
      });
      html += '</tbody></table>';
    } else if (data.rawSnippet) {
      html = `<pre style="font-size:10px;color:#64748b;white-space:pre-wrap;max-height:200px;overflow:auto">${esc(data.rawSnippet)}</pre>`;
    } else {
      html = '<p style="color:#94a3b8;font-size:11px;padding:8px">No sitemap data found</p>';
    }
  } else {
    html = renderEnhancementData(data);
  }

  $('#dataResultsContent').innerHTML = html;
}

const SCRAPER_TITLES = {
  SCRAPE_PAGES: 'PAGES REPORT',
  SCRAPE_PERFORMANCE: 'PERFORMANCE DATA',
  SCRAPE_ENHANCEMENTS: 'ENHANCEMENTS OVERVIEW',
  SCRAPE_MERCHANT: 'MERCHANT LISTINGS',
  SCRAPE_PRODUCT_SNIPPETS: 'PRODUCT SNIPPETS',
  SCRAPE_REVIEW_SNIPPETS: 'REVIEW SNIPPETS',
  SCRAPE_VIDEOS: 'VIDEOS',
  SCRAPE_LINKS: 'LINKS',
  SCRAPE_SITEMAPS: 'SITEMAPS',
};

// Individual scraper buttons
$$('.data-btn[data-msg]').forEach(btn => {
  btn.addEventListener('click', async () => {
    const msgType = btn.dataset.msg;
    const title = SCRAPER_TITLES[msgType] || 'DATA';
    showDataLoading(title);
    try {
      const data = await sendMsg({ type: msgType });
      lastScrapedData = data;
      chrome.storage.local.set({ lastScrapedUIData: { type: msgType, data } });
      renderScrapedData(msgType, data);
    } catch (e) { showDataError(e.message || 'Failed'); }
  });
});

// Fetch All button
$('#btnFetchAll').addEventListener('click', async () => {
  const btn = $('#btnFetchAll');
  btn.disabled = true;
  btn.textContent = 'Fetching...';
  $$('.data-btn').forEach(b => b.disabled = true);
  $('#fetchAllProgress').style.display = '';
  $('#fetchAllLabel').textContent = 'Starting...';
  $('#fetchAllFill').style.width = '0%';
  $('#fetchAllPct').textContent = '0%';

  $('#dataResults').style.display = '';
  $('#dataResultsTitle').textContent = 'ALL GSC DATA';
  $('#dataResultsContent').innerHTML = '<div class="loading-msg"><span class="spinner"></span> Fetching all GSC reports sequentially... this takes ~2 minutes</div>';

  try {
    const data = await sendMsg({ type: 'FETCH_ALL' });
    lastScrapedData = data;

    let html = '';
    const sections = [
      { key: 'pages', title: 'Pages Report', type: 'SCRAPE_PAGES' },
      { key: 'performance', title: 'Performance', type: 'SCRAPE_PERFORMANCE' },
      { key: 'enhancements', title: 'Enhancements', type: 'SCRAPE_ENHANCEMENTS' },
      { key: 'merchantListings', title: 'Merchant Listings', type: 'SCRAPE_MERCHANT' },
      { key: 'productSnippets', title: 'Product Snippets', type: 'SCRAPE_PRODUCT_SNIPPETS' },
      { key: 'reviewSnippets', title: 'Review Snippets', type: 'SCRAPE_REVIEW_SNIPPETS' },
      { key: 'videos', title: 'Videos', type: 'SCRAPE_VIDEOS' },
      { key: 'links', title: 'Links', type: 'SCRAPE_LINKS' },
      { key: 'sitemaps', title: 'Sitemaps', type: 'SCRAPE_SITEMAPS' },
    ];

    for (const s of sections) {
      const sectionData = data[s.key];
      if (!sectionData) continue;
      html += `<div class="fetch-all-section">`;
      html += `<h3 class="fetch-all-title">${esc(s.title)}</h3>`;
      if (sectionData.error) {
        html += `<div style="color:#ef4444;font-size:11px;padding:4px 0">Error: ${esc(sectionData.error)}</div>`;
      } else {
        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = (() => {
          const saved = $('#dataResultsContent').innerHTML;
          renderScrapedData(s.type, sectionData);
          const result = $('#dataResultsContent').innerHTML;
          $('#dataResultsContent').innerHTML = saved;
          return result;
        })();
        html += tempDiv.innerHTML;
      }
      html += `</div>`;
    }

    if (data._dashboardSync?.ok !== undefined) {
      const ok = data._dashboardSync.ok !== false;
      html += `<div class="sync-status ${ok ? 'sync-ok' : 'sync-err'}">${ok ? 'Dashboard synced — data saved to server' : 'Dashboard sync failed: ' + esc(data._dashboardSync.error || 'Check Flask is running on port 5001')}</div>`;
      showToast(ok ? 'All GSC data synced to dashboard' : 'Dashboard sync failed', ok ? 'ok' : 'err');
    }

    $('#dataResultsContent').innerHTML = html;
  } catch (e) {
    showDataError(e.message || 'Fetch All failed');
  }

  btn.disabled = false;
  btn.textContent = 'Fetch All';
  $$('.data-btn').forEach(b => b.disabled = false);
  $('#fetchAllProgress').style.display = 'none';
});

// Listen for progress and sync updates
chrome.runtime.onMessage.addListener((msg) => {
  if (msg.type === 'STATE_UPDATE') updateUI(msg.queue);
  if (msg.type === 'FETCH_ALL_PROGRESS') {
    const pct = Math.round((msg.done / msg.total) * 100);
    $('#fetchAllLabel').textContent = `Fetching: ${msg.current}`;
    $('#fetchAllFill').style.width = `${pct}%`;
    $('#fetchAllPct').textContent = `${pct}%`;
  }
  if (msg.type === 'BULK_SYNC_STATUS') {
    showToast(msg.ok ? 'Bulk results synced to dashboard' : 'Bulk sync failed — check dashboard URL', msg.ok ? 'ok' : 'err');
    if (msg.ok) {
      $('#syncPendingBanner').style.display = 'none';
    } else {
      $('#syncPendingBanner').style.display = 'flex';
    }
  }
  return false;
});

function showToast(text, type) {
  let toast = document.getElementById('toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'toast';
    document.body.appendChild(toast);
  }
  toast.textContent = text;
  toast.className = `toast toast-${type || 'ok'} toast-show`;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => { toast.classList.remove('toast-show'); }, 4000);
}

// ─── Settings ───
(async () => {
  const settings = await sendMsg({ type: 'GET_SETTINGS' });
  if (settings?.dashboardUrl) $('#dashboardUrl').value = settings.dashboardUrl;
  if (settings?.property) $('#propertyUrl').value = settings.property;
  if (settings?.syncPending) {
    $('#syncPendingBanner').style.display = 'flex';
  }

  // Load persisted scraped data if available
  const scraped = await sendMsg({ type: 'GET_SCRAPED_DATA' });
  if (scraped?.data) {
    lastScrapedData = scraped.data;
  }
})();

$('#btnSaveProperty').addEventListener('click', async () => {
  let prop = $('#propertyUrl').value.trim();
  if (!prop) return;
  if (!prop.endsWith('/')) prop += '/';
  await sendMsg({ type: 'SET_PROPERTY', property: prop });
  $('#btnSaveProperty').textContent = 'Saved!';
  showToast('Property updated — reload GSC tab to apply', 'ok');
  setTimeout(() => { $('#btnSaveProperty').textContent = 'Save'; }, 1500);
});

$('#btnSaveUrl').addEventListener('click', async () => {
  let url = $('#dashboardUrl').value.trim().replace(/\/+$/, '');
  if (!url) return;
  if (url.includes('localhost:3001') || url.includes('localhost:3000') || url.includes('localhost:5000')) {
    url = 'http://localhost:5001';
    $('#dashboardUrl').value = url;
    showToast('Corrected to Flask API port 5001', 'ok');
  }
  await sendMsg({ type: 'SET_DASHBOARD_URL', url });
  $('#btnSaveUrl').textContent = 'Saved!';
  setTimeout(() => { $('#btnSaveUrl').textContent = 'Save'; }, 1500);
});

$('#btnRetrySync').addEventListener('click', async () => {
  $('#btnRetrySync').disabled = true;
  $('#btnRetrySync').textContent = 'Syncing...';
  const resp = await sendMsg({ type: 'RETRY_SYNC' });
  setTimeout(() => {
    $('#btnRetrySync').disabled = false;
    $('#btnRetrySync').textContent = 'Retry Sync';
  }, 3000);
});

$('#btnExportData').addEventListener('click', () => {
  if (!lastScrapedData) return;
  const blob = new Blob([JSON.stringify(lastScrapedData, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  const blobUrl = URL.createObjectURL(blob);
  a.href = blobUrl;
  a.download = `gsc_data_${new Date().toISOString().slice(0, 10)}.json`;
  a.click();
  URL.revokeObjectURL(blobUrl);
});

$('#btnExportResults').addEventListener('click', async () => {
  const resp = await sendMsg({ type: 'GET_STATE' });
  const results = resp?.queue?.results;
  if (!results?.length) return;
  const rows = ['URL,Status,Coverage,Action,Rich Results'];
  results.forEach(r => {
    const rich = (r.richResults || []).join('; ');
    rows.push(`"${(r.url || '').replace(/"/g, '""')}","${r.status || ''}","${(r.coverage || '').replace(/"/g, '""')}","${(r.action || r.error || '').replace(/"/g, '""')}","${rich}"`);
  });
  const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
  const a = document.createElement('a');
  const blobUrl = URL.createObjectURL(blob);
  a.href = blobUrl;
  a.download = `bulk_results_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(blobUrl);
});

fetchState();
