const BASE = '/api';

async function fetchJSON(url, opts = {}) {
  const res = await fetch(BASE + url, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => '');
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  // Combined live endpoint — one call for all GSC data
  getLiveData: () => fetchJSON('/live/all'),

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

  // Actions
  smartSync: () => fetchJSON('/smart-sync', { method: 'POST' }),
  autoInspect: (urls) => fetchJSON('/auto-inspect', { method: 'POST', body: JSON.stringify({ urls: urls || [] }) }),
  saveGscReports: (data) => fetchJSON('/gsc-reports', { method: 'POST', body: JSON.stringify(data) }),
  clearCache: () => fetchJSON('/cache/clear', { method: 'POST' }),
};
