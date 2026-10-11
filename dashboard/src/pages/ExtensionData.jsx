import { useState, useEffect, useRef } from 'react';
import { api } from '../lib/api';
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer,
} from 'recharts';
import {
  RefreshCw, CheckCircle, XCircle, AlertTriangle, Upload, Globe,
  BarChart3, ShoppingCart, Star, Link2, Map, Video, FileText,
  Clock, TrendingUp, AlertOctagon, ChevronDown, ChevronUp,
  MousePointer, Eye, Percent, Hash, ExternalLink, Search,
} from 'lucide-react';

const STATUS_COLORS = {
  indexed: 'text-green-600 bg-green-50',
  requested: 'text-blue-600 bg-blue-50',
  not_indexed: 'text-amber-600 bg-amber-50',
  error: 'text-red-600 bg-red-50',
};

const STATUS_LABELS = {
  indexed: 'Indexed',
  requested: 'Requested',
  not_indexed: 'Not Indexed',
  error: 'Error',
};

const DONUT_COLORS = ['#22c55e', '#ef4444'];
const BULK_PIE_COLORS = { indexed: '#22c55e', requested: '#3b82f6', not_indexed: '#f59e0b', error: '#ef4444' };

const SEVERITY_COLORS = [
  '#ef4444', '#f97316', '#f59e0b', '#eab308', '#84cc16',
  '#22c55e', '#14b8a6', '#06b6d4', '#3b82f6', '#6366f1',
  '#8b5cf6', '#a855f7', '#d946ef', '#ec4899', '#f43f5e',
];

function parseNum(val) {
  return parseInt(String(val || '0').replace(/,/g, ''), 10) || 0;
}

