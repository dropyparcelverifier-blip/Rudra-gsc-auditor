import { useState, useEffect, useRef, useCallback } from 'react';
import { api } from '../lib/api';
import {
  PieChart, Pie, Cell, BarChart, Bar, XAxis, YAxis, Tooltip,
  ResponsiveContainer,
} from 'recharts';
import {
  RefreshCw, CheckCircle, XCircle, AlertTriangle, Upload, Globe,
  ShoppingCart, Star, Link2, Map, Video, FileText,
  Clock, AlertOctagon, ChevronDown, ChevronUp, ExternalLink,
  MousePointer, Eye, Percent, Hash, Search, Package, X, Loader,
} from 'lucide-react';
import IndexDonut from '../components/IndexDonut';
import { STATUS_COLORS, STATUS_LABELS, STATUS_HEX } from '../lib/statusConstants';

const BULK_PIE_COLORS = STATUS_HEX;

const SEVERITY_COLORS = [
  '#ef4444', '#f97316', '#f59e0b', '#eab308', '#84cc16',
  '#22c55e', '#14b8a6', '#06b6d4', '#3b82f6', '#6366f1',
  '#8b5cf6', '#a855f7', '#d946ef', '#ec4899', '#f43f5e',
];

const GSC_PROPERTY = 'https://rudraretails.com/';
const GSC_BASE = 'https://search.google.com/search-console';
const GSC_RID = `resource_id=${encodeURIComponent(GSC_PROPERTY)}`;
const GSC_LINKS = {
  'Merchant Listings': `${GSC_BASE}/r/merchant-listings?${GSC_RID}`,
  'Product Snippets': `${GSC_BASE}/r/product?${GSC_RID}`,
  'Review Snippets': `${GSC_BASE}/r/review-snippet?${GSC_RID}`,
  'Videos': `${GSC_BASE}/r/videos?${GSC_RID}`,
  'Index Coverage': `${GSC_BASE}/index?${GSC_RID}`,
};

function parseNum(val) {
  return parseInt(String(val || '0').replace(/,/g, ''), 10) || 0;
}

