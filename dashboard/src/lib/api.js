const BASE = '/api';

async function fetchJSON(url, opts = {}) {
  const { signal, ...rest } = opts;
  const headers = rest.body ? { 'Content-Type': 'application/json', ...rest.headers } : { ...rest.headers };
  const res = await fetch(BASE + url, { ...rest, headers, signal });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Combined live endpoint — one call for all GSC data
  getLiveData: (signal) => fetchJSON('/live/all', { signal }),

  // Individual live endpoints
  getSitemapStats: () => fetchJSON('/live/sitemap-stats'),
  getSnippetStats: () => fetchJSON('/live/snippet-stats'),
  getSearchPerformance: () => fetchJSON('/live/search-performance'),
  getTopQueries: () => fetchJSON('/live/top-queries'),
  getTopPages: () => fetchJSON('/live/top-pages'),
  getDeviceStats: () => fetchJSON('/live/device-stats'),
  getCountryStats: () => fetchJSON('/live/country-stats'),

  // Monitoring
  getMonitor: () => fetchJSON('/monitor'),
  getClassifications: () => fetchJSON('/classifications'),

  // Pipeline DB endpoints
  getDashboardData: () => fetchJSON('/dashboard-data'),
  getTrackedUrls: (params) => fetchJSON('/tracked-urls?' + new URLSearchParams(params)),
  getAccounts: () => fetchJSON('/accounts'),
  getGscReports: () => fetchJSON('/gsc-reports'),

  // Category browsing
  getUrlsByCategory: (params) => fetchJSON('/urls-by-category?' + new URLSearchParams(params)),
  batchSubmit: (data) => fetchJSON('/batch-submit', { method: 'POST', body: JSON.stringify(data) }),

  // Pipeline status (for notifications)
  getPipelineStatus: () => fetchJSON('/pipeline-status'),

  // Change log (de-indexing, newly indexed, status changes)
  getChanges: (params) => fetchJSON('/changes?' + new URLSearchParams(params)),

  // Bulk queue
  bulkQueueStart: (urls) => fetchJSON('/bulk-queue', { method: 'POST', body: JSON.stringify({ urls }) }),
  bulkQueueStatus: () => fetchJSON('/bulk-queue/status'),
  bulkQueuePause: () => fetchJSON('/bulk-queue/pause', { method: 'POST' }),
  bulkQueueResume: () => fetchJSON('/bulk-queue/resume', { method: 'POST' }),
  bulkQueueStop: () => fetchJSON('/bulk-queue/stop', { method: 'POST' }),
  bulkQueueClear: () => fetchJSON('/bulk-queue/clear', { method: 'POST' }),

  // Extension data
  getExtensionGscData: () => fetchJSON('/extension/gsc-data'),
  getBulkResults: () => fetchJSON('/bulk-results'),

  // Extension queue relay (browser-based bulk processing)
  extQueueStart: (urls) => fetchJSON('/extension/queue', { method: 'POST', body: JSON.stringify({ urls }) }),
  extQueueStatus: () => fetchJSON('/extension/queue/status'),
  extQueueClear: () => fetchJSON('/extension/queue/clear', { method: 'POST' }),

  // Enhancement URLs from pipeline inspection data
  getEnhancementUrls: (params) => fetchJSON('/enhancement-urls?' + new URLSearchParams(params)),

  // Actions
  smartSync: () => fetchJSON('/smart-sync', { method: 'POST' }),
  autoInspect: (urls) => fetchJSON('/auto-inspect', { method: 'POST', body: JSON.stringify({ urls: urls || [] }) }),
  saveGscReports: (data) => fetchJSON('/gsc-reports', { method: 'POST', body: JSON.stringify(data) }),
  clearCache: () => fetchJSON('/cache/clear', { method: 'POST' }),
};