export default function ExtensionData() {
  const [gscData, setGscData] = useState(null);
  const [bulkResults, setBulkResults] = useState(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const intervalRef = useRef(null);

  const fetchData = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [gsc, bulk] = await Promise.allSettled([
        api.getExtensionGscData(),
        api.getBulkResults(),
      ]);
      if (gsc.status === 'fulfilled') setGscData(gsc.value);
      if (bulk.status === 'fulfilled') setBulkResults(bulk.value);
    } catch {}
    if (!silent) setLoading(false);
  };

  useEffect(() => { fetchData(); }, []);

  useEffect(() => {
    if (autoRefresh) {
      intervalRef.current = setInterval(() => fetchData(true), 15000);
    }
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [autoRefresh]);

  const pages = gscData?.pages;
  const perf = gscData?.performance;
  const merchant = gscData?.merchantListings;
  const product = gscData?.productSnippets;
  const review = gscData?.reviewSnippets;
  const videos = gscData?.videos;
  const links = gscData?.links;
  const sitemaps = gscData?.sitemaps;
  const results = bulkResults?.results || [];

  const totalIssues = [merchant, product, review, videos].reduce((sum, d) => {
    if (!d?.issues?.length) return sum;
    return sum + d.issues.reduce((s, item) => s + parseNum(item.count), 0);
  }, 0);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600 shadow-lg shadow-purple-200">
            <Globe size={20} className="text-white" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-900">Extension Data</h1>
            <p className="text-xs text-slate-500">
              Live data synced from Chrome extension
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {gscData?.received_at && (
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <Clock size={12} />
              <span>Last sync: {gscData.received_at}</span>
            </div>
          )}
          <label className="flex items-center gap-1.5 text-xs text-slate-500 cursor-pointer select-none">
            {autoRefresh && (
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-green-500" />
              </span>
            )}
            <input type="checkbox" checked={autoRefresh} onChange={e => setAutoRefresh(e.target.checked)}
              className="rounded border-slate-300 text-blue-600 focus:ring-blue-500 h-3.5 w-3.5" />
            Auto-refresh
          </label>
          <button onClick={() => fetchData()} disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-600 hover:bg-slate-50 disabled:opacity-40 transition-all">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>
      </div>

      {/* Empty State */}
      {!gscData && !bulkResults && !loading && (
        <div className="rounded-2xl border-2 border-dashed border-slate-200 bg-white p-16 text-center">
          <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-purple-50 to-indigo-100">
            <Globe size={40} className="text-indigo-400" />
          </div>
          <h3 className="text-lg font-bold text-slate-800">No Extension Data Yet</h3>
          <p className="text-sm text-slate-500 mt-2 max-w-md mx-auto leading-relaxed">
            Use the Chrome extension's "Fetch All" button to scrape GSC data, or run a Bulk Indexing queue. Data will appear here automatically.
          </p>
          <div className="mt-6 flex items-center justify-center gap-3">
            <div className="flex items-center gap-1.5 rounded-full bg-purple-50 px-4 py-2 text-xs font-medium text-purple-700">
              <Search size={12} /> Waiting for data...
            </div>
          </div>
        </div>
      )}

      {/* GSC Report Cards */}
      {gscData && (
        <>
          {/* Summary Strip with Donut + Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-6 gap-4 mb-5">
            {pages && (
              <div className="md:col-span-2 rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
                <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide mb-2">Index Coverage</div>
                <div className="flex items-center gap-4">
                  <div className="w-24 h-24 flex-shrink-0">
                    <IndexDonut indexed={parseNum(pages.indexed)} notIndexed={parseNum(pages.notIndexed)} />
                  </div>
                  <div className="space-y-2 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="h-2.5 w-2.5 rounded-full bg-green-500" />
                      <span className="text-xs text-slate-500">Indexed</span>
                      <span className="ml-auto text-sm font-bold text-slate-900">{pages.indexed || '—'}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="h-2.5 w-2.5 rounded-full bg-red-500" />
                      <span className="text-xs text-slate-500">Not Indexed</span>
                      <span className="ml-auto text-sm font-bold text-slate-900">{pages.notIndexed || '—'}</span>
                    </div>
                    {(() => {
                      const total = parseNum(pages.indexed) + parseNum(pages.notIndexed);
                      const pct = total > 0 ? Math.round((parseNum(pages.indexed) / total) * 100) : 0;
                      return (
                        <div className="text-[10px] text-slate-400 pt-1 border-t border-slate-100">
                          {pct}% coverage rate
                        </div>
                      );
                    })()}
                  </div>
                </div>
              </div>
            )}
            {perf && (
              <>
                <StatCard
                  icon={MousePointer} iconBg="bg-blue-100" iconColor="text-blue-600"
                  borderColor="border-l-blue-500" label="Clicks" value={perf.clicks || '—'}
                />
                <StatCard
                  icon={Eye} iconBg="bg-indigo-100" iconColor="text-indigo-600"
                  borderColor="border-l-indigo-500" label="Impressions" value={perf.impressions || '—'}
                />
                <StatCard
                  icon={Percent} iconBg="bg-teal-100" iconColor="text-teal-600"
                  borderColor="border-l-teal-500" label="CTR" value={perf.ctr || '—'}
                />
                <StatCard
                  icon={Hash} iconBg="bg-amber-100" iconColor="text-amber-600"
                  borderColor="border-l-amber-500" label="Avg Position" value={perf.position || '—'}
                />
              </>
            )}
          </div>

          {/* Not-Indexed Reasons Chart */}
          {pages?.reasons?.length > 0 && <ReasonsChart reasons={pages.reasons} />}

          {/* Enhancement Summary */}
          {totalIssues > 0 && (
            <div className="flex items-center gap-2 mb-3 px-1">
              <AlertOctagon size={14} className="text-amber-500" />
              <span className="text-xs font-medium text-slate-600">
                {totalIssues.toLocaleString()} total enhancement issues across all types
              </span>
            </div>
          )}

          {/* Enhancement Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
            {merchant && <EnhancementCard icon={ShoppingCart} title="Merchant Listings" data={merchant} />}
            {product && <EnhancementCard icon={FileText} title="Product Snippets" data={product} />}
            {review && <EnhancementCard icon={Star} title="Review Snippets" data={review} />}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
            {videos && <EnhancementCard icon={Video} title="Videos" data={videos} />}
            {links && <LinksCard links={links} />}
            {sitemaps && <SitemapsCard sitemaps={sitemaps} />}
          </div>
        </>
      )}

      {/* Bulk Indexing Results */}
      {results.length > 0 && <BulkResultsTable results={results} receivedAt={bulkResults?.received_at} />}
    </div>
  );
}

/* ─── Index Coverage Donut ─── */
function IndexDonut({ indexed, notIndexed }) {
  const total = indexed + notIndexed;
  if (total === 0) return <div className="w-full h-full flex items-center justify-center text-xs text-slate-400">No data</div>;
  const pct = Math.round((indexed / total) * 100);
  const data = [
    { name: 'Indexed', value: indexed },
    { name: 'Not Indexed', value: notIndexed },
  ];

  return (
    <ResponsiveContainer width="100%" height="100%">
      <PieChart>
        <Pie
          data={data} dataKey="value" cx="50%" cy="50%"
          innerRadius={28} outerRadius={42} strokeWidth={2} stroke="#fff"
        >
          {data.map((_, i) => <Cell key={i} fill={DONUT_COLORS[i]} />)}
        </Pie>
        <text x="50%" y="50%" textAnchor="middle" dominantBaseline="middle"
          className="text-sm font-bold fill-slate-800">
          {pct}%
        </text>
        <Tooltip
          formatter={(val, name) => [(val ?? 0).toLocaleString(), name]}
          contentStyle={{ borderRadius: 8, fontSize: 12, border: '1px solid #e2e8f0' }}
        />
      </PieChart>
    </ResponsiveContainer>
  );
}

/* ─── Stat Card (Performance) ─── */
function StatCard({ icon: Icon, iconBg, iconColor, borderColor, label, value }) {
  return (
    <div className={`rounded-xl border border-slate-200 bg-white p-4 shadow-sm border-l-4 ${borderColor}`}>
      <div className="flex items-center gap-2 mb-2">
        <div className={`flex h-7 w-7 items-center justify-center rounded-lg ${iconBg}`}>
          <Icon size={14} className={iconColor} />
        </div>
        <span className="text-xs text-slate-500">{label}</span>
      </div>
      <div className="text-2xl font-bold text-slate-900">{value}</div>
    </div>
  );
}

/* ─── Not-Indexed Reasons (Bar Chart) ─── */
function ReasonsChart({ reasons }) {
  const [expanded, setExpanded] = useState(false);
  const sorted = [...reasons].sort((a, b) => parseNum(b.count) - parseNum(a.count));
  const visible = expanded ? sorted : sorted.slice(0, 5);

  const chartData = visible.map((r, i) => ({
    reason: ((r.reason || 'Unknown').length > 40 ? (r.reason || 'Unknown').slice(0, 37) + '...' : (r.reason || 'Unknown')),
    fullReason: r.reason,
    count: parseNum(r.count),
    fill: SEVERITY_COLORS[i % SEVERITY_COLORS.length],
  }));

  const maxCount = Math.max(...chartData.map(d => d.count), 1);
  const chartHeight = Math.max(chartData.length * 40 + 20, 120);

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden mb-5">
      <div className="px-4 py-3 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <XCircle size={14} className="text-red-500" />
          <h3 className="text-sm font-bold text-slate-800">Not-Indexed Reasons</h3>
        </div>
        <span className="text-xs text-slate-400">{reasons.length} reasons</span>
      </div>
      <div className="px-4 py-3">
        <ResponsiveContainer width="100%" height={chartHeight}>
          <BarChart data={chartData} layout="vertical" margin={{ left: 10, right: 30, top: 5, bottom: 5 }}>
            <XAxis type="number" domain={[0, maxCount]} tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
            <YAxis
              dataKey="reason" type="category" width={220}
              tick={{ fontSize: 11, fill: '#64748b' }} tickLine={false} axisLine={false}
            />
            <Tooltip
              formatter={(val) => [(val ?? 0).toLocaleString(), 'Pages']}
              labelFormatter={(_, payload) => payload?.[0]?.payload?.fullReason || ''}
              contentStyle={{ borderRadius: 8, fontSize: 12, border: '1px solid #e2e8f0' }}
            />
            <Bar dataKey="count" radius={[0, 6, 6, 0]} barSize={20}>
              {chartData.map((entry, i) => (
                <Cell key={i} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {sorted.length > 5 && (
        <button onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-center gap-1 py-2.5 text-xs text-blue-600 hover:bg-slate-50 border-t border-slate-100 font-medium transition-colors">
          {expanded ? <><ChevronUp size={12} /> Show top 5 only</> : <><ChevronDown size={12} /> Show all {sorted.length} reasons</>}
        </button>
      )}
    </div>
  );
}

/* ─── Enhancement Card (with progress bar + hover) ─── */
function EnhancementCard({ icon: Icon, title, data }) {
  if (!data) return null;
  if (data.notAvailable) {
    return (
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm opacity-50">
        <div className="flex items-center gap-2 mb-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-slate-100">
            <Icon size={16} className="text-slate-400" />
          </div>
          <h3 className="text-sm font-bold text-slate-500">{title}</h3>
        </div>
        <p className="text-xs text-slate-400">Not available for this property</p>
      </div>
    );
  }

  const valid = parseNum(data.valid);
  const error = parseNum(data.error);
  const warning = parseNum(data.warning);
  const total = valid + error + warning;
  const validPct = total > 0 ? (valid / total) * 100 : 0;
  const errorPct = total > 0 ? (error / total) * 100 : 0;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200 cursor-default">
      <div className="flex items-center gap-2 mb-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-orange-100">
          <Icon size={16} className="text-orange-600" />
        </div>
        <h3 className="text-sm font-bold text-slate-800">{title}</h3>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <div className="text-lg font-bold text-green-600">{data.valid || '0'}</div>
          <div className="text-[10px] text-slate-400">Valid</div>
        </div>
        <div>
          <div className="text-lg font-bold text-red-500">{data.error || '0'}</div>
          <div className="text-[10px] text-slate-400">Errors</div>
        </div>
        <div>
          <div className="text-lg font-bold text-amber-500">{data.warning || '0'}</div>
          <div className="text-[10px] text-slate-400">Warnings</div>
        </div>
      </div>

      {/* Progress bar */}
      {total > 0 && (
        <div className="mt-3">
          <div className="flex items-center justify-between text-[10px] text-slate-400 mb-1">
            <span>Valid {Math.round(validPct)}%</span>
            {error > 0 && <span>Errors {Math.round(errorPct)}%</span>}
          </div>
          <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden flex">
            <div className="h-full bg-green-500 rounded-l-full" style={{ width: `${validPct}%` }} />
            <div className="h-full bg-red-500" style={{ width: `${errorPct}%` }} />
            <div className="h-full bg-amber-400 rounded-r-full" style={{ width: `${100 - validPct - errorPct}%` }} />
          </div>
        </div>
      )}

      {data.issues?.length > 0 && (
        <div className="mt-3 border-t border-slate-100 pt-2">
          <div className="text-[10px] font-medium text-slate-500 mb-1">Top Issues:</div>
          {data.issues.slice(0, 5).map((item, i) => (
            <div key={i} className="flex justify-between text-xs text-slate-500 py-0.5">
              <span className="truncate mr-2">{typeof item === 'string' ? item : item.issue || item.name || '—'}</span>
              {typeof item === 'object' && item.count != null && (
                <span className="font-mono font-medium text-slate-700 shrink-0">{item.count}</span>
              )}
            </div>
          ))}
          {data.issues.length > 5 && (
            <div className="text-[10px] text-slate-400 mt-1">+{data.issues.length - 5} more</div>
          )}
        </div>
      )}
    </div>
  );
}

/* ─── Links Card (with mini bars) ─── */
function LinksCard({ links }) {
  const domains = links.topLinkingDomains || [];
  const linkedPages = links.topLinkedPages || [];

  const domainMax = Math.max(...domains.slice(0, 3).map(d => parseNum(d.count)), 1);
  const pageMax = Math.max(...linkedPages.slice(0, 3).map(p => parseNum(p.count)), 1);

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200">
      <div className="flex items-center gap-2 mb-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-100">
          <Link2 size={16} className="text-blue-600" />
        </div>
        <h3 className="text-sm font-bold text-slate-800">Links</h3>
      </div>
      <div className="space-y-1.5 text-sm">
        <div className="flex justify-between">
          <span className="text-slate-500">External Links</span>
          <span className="font-bold text-slate-800">{links.externalLinks || '—'}</span>
        </div>
        <div className="flex justify-between">
          <span className="text-slate-500">Internal Links</span>
          <span className="font-bold text-slate-800">{links.internalLinks || '—'}</span>
        </div>
      </div>
      {domains.length > 0 && (
        <div className="mt-3 border-t border-slate-100 pt-2">
          <div className="text-[10px] font-medium text-slate-500 mb-1.5">Top Linking Domains:</div>
          {domains.slice(0, 3).map((d, i) => {
            const count = parseNum(d.count);
            const pct = (count / domainMax) * 100;
            return (
              <div key={i} className="mb-1.5">
                <div className="flex justify-between text-xs text-slate-600 mb-0.5">
                  <span className="truncate mr-2">{d.domain || d.page || '—'}</span>
                  <span className="font-mono font-medium text-slate-700 shrink-0">{d.count}</span>
                </div>
                <div className="h-1 rounded-full bg-slate-100 overflow-hidden">
                  <div className="h-full rounded-full bg-blue-400" style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
      {linkedPages.length > 0 && (
        <div className="mt-2 border-t border-slate-100 pt-2">
          <div className="text-[10px] font-medium text-slate-500 mb-1.5">Top Linked Pages:</div>
          {linkedPages.slice(0, 3).map((p, i) => {
            const count = parseNum(p.count);
            const pct = (count / pageMax) * 100;
            return (
              <div key={i} className="mb-1.5">
                <div className="flex justify-between text-xs text-slate-600 mb-0.5">
                  <span className="truncate mr-2">{p.page || '—'}</span>
                  <span className="font-mono font-medium text-slate-700 shrink-0">{p.count}</span>
                </div>
                <div className="h-1 rounded-full bg-slate-100 overflow-hidden">
                  <div className="h-full rounded-full bg-indigo-400" style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ─── Sitemaps Card (with status icons) ─── */
function SitemapsCard({ sitemaps }) {
  const list = (sitemaps && sitemaps.sitemaps) || [];

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200">
      <div className="flex items-center gap-2 mb-3">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-green-100">
          <Map size={16} className="text-green-600" />
        </div>
        <h3 className="text-sm font-bold text-slate-800">Sitemaps</h3>
      </div>
      {list.length > 0 ? (
        <div className="space-y-2">
          {list.map((s, i) => (
            <div key={i} className="rounded-lg bg-slate-50 px-3 py-2">
              <div className="flex items-start gap-2">
                {s.status === 'Success'
                  ? <CheckCircle size={14} className="text-green-500 mt-0.5 shrink-0" />
                  : <AlertTriangle size={14} className="text-amber-500 mt-0.5 shrink-0" />
                }
                <div className="min-w-0 flex-1">
                  <div className="font-mono text-xs text-slate-700 truncate">{s.url}</div>
                  <div className="flex gap-3 mt-1 text-[10px] text-slate-400">
                    {s.type && <span className="bg-slate-200 rounded px-1.5 py-0.5">{s.type}</span>}
                    {s.status && (
                      <span className={`font-medium ${s.status === 'Success' ? 'text-green-600' : 'text-amber-600'}`}>
                        {s.status}
                      </span>
                    )}
                    {s.submitted && <span>Submitted: {s.submitted}</span>}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-1 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-500">Submitted</span>
            <span className="font-medium">{sitemaps.submitted || '—'}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">Successful</span>
            <span className="font-medium">{sitemaps.successful || '—'}</span>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Bulk Results Table (with summary pie) ─── */
function BulkResultsTable({ results, receivedAt }) {
  const indexed = results.filter(r => r.status === 'indexed').length;
  const requested = results.filter(r => r.status === 'requested').length;
  const notIndexed = results.filter(r => r.status === 'not_indexed').length;
  const errors = results.filter(r => r.status === 'error').length;

  const pieData = [
    { name: 'Indexed', value: indexed, color: BULK_PIE_COLORS.indexed },
    { name: 'Requested', value: requested, color: BULK_PIE_COLORS.requested },
    { name: 'Not Indexed', value: notIndexed, color: BULK_PIE_COLORS.not_indexed },
    { name: 'Error', value: errors, color: BULK_PIE_COLORS.error },
  ].filter(d => d.value > 0);

  return (
    <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden mt-5">
      <div className="px-5 py-3 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-purple-500" />
          <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wide">Bulk Indexing Results</h2>
          <span className="text-xs text-slate-400 ml-1">({results.length} URLs)</span>
        </div>
        {receivedAt && <span className="text-xs text-slate-400">Synced: {receivedAt}</span>}
      </div>

      {/* Summary row with mini donut */}
      <div className="px-5 py-4 border-b border-slate-100 bg-slate-50/50 flex items-center gap-6">
        <div className="w-20 h-20 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={pieData} dataKey="value" cx="50%" cy="50%"
                innerRadius={22} outerRadius={35} strokeWidth={2} stroke="#fff">
                {pieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Pie>
              <Tooltip
                formatter={(val, name) => [val, name]}
                contentStyle={{ borderRadius: 8, fontSize: 11, border: '1px solid #e2e8f0' }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="flex flex-wrap gap-4 text-sm">
          {indexed > 0 && (
            <div className="flex items-center gap-1.5">
              <CheckCircle size={14} className="text-green-500" />
              <span className="font-bold text-green-700">{indexed}</span>
              <span className="text-slate-500">indexed</span>
            </div>
          )}
          {requested > 0 && (
            <div className="flex items-center gap-1.5">
              <Upload size={14} className="text-blue-500" />
              <span className="font-bold text-blue-700">{requested}</span>
              <span className="text-slate-500">requested</span>
            </div>
          )}
          {notIndexed > 0 && (
            <div className="flex items-center gap-1.5">
              <AlertTriangle size={14} className="text-amber-500" />
              <span className="font-bold text-amber-700">{notIndexed}</span>
              <span className="text-slate-500">not indexed</span>
            </div>
          )}
          {errors > 0 && (
            <div className="flex items-center gap-1.5">
              <XCircle size={14} className="text-red-500" />
              <span className="font-bold text-red-700">{errors}</span>
              <span className="text-slate-500">errors</span>
            </div>
          )}
        </div>
      </div>

      <div className="max-h-[500px] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-slate-50 text-xs text-slate-500">
            <tr>
              <th className="text-left px-5 py-2 font-medium w-10">#</th>
              <th className="text-left px-2 py-2 font-medium">URL</th>
              <th className="text-left px-2 py-2 font-medium">Coverage</th>
              <th className="text-left px-2 py-2 font-medium">Status</th>
              <th className="text-left px-2 py-2 font-medium">Rich Results</th>
              <th className="text-left px-2 py-2 font-medium">Action</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r, i) => (
              <tr key={i} className="border-t border-slate-50 hover:bg-blue-50/30 transition-colors">
                <td className="px-5 py-2 text-slate-400 text-xs">{i + 1}</td>
                <td className="px-2 py-2 font-mono text-xs text-slate-600 max-w-xs truncate" title={r.url}>
                  {(r.url || '').replace(/^https?:\/\//, '').slice(0, 60)}
                </td>
                <td className="px-2 py-2 text-xs">{r.coverage || '—'}</td>
                <td className="px-2 py-2">
                  <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[r.status] || 'text-slate-500 bg-slate-50'}`}>
                    {r.status === 'indexed' && <CheckCircle size={10} />}
                    {r.status === 'requested' && <Upload size={10} />}
                    {r.status === 'not_indexed' && <AlertTriangle size={10} />}
                    {r.status === 'error' && <XCircle size={10} />}
                    {STATUS_LABELS[r.status] || r.status}
                  </span>
                </td>
                <td className="px-2 py-2 text-xs text-slate-500">{(r.richResults || []).join(', ') || '—'}</td>
                <td className="px-2 py-2 text-xs text-slate-500">{r.action || r.error || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
