import { useState, useEffect, useCallback } from 'react';
import { Search, ChevronLeft, ChevronRight, ArrowUpDown, ExternalLink, Zap, RefreshCw } from 'lucide-react';
import Header from '../components/Header';
import { api } from '../lib/api';

const STATUS_OPTIONS = ['all', 'Submitted and indexed', 'Crawled - currently not indexed', 'URL is unknown to Google', 'Discovered - currently not indexed', 'Blocked by robots.txt'];
const PAGE_SIZE = 50;

export default function UrlBrowser() {
  const [urls, setUrls] = useState([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('all');
  const [richFilter, setRichFilter] = useState('');
  const [sortBy, setSortBy] = useState('checked_at');
  const [sortDir, setSortDir] = useState('desc');
  const [loading, setLoading] = useState(false);
  const [inspecting, setInspecting] = useState(false);
  const [inspectResult, setInspectResult] = useState(null);

  const fetchUrls = useCallback(async () => {
    setLoading(true);
    try {
      const params = { page, per_page: PAGE_SIZE, sort: sortBy, dir: sortDir };
      if (search) params.search = search;
      if (status !== 'all') params.status = status;
      if (richFilter) params.rich = richFilter;
      const d = await api.getTrackedUrls(params);
      setUrls(d.urls || []);
      setTotal(d.total || 0);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, [page, search, status, richFilter, sortBy, sortDir]);

  useEffect(() => { fetchUrls(); }, [fetchUrls]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const toggleSort = (col) => {
    if (sortBy === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortBy(col); setSortDir('desc'); }
    setPage(1);
  };

  const handleAutoInspect = async () => {
    setInspecting(true);
    setInspectResult(null);
    try {
      const d = await api.autoInspect([]);
      setInspectResult(`Inspected ${d.inspected} URLs`);
      fetchUrls();
    } catch (e) { setInspectResult('Error: ' + e.message); }
    setInspecting(false);
  };

  const SortHeader = ({ col, children, align = 'left' }) => (
    <th className={`cursor-pointer px-3 py-2.5 font-semibold text-slate-600 select-none hover:text-slate-900 ${align === 'right' ? 'text-right' : 'text-left'}`} onClick={() => toggleSort(col)}>
      <span className={`flex items-center gap-1 ${align === 'right' ? 'justify-end' : ''}`}>{children}<ArrowUpDown size={12} className={sortBy === col ? 'text-orange-500' : 'text-slate-300'} /></span>
    </th>
  );

  const statusColor = (s) => {
    if (!s) return 'bg-slate-100 text-slate-600';
    if (s.includes('indexed') && !s.includes('not')) return 'bg-emerald-100 text-emerald-700';
    if (s.includes('not indexed')) return 'bg-amber-100 text-amber-700';
    if (s.includes('unknown')) return 'bg-red-100 text-red-700';
    if (s.includes('robots')) return 'bg-purple-100 text-purple-700';
    if (s.includes('Discovered')) return 'bg-blue-100 text-blue-700';
    return 'bg-slate-100 text-slate-600';
  };

  return (
    <div>
      <Header title="URL Browser" loading={loading} />
      <div className="space-y-4 p-6">
        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input type="text" placeholder="Search URLs..." value={search}
              onChange={e => { setSearch(e.target.value); setPage(1); }}
              className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm outline-none focus:border-orange-300 focus:ring-2 focus:ring-orange-100" />
          </div>
          <select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-orange-300">
            {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s === 'all' ? 'All Statuses' : s}</option>)}
          </select>
          <select value={richFilter} onChange={e => { setRichFilter(e.target.value); setPage(1); }}
            className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm outline-none focus:border-orange-300">
            <option value="">All Rich Results</option>
            <option value="Product">Product Snippets</option>
            <option value="Merchant">Merchant Listings</option>
            <option value="Review">Review Snippets</option>
            <option value="none">No Rich Results</option>
          </select>
          <button onClick={handleAutoInspect} disabled={inspecting}
            className="flex items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-blue-700 disabled:opacity-50">
            {inspecting ? <RefreshCw size={14} className="animate-spin" /> : <Zap size={14} />}
            Auto-Inspect 50
          </button>
        </div>

        <div className="flex items-center justify-between">
          <p className="text-xs text-slate-500">{total.toLocaleString()} URLs found</p>
          {inspectResult && <p className="text-xs font-semibold text-emerald-600">{inspectResult}</p>}
        </div>

        {/* Table */}
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <SortHeader col="url">URL</SortHeader>
                <SortHeader col="coverage">Status</SortHeader>
                <SortHeader col="checked_at">Checked</SortHeader>
                <th className="px-3 py-2.5 text-left font-semibold text-slate-600">Rich Results</th>
                <SortHeader col="last_crawl">Last Crawl</SortHeader>
              </tr>
            </thead>
            <tbody>
              {urls.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">{loading ? 'Loading...' : 'No URLs found'}</td></tr>
              )}
              {urls.map((u, i) => (
                <tr key={i} className="border-b border-slate-50 hover:bg-slate-50">
                  <td className="max-w-xs truncate px-3 py-2">
                    <a href={u.url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-blue-600 hover:underline">
                      <span className="truncate">{u.url?.replace('https://www.rudraretails.com/', '/').replace('https://rudraretails.com/', '/')}</span>
                      <ExternalLink size={12} className="flex-shrink-0" />
                    </a>
                  </td>
                  <td className="px-3 py-2">
                    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${statusColor(u.coverage)}`}>
                      {u.coverage || 'Unknown'}
                    </span>
                  </td>
                  <td className="px-3 py-2 text-slate-500 text-xs">{u.checked_at || '—'}</td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      {(u.rich_results || []).map((r, j) => (
                        <span key={j} className="rounded bg-purple-100 px-1.5 py-0.5 text-[10px] font-semibold text-purple-700">{r}</span>
                      ))}
                    </div>
                  </td>
                  <td className="px-3 py-2 text-slate-500 text-xs">{u.last_crawl || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              className="flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-40">
              <ChevronLeft size={14} /> Previous
            </button>
            <div className="flex items-center gap-1">
              {[...Array(Math.min(5, totalPages))].map((_, i) => {
                const p = page <= 3 ? i + 1 : page - 2 + i;
                if (p > totalPages || p < 1) return null;
                return (
                  <button key={p} onClick={() => setPage(p)}
                    className={`h-7 w-7 rounded text-xs font-semibold ${p === page ? 'bg-orange-600 text-white' : 'text-slate-600 hover:bg-slate-100'}`}>
                    {p}
                  </button>
                );
              })}
              {totalPages > 5 && <span className="text-xs text-slate-400">... of {totalPages}</span>}
            </div>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
              className="flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-40">
              Next <ChevronRight size={14} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
