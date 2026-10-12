"""
Rudra Retail GSC Auditor — Dashboard Template v4
Single-page SaaS dashboard with Tailwind CSS + Chart.js + Lucide icons.
"""

DASHBOARD_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{{ brand }} — SEO Dashboard</title>
  <script src="https://cdn.tailwindcss.com/3.4.1"></script>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg: #0a0c10; --surface-1: #12151c; --surface-2: #1a1f2b;
      --surface-3: #242b3a; --border: #2d3548; --text: #e2e8f3;
      --muted: #6b7a94; --green: #22c55e; --red: #ef4444;
      --orange: #f97316; --yellow: #eab308; --blue: #3b82f6;
      --purple: #a855f7; --cyan: #06b6d4; --pink: #ec4899;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: 'Inter', sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
    .card { background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px; padding: 20px; }
    .stat-card { background: var(--surface-1); border: 1px solid var(--border); border-radius: 12px; padding: 16px 20px; display: flex; flex-direction: column; gap: 4px; }
    .stat-value { font-size: 28px; font-weight: 800; line-height: 1.1; }
    .stat-label { font-size: 13px; color: var(--muted); font-weight: 500; }
    .stat-delta { font-size: 12px; font-weight: 600; }
    .badge { display: inline-flex; align-items: center; gap: 4px; padding: 2px 10px; border-radius: 999px; font-size: 12px; font-weight: 600; }
    .badge-green { background: rgba(34,197,94,0.15); color: #4ade80; }
    .badge-red { background: rgba(239,68,68,0.15); color: #f87171; }
    .badge-yellow { background: rgba(234,179,8,0.15); color: #facc15; }
    .badge-blue { background: rgba(59,130,246,0.15); color: #60a5fa; }
    .badge-purple { background: rgba(168,85,247,0.15); color: #c084fc; }
    .badge-cyan { background: rgba(6,182,212,0.15); color: #22d3ee; }
    .badge-orange { background: rgba(249,115,22,0.15); color: #fb923c; }
    .btn { padding: 8px 16px; border-radius: 8px; font-size: 13px; font-weight: 600; cursor: pointer; border: none; transition: all 0.15s; }
    .btn-primary { background: var(--blue); color: white; }
    .btn-primary:hover { background: #2563eb; }
    .btn-outline { background: transparent; border: 1px solid var(--border); color: var(--text); }
    .btn-outline:hover { background: var(--surface-2); }
    table { width: 100%; border-collapse: collapse; }
    th { text-align: left; padding: 10px 12px; font-size: 12px; color: var(--muted); font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid var(--border); }
    td { padding: 10px 12px; font-size: 13px; border-bottom: 1px solid var(--border); }
    tr:hover td { background: var(--surface-2); }
    .filter-pill { padding: 6px 14px; border-radius: 999px; font-size: 12px; font-weight: 600; cursor: pointer; border: 1px solid var(--border); background: transparent; color: var(--muted); transition: all 0.15s; }
    .filter-pill.active { background: var(--blue); color: white; border-color: var(--blue); }
    .search-input { background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; color: var(--text); font-size: 13px; width: 100%; outline: none; }
    .search-input:focus { border-color: var(--blue); }
    .progress-bar { height: 8px; border-radius: 999px; background: var(--surface-3); overflow: hidden; }
    .progress-fill { height: 100%; border-radius: 999px; transition: width 0.5s ease; }
    .tab { padding: 8px 16px; font-size: 13px; font-weight: 600; cursor: pointer; border: none; background: transparent; color: var(--muted); border-bottom: 2px solid transparent; }
    .tab.active { color: var(--text); border-bottom-color: var(--blue); }
    @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
    .loading { animation: pulse 1.5s ease-in-out infinite; }
  </style>
</head>
<body>
  <!-- Header -->
  <header style="background: var(--surface-1); border-bottom: 1px solid var(--border); padding: 12px 24px; display: flex; justify-content: space-between; align-items: center; position: sticky; top: 0; z-index: 50;">
    <div style="display: flex; align-items: center; gap: 12px;">
      <div style="width: 32px; height: 32px; background: linear-gradient(135deg, var(--orange), var(--red)); border-radius: 8px; display: flex; align-items: center; justify-content: center; font-weight: 800; font-size: 14px;">R</div>
      <div>
        <div style="font-weight: 700; font-size: 15px;">{{ brand }}</div>
        <div style="font-size: 11px; color: var(--muted);">{{ domain }} &middot; SEO Dashboard</div>
      </div>
    </div>
    <div style="display: flex; gap: 8px; align-items: center;">
      <span id="lastSync" style="font-size: 11px; color: var(--muted);"></span>
      <button class="btn btn-outline" onclick="loadDashboard()">Refresh</button>
      <button class="btn btn-primary" onclick="smartSync()">Smart Sync</button>
    </div>
  </header>

  <main style="max-width: 1400px; margin: 0 auto; padding: 24px;">

    <!-- Stat Cards Row -->
    <div id="statsGrid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin-bottom: 24px;">
      <div class="stat-card loading"><div class="stat-value" style="color: var(--green);">—</div><div class="stat-label">Indexed</div></div>
      <div class="stat-card loading"><div class="stat-value" style="color: var(--red);">—</div><div class="stat-label">Not Indexed</div></div>
      <div class="stat-card loading"><div class="stat-value" style="color: var(--blue);">—</div><div class="stat-label">Total Tracked</div></div>
      <div class="stat-card loading"><div class="stat-value" style="color: var(--orange);">—</div><div class="stat-label">Submitted Today</div></div>
      <div class="stat-card loading"><div class="stat-value" style="color: var(--purple);">—</div><div class="stat-label">Product Snippets</div></div>
      <div class="stat-card loading"><div class="stat-value" style="color: var(--cyan);">—</div><div class="stat-label">Merchant Listings</div></div>
      <div class="stat-card loading"><div class="stat-value" style="color: var(--yellow);">—</div><div class="stat-label">Review Snippets</div></div>
      <div class="stat-card loading"><div class="stat-value" style="color: var(--muted);">—</div><div class="stat-label">No Rich Results</div></div>
    </div>

    <!-- Index Progress Bar -->
    <div class="card" style="margin-bottom: 24px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
        <span style="font-weight: 600; font-size: 14px;">Indexing Progress</span>
        <span id="indexPct" style="font-size: 13px; color: var(--muted);">—</span>
      </div>
      <div class="progress-bar">
        <div id="indexBar" class="progress-fill" style="width: 0%; background: linear-gradient(90deg, var(--green), var(--cyan));"></div>
      </div>
    </div>

    <!-- Two Column: Coverage Breakdown + Accounts -->
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px;">

      <!-- Coverage Breakdown -->
      <div class="card">
        <h3 style="font-weight: 700; font-size: 15px; margin-bottom: 12px;">Coverage Breakdown</h3>
        <div id="coverageList" style="display: flex; flex-direction: column; gap: 6px;">
          <div class="loading" style="height: 24px; background: var(--surface-2); border-radius: 6px;"></div>
        </div>
      </div>

      <!-- Service Accounts -->
      <div class="card">
        <h3 style="font-weight: 700; font-size: 15px; margin-bottom: 12px;">Service Accounts</h3>
        <div id="accountsList" style="display: flex; flex-direction: column; gap: 8px;">
          <div class="loading" style="height: 24px; background: var(--surface-2); border-radius: 6px;"></div>
        </div>
      </div>
    </div>

    <!-- Charts Row -->
    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px;">
      <div class="card">
        <h3 style="font-weight: 700; font-size: 15px; margin-bottom: 12px;">Index Status Distribution</h3>
        <canvas id="coverageChart" height="200"></canvas>
      </div>
      <div class="card">
        <h3 style="font-weight: 700; font-size: 15px; margin-bottom: 12px;">Daily Index History</h3>
        <canvas id="historyChart" height="200"></canvas>
      </div>
    </div>

    <!-- Rich Results Chart -->
    <div class="card" style="margin-bottom: 24px;">
      <h3 style="font-weight: 700; font-size: 15px; margin-bottom: 12px;">Rich Results / Snippets</h3>
      <canvas id="richChart" height="120"></canvas>
    </div>

    <!-- URL Browser -->
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <h3 style="font-weight: 700; font-size: 15px;">URL Browser</h3>
        <div style="display: flex; gap: 8px; align-items: center;">
          <input id="urlSearch" class="search-input" style="width: 250px;" placeholder="Search URLs..." oninput="debounceSearch()">
          <button class="btn btn-outline" onclick="autoInspect()">Auto-Inspect 50</button>
        </div>
      </div>

      <!-- Status Filter Pills -->
      <div id="filterPills" style="display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px;">
        <button class="filter-pill active" data-filter="" onclick="setFilter(this, '')">All</button>
        <button class="filter-pill" data-filter="indexed" onclick="setFilter(this, 'indexed')">Indexed</button>
        <button class="filter-pill" data-filter="crawled" onclick="setFilter(this, 'crawled')">Crawled Not Indexed</button>
        <button class="filter-pill" data-filter="unknown" onclick="setFilter(this, 'unknown')">Unknown</button>
        <button class="filter-pill" data-filter="discovered" onclick="setFilter(this, 'discovered')">Discovered</button>
        <button class="filter-pill" data-filter="blocked" onclick="setFilter(this, 'blocked')">Blocked</button>
      </div>

      <!-- Rich Result Filter -->
      <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 12px;">
        <span style="font-size: 12px; color: var(--muted); padding: 6px 0;">Rich:</span>
        <button class="filter-pill" data-rich="" onclick="setRichFilter(this, '')">All</button>
        <button class="filter-pill" data-rich="product" onclick="setRichFilter(this, 'product')">Product</button>
        <button class="filter-pill" data-rich="merchant" onclick="setRichFilter(this, 'merchant')">Merchant</button>
        <button class="filter-pill" data-rich="review" onclick="setRichFilter(this, 'review')">Review</button>
        <button class="filter-pill" data-rich="none" onclick="setRichFilter(this, 'none')">None</button>
      </div>

      <table>
        <thead>
          <tr>
            <th style="width: 50%;">URL</th>
            <th>Status</th>
            <th>Rich Results</th>
            <th>Last Crawl</th>
            <th>Checked</th>
          </tr>
        </thead>
        <tbody id="urlTableBody">
          <tr><td colspan="5" style="text-align: center; color: var(--muted); padding: 40px;">Loading...</td></tr>
        </tbody>
      </table>

      <!-- Pagination -->
      <div id="pagination" style="display: flex; justify-content: space-between; align-items: center; margin-top: 12px; padding-top: 12px; border-top: 1px solid var(--border);">
        <span id="pageInfo" style="font-size: 12px; color: var(--muted);"></span>
        <div style="display: flex; gap: 6px;">
          <button class="btn btn-outline" id="prevBtn" onclick="changePage(-1)">Prev</button>
          <button class="btn btn-outline" id="nextBtn" onclick="changePage(1)">Next</button>
        </div>
      </div>
    </div>

    <!-- GSC Reports Sync -->
    <div class="card" style="margin-top: 24px;">
      <h3 style="font-weight: 700; font-size: 15px; margin-bottom: 12px;">GSC Reports (Manual Sync)</h3>
      <p style="font-size: 12px; color: var(--muted); margin-bottom: 12px;">Enter numbers from Google Search Console UI → Pages → Indexing</p>
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px;">
        <div>
          <label style="font-size: 12px; color: var(--muted); display: block; margin-bottom: 4px;">Pages Indexed</label>
          <input id="rptIndexed" class="search-input" type="number" placeholder="0">
        </div>
        <div>
          <label style="font-size: 12px; color: var(--muted); display: block; margin-bottom: 4px;">Pages Not Indexed</label>
          <input id="rptNotIndexed" class="search-input" type="number" placeholder="0">
        </div>
        <div>
          <label style="font-size: 12px; color: var(--muted); display: block; margin-bottom: 4px;">Product Snippets Valid</label>
          <input id="rptProductSnippets" class="search-input" type="number" placeholder="0">
        </div>
        <div>
          <label style="font-size: 12px; color: var(--muted); display: block; margin-bottom: 4px;">Merchant Listings Valid</label>
          <input id="rptMerchantListings" class="search-input" type="number" placeholder="0">
        </div>
        <div>
          <label style="font-size: 12px; color: var(--muted); display: block; margin-bottom: 4px;">Review Snippets Valid</label>
          <input id="rptReviewSnippets" class="search-input" type="number" placeholder="0">
        </div>
        <div style="display: flex; align-items: end;">
          <button class="btn btn-primary" onclick="saveGscReports()">Save Reports</button>
        </div>
      </div>
    </div>

  </main>

  <script>
    let currentPage = 1;
    let currentFilter = '';
    let currentRichFilter = '';
    let searchTimeout = null;
    let coverageChartInstance = null;
    let historyChartInstance = null;
    let richChartInstance = null;

    function fmt(n) { return (n || 0).toLocaleString(); }

    async function loadDashboard() {
      try {
        const resp = await fetch('/api/dashboard-data');
        const data = await resp.json();
        renderStats(data.stats);
        renderCoverage(data.coverage_breakdown, data.stats.total_tracked);
        renderAccounts(data.accounts);
        renderCoverageChart(data.coverage_breakdown);
        renderHistoryChart(data.daily_history);
        renderRichChart(data.rich_breakdown);
        fillGscReports(data.gsc_reports);
        document.getElementById('lastSync').textContent = 'Last refresh: ' + new Date().toLocaleTimeString();
      } catch (e) {
        console.error('Dashboard load error:', e);
      }
      loadUrls();
    }

    function renderStats(s) {
      const pct = s.total_tracked ? ((s.indexed / s.total_tracked) * 100).toFixed(1) : '0';
      const cards = [
        { value: fmt(s.indexed), label: 'Indexed', color: 'var(--green)', delta: pct + '%' },
        { value: fmt(s.not_indexed), label: 'Not Indexed', color: 'var(--red)' },
        { value: fmt(s.total_tracked), label: 'Total Tracked', color: 'var(--blue)' },
        { value: fmt(s.submitted_today), label: 'Submitted Today', color: 'var(--orange)' },
        { value: fmt(s.product_snippets), label: 'Product Snippets', color: 'var(--purple)' },
        { value: fmt(s.merchant_listings), label: 'Merchant Listings', color: 'var(--cyan)' },
        { value: fmt(s.review_snippets), label: 'Review Snippets', color: 'var(--yellow)' },
        { value: fmt(s.no_rich_results), label: 'No Rich Results', color: 'var(--muted)' },
      ];

      document.getElementById('statsGrid').innerHTML = cards.map(c => `
        <div class="stat-card">
          <div class="stat-value" style="color: ${c.color};">${c.value}</div>
          <div class="stat-label">${c.label}</div>
          ${c.delta ? `<div class="stat-delta" style="color: var(--green);">${c.delta}</div>` : ''}
        </div>
      `).join('');

      // Index progress bar
      document.getElementById('indexBar').style.width = pct + '%';
      document.getElementById('indexPct').textContent = `${fmt(s.indexed)} / ${fmt(s.total_tracked)} (${pct}%)`;
    }

    function renderCoverage(breakdown, total) {
      const colors = {
        'Submitted and indexed': 'var(--green)',
        'Crawled - currently not indexed': 'var(--yellow)',
        'URL is unknown to Google': 'var(--red)',
        'Discovered - currently not indexed': 'var(--orange)',
        'Blocked by robots.txt': 'var(--muted)',
        'Blocked due to other 4xx issue': 'var(--pink)',
      };
      const sorted = Object.entries(breakdown).sort((a, b) => b[1] - a[1]);
      document.getElementById('coverageList').innerHTML = sorted.map(([status, count]) => {
        const pct = total ? ((count / total) * 100).toFixed(1) : '0';
        const color = colors[status] || 'var(--muted)';
        return `
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 6px 0;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <div style="width: 8px; height: 8px; border-radius: 50%; background: ${color};"></div>
              <span style="font-size: 13px;">${status}</span>
            </div>
            <div style="display: flex; gap: 8px; align-items: center;">
              <span style="font-size: 13px; font-weight: 600;">${fmt(count)}</span>
              <span style="font-size: 11px; color: var(--muted);">${pct}%</span>
            </div>
          </div>`;
      }).join('');
    }

    function renderAccounts(accounts) {
      if (!accounts.length) {
        document.getElementById('accountsList').innerHTML = '<div style="font-size: 13px; color: var(--muted);">No accounts configured. Run: python indexing_pipeline.py accounts</div>';
        return;
      }
      document.getElementById('accountsList').innerHTML = accounts.map(a => {
        const inspectPct = a.inspect_limit ? ((a.inspect_used / a.inspect_limit) * 100).toFixed(0) : 0;
        const indexPct = a.index_limit ? ((a.index_used / a.index_limit) * 100).toFixed(0) : 0;
        return `
          <div style="background: var(--surface-2); border-radius: 8px; padding: 12px;">
            <div style="font-size: 13px; font-weight: 600; margin-bottom: 6px;">${a.name}</div>
            <div style="display: flex; gap: 16px;">
              <div style="flex: 1;">
                <div style="font-size: 11px; color: var(--muted); margin-bottom: 4px;">Inspect ${a.inspect_used}/${a.inspect_limit}</div>
                <div class="progress-bar"><div class="progress-fill" style="width: ${inspectPct}%; background: var(--blue);"></div></div>
              </div>
              <div style="flex: 1;">
                <div style="font-size: 11px; color: var(--muted); margin-bottom: 4px;">Index ${a.index_used}/${a.index_limit}</div>
                <div class="progress-bar"><div class="progress-fill" style="width: ${indexPct}%; background: var(--orange);"></div></div>
              </div>
            </div>
          </div>`;
      }).join('');
    }

    function renderCoverageChart(breakdown) {
      const ctx = document.getElementById('coverageChart').getContext('2d');
      if (coverageChartInstance) coverageChartInstance.destroy();
      const labels = Object.keys(breakdown);
      const values = Object.values(breakdown);
      const colors = ['#22c55e','#eab308','#ef4444','#f97316','#6b7a94','#ec4899','#a855f7','#06b6d4'];
      coverageChartInstance = new Chart(ctx, {
        type: 'doughnut',
        data: { labels, datasets: [{ data: values, backgroundColor: colors.slice(0, labels.length), borderWidth: 0 }] },
        options: { responsive: true, plugins: { legend: { position: 'right', labels: { color: '#6b7a94', font: { size: 11 } } } } }
      });
    }

    function renderHistoryChart(history) {
      const ctx = document.getElementById('historyChart').getContext('2d');
      if (historyChartInstance) historyChartInstance.destroy();
      if (!history.length) return;
      const labels = history.map(h => h.date);
      const indexed = history.map(h => h.indexed || 0);
      const notIndexed = history.map(h => h.not_indexed || 0);
      historyChartInstance = new Chart(ctx, {
        type: 'line',
        data: {
          labels,
          datasets: [
            { label: 'Indexed', data: indexed, borderColor: '#22c55e', backgroundColor: 'rgba(34,197,94,0.1)', fill: true, tension: 0.3 },
            { label: 'Not Indexed', data: notIndexed, borderColor: '#ef4444', backgroundColor: 'rgba(239,68,68,0.1)', fill: true, tension: 0.3 },
          ]
        },
        options: { responsive: true, scales: { x: { ticks: { color: '#6b7a94', font: { size: 10 } }, grid: { color: '#1a1f2b' } }, y: { ticks: { color: '#6b7a94' }, grid: { color: '#1a1f2b' } } }, plugins: { legend: { labels: { color: '#6b7a94' } } } }
      });
    }

    function renderRichChart(rich) {
      const ctx = document.getElementById('richChart').getContext('2d');
      if (richChartInstance) richChartInstance.destroy();
      const labels = Object.keys(rich);
      const values = Object.values(rich);
      const colors = ['#a855f7', '#06b6d4', '#eab308', '#6b7a94'];
      richChartInstance = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets: [{ data: values, backgroundColor: colors, borderRadius: 6, barThickness: 40 }] },
        options: { responsive: true, indexAxis: 'y', scales: { x: { ticks: { color: '#6b7a94' }, grid: { color: '#1a1f2b' } }, y: { ticks: { color: '#e2e8f3', font: { size: 12 } }, grid: { display: false } } }, plugins: { legend: { display: false } } }
      });
    }

    function fillGscReports(r) {
      if (!r) return;
      if (r.pages_indexed) document.getElementById('rptIndexed').value = r.pages_indexed;
      if (r.pages_not_indexed) document.getElementById('rptNotIndexed').value = r.pages_not_indexed;
      if (r.product_snippets_valid) document.getElementById('rptProductSnippets').value = r.product_snippets_valid;
      if (r.merchant_listings_valid) document.getElementById('rptMerchantListings').value = r.merchant_listings_valid;
      if (r.review_snippets_valid) document.getElementById('rptReviewSnippets').value = r.review_snippets_valid;
    }

    async function loadUrls() {
      const search = document.getElementById('urlSearch').value;
      const params = new URLSearchParams({ page: currentPage, per_page: 50, status: currentFilter, search, rich: currentRichFilter });
      try {
        const resp = await fetch('/api/tracked-urls?' + params);
        const data = await resp.json();
        renderUrlTable(data);
      } catch (e) { console.error('URL load error:', e); }
    }

    function renderUrlTable(data) {
      const tbody = document.getElementById('urlTableBody');
      if (!data.urls.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--muted); padding: 40px;">No URLs found</td></tr>';
        document.getElementById('pageInfo').textContent = '0 results';
        return;
      }

      const statusBadge = (cov) => {
        if (!cov) return '<span class="badge badge-blue">Unknown</span>';
        if (cov.includes('indexed') && !cov.includes('not')) return '<span class="badge badge-green">Indexed</span>';
        if (cov.includes('Crawled')) return '<span class="badge badge-yellow">Crawled</span>';
        if (cov.includes('unknown')) return '<span class="badge badge-red">Unknown</span>';
        if (cov.includes('Discovered')) return '<span class="badge badge-orange">Discovered</span>';
        if (cov.includes('Blocked')) return '<span class="badge badge-purple">Blocked</span>';
        if (cov.startsWith('ERROR')) return '<span class="badge badge-red">Error</span>';
        return `<span class="badge badge-blue">${cov.substring(0, 20)}</span>`;
      };

      const richBadges = (rich) => {
        if (!rich || !rich.length) return '<span style="color: var(--muted); font-size: 11px;">—</span>';
        return rich.map(r => {
          if (r.includes('Review')) return '<span class="badge badge-yellow">Review</span>';
          if (r.includes('Merchant')) return '<span class="badge badge-cyan">Merchant</span>';
          if (r.includes('Product')) return '<span class="badge badge-purple">Product</span>';
          return `<span class="badge badge-blue">${r}</span>`;
        }).join(' ');
      };

      tbody.innerHTML = data.urls.map(u => {
        const shortUrl = u.url.replace('https://rudraretails.com/products/', '/products/');
        return `<tr>
          <td><a href="${u.url}" target="_blank" style="color: var(--blue); text-decoration: none; font-size: 12px;">${shortUrl}</a></td>
          <td>${statusBadge(u.coverage)}</td>
          <td>${richBadges(u.rich_results)}</td>
          <td style="font-size: 12px; color: var(--muted);">${u.last_crawl || '—'}</td>
          <td style="font-size: 12px; color: var(--muted);">${u.checked_at || '—'}</td>
        </tr>`;
      }).join('');

      const start = (data.page - 1) * data.per_page + 1;
      const end = Math.min(data.page * data.per_page, data.total);
      document.getElementById('pageInfo').textContent = `${start}-${end} of ${fmt(data.total)}`;
      document.getElementById('prevBtn').disabled = data.page <= 1;
      document.getElementById('nextBtn').disabled = data.page >= data.pages;
    }

    function setFilter(el, filter) {
      currentFilter = filter;
      currentPage = 1;
      document.querySelectorAll('[data-filter]').forEach(p => p.classList.remove('active'));
      el.classList.add('active');
      loadUrls();
    }

    function setRichFilter(el, filter) {
      currentRichFilter = filter;
      currentPage = 1;
      document.querySelectorAll('[data-rich]').forEach(p => p.classList.remove('active'));
      el.classList.add('active');
      loadUrls();
    }

    function changePage(delta) {
      currentPage += delta;
      if (currentPage < 1) currentPage = 1;
      loadUrls();
    }

    function debounceSearch() {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => { currentPage = 1; loadUrls(); }, 300);
    }

    async function smartSync() {
      const btn = event.target;
      btn.textContent = 'Syncing...';
      btn.disabled = true;
      try {
        const resp = await fetch('/api/smart-sync', { method: 'POST' });
        const data = await resp.json();
        if (data.ok) {
          alert(`Smart Sync complete!\n\nURLs from Search Analytics: ${fmt(data.urls_from_analytics)}\nNewly synced as indexed: ${fmt(data.newly_synced)}\nTotal tracked: ${fmt(data.total_tracked)}`);
          loadDashboard();
        } else {
          alert('Error: ' + (data.error || 'Unknown'));
        }
      } catch (e) { alert('Error: ' + e.message); }
      btn.textContent = 'Smart Sync';
      btn.disabled = false;
    }

    async function autoInspect() {
      const btn = event.target;
      btn.textContent = 'Inspecting...';
      btn.disabled = true;
      try {
        const resp = await fetch('/api/auto-inspect', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' });
        const data = await resp.json();
        if (data.ok) {
          alert(`Inspected ${data.inspected} URLs`);
          loadDashboard();
        } else {
          alert('Error: ' + (data.error || 'Unknown'));
        }
      } catch (e) { alert('Error: ' + e.message); }
      btn.textContent = 'Auto-Inspect 50';
      btn.disabled = false;
    }

    async function saveGscReports() {
      const body = {
        pages_indexed: parseInt(document.getElementById('rptIndexed').value) || 0,
        pages_not_indexed: parseInt(document.getElementById('rptNotIndexed').value) || 0,
        product_snippets_valid: parseInt(document.getElementById('rptProductSnippets').value) || 0,
        merchant_listings_valid: parseInt(document.getElementById('rptMerchantListings').value) || 0,
        review_snippets_valid: parseInt(document.getElementById('rptReviewSnippets').value) || 0,
      };
      try {
        const resp = await fetch('/api/gsc-reports', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        const data = await resp.json();
        if (data.ok) alert('GSC Reports saved!');
      } catch (e) { alert('Error: ' + e.message); }
    }

    // Load on startup
    loadDashboard();
  </script>
</body>
</html>"""
