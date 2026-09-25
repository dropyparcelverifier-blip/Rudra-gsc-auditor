import { useState, useEffect, useCallback } from 'react';
import { CheckCircle, AlertTriangle, Globe, TrendingUp, Info, Search, Zap, RefreshCw, Send, ExternalLink, ChevronLeft, ChevronRight } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from 'recharts';
import Header from '../components/Header';
import StatCard from '../components/StatCard';
import DataSourceBadge from '../components/DataSourceBadge';
import CoverageBreakdown from '../components/CoverageBreakdown';
import { api } from '../lib/api';
import { computePipelineStats } from '../lib/pipelineStats';

const COV_COLORS = {
  'Submitted and indexed': '#22c55e',
  'Crawled - currently not indexed': '#f59e0b',
  'Discovered - currently not indexed': '#3b82f6',
  'URL is unknown to Google': '#ef4444',
  'Blocked by robots.txt': '#94a3b8',
  'Duplicate without user-selected canonical': '#a855f7',
  'Duplicate, Google chose different canonical': '#ec4899',
};

export default function Indexing({ data, loading, refresh }) {
  const [classData, setClassData] = useState(null);
  const [inspecting, setInspecting] = useState(false);
  const [inspectResult, setInspectResult] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState(null);
  const [selectedCat, setSelectedCat] = useState(null);
  const [catUrls, setCatUrls] = useState([]);
  const [catTotal, setCatTotal] = useState(0);
  const [catPage, setCatPage] = useState(1);
  const [catLoading, setCatLoading] = useState(false);

  const fetchClassifications = useCallback(async () => {
    try { setClassData(await api.getClassifications()); } catch {}
  }, []);

  useEffect(() => { fetchClassifications(); }, [fetchClassifications]);

  const handleAutoInspect = async () => {
    setInspecting(true);
    setInspectResult(null);
    try {
      const d = await api.autoInspect([]);
      setInspectResult(`Inspected ${d.inspected} URLs`);
      fetchClassifications();
      refresh();
    } catch (e) { setInspectResult('Error: ' + e.message); }
    setInspecting(false);
  };

  const handleBatchSubmit = async (category) => {
    setSubmitting(true);
    setSubmitResult(null);
    try {
      const d = await api.batchSubmit({ category, limit: 50 });
      setSubmitResult(`Submitted ${d.submitted} URLs via ${d.account || 'service account'}${d.errors?.length ? ` (${d.errors.length} errors)` : ''}`);
      fetchClassifications();
      refresh();
      if (selectedCat) loadCategoryUrls(selectedCat, 1);
    } catch (e) { setSubmitResult('Error: ' + e.message); }
    setSubmitting(false);
  };

  const loadCategoryUrls = async (category, page = 1) => {
    setCatLoading(true);
    setSelectedCat(category);
    setCatPage(page);
    try {
      const params = { page, per_page: 30 };
      if (category === 'submit') params.action = 'submit';
      else if (category === 'indexed') params.action = 'indexed';
      else if (category === 'not_indexed') params.action = 'not_indexed';
      else params.category = category;
      const d = await api.getUrlsByCategory(params);
      setCatUrls(d.urls || []);
      setCatTotal(d.total || 0);
    } catch (e) { console.error(e); }
    setCatLoading(false);
  };

  if (!data) return <div className="flex h-96 items-center justify-center text-slate-400">Loading...</div>;

  const sm = data.sitemaps || {};
  const pipeline = data.pipeline || {};
  const { pipelineTotal, pipelineIndexed, pipelineNotIndexed, pipelineRate, totalSubmitted, scanPct } = computePipelineStats(data);

  const coverageData = Object.entries(pipeline.coverage_breakdown || {})
    .map(([name, value]) => ({ name, value }))
    .sort((a, b) => b.value - a.value);

  const actionCounts = classData?.action_counts || {};
  const catTotalPages = Math.ceil(catTotal / 30);

  const statusColor = (s) => {
    if (!s) return 'bg-slate-100 text-slate-600';
    const l = s.toLowerCase();
    if (l.includes('indexed') && !l.includes('not')) return 'bg-emerald-100 text-emerald-700';
    if (l.includes('not indexed')) return 'bg-amber-100 text-amber-700';
    if (l.includes('unknown')) return 'bg-red-100 text-red-700';
    if (l.includes('robots')) return 'bg-purple-100 text-purple-700';
    if (l.includes('discovered')) return 'bg-blue-100 text-blue-700';
    if (l.includes('duplicate')) return 'bg-pink-100 text-pink-700';
    return 'bg-slate-100 text-slate-600';
  };

  return (
    <div>
      <Header title="Page Indexing" onRefresh={() => { refresh(true); fetchClassifications(); }} loading={loading} />
      <div className="space-y-6 p-6">

        {/* Scan progress banner */}
        <div className="rounded-xl border border-blue-200 bg-blue-50 p-4">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Search size={16} className="text-blue-600" />
              <span className="text-sm font-semibold text-blue-800">URL Inspection Scan</span>
              <DataSourceBadge source="pipeline_db" />
            </div>
            <div className="flex items-center gap-2">
              {inspectResult && <span className="text-xs font-semibold text-emerald-600">{inspectResult}</span>}
              <button onClick={handleAutoInspect} disabled={inspecting}
                className="flex items-center gap-1 rounded bg-blue-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-blue-700 disabled:opacity-50">
                {inspecting ? <RefreshCw size={12} className="animate-spin" /> : <Zap size={12} />}
                Inspect Next 50
              </button>
            </div>
          </div>
          <div className="h-3 w-full overflow-hidden rounded-full bg-blue-100">
            <div className="h-full rounded-full bg-blue-500 transition-all duration-500" style={{ width: `${Math.min(scanPct, 100)}%` }} />
          </div>
          <div className="mt-1 flex justify-between text-[10px] text-blue-600">
            <span>{pipelineTotal.toLocaleString()} of {totalSubmitted.toLocaleString()} inspected ({scanPct}%)</span>
            <span>20,000/day capacity (10 accounts)</span>
          </div>
        </div>

        {/* Primary stats */}
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard label="Indexed" value={pipelineIndexed} color="green" icon={CheckCircle}
            subtitle="URL Inspection API" delta={pipelineTotal ? `${pipelineRate}% of inspected` : ''} />
          <StatCard label="Not Indexed" value={pipelineNotIndexed} color="red" icon={AlertTriangle}
            subtitle={`${pipelineTotal ? (100 - pipelineRate).toFixed(1) : 0}% gap`} />
          <StatCard label="Total Inspected" value={pipelineTotal} color="blue" icon={Globe}
            subtitle={`of ${totalSubmitted.toLocaleString()} in sitemaps`} />
          <StatCard label="Index Rate" value={`${pipelineRate}%`} color="green" icon={TrendingUp}
            delta={`${pipelineIndexed.toLocaleString()} of ${pipelineTotal.toLocaleString()}`} />
        </div>

        {/* Smart Classification cards — clickable to show URLs */}
        {classData && (
          <div>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
              Actions — Click to View URLs
            </h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                { key: 'submit', label: 'Submit for Indexing', count: actionCounts.submit || 0, active: 'border-purple-500 ring-2 ring-purple-200', title: 'text-purple-600', value: 'text-purple-700', canSubmit: true },
                { key: 'not_indexed', label: 'Not Indexed', count: pipelineNotIndexed, active: 'border-red-500 ring-2 ring-red-200', title: 'text-red-600', value: 'text-red-700' },
                { key: 'indexed', label: 'Indexed', count: pipelineIndexed, active: 'border-emerald-500 ring-2 ring-emerald-200', title: 'text-emerald-600', value: 'text-emerald-700' },
                { key: 'snippet', label: 'Has Rich Results', count: actionCounts.snippet || 0, active: 'border-amber-500 ring-2 ring-amber-200', title: 'text-amber-600', value: 'text-amber-700' },
              ].map(item => (
                <button key={item.key} onClick={() => loadCategoryUrls(item.key)}
                  className={`rounded-xl border p-4 text-left transition hover:shadow-md ${selectedCat === item.key ? item.active : 'border-slate-200'}`}>
                  <p className={`text-[10px] font-semibold uppercase ${item.title}`}>{item.label}</p>
                  <p className={`mt-1 text-2xl font-extrabold ${item.value}`}>{item.count.toLocaleString()}</p>
                  <p className="mt-1 text-[10px] text-slate-500">Click to view URLs →</p>
                </button>
              ))}
            </div>

            {submitResult && (
              <div className="mt-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-semibold text-emerald-700">
                {submitResult}
              </div>
            )}
          </div>
        )}

        {/* URL list for selected category */}
        {selectedCat && (
          <div className="rounded-xl border border-slate-200 bg-white">
            <div className="border-b border-slate-100 px-4 py-3 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <h3 className="text-sm font-semibold text-slate-700">
                  {selectedCat === 'submit' ? 'Eligible for Submission' : selectedCat === 'indexed' ? 'Indexed URLs' : selectedCat === 'not_indexed' ? 'Not Indexed URLs' : 'URLs with Rich Results'}
                </h3>
                <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-slate-600">{catTotal.toLocaleString()}</span>
              </div>
              <div className="flex items-center gap-2">
                {selectedCat === 'submit' && (actionCounts.submit || 0) > 0 && (
                  <button onClick={() => handleBatchSubmit('')} disabled={submitting}
                    className="flex items-center gap-1 rounded bg-purple-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-purple-700 disabled:opacity-50">
                    {submitting ? <RefreshCw size={12} className="animate-spin" /> : <Send size={12} />}
                    Submit Next 50
                  </button>
                )}
                <button onClick={() => { setSelectedCat(null); setCatUrls([]); }}
                  className="text-xs text-slate-400 hover:text-slate-600">Close</button>
              </div>
            </div>
            <div className="max-h-[500px] overflow-y-auto">
              <table className="w-full text-xs">
                <thead className="sticky top-0">
                  <tr className="border-b border-slate-100 bg-slate-50 text-left">
                    <th className="px-3 py-2 font-semibold text-slate-600">URL</th>
                    <th className="px-3 py-2 font-semibold text-slate-600">Status</th>
                    <th className="px-3 py-2 font-semibold text-slate-600">Rich Results</th>
                    <th className="px-3 py-2 font-semibold text-slate-600">Checked</th>
                  </tr>
                </thead>
                <tbody>
                  {catLoading && <tr><td colSpan={4} className="px-4 py-6 text-center text-slate-400">Loading...</td></tr>}
                  {!catLoading && catUrls.length === 0 && <tr><td colSpan={4} className="px-4 py-6 text-center text-slate-400">No URLs found</td></tr>}
                  {catUrls.map((u, i) => (
                    <tr key={i} className="border-b border-slate-50 hover:bg-slate-50">
                      <td className="max-w-xs truncate px-3 py-1.5">
                        <a href={u.url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-blue-600 hover:underline">
                          <span className="truncate">{u.url?.replace('https://www.rudraretails.com/', '/').replace('https://rudraretails.com/', '/')}</span>
                          <ExternalLink size={10} className="flex-shrink-0" />
                        </a>
                      </td>
                      <td className="px-3 py-1.5">
                        <span className={`inline-block rounded-full px-2 py-0.5 text-[10px] font-semibold ${statusColor(u.coverage)}`}>
                          {u.coverage || 'Unknown'}
                        </span>
                      </td>
                      <td className="px-3 py-1.5">
                        <div className="flex flex-wrap gap-1">
                          {(u.rich_results || []).map((r, j) => (
                            <span key={j} className="rounded bg-purple-100 px-1 py-0.5 text-[9px] font-semibold text-purple-700">{r}</span>
                          ))}
                        </div>
                      </td>
                      <td className="px-3 py-1.5 text-slate-500">{u.checked_at || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {catTotalPages > 1 && (
              <div className="flex items-center justify-between border-t border-slate-100 px-4 py-2">
                <button onClick={() => loadCategoryUrls(selectedCat, Math.max(1, catPage - 1))} disabled={catPage === 1}
                  className="flex items-center gap-1 text-xs text-slate-600 disabled:opacity-40"><ChevronLeft size={14} /> Prev</button>
                <span className="text-xs text-slate-500">Page {catPage} of {catTotalPages}</span>
                <button onClick={() => loadCategoryUrls(selectedCat, Math.min(catTotalPages, catPage + 1))} disabled={catPage === catTotalPages}
                  className="flex items-center gap-1 text-xs text-slate-600 disabled:opacity-40">Next <ChevronRight size={14} /></button>
              </div>
            )}
          </div>
        )}

        {/* Coverage Breakdown */}
        <CoverageBreakdown
          breakdown={pipeline.coverage_breakdown}
          totalTracked={pipelineTotal}
          title={`Not Indexed Reasons — ${pipelineTotal.toLocaleString()} inspected`}
        />

        {/* Coverage breakdown — clickable bars */}
        {coverageData.length > 0 && (
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-700">
              Coverage Distribution ({pipelineTotal.toLocaleString()} URLs)
            </h3>
            <div className="space-y-2">
              {coverageData.map((entry) => {
                const pct = pipelineTotal ? (entry.value / pipelineTotal * 100).toFixed(1) : 0;
                const isSubmittable = ['crawled', 'unknown', 'discovered'].some(k => entry.name.toLowerCase().includes(k));
                return (
                  <button key={entry.name} onClick={() => loadCategoryUrls(entry.name)}
                    className={`w-full text-left rounded-lg border p-3 transition hover:shadow-sm ${selectedCat === entry.name ? 'border-blue-400 bg-blue-50' : 'border-slate-100 hover:border-slate-200'}`}>
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <div className="h-2.5 w-2.5 rounded-full" style={{ background: COV_COLORS[entry.name] || '#6366f1' }} />
                        <span className="text-xs font-semibold text-slate-700">{entry.name}</span>
                        {isSubmittable && <span className="rounded bg-purple-100 px-1 py-0.5 text-[9px] font-semibold text-purple-700">Can Submit</span>}
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-bold text-slate-800">{entry.value.toLocaleString()}</span>
                        <span className="text-[10px] text-slate-400">{pct}%</span>
                        {isSubmittable && (
                          <span role="button" tabIndex={0} onClick={(e) => { e.stopPropagation(); handleBatchSubmit(entry.name.split(' ')[0]); }}
                            className="flex items-center gap-0.5 rounded bg-purple-600 px-2 py-0.5 text-[9px] font-semibold text-white hover:bg-purple-700 cursor-pointer">
                            <Send size={8} /> Submit
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                      <div className="h-full rounded-full transition-all" style={{ background: COV_COLORS[entry.name] || '#6366f1', width: `${pct}%` }} />
                    </div>
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Sitemaps — LIVE */}
        {sm.details && sm.details.length > 0 && (
          <div className="rounded-xl border border-slate-200 bg-white">
            <div className="border-b border-slate-100 px-4 py-3 flex items-center gap-2">
              <h3 className="text-sm font-semibold text-slate-700">Sitemaps</h3>
              <DataSourceBadge source="live" />
            </div>
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50 text-left">
                  <th className="px-4 py-2.5 font-semibold text-slate-600">Sitemap</th>
                  <th className="px-4 py-2.5 text-right font-semibold text-slate-600">Submitted</th>
                  <th className="px-4 py-2.5 text-right font-semibold text-slate-600">Indexed</th>
                  <th className="px-4 py-2.5 text-right font-semibold text-slate-600">Gap</th>
                </tr>
              </thead>
              <tbody>
                {sm.details.map((s, i) => (
                  <tr key={i} className="border-b border-slate-50 hover:bg-slate-50">
                    <td className="px-4 py-2.5 text-blue-600 truncate max-w-xs">{s.path.replace(/^https?:\/\/[^/]+/, '')}</td>
                    <td className="px-4 py-2.5 text-right">{s.submitted.toLocaleString()}</td>
                    <td className="px-4 py-2.5 text-right font-semibold text-emerald-700">{s.indexed.toLocaleString()}</td>
                    <td className="px-4 py-2.5 text-right font-semibold text-red-600">{(s.submitted - s.indexed).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* How it works */}
        <div className="flex gap-2 rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs text-slate-600">
          <Info size={16} className="mt-0.5 shrink-0 text-slate-400" />
          <div>
            <p className="font-semibold text-slate-700 mb-1">Fully Automatic Pipeline</p>
            <p>
              Run <code className="rounded bg-slate-200 px-1">python indexing_pipeline.py daily</code> to automatically
              inspect URLs, classify them, and submit eligible ones for indexing. Capacity: 20,000 inspections/day + 2,000 submissions/day
              across 10 service accounts. Full scan: ~{Math.ceil(totalSubmitted / 20000)} days.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