export default function ExtensionData() {
  const [gscData, setGscData] = useState(null);
  const [bulkResults, setBulkResults] = useState(null);
  const [gscEnhancements, setGscEnhancements] = useState(null);
  const [liveReports, setLiveReports] = useState(null);
  const [loading, setLoading] = useState(true);
  const [autoRefresh, setAutoRefresh] = useState(true);
  const intervalRef = useRef(null);

  const fetchData = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [gsc, bulk, reports] = await Promise.allSettled([
        api.getExtensionGscData(),
        api.getBulkResults(),
        api.getGscReports(),
      ]);
      if (gsc.status === 'fulfilled') setGscData(gsc.value);
      if (bulk.status === 'fulfilled') setBulkResults(bulk.value);
      if (reports.status === 'fulfilled') {
        setLiveReports(reports.value);
        const r = reports.value;
        setGscEnhancements({
          product_snippets: { valid: r.product_snippets_valid || 0, invalid: r.product_snippets_invalid || 0 },
          merchant_listings: { valid: r.merchant_listings_valid || 0, invalid: r.merchant_listings_invalid || 0 },
          review_snippets: { valid: r.review_snippets_valid || 0, invalid: r.review_snippets_invalid || 0 },
        });
      }
    } catch (e) { console.error('Failed to fetch extension data:', e); }
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

  const [urlDrawer, setUrlDrawer] = useState(null);

  const openUrlDrawer = useCallback((type, title) => {
    setUrlDrawer({ type, title, urls: [], loading: true, page: 1, total: 0 });
    api.getEnhancementUrls({ type, page: 1, per_page: 100 }).then(data => {
      setUrlDrawer(prev => prev ? { ...prev, urls: data.urls || [], total: data.total || 0, loading: false } : null);
    }).catch(() => {
      setUrlDrawer(prev => prev ? { ...prev, loading: false } : null);
    });
  }, []);

  const loadMoreUrls = useCallback(() => {
    if (!urlDrawer || urlDrawer.loading) return;
    const nextPage = urlDrawer.page + 1;
    setUrlDrawer(prev => prev ? { ...prev, loading: true, page: nextPage } : null);
    api.getEnhancementUrls({ type: urlDrawer.type, page: nextPage, per_page: 100 }).then(data => {
      setUrlDrawer(prev => prev ? { ...prev, urls: [...prev.urls, ...(data.urls || [])], loading: false } : null);
    }).catch(() => {
      setUrlDrawer(prev => prev ? { ...prev, loading: false } : null);
    });
  }, [urlDrawer]);

  const enh = gscEnhancements || {};

  const totalIssues = [merchant, product, review, videos].reduce((sum, d) => {
    if (!d?.issues?.length) return sum;
    return sum + d.issues.reduce((s, item) => s + parseNum(item.count), 0);
  }, 0);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50/30">
      <div className="px-5 py-5 max-w-7xl mx-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-gradient-to-br from-violet-500 to-indigo-600 shadow-lg shadow-violet-200/50">
              <Globe size={22} className="text-white" />
            </div>
            <div>
              <h1 className="text-2xl font-extrabold text-slate-900 tracking-tight">Extension Data</h1>
              <p className="text-sm text-slate-500">Live data synced from Chrome extension</p>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {gscData?.received_at && (
              <div className="flex items-center gap-1.5 text-xs text-slate-400 bg-white rounded-lg px-3 py-2 border border-slate-100">
                <Clock size={12} />
                <span>Last sync: {gscData.received_at}</span>
              </div>
            )}
            <label className="flex items-center gap-2 text-xs text-slate-500 cursor-pointer select-none bg-white rounded-lg px-3 py-2 border border-slate-100">
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
              className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-4 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 hover:border-slate-300 disabled:opacity-40 transition-all shadow-sm">
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
            {/* Summary Strip — Index Coverage + Performance */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-5">
              {(pages || liveReports) && (() => {
                const idx = liveReports?.pages_indexed || parseNum(pages?.indexed);
                const notIdx = liveReports?.pages_not_indexed || parseNum(pages?.notIndexed);
                const total = idx + notIdx;
                const pct = total > 0 ? Math.round((idx / total) * 100) : 0;
                return (
                  <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                    <div className="flex items-center gap-2 mb-3">
                      <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-green-600 shadow-sm">
                        <CheckCircle size={14} className="text-white" />
                      </div>
                      <span className="text-xs font-medium text-slate-500">Coverage</span>
                    </div>
                    <div className="text-2xl font-extrabold text-slate-900 tracking-tight">{pct}%</div>
                    <div className="mt-2 h-2 rounded-full bg-slate-100 overflow-hidden flex">
                      <div className="h-full bg-emerald-500 rounded-full" style={{ width: `${pct}%` }} />
                      <div className="h-full bg-red-400" style={{ width: `${100 - pct}%` }} />
                    </div>
                    <div className="mt-1.5 flex justify-between text-[10px] text-slate-400">
                      <span className="text-emerald-600 font-semibold">{idx.toLocaleString()} indexed</span>
                      <span className="text-red-500 font-semibold">{notIdx.toLocaleString()} not</span>
                    </div>
                  </div>
                );
              })()}
              {perf && (
                <>
                  <PerfStatCard icon={MousePointer} gradient="from-blue-500 to-blue-600" label="Clicks" value={perf.clicks || '—'} />
                  <PerfStatCard icon={Eye} gradient="from-indigo-500 to-purple-600" label="Impressions" value={perf.impressions || '—'} />
                  <PerfStatCard icon={Percent} gradient="from-teal-500 to-emerald-600" label="CTR" value={perf.ctr || '—'} />
                  <PerfStatCard icon={Hash} gradient="from-amber-500 to-orange-600" label="Avg Position" value={perf.position || '—'} />
                </>
              )}
            </div>

            {/* Not-Indexed Reasons Chart */}
            {pages?.reasons?.length > 0 && <ReasonsChart reasons={pages.reasons} />}

            {/* Enhancement Summary */}
            {totalIssues > 0 && (
              <div className="flex items-center gap-2.5 mb-3 px-1">
                <div className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-100">
                  <AlertOctagon size={13} className="text-amber-600" />
                </div>
                <span className="text-sm font-semibold text-slate-700">
                  {totalIssues.toLocaleString()} total enhancement issues across all types
                </span>
              </div>
            )}

            {/* Enhancement Cards — using corrected GSC data */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
              <EnhancementCard
                icon={ShoppingCart} title="Merchant Listings"
                data={merchant} corrected={enh.merchant_listings}
                color="cyan" gradient="from-cyan-500 to-teal-600"
                gscLink={GSC_LINKS['Merchant Listings']}
                onViewUrls={() => openUrlDrawer('Merchant listings', 'Merchant Listings')}
              />
              <EnhancementCard
                icon={Package} title="Product Snippets"
                data={product} corrected={enh.product_snippets}
                color="purple" gradient="from-purple-500 to-indigo-600"
                gscLink={GSC_LINKS['Product Snippets']}
                onViewUrls={() => openUrlDrawer('Product snippets', 'Product Snippets')}
              />
              <EnhancementCard
                icon={Star} title="Review Snippets"
                data={review} corrected={enh.review_snippets}
                color="amber" gradient="from-amber-500 to-orange-600"
                gscLink={GSC_LINKS['Review Snippets']}
                onViewUrls={() => openUrlDrawer('Review snippets', 'Review Snippets')}
              />
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-5">
              {videos && <EnhancementCard icon={Video} title="Videos" data={videos} color="red" gradient="from-red-500 to-rose-600" gscLink={GSC_LINKS['Videos']} />}
              {links && <LinksCard links={links} />}
              {sitemaps && <SitemapsCard sitemaps={sitemaps} />}
            </div>
          </>
        )}

        {/* Bulk Indexing Results */}
        {results.length > 0 && <BulkResultsTable results={results} receivedAt={bulkResults?.received_at} />}
      </div>

      {/* URL Drawer */}
      {urlDrawer && <UrlDrawer drawer={urlDrawer} onClose={() => setUrlDrawer(null)} onLoadMore={loadMoreUrls} />}
    </div>
  );
}

