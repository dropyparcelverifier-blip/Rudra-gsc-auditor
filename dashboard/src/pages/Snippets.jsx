import { useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, AreaChart, Area, CartesianGrid, Legend } from 'recharts';
import { Package, ShoppingCart, Star, TrendingUp, Eye, MousePointerClick, Search, Info, ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react';
import Header from '../components/Header';
import DataSourceBadge from '../components/DataSourceBadge';
import { api } from '../lib/api';

const COLORS = ['#a855f7', '#06b6d4', '#eab308', '#22c55e', '#ef4444', '#f97316', '#6366f1'];

const SNIPPET_NAMES = {
  PRODUCT_SNIPPETS: 'Product Snippets',
  PRODUCT_SNIPPET: 'Product Snippets',
  MERCHANT_LISTINGS: 'Merchant Listings',
  REVIEW_SNIPPET: 'Review Snippets',
  AMP_BLUE_LINK: 'AMP Blue Link',
  PRODUCT_IMAGE_SNIPPET: 'Product Image Snippet',
  SHOPPING_TAB: 'Shopping Tab',
};

const RICH_CONFIG = [
  { key: 'Product', label: 'Product Snippets', icon: Package, gradient: 'from-purple-500 to-indigo-500', border: 'border-purple-200', bg: 'bg-gradient-to-br from-purple-50 to-white', text: 'text-purple-700' },
  { key: 'MerchantListing', label: 'Merchant Listings', icon: ShoppingCart, gradient: 'from-cyan-500 to-teal-500', border: 'border-cyan-200', bg: 'bg-gradient-to-br from-cyan-50 to-white', text: 'text-cyan-700' },
  { key: 'Review', label: 'Review Snippets', icon: Star, gradient: 'from-amber-500 to-orange-500', border: 'border-amber-200', bg: 'bg-gradient-to-br from-amber-50 to-white', text: 'text-amber-700' },
  { key: 'None', label: 'No Rich Results', icon: Search, gradient: 'from-slate-400 to-slate-500', border: 'border-slate-200', bg: 'bg-gradient-to-br from-slate-50 to-white', text: 'text-slate-600' },
];

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3 shadow-xl text-xs backdrop-blur-sm">
      <p className="font-semibold text-slate-700 mb-1">{label}</p>
      {payload.map((p, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full" style={{ background: p.color }} />
          <span className="text-slate-500">{p.name}:</span>
          <span className="font-bold text-slate-800">{(p.value || 0).toLocaleString()}</span>
        </div>
      ))}
    </div>
  );
}

function DeltaBadge({ current, previous, invert = false }) {
  if (previous == null) return null;
  const diff = current - previous;
  if (diff === 0) return <span className="inline-flex items-center gap-0.5 text-[10px] text-slate-400"><Minus size={10} /> no change</span>;
  const isUp = diff > 0;
  const isGood = invert ? !isUp : isUp;
  const Icon = isUp ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={`inline-flex items-center gap-0.5 text-[10px] font-semibold ${isGood ? 'text-emerald-600' : 'text-red-500'}`}>
      <Icon size={10} />
      {isUp ? '+' : ''}{diff.toLocaleString()}
    </span>
  );
}

