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
      if (d.errors?.includes('QUOTA_EXCEEDED')) {
        setInspectResult('⚠ Daily inspection quota exceeded — resets tomorrow');
      } else if (d.inspected > 0) {
        setInspectResult(`Inspected ${d.inspected} URLs`);
        fetchUrls();
      } else {
        setInspectResult('No URLs to inspect');
      }
    } catch (e) {
      const msg = e.message || '';
      if (msg.includes('401') || msg.includes('authenticated')) {
        setInspectResult('⚠ GSC credentials not configured');
      } else {
        setInspectResult('Error: ' + msg);
      }
    }
    setInspecting(false);
  };

  const SortHeader = ({ col, children, align = 'left' }) => (
    <th className={`cursor-pointer px-4 py-3 font-semibold text-slate-600 select-none hover:text-slate-900 transition-colors ${align === 'right' ? 'text-right' : 'text-left'}`} onClick={() => toggleSort(col)}>
      <span className={`flex items-center gap-1 ${align === 'right' ? 'justify-end' : ''}`}>{children}<ArrowUpDown size={12} className={sortBy === col ? 'text-orange-500' : 'text-slate-300'} /></span>
    </th>
  );

  const statusColor = (s) => {
    if (!s) return 'bg-slate-100 text-slate-600';
    const l = s.toLowerCase();
    if (l.includes('indexed') && !l.includes('not')) return 'bg-gradient-to-r from-emerald-100 to-emerald-50 text-emerald-700 border border-emerald-200/50';
    if (l.includes('not indexed')) return 'bg-gradient-to-r from-amber-100 to-amber-50 text-amber-700 border border-amber-200/50';
    if (l.includes('unknown')) return 'bg-gradient-to-r from-red-100 to-red-50 text-red-700 border border-red-200/50';
    if (l.includes('robots')) return 'bg-gradient-to-r from-purple-100 to-purple-50 text-purple-700 border border-purple-200/50';
    if (l.includes('discovered')) return 'bg-gradient-to-r from-blue-100 to-blue-50 text-blue-700 border border-blue-200/50';
    return 'bg-slate-100 text-slate-600';
  };

  return (
    <div>
      <Header title="URL Browser" loading={loading} />
      <div className="space-y-4 px-5 py-5">
        {/* Filters */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input type="text" placeholder="Search URLs..." value={search}
              onChange={e => { setSearch(e.target.value); setPage(1); }}
              className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-10 pr-3 text-sm outline-none transition-all focus:border-orange-300 focus:ring-2 focus:ring-orange-200 hover:border-slate-300" />
          </div>
          <select value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition-all focus:border-orange-300 focus:ring-2 focus:ring-orange-200 hover:border-slate-300">
            {STATUS_OPTIONS.map(s => <option key={s} value={s}>{s === 'all' ? 'All Statuses' : s}</option>)}
          </select>
          <select value={richFilter} onChange={e => { setRichFilter(e.target.value); setPage(1); }}
            className="rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm outline-none transition-all focus:border-orange-300 focus:ring-2 focus:ring-orange-200 hover:border-slate-300">
            <option value="">All Rich Results</option>
            <option value="Product">Product Snippets</option>
            <option value="Merchant">Merchant Listings</option>
            <option value="Review">Review Snippets</option>
            <option value="none">No Rich Results</option>
          </select>
          <button onClick={handleAutoInspect} disabled={inspecting}
            className="flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-2.5 text-xs font-semibold text-white shadow-md transition-all hover:shadow-lg hover:shadow-blue-200/50 hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-50 disabled:hover:translate-y-0 disabled:hover:shadow-md">
            {inspecting ? <RefreshCw size={14} className="animate-spin" /> : <Zap size={14} />}
            Auto-Inspect 50
          </button>
        </div>

        <div className="flex items-center justify-between">
          <p className="text-xs text-slate-500">{total.toLocaleString()} URLs found</p>
          {inspectResult && <p className="text-xs font-semibold text-emerald-600">{inspectResult}</p>}
        </div>

        {/* Table */}
        <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200 bg-gradient-to-r from-slate-50 to-white">
                <SortHeader col="url">URL</SortHeader>
                <SortHeader col="coverage">Status</SortHeader>
                <SortHeader col="checked_at">Checked</SortHeader>
                <th className="px-4 py-3 text-left font-semibold text-slate-600">Rich Results</th>
                <SortHeader col="last_crawl">Last Crawl</SortHeader>
              </tr>
            </thead>
            <tbody>
              {urls.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">{loading ? 'Loading...' : 'No URLs found'}</td></tr>
              )}
              {urls.map((u, i) => (
                <tr key={i} className={`border-b border-slate-50 hover:bg-orange-50/30 transition-colors ${i % 2 === 0 ? 'bg-white' : 'bg-slate-50/40'}`}>
                  <td className="max-w-xs truncate px-4 py-2.5">
                    <a href={u.url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-blue-600 hover:underline">
                      <span className="truncate">{u.url?.replace('https://www.rudraretails.com/', '/').replace('https://rudraretails.com/', '/')}</span>
                      <ExternalLink size={12} className="flex-shrink-0" />
                    </a>
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`inline-block rounded-lg px-2.5 py-1 text-xs font-semibold ${statusColor(u.coverage)}`}>
                      {u.coverage || 'Unknown'}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-slate-500 text-xs">{u.checked_at || '—'}</td>
                  <td className="px-4 py-2.5">
                    <div className="flex flex-wrap gap-1">
                      {(u.rich_results || []).map((r, j) => (
                        <span key={j} className="rounded-lg bg-gradient-to-r from-purple-100 to-purple-50 border border-purple-200/50 px-2 py-0.5 text-[10px] font-semibold text-purple-700">{r}</span>
                      ))}
                    </div>
                  </td>
                  <td className="px-4 py-2.5 text-slate-500 text-xs">{u.last_crawl || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-between">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1}
              className="flex items-center gap-1 rounded-xl border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-40">
              <ChevronLeft size={14} /> Previous
            </button>
            <div className="flex items-center gap-1.5">
              {[...Array(Math.min(5, totalPages))].map((_, i) => {
                const p = page <= 3 ? i + 1 : page - 2 + i;
                if (p > totalPages || p < 1) return null;
                return (
                  <button key={p} onClick={() => setPage(p)}
                    className={`h-9 w-9 rounded-xl text-xs font-semibold transition-all ${p === page ? 'bg-gradient-to-r from-orange-500 to-orange-600 text-white shadow-md shadow-orange-200/50' : 'text-slate-600 hover:bg-slate-100'}`}>
                    {p}
                  </button>
                );
              })}
              {totalPages > 5 && <span className="text-xs text-slate-400 ml-1">... of {totalPages}</span>}
            </div>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page === totalPages}
              className="flex items-center gap-1 rounded-xl border border-slate-200 px-4 py-2 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-40">
              Next <ChevronRight size={14} />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