/* ─── Performance Stat Card ─── */
function PerfStatCard({ icon: Icon, gradient, label, value }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm hover:shadow-md transition-shadow">
      <div className="flex items-center gap-2 mb-3">
        <div className={`flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br ${gradient} shadow-sm`}>
          <Icon size={14} className="text-white" />
        </div>
        <span className="text-xs font-medium text-slate-500">{label}</span>
      </div>
      <div className="text-2xl font-extrabold text-slate-900 tracking-tight">{value}</div>
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
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden mb-6">
      <div className="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-red-100">
            <XCircle size={16} className="text-red-500" />
          </div>
          <h3 className="text-sm font-bold text-slate-800">Not-Indexed Reasons</h3>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-xs font-medium text-slate-400 bg-slate-50 rounded-full px-3 py-1">{reasons.length} reasons</span>
          <a href={GSC_LINKS['Index Coverage']} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1 text-[10px] font-semibold text-blue-500 hover:text-blue-700 transition-colors">
            View in GSC <ExternalLink size={10} />
          </a>
        </div>
      </div>
      <div className="px-4 py-4">
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
              contentStyle={{ borderRadius: 12, fontSize: 12, border: '1px solid #e2e8f0', boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1)' }}
            />
            <Bar dataKey="count" radius={[0, 8, 8, 0]} barSize={22}>
              {chartData.map((entry, i) => (
                <Cell key={i} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {sorted.length > 5 && (
        <button onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-center gap-1.5 py-3 text-xs text-blue-600 hover:bg-blue-50/50 border-t border-slate-100 font-semibold transition-colors">
          {expanded ? <><ChevronUp size={12} /> Show top 5 only</> : <><ChevronDown size={12} /> Show all {sorted.length} reasons</>}
        </button>
      )}
    </div>
  );
}

/* ─── Enhancement Card ─── */
function EnhancementCard({ icon: Icon, title, data, corrected, color = 'slate', gradient = 'from-slate-400 to-slate-500', gscLink, onViewUrls }) {
  if (!data) return null;
  if (data.notAvailable) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm opacity-50">
        <div className="flex items-center gap-2 mb-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100">
            <Icon size={17} className="text-slate-400" />
          </div>
          <h3 className="text-sm font-bold text-slate-500">{title}</h3>
        </div>
        <p className="text-xs text-slate-400">Not available for this property</p>
      </div>
    );
  }

  const valid = corrected?.valid ?? parseNum(data.valid);
  const invalid = corrected?.invalid ?? parseNum(data.error);
  const warning = parseNum(data.warning);
  const total = valid + invalid + warning;
  const validPct = total > 0 ? (valid / total) * 100 : (valid > 0 ? 100 : 0);
  const invalidPct = total > 0 ? (invalid / total) * 100 : 0;

  const colorMap = {
    cyan: { bg: 'bg-cyan-50', border: 'border-cyan-200', validText: 'text-cyan-700', ring: 'ring-cyan-100' },
    purple: { bg: 'bg-purple-50', border: 'border-purple-200', validText: 'text-purple-700', ring: 'ring-purple-100' },
    amber: { bg: 'bg-amber-50', border: 'border-amber-200', validText: 'text-amber-700', ring: 'ring-amber-100' },
    red: { bg: 'bg-red-50', border: 'border-red-200', validText: 'text-red-700', ring: 'ring-red-100' },
    slate: { bg: 'bg-slate-50', border: 'border-slate-200', validText: 'text-slate-700', ring: 'ring-slate-100' },
  };
  const c = colorMap[color] || colorMap.slate;

  const issues = corrected?.issues?.length ? corrected.issues : data.issues;

  return (
    <div className={`rounded-2xl border ${c.border} bg-white p-5 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200`}>
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className={`flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ${gradient} shadow-md`}>
            <Icon size={18} className="text-white" />
          </div>
          <h3 className="text-sm font-bold text-slate-800">{title}</h3>
        </div>
        {gscLink && (
          <a href={gscLink} target="_blank" rel="noopener noreferrer"
            className="flex items-center gap-1 text-[10px] font-semibold text-blue-500 hover:text-blue-700 transition-colors">
            Open in GSC <ExternalLink size={10} />
          </a>
        )}
      </div>

      <div className="grid grid-cols-3 gap-3 text-center mb-4">
        {gscLink ? (
          <a href={gscLink} target="_blank" rel="noopener noreferrer" className={`rounded-xl ${c.bg} p-3 cursor-pointer hover:ring-2 ${c.ring} transition-all`}>
            <div className="text-xl font-extrabold text-emerald-600">{valid.toLocaleString()}</div>
            <div className="text-[10px] font-semibold text-emerald-500 uppercase mt-0.5">Valid</div>
          </a>
        ) : (
          <div className={`rounded-xl ${c.bg} p-3`}>
            <div className="text-xl font-extrabold text-emerald-600">{valid.toLocaleString()}</div>
            <div className="text-[10px] font-semibold text-emerald-500 uppercase mt-0.5">Valid</div>
          </div>
        )}
        {gscLink ? (
          <a href={gscLink} target="_blank" rel="noopener noreferrer" className="rounded-xl bg-red-50 p-3 cursor-pointer hover:ring-2 ring-red-100 transition-all">
            <div className="text-xl font-extrabold text-red-500">{invalid.toLocaleString()}</div>
            <div className="text-[10px] font-semibold text-red-400 uppercase mt-0.5">Errors</div>
          </a>
        ) : (
          <div className="rounded-xl bg-red-50 p-3">
            <div className="text-xl font-extrabold text-red-500">{invalid.toLocaleString()}</div>
            <div className="text-[10px] font-semibold text-red-400 uppercase mt-0.5">Errors</div>
          </div>
        )}
        {gscLink ? (
          <a href={gscLink} target="_blank" rel="noopener noreferrer" className="rounded-xl bg-amber-50 p-3 cursor-pointer hover:ring-2 ring-amber-100 transition-all">
            <div className="text-xl font-extrabold text-amber-500">{warning.toLocaleString()}</div>
            <div className="text-[10px] font-semibold text-amber-400 uppercase mt-0.5">Warnings</div>
          </a>
        ) : (
          <div className="rounded-xl bg-amber-50 p-3">
            <div className="text-xl font-extrabold text-amber-500">{warning.toLocaleString()}</div>
            <div className="text-[10px] font-semibold text-amber-400 uppercase mt-0.5">Warnings</div>
          </div>
        )}
      </div>

      {/* Progress bar */}
      {(valid > 0 || invalid > 0) && (
        <div className="mb-3">
          <div className="h-2 rounded-full bg-slate-100 overflow-hidden flex">
            <div className="h-full bg-emerald-500 transition-all duration-500" style={{ width: `${validPct}%` }} />
            <div className="h-full bg-red-500 transition-all duration-500" style={{ width: `${invalidPct}%` }} />
            {warning > 0 && <div className="h-full bg-amber-400" style={{ width: `${100 - validPct - invalidPct}%` }} />}
          </div>
        </div>
      )}

      {onViewUrls && valid > 0 && (
        <button onClick={onViewUrls}
          className="w-full flex items-center justify-center gap-1.5 py-2 mb-3 text-[11px] font-semibold text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors">
          <Eye size={12} /> View {valid.toLocaleString()} URLs with {title}
        </button>
      )}

      {issues?.length > 0 && (
        <IssueList issues={issues} gscLink={gscLink} />
      )}
    </div>
  );
}

/* ─── Issue List with expandable URLs ─── */
function IssueList({ issues, gscLink }) {
  const [expanded, setExpanded] = useState(null);

  return (
    <div className="border-t border-slate-100 pt-3">
      <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Top Issues:</div>
      <div className="space-y-1">
        {issues.slice(0, 5).map((item, i) => {
          const issueText = typeof item === 'string' ? item : item.issue || item.name || '—';
          const issueCount = typeof item === 'object' && item.count != null ? item.count : null;
          const issueUrls = (typeof item === 'object' && item.urls) || [];
          const isExpanded = expanded === i;

          return (
            <div key={i}>
              <button
                onClick={() => setExpanded(isExpanded ? null : i)}
                className="w-full flex justify-between items-center text-xs py-1.5 px-2 rounded-lg hover:bg-blue-50 transition-colors cursor-pointer group text-left"
              >
                <span className="flex items-center gap-1.5 text-slate-600 truncate mr-2">
                  {issueUrls.length > 0 && (
                    isExpanded ? <ChevronUp size={10} className="shrink-0 text-blue-500" /> : <ChevronDown size={10} className="shrink-0 text-slate-400" />
                  )}
                  {issueText}
                </span>
                <span className="flex items-center gap-1.5">
                  {issueCount != null && (
                    <span className="font-mono font-bold text-slate-800 shrink-0 bg-slate-100 rounded-md px-2 py-0.5 text-[10px]">{issueCount}</span>
                  )}
                  {gscLink && <ExternalLink size={10} className="text-slate-300 group-hover:text-blue-500 shrink-0" />}
                </span>
              </button>
              {isExpanded && issueUrls.length > 0 && (
                <div className="ml-5 mt-1 mb-2 space-y-1 border-l-2 border-blue-200 pl-3">
                  {issueUrls.map((url, j) => (
                    <a key={j} href={url.startsWith('http') ? url : `https://rudraretails.com${url}`}
                      target="_blank" rel="noopener noreferrer"
                      className="block text-[11px] text-blue-600 hover:text-blue-800 hover:underline truncate font-mono"
                      title={url}>
                      {url.replace(/^https?:\/\//, '').slice(0, 80)}
                    </a>
                  ))}
                </div>
              )}
              {isExpanded && issueUrls.length === 0 && gscLink && (
                <div className="ml-5 mt-1 mb-2 pl-3">
                  <a href={gscLink} target="_blank" rel="noopener noreferrer"
                    className="text-[10px] text-blue-500 hover:text-blue-700 flex items-center gap-1">
                    View affected URLs in GSC <ExternalLink size={9} />
                  </a>
                  <p className="text-[10px] text-slate-400 mt-0.5">Run "Fetch All" in the extension to scrape URLs</p>
                </div>
              )}
            </div>
          );
        })}
      </div>
      {issues.length > 5 && (
        <div className="text-[10px] text-slate-400 mt-2 pl-2">+{issues.length - 5} more</div>
      )}
    </div>
  );
}

/* ─── Links Card ─── */
function LinksCard({ links }) {
  const domains = links.topLinkingDomains || [];
  const linkedPages = links.topLinkedPages || [];
  const domainMax = Math.max(...domains.slice(0, 3).map(d => parseNum(d.count)), 1);
  const pageMax = Math.max(...linkedPages.slice(0, 3).map(p => parseNum(p.count)), 1);

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200">
      <div className="flex items-center gap-3 mb-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-md">
          <Link2 size={18} className="text-white" />
        </div>
        <h3 className="text-sm font-bold text-slate-800">Links</h3>
      </div>
      <div className="grid grid-cols-2 gap-3 mb-4">
        <div className="rounded-xl bg-blue-50 p-3 text-center">
          <div className="text-lg font-extrabold text-blue-700">{links.externalLinks || '—'}</div>
          <div className="text-[10px] font-semibold text-blue-500 uppercase">External</div>
        </div>
        <div className="rounded-xl bg-indigo-50 p-3 text-center">
          <div className="text-lg font-extrabold text-indigo-700">{links.internalLinks || '—'}</div>
          <div className="text-[10px] font-semibold text-indigo-500 uppercase">Internal</div>
        </div>
      </div>
      {domains.length > 0 && (
        <div className="border-t border-slate-100 pt-3 mb-3">
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Top Linking Domains:</div>
          {domains.slice(0, 3).map((d, i) => {
            const count = parseNum(d.count);
            const pct = (count / domainMax) * 100;
            return (
              <div key={i} className="mb-2">
                <div className="flex justify-between text-xs text-slate-600 mb-1">
                  <span className="truncate mr-2 font-medium">{d.domain || d.page || '—'}</span>
                  <span className="font-mono font-bold text-slate-800 shrink-0">{d.count}</span>
                </div>
                <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
                  <div className="h-full rounded-full bg-gradient-to-r from-blue-400 to-blue-500 transition-all duration-500" style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
      {linkedPages.length > 0 && (
        <div className="border-t border-slate-100 pt-3">
          <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-2">Top Linked Pages:</div>
          {linkedPages.slice(0, 3).map((p, i) => {
            const count = parseNum(p.count);
            const pct = (count / pageMax) * 100;
            return (
              <div key={i} className="mb-2">
                <div className="flex justify-between text-xs text-slate-600 mb-1">
                  <span className="truncate mr-2 font-medium">{p.page || '—'}</span>
                  <span className="font-mono font-bold text-slate-800 shrink-0">{p.count}</span>
                </div>
                <div className="h-1.5 rounded-full bg-slate-100 overflow-hidden">
                  <div className="h-full rounded-full bg-gradient-to-r from-indigo-400 to-indigo-500 transition-all duration-500" style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* ─── Sitemaps Card ─── */
function SitemapsCard({ sitemaps }) {
  const list = (sitemaps && sitemaps.sitemaps) || [];

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-200">
      <div className="flex items-center gap-3 mb-4">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-emerald-500 to-green-600 shadow-md">
          <Map size={18} className="text-white" />
        </div>
        <h3 className="text-sm font-bold text-slate-800">Sitemaps</h3>
      </div>
      {list.length > 0 ? (
        <div className="space-y-2.5">
          {list.map((s, i) => (
            <div key={i} className="rounded-xl bg-slate-50 px-3 py-2.5 border border-slate-100">
              <div className="flex items-start gap-2">
                {s.status === 'Success'
                  ? <CheckCircle size={14} className="text-emerald-500 mt-0.5 shrink-0" />
                  : <AlertTriangle size={14} className="text-amber-500 mt-0.5 shrink-0" />
                }
                <div className="min-w-0 flex-1">
                  <div className="font-mono text-xs text-slate-700 truncate">{s.url}</div>
                  <div className="flex gap-3 mt-1.5 text-[10px] text-slate-400">
                    {s.type && <span className="bg-slate-200 rounded-md px-2 py-0.5 font-medium">{s.type}</span>}
                    {s.status && (
                      <span className={`font-semibold ${s.status === 'Success' ? 'text-emerald-600' : 'text-amber-600'}`}>
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
        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-xl bg-emerald-50 p-3 text-center">
            <div className="text-lg font-extrabold text-emerald-700">{sitemaps.submitted || '—'}</div>
            <div className="text-[10px] font-semibold text-emerald-500 uppercase">Submitted</div>
          </div>
          <div className="rounded-xl bg-green-50 p-3 text-center">
            <div className="text-lg font-extrabold text-green-700">{sitemaps.successful || '—'}</div>
            <div className="text-[10px] font-semibold text-green-500 uppercase">Successful</div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── URL Drawer (slide-over panel) ─── */
function UrlDrawer({ drawer, onClose, onLoadMore }) {
  const { title, urls, loading, total } = drawer;
  const indexed = urls.filter(u => u.is_indexed).length;
  const notIndexed = urls.filter(u => !u.is_indexed).length;

  return (
    <>
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} />
      <div className="fixed right-0 top-0 bottom-0 w-full max-w-xl bg-white shadow-2xl z-50 flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-200 bg-slate-50">
          <div>
            <h2 className="text-base font-bold text-slate-800">{title} — URLs</h2>
            <p className="text-xs text-slate-500 mt-0.5">
              {total.toLocaleString()} total URLs from pipeline inspection
              {indexed > 0 && <span className="ml-2 text-emerald-600 font-semibold">{indexed} indexed</span>}
              {notIndexed > 0 && <span className="ml-2 text-red-500 font-semibold">{notIndexed} not indexed</span>}
            </p>
          </div>
          <button onClick={onClose} className="p-2 rounded-lg hover:bg-slate-200 transition-colors">
            <X size={18} className="text-slate-500" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {urls.length === 0 && !loading && (
            <div className="p-8 text-center text-slate-400 text-sm">No URLs found for this enhancement type.</div>
          )}
          <div className="divide-y divide-slate-100">
            {urls.map((item, i) => (
              <div key={i} className="px-5 py-3 hover:bg-blue-50/50 transition-colors">
                <div className="flex items-center gap-2">
                  {item.is_indexed
                    ? <CheckCircle size={13} className="text-emerald-500 shrink-0" />
                    : <XCircle size={13} className="text-red-400 shrink-0" />
                  }
                  <a href={item.url} target="_blank" rel="noopener noreferrer"
                    className="text-xs font-mono text-blue-600 hover:text-blue-800 hover:underline truncate"
                    title={item.url}>
                    {item.url.replace(/^https?:\/\//, '').slice(0, 80)}
                  </a>
                </div>
                <div className="flex gap-3 mt-1 ml-5 text-[10px] text-slate-400">
                  <span className={item.is_indexed ? 'text-emerald-600 font-semibold' : 'text-red-500 font-semibold'}>
                    {item.coverage || (item.is_indexed ? 'Indexed' : 'Not indexed')}
                  </span>
                  {item.checked_at && <span>Checked: {item.checked_at}</span>}
                </div>
              </div>
            ))}
          </div>

          {urls.length < total && (
            <div className="px-5 py-4 text-center">
              <button onClick={onLoadMore} disabled={loading}
                className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-blue-600 bg-blue-50 hover:bg-blue-100 rounded-lg transition-colors disabled:opacity-50">
                {loading ? <><Loader size={12} className="animate-spin" /> Loading...</> : <>Load more ({total - urls.length} remaining)</>}
              </button>
            </div>
          )}

          {loading && urls.length === 0 && (
            <div className="flex items-center justify-center py-12 gap-2 text-slate-400">
              <Loader size={16} className="animate-spin" /> Loading URLs...
            </div>
          )}
        </div>

        <div className="border-t border-slate-200 px-5 py-3 bg-slate-50 text-[10px] text-slate-400">
          Showing {urls.length} of {total.toLocaleString()} — Data from pipeline URL inspection
        </div>
      </div>
    </>
  );
}

/* ─── Bulk Results Table ─── */
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
    <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden mt-6">
      <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-purple-500 to-indigo-600">
            <Upload size={14} className="text-white" />
          </div>
          <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wide">Bulk Indexing Results</h2>
          <span className="text-xs text-slate-400 bg-white rounded-full px-2.5 py-1 border border-slate-100 font-medium">{results.length} URLs</span>
        </div>
        {receivedAt && <span className="text-xs text-slate-400">Synced: {receivedAt}</span>}
      </div>

      {/* Summary row */}
      <div className="px-6 py-5 border-b border-slate-100 flex items-center gap-8">
        <div className="w-20 h-20 shrink-0">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie data={pieData} dataKey="value" cx="50%" cy="50%"
                innerRadius={22} outerRadius={35} strokeWidth={2} stroke="#fff">
                {pieData.map((entry, i) => <Cell key={i} fill={entry.color} />)}
              </Pie>
              <Tooltip
                formatter={(val, name) => [val, name]}
                contentStyle={{ borderRadius: 12, fontSize: 11, border: '1px solid #e2e8f0' }}
              />
            </PieChart>
          </ResponsiveContainer>
        </div>
        <div className="flex flex-wrap gap-5 text-sm">
          {indexed > 0 && (
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-emerald-100">
                <CheckCircle size={12} className="text-emerald-600" />
              </div>
              <span className="font-extrabold text-emerald-700">{indexed}</span>
              <span className="text-slate-500">indexed</span>
            </div>
          )}
          {requested > 0 && (
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-blue-100">
                <Upload size={12} className="text-blue-600" />
              </div>
              <span className="font-extrabold text-blue-700">{requested}</span>
              <span className="text-slate-500">requested</span>
            </div>
          )}
          {notIndexed > 0 && (
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-amber-100">
                <AlertTriangle size={12} className="text-amber-600" />
              </div>
              <span className="font-extrabold text-amber-700">{notIndexed}</span>
              <span className="text-slate-500">not indexed</span>
            </div>
          )}
          {errors > 0 && (
            <div className="flex items-center gap-2">
              <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-red-100">
                <XCircle size={12} className="text-red-600" />
              </div>
              <span className="font-extrabold text-red-700">{errors}</span>
              <span className="text-slate-500">errors</span>
            </div>
          )}
        </div>
      </div>

      <div className="max-h-[500px] overflow-y-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 bg-slate-50 text-xs text-slate-500 border-b border-slate-100">
            <tr>
              <th className="text-left px-6 py-3 font-semibold w-10">#</th>
              <th className="text-left px-3 py-3 font-semibold">URL</th>
              <th className="text-left px-3 py-3 font-semibold">Coverage</th>
              <th className="text-left px-3 py-3 font-semibold">Status</th>
              <th className="text-left px-3 py-3 font-semibold">Rich Results</th>
              <th className="text-left px-3 py-3 font-semibold">Action</th>
            </tr>
          </thead>
          <tbody>
            {results.map((r, i) => (
              <tr key={i} className="border-t border-slate-50 hover:bg-blue-50/30 transition-colors">
                <td className="px-6 py-2.5 text-slate-400 text-xs font-medium">{i + 1}</td>
                <td className="px-3 py-2.5 font-mono text-xs text-slate-600 max-w-xs truncate" title={r.url}>
                  {(r.url || '').replace(/^https?:\/\//, '').slice(0, 60)}
                </td>
                <td className="px-3 py-2.5 text-xs">{r.coverage || '—'}</td>
                <td className="px-3 py-2.5">
                  <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-xs font-semibold ${STATUS_COLORS[r.status] || 'text-slate-500 bg-slate-50'}`}>
                    {r.status === 'indexed' && <CheckCircle size={10} />}
                    {r.status === 'requested' && <Upload size={10} />}
                    {r.status === 'not_indexed' && <AlertTriangle size={10} />}
                    {r.status === 'error' && <XCircle size={10} />}
                    {STATUS_LABELS[r.status] || r.status}
                  </span>
                </td>
                <td className="px-3 py-2.5 text-xs text-slate-500">{(r.richResults || []).join(', ') || '—'}</td>
                <td className="px-3 py-2.5 text-xs text-slate-500">{r.action || r.error || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