export default function Snippets({ data, loading, refresh }) {
  const [changes, setChanges] = useState(null);

  useEffect(() => {
    api.getChanges({ per_page: 100 })
      .then(d => setChanges(d))
      .catch(() => {});
  }, []);

  if (!data) return (
    <div className="flex h-96 flex-col items-center justify-center gap-3 text-slate-400">
      <div className="h-10 w-10 rounded-full border-2 border-slate-200 border-t-purple-500 animate-spin" />
      <span className="text-sm font-medium">Loading rich results data...</span>
    </div>
  );

  const liveSnippets = data.snippets || {};
  const pipeline = data.pipeline || {};
  const richBreakdown = pipeline.rich_breakdown || {};
  const gscEnh = data.gsc_enhancements || {};
  const history = data.daily_history || [];
  const today = history.length > 0 ? history[history.length - 1] : null;
  const yesterday = history.length > 1 ? history[history.length - 2] : null;
  const todayRich = today?.rich_breakdown || null;
  const yesterdayRich = yesterday?.rich_breakdown || null;

  const snippetData = Object.entries(liveSnippets)
    .filter(([, stats]) => stats && typeof stats === 'object')
    .map(([key, stats], idx) => ({
      name: SNIPPET_NAMES[key] || key,
      key,
      impressions: stats.impressions || 0,
      clicks: stats.clicks || 0,
      ctr: stats.ctr || 0,
      position: stats.avg_position || 0,
      color: COLORS[idx % COLORS.length],
    }));

  const totalImpressions = snippetData.reduce((s, d) => s + d.impressions, 0);
  const totalClicks = snippetData.reduce((s, d) => s + d.clicks, 0);
  const avgCTR = totalImpressions ? (totalClicks / totalImpressions * 100).toFixed(1) : 0;
  const totalRich = Object.values(richBreakdown).reduce((s, v) => s + v, 0);

  const historyWithRich = history.filter(h => h.rich_breakdown).slice(-7);
  const recentChanges = changes?.changes || [];

  return (
    <div>
      <Header title="Rich Results & Snippets" onRefresh={() => refresh(true)} loading={loading} />
      <div className="space-y-5 px-5 py-5">

        {/* Summary stats row */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <div className="rounded-2xl border border-purple-200 bg-gradient-to-br from-purple-50 to-white p-4 shadow-sm transition-all duration-200 hover:shadow-md hover:-translate-y-0.5">
            <div className="flex items-center gap-2 mb-1">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-purple-500 to-indigo-500 text-white shadow-sm">
                <Eye size={13} />
              </div>
              <span className="text-[10px] font-semibold uppercase text-purple-500">Impressions</span>
            </div>
            <p className="text-2xl font-extrabold text-purple-700">{totalImpressions.toLocaleString()}</p>
            <p className="text-[10px] text-purple-400 mt-0.5">90 day total</p>
          </div>
          <div className="rounded-2xl border border-blue-200 bg-gradient-to-br from-blue-50 to-white p-4 shadow-sm transition-all duration-200 hover:shadow-md hover:-translate-y-0.5">
            <div className="flex items-center gap-2 mb-1">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-blue-500 to-cyan-500 text-white shadow-sm">
                <MousePointerClick size={13} />
              </div>
              <span className="text-[10px] font-semibold uppercase text-blue-500">Clicks</span>
            </div>
            <p className="text-2xl font-extrabold text-blue-700">{totalClicks.toLocaleString()}</p>
            <p className="text-[10px] text-blue-400 mt-0.5">90 day total</p>
          </div>
          <div className="rounded-2xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-white p-4 shadow-sm transition-all duration-200 hover:shadow-md hover:-translate-y-0.5">
            <div className="flex items-center gap-2 mb-1">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-500 to-teal-500 text-white shadow-sm">
                <TrendingUp size={13} />
              </div>
              <span className="text-[10px] font-semibold uppercase text-emerald-500">Avg CTR</span>
            </div>
            <p className="text-2xl font-extrabold text-emerald-700">{avgCTR}%</p>
            <p className="text-[10px] text-emerald-400 mt-0.5">across all types</p>
          </div>
          <div className="rounded-2xl border border-amber-200 bg-gradient-to-br from-amber-50 to-white p-4 shadow-sm transition-all duration-200 hover:shadow-md hover:-translate-y-0.5">
            <div className="flex items-center gap-2 mb-1">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br from-amber-500 to-orange-500 text-white shadow-sm">
                <Package size={13} />
              </div>
              <span className="text-[10px] font-semibold uppercase text-amber-500">Types Found</span>
            </div>
            <p className="text-2xl font-extrabold text-amber-700">{snippetData.length}</p>
            <p className="text-[10px] text-amber-400 mt-0.5">snippet types active</p>
          </div>
        </div>

        {/* GSC Enhancement Reports */}
        {(gscEnh.product_snippets?.valid > 0 || gscEnh.merchant_listings?.valid > 0 || gscEnh.review_snippets?.valid > 0) && (
          <div>
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-slate-400">
              <span className="h-4 w-1 rounded-full bg-gradient-to-b from-emerald-400 to-emerald-600" />
              GSC Enhancement Reports
              <span className="ml-1 inline-flex items-center rounded-full bg-emerald-100 px-2 py-0.5 text-[9px] font-bold text-emerald-700">GOOGLE DATA</span>
            </h2>
            <p className="mb-3 text-xs text-slate-500">
              Valid structured data items as reported by Google Search Console. {gscEnh.last_updated ? `Last synced: ${gscEnh.last_updated}` : ''}
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              {[
                { data: gscEnh.product_snippets, label: 'Product Snippets', icon: Package, gradient: 'from-purple-500 to-indigo-500', border: 'border-purple-200', bg: 'bg-gradient-to-br from-purple-50 via-purple-50/50 to-white', text: 'text-purple-700', validColor: 'bg-emerald-500', invalidColor: 'bg-red-500' },
                { data: gscEnh.merchant_listings, label: 'Merchant Listings', icon: ShoppingCart, gradient: 'from-cyan-500 to-teal-500', border: 'border-cyan-200', bg: 'bg-gradient-to-br from-cyan-50 via-cyan-50/50 to-white', text: 'text-cyan-700', validColor: 'bg-emerald-500', invalidColor: 'bg-red-500' },
                { data: gscEnh.review_snippets, label: 'Review Snippets', icon: Star, gradient: 'from-amber-500 to-orange-500', border: 'border-amber-200', bg: 'bg-gradient-to-br from-amber-50 via-amber-50/50 to-white', text: 'text-amber-700', validColor: 'bg-emerald-500', invalidColor: 'bg-red-500' },
              ].map(item => {
                const valid = item.data?.valid || 0;
                const invalid = item.data?.invalid || 0;
                const total = valid + invalid;
                const issues = item.data?.issues || [];
                return (
                  <div key={item.label} className={`rounded-2xl border ${item.border} ${item.bg} p-5 shadow-sm transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5`}>
                    <div className="flex items-center gap-2.5 mb-4">
                      <div className={`flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br ${item.gradient} text-white shadow-md`}>
                        <item.icon size={18} />
                      </div>
                      <span className="text-sm font-bold text-slate-700">{item.label}</span>
                    </div>
                    <div className="flex gap-3 mb-4">
                      <div className="flex-1 rounded-xl bg-gradient-to-br from-emerald-500 to-emerald-600 p-3 text-center text-white shadow-sm">
                        <p className="text-[10px] font-semibold opacity-80">Valid</p>
                        <p className="text-2xl font-extrabold">{valid.toLocaleString()}</p>
                      </div>
                      <div className={`flex-1 rounded-xl ${invalid > 0 ? 'bg-gradient-to-br from-red-500 to-red-600 text-white shadow-sm' : 'bg-slate-200 text-slate-600'} p-3 text-center`}>
                        <p className="text-[10px] font-semibold opacity-80">Invalid</p>
                        <p className="text-2xl font-extrabold">{invalid.toLocaleString()}</p>
                        {invalid === 0 && <p className="text-[9px]">No critical issues</p>}
                      </div>
                    </div>
                    {total > 0 && (
                      <div className="h-3 overflow-hidden rounded-full bg-red-200/60">
                        <div className="h-full rounded-full bg-gradient-to-r from-emerald-400 to-emerald-500 transition-all duration-500" style={{ width: `${(valid / total * 100)}%` }} />
                      </div>
                    )}
                    {issues.length > 0 && (
                      <div className="mt-3 space-y-1.5">
                        <p className="text-[10px] font-semibold text-slate-500">Issues to improve:</p>
                        {issues.slice(0, 3).map((iss, j) => (
                          <div key={j} className="flex items-center justify-between rounded-lg bg-white/80 border border-slate-100 px-2.5 py-1.5 shadow-sm">
                            <span className="text-[10px] text-slate-600 truncate mr-2">{iss.issue}</span>
                            <span className="text-[10px] font-bold text-amber-600 whitespace-nowrap">{iss.count} items</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Rich Results Detected with Daily Comparison */}
        {totalRich > 0 && (
          <div>
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-slate-400">
              <span className="h-4 w-1 rounded-full bg-gradient-to-b from-purple-400 to-purple-600" />
              Detected Rich Results
              <DataSourceBadge source="pipeline_db" className="ml-1" />
            </h2>
            <p className="mb-3 text-xs text-slate-500">
              From {totalRich.toLocaleString()} inspected URLs. {todayRich && yesterdayRich ? 'Daily changes shown vs previous run.' : 'Run the pipeline again to see daily changes.'}
            </p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {RICH_CONFIG.map(rc => {
                const count = richBreakdown[rc.key] || 0;
                const pct = totalRich ? (count / totalRich * 100).toFixed(1) : 0;
                const prevCount = yesterdayRich ? (yesterdayRich[rc.key] || 0) : null;
                return (
                  <div key={rc.key} className={`rounded-2xl border ${rc.border} ${rc.bg} p-4 shadow-sm transition-all duration-200 hover:shadow-lg hover:-translate-y-1`}>
                    <div className="flex items-center gap-2 mb-3">
                      <div className={`flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br ${rc.gradient} text-white shadow-md`}>
                        <rc.icon size={16} />
                      </div>
                      <span className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{rc.label}</span>
                    </div>
                    <p className={`text-3xl font-extrabold ${rc.text}`}>{count.toLocaleString()}</p>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="text-[10px] text-slate-500">{pct}% of inspected</span>
                      <DeltaBadge current={count} previous={prevCount} invert={rc.key === 'None'} />
                    </div>
                    <div className="mt-2 h-2 overflow-hidden rounded-full bg-white/50">
                      <div className={`h-full rounded-full bg-gradient-to-r ${rc.gradient} transition-all duration-500`} style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Rich Results Trend Chart */}
        {historyWithRich.length > 1 && (
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
              <span className="h-4 w-1 rounded-full bg-gradient-to-b from-blue-400 to-blue-600" />
              Rich Results Trend
            </h3>
            <ResponsiveContainer width="100%" height={220}>
              <AreaChart data={historyWithRich.map(h => ({
                date: h.date,
                Product: h.rich_breakdown?.Product || 0,
                Merchant: h.rich_breakdown?.MerchantListing || 0,
                Review: h.rich_breakdown?.Review || 0,
              }))}>
                <defs>
                  <linearGradient id="prodGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#a855f7" stopOpacity={0.35} />
                    <stop offset="50%" stopColor="#a855f7" stopOpacity={0.1} />
                    <stop offset="100%" stopColor="#a855f7" stopOpacity={0.01} />
                  </linearGradient>
                  <linearGradient id="merchGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#06b6d4" stopOpacity={0.35} />
                    <stop offset="50%" stopColor="#06b6d4" stopOpacity={0.1} />
                    <stop offset="100%" stopColor="#06b6d4" stopOpacity={0.01} />
                  </linearGradient>
                  <linearGradient id="revGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#f59e0b" stopOpacity={0.35} />
                    <stop offset="50%" stopColor="#f59e0b" stopOpacity={0.1} />
                    <stop offset="100%" stopColor="#f59e0b" stopOpacity={0.01} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#94a3b8' }} tickFormatter={d => d.slice(5)} axisLine={false} />
                <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Area type="monotoneX" dataKey="Product" stroke="#a855f7" fill="url(#prodGrad)" strokeWidth={2.5} dot={{ r: 3, fill: '#a855f7', strokeWidth: 2, stroke: '#fff' }} activeDot={{ r: 5, stroke: '#a855f7', strokeWidth: 2, fill: '#fff' }} />
                <Area type="monotoneX" dataKey="Merchant" stroke="#06b6d4" fill="url(#merchGrad)" strokeWidth={2.5} dot={{ r: 3, fill: '#06b6d4', strokeWidth: 2, stroke: '#fff' }} activeDot={{ r: 5, stroke: '#06b6d4', strokeWidth: 2, fill: '#fff' }} />
                <Area type="monotoneX" dataKey="Review" stroke="#f59e0b" fill="url(#revGrad)" strokeWidth={2.5} dot={{ r: 3, fill: '#f59e0b', strokeWidth: 2, stroke: '#fff' }} activeDot={{ r: 5, stroke: '#f59e0b', strokeWidth: 2, fill: '#fff' }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Daily Comparison Table */}
        {todayRich && yesterdayRich && (
          <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-sm">
            <div className="border-b border-slate-100 bg-slate-50 px-4 py-3 flex items-center justify-between">
              <h3 className="flex items-center gap-2 text-xs font-semibold text-slate-600">
                <span className="h-3 w-1 rounded-full bg-gradient-to-b from-orange-400 to-orange-600" />
                Rich Results: Today vs Previous Run
              </h3>
              <span className="text-[10px] text-slate-400">{today?.date} vs {yesterday?.date}</span>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-100 text-left">
                    <th className="px-4 py-2.5 text-xs font-semibold text-slate-500">Type</th>
                    <th className="px-4 py-2.5 text-right text-xs font-semibold text-slate-500">Previous</th>
                    <th className="px-4 py-2.5 text-right text-xs font-semibold text-slate-500">Current</th>
                    <th className="px-4 py-2.5 text-right text-xs font-semibold text-slate-500">Change</th>
                    <th className="px-4 py-2.5 text-xs font-semibold text-slate-500">Trend</th>
                  </tr>
                </thead>
                <tbody>
                  {RICH_CONFIG.filter(rc => rc.key !== 'None').map((rc, idx) => {
                    const curr = todayRich[rc.key] || 0;
                    const prev = yesterdayRich[rc.key] || 0;
                    const diff = curr - prev;
                    return (
                      <tr key={rc.key} className={`border-b border-slate-50 transition-colors duration-150 hover:bg-slate-50/80 ${idx % 2 === 1 ? 'bg-slate-25' : ''}`}>
                        <td className="px-4 py-3 flex items-center gap-2">
                          <div className={`flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br ${rc.gradient} text-white shadow-sm`}>
                            <rc.icon size={13} />
                          </div>
                          <span className="font-medium text-slate-700">{rc.label}</span>
                        </td>
                        <td className="px-4 py-3 text-right text-slate-500">{prev.toLocaleString()}</td>
                        <td className="px-4 py-3 text-right font-semibold text-slate-800">{curr.toLocaleString()}</td>
                        <td className="px-4 py-3 text-right">
                          <span className={`inline-block rounded-lg px-2 py-0.5 text-xs font-semibold ${diff > 0 ? 'bg-emerald-50 text-emerald-700' : diff < 0 ? 'bg-red-50 text-red-600' : 'bg-slate-50 text-slate-500'}`}>
                            <DeltaBadge current={curr} previous={prev} />
                          </span>
                        </td>
                        <td className="px-4 py-3">
                          {diff > 0 && <span className="rounded-full bg-gradient-to-r from-emerald-100 to-emerald-50 px-2.5 py-0.5 text-[10px] font-semibold text-emerald-700 shadow-sm">Growing</span>}
                          {diff < 0 && <span className="rounded-full bg-gradient-to-r from-red-100 to-red-50 px-2.5 py-0.5 text-[10px] font-semibold text-red-700 shadow-sm">Declining</span>}
                          {diff === 0 && <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-[10px] font-semibold text-slate-500">Stable</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Search Analytics by Snippet Type */}
        <div>
          <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-slate-400">
            <span className="h-4 w-1 rounded-full bg-gradient-to-b from-indigo-400 to-indigo-600" />
            Search Performance by Type
            <DataSourceBadge source="search_analytics" className="ml-1" />
          </h2>
          <p className="mb-3 text-xs text-slate-500">
            How each rich result type performs in Google Search (last 90 days).
          </p>

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {snippetData.map((s) => (
              <div key={s.key} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition-all duration-200 hover:shadow-lg hover:-translate-y-0.5">
                <div className="mb-3 flex items-center gap-2">
                  <div className="h-4 w-4 rounded-full shadow-sm ring-2 ring-white" style={{ background: s.color }} />
                  <span className="text-sm font-semibold text-slate-700">{s.name}</span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-xl bg-gradient-to-br from-slate-50 to-white border border-slate-100 p-2.5 text-center">
                    <p className="text-lg font-extrabold text-slate-800">{s.impressions.toLocaleString()}</p>
                    <p className="text-[10px] text-slate-400">Impressions</p>
                  </div>
                  <div className="rounded-xl bg-gradient-to-br from-slate-50 to-white border border-slate-100 p-2.5 text-center">
                    <p className="text-lg font-extrabold text-slate-800">{s.clicks.toLocaleString()}</p>
                    <p className="text-[10px] text-slate-400">Clicks</p>
                  </div>
                </div>
                <div className="mt-3 flex items-center justify-between text-xs">
                  <span className="text-slate-500">CTR: <span className="font-bold text-slate-700">{s.ctr}%</span></span>
                  <span className="text-slate-500">Avg Pos: <span className="font-bold text-slate-700">{s.position}</span></span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full transition-all duration-500" style={{ background: `linear-gradient(90deg, ${s.color}, ${s.color}88)`, width: `${totalImpressions ? (s.impressions / totalImpressions * 100) : 0}%` }} />
                </div>
                <p className="mt-1 text-[10px] text-slate-400 text-right">{totalImpressions ? (s.impressions / totalImpressions * 100).toFixed(1) : 0}% share</p>
              </div>
            ))}
          </div>
        </div>

        {/* Charts row */}
        <div className="grid gap-3 lg:grid-cols-2">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
              <span className="h-4 w-1 rounded-full bg-gradient-to-b from-violet-400 to-violet-600" />
              Impression Share
            </h3>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={snippetData.map(d => ({ name: d.name, value: d.impressions, color: d.color }))}
                  dataKey="value" nameKey="name" cx="50%" cy="50%"
                  innerRadius={55} outerRadius={95} paddingAngle={3} strokeWidth={0}
                >
                  {snippetData.map((d, i) => <Cell key={i} fill={d.color} />)}
                </Pie>
                <Tooltip formatter={(v) => (v ?? 0).toLocaleString()} />
              </PieChart>
            </ResponsiveContainer>
            <div className="mt-2 flex flex-wrap justify-center gap-3">
              {snippetData.map(d => (
                <span key={d.key} className="inline-flex items-center gap-1.5 text-[10px] text-slate-500">
                  <span className="h-2 w-2 rounded-full" style={{ background: d.color }} />
                  {d.name}
                </span>
              ))}
            </div>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
              <span className="h-4 w-1 rounded-full bg-gradient-to-b from-cyan-400 to-cyan-600" />
              Clicks by Type
            </h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={snippetData} layout="vertical" margin={{ left: 10 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" horizontal={false} />
                <XAxis type="number" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} />
                <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="clicks" radius={[0, 8, 8, 0]} barSize={22}>
                  {snippetData.map((d, i) => <Cell key={i} fill={d.color} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Full comparison table */}
        <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-sm">
          <div className="border-b border-slate-100 bg-slate-50 px-4 py-3">
            <h3 className="flex items-center gap-2 text-xs font-semibold text-slate-600">
              <span className="h-3 w-1 rounded-full bg-gradient-to-b from-slate-400 to-slate-600" />
              Search Analytics Comparison
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left">
                  <th className="px-4 py-2.5 font-semibold text-slate-600">Type</th>
                  <th className="px-4 py-2.5 text-right font-semibold text-slate-600">Impressions</th>
                  <th className="px-4 py-2.5 text-right font-semibold text-slate-600">Clicks</th>
                  <th className="px-4 py-2.5 text-right font-semibold text-slate-600">CTR</th>
                  <th className="px-4 py-2.5 text-right font-semibold text-slate-600">Avg Position</th>
                  <th className="px-4 py-2.5 text-right font-semibold text-slate-600">Share%</th>
                </tr>
              </thead>
              <tbody>
                {[...snippetData].sort((a, b) => b.impressions - a.impressions).map((d, idx) => (
                  <tr key={d.key} className={`border-b border-slate-50 transition-colors duration-150 hover:bg-slate-50/80 ${idx % 2 === 1 ? 'bg-slate-50/40' : ''}`}>
                    <td className="px-4 py-2.5">
                      <span className="flex items-center gap-2">
                        <span className="h-2.5 w-2.5 rounded-full shadow-sm ring-2 ring-white" style={{ background: d.color }} />
                        <span className="font-medium">{d.name}</span>
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-right font-semibold">{d.impressions.toLocaleString()}</td>
                    <td className="px-4 py-2.5 text-right">{d.clicks.toLocaleString()}</td>
                    <td className="px-4 py-2.5 text-right">{d.ctr}%</td>
                    <td className="px-4 py-2.5 text-right">{d.position}</td>
                    <td className="px-4 py-2.5 text-right text-slate-500">{totalImpressions ? (d.impressions / totalImpressions * 100).toFixed(1) : 0}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Recent URL Status Changes */}
        {recentChanges.length > 0 && (
          <div>
            <h2 className="mb-3 flex items-center gap-2 text-sm font-semibold uppercase tracking-wider text-slate-400">
              <span className="h-4 w-1 rounded-full bg-gradient-to-b from-rose-400 to-rose-600" />
              Recent Status Changes
              <DataSourceBadge source="pipeline_db" className="ml-1" />
            </h2>
            <div className="rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-sm">
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b border-slate-100 bg-slate-50 text-left">
                      <th className="px-4 py-2.5 font-semibold text-slate-500">Date</th>
                      <th className="px-4 py-2.5 font-semibold text-slate-500">Type</th>
                      <th className="px-4 py-2.5 font-semibold text-slate-500">URL</th>
                      <th className="px-4 py-2.5 font-semibold text-slate-500">Old Status</th>
                      <th className="px-4 py-2.5 font-semibold text-slate-500">New Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {recentChanges.slice(0, 20).map((c, i) => (
                      <tr key={i} className={`border-b border-slate-50 transition-colors duration-150 hover:bg-slate-50/80 ${i % 2 === 1 ? 'bg-slate-50/40' : ''}`}>
                        <td className="px-4 py-2.5 text-slate-500 whitespace-nowrap">{c.date}</td>
                        <td className="px-4 py-2.5">
                          {c.type === 'newly_indexed' && <span className="rounded-full bg-gradient-to-r from-emerald-100 to-emerald-50 px-2.5 py-0.5 text-[10px] font-semibold text-emerald-700 shadow-sm">Indexed</span>}
                          {c.type === 'dropped_from_index' && <span className="rounded-full bg-gradient-to-r from-red-100 to-red-50 px-2.5 py-0.5 text-[10px] font-semibold text-red-700 shadow-sm">Dropped</span>}
                          {c.type === 'status_change' && <span className="rounded-full bg-gradient-to-r from-amber-100 to-amber-50 px-2.5 py-0.5 text-[10px] font-semibold text-amber-700 shadow-sm">Changed</span>}
                        </td>
                        <td className="px-4 py-2.5 max-w-xs truncate text-slate-600" title={c.url}>{c.url?.replace('https://rudraretails.com/', '/')}</td>
                        <td className="px-4 py-2.5 text-slate-500">{c.old_coverage || '—'}</td>
                        <td className="px-4 py-2.5 font-medium text-slate-700">{c.new_coverage || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {changes?.total > 20 && (
                <div className="border-t border-slate-100 bg-slate-50 px-4 py-2.5 text-center">
                  <span className="text-[10px] text-slate-500">{changes.total - 20} more changes — check the Indexing page for full history</span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Note */}
        <div className="flex gap-2 rounded-2xl border border-slate-200 bg-gradient-to-r from-slate-50 to-white p-4 text-xs text-slate-600 shadow-sm">
          <Info size={16} className="mt-0.5 shrink-0 text-slate-400" />
          <div>
            <p><strong>Two data sources shown:</strong></p>
            <p className="mt-1"><strong>URL Inspection (top)</strong> — which specific URLs have Product/Merchant/Review structured data detected. Daily comparison shows how counts change between pipeline runs.</p>
            <p className="mt-1"><strong>Search Analytics (below)</strong> — aggregate performance (impressions, clicks, CTR) for each rich result type across your site over 90 days.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
