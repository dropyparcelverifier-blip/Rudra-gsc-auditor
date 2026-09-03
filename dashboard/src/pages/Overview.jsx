import { Globe, CheckCircle, AlertTriangle, Package, ShoppingCart, Star, TrendingUp, TrendingDown, MousePointerClick, Eye, Monitor, Smartphone, Tablet, Search, ArrowUpRight, ArrowDownRight, Minus } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, Legend, PieChart, Pie, Cell, BarChart, Bar } from 'recharts';
import StatCard from '../components/StatCard';
import Header from '../components/Header';
import DataSourceBadge from '../components/DataSourceBadge';
import IndexDonut from '../components/IndexDonut';
import { computePipelineStats } from '../lib/pipelineStats';

const DEVICE_ICONS = { DESKTOP: Monitor, MOBILE: Smartphone, TABLET: Tablet };
const DEVICE_COLORS = { DESKTOP: '#3b82f6', MOBILE: '#22c55e', TABLET: '#a855f7' };

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 shadow-lg text-xs">
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

function DeltaBadge({ current, previous, suffix = '', invert = false }) {
  if (previous == null || previous === 0) return null;
  const diff = current - previous;
  if (diff === 0) return <span className="inline-flex items-center gap-0.5 text-[10px] text-slate-400"><Minus size={10} /> no change</span>;
  const isUp = diff > 0;
  const isGood = invert ? !isUp : isUp;
  const Icon = isUp ? ArrowUpRight : ArrowDownRight;
  return (
    <span className={`inline-flex items-center gap-0.5 text-[10px] font-semibold ${isGood ? 'text-emerald-600' : 'text-red-500'}`}>
      <Icon size={10} />
      {isUp ? '+' : ''}{diff.toLocaleString()}{suffix}
    </span>
  );
}

export default function Overview({ data, loading, refresh }) {
  if (!data) return (
    <div className="flex h-96 flex-col items-center justify-center gap-3 text-slate-400">
      <div className="h-12 w-12 rounded-full border-[3px] border-slate-200 border-t-blue-500 border-r-cyan-400 animate-spin" />
      <span className="text-sm font-medium animate-pulse">Loading live data from GSC...</span>
    </div>
  );

  const { sitemaps, snippets, search_performance, devices, countries, pipeline, accounts, daily_history, gsc_enhancements, is_live, fetched_at, errors } = data;
  const sm = sitemaps || {};
  const perf = search_performance || {};
  const perfDaily = (perf.daily || []).slice(-28);
  const pl = pipeline || {};
  const richBreakdown = pl.rich_breakdown || {};
  const gscEnh = gsc_enhancements || {};

  const { pipelineTotal, pipelineIndexed, pipelineNotIndexed, pipelineRate, totalSubmitted, scanPct } = computePipelineStats(data);

  const history = daily_history || [];
  const today = history.length > 0 ? history[history.length - 1] : null;
  const yesterday = history.length > 1 ? history[history.length - 2] : null;
  const historyLast7 = history.slice(-7);

  return (
    <div>
      <Header title="Overview" onRefresh={() => refresh(true)} loading={loading} />

      <div className="space-y-5 px-5 py-5">
        {/* Live status badge */}
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-semibold ${is_live ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
            <span className={`h-2 w-2 rounded-full ${is_live ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
            {is_live ? 'LIVE' : 'OFFLINE'}
          </span>
          {fetched_at && <span>Last updated: {fetched_at}</span>}
          {Object.keys(errors || {}).length > 0 && <span className="text-amber-600">{Object.keys(errors).length} API warning(s)</span>}
        </div>

        {/* Indexing Status — with Donut */}
        <div>
          <h2 className="mb-3 flex items-center gap-2 text-base font-semibold uppercase tracking-wider text-slate-400">
            <span className="h-2 w-2 rounded-full bg-blue-500" />
            Indexing Status
            <DataSourceBadge source="pipeline_db" className="ml-2" />
          </h2>
          <div className="rounded-2xl border-2 border-transparent bg-white p-4 shadow-sm" style={{ backgroundImage: 'linear-gradient(white, white), linear-gradient(135deg, #3b82f6, #06b6d4)', backgroundOrigin: 'border-box', backgroundClip: 'padding-box, border-box' }}>
            <div className="flex flex-col lg:flex-row gap-6 items-center">
              <div className="flex-shrink-0">
                <IndexDonut indexed={pipelineIndexed} notIndexed={pipelineNotIndexed} />
              </div>

              <div className="flex-1 grid grid-cols-2 gap-2.5 w-full">
                <div className="rounded-2xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-white p-4 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300">
                  <div className="flex items-center gap-2 mb-1">
                    <CheckCircle size={14} className="text-emerald-600" />
                    <span className="text-[10px] font-semibold uppercase text-emerald-600">Indexed</span>
                  </div>
                  <p className="text-2xl font-extrabold text-emerald-700">{pipelineIndexed.toLocaleString()}</p>
                  <div className="mt-1 flex items-center gap-2">
                    <span className="text-[10px] text-emerald-600">{pipelineRate}%</span>
                    <DeltaBadge current={today?.indexed} previous={yesterday?.indexed} />
                  </div>
                </div>

                <div className="rounded-2xl border border-red-200 bg-gradient-to-br from-red-50 to-white p-4 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300">
                  <div className="flex items-center gap-2 mb-1">
                    <AlertTriangle size={14} className="text-red-500" />
                    <span className="text-[10px] font-semibold uppercase text-red-500">Not Indexed</span>
                  </div>
                  <p className="text-2xl font-extrabold text-red-600">{pipelineNotIndexed.toLocaleString()}</p>
                  <div className="mt-1 flex items-center gap-2">
                    <span className="text-[10px] text-red-500">{pipelineTotal ? (100 - pipelineRate).toFixed(1) : 0}% gap</span>
                    <DeltaBadge current={today?.not_indexed} previous={yesterday?.not_indexed} invert />
                  </div>
                </div>

                <div className="rounded-2xl border border-blue-200 bg-gradient-to-br from-blue-50 to-white p-4 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300">
                  <div className="flex items-center gap-2 mb-1">
                    <Globe size={14} className="text-blue-600" />
                    <span className="text-[10px] font-semibold uppercase text-blue-600">In Sitemaps</span>
                  </div>
                  <p className="text-2xl font-extrabold text-blue-700">{totalSubmitted.toLocaleString()}</p>
                  <span className="text-[10px] text-blue-500">Sitemaps API (LIVE)</span>
                </div>

                <div className="rounded-2xl border border-amber-200 bg-gradient-to-br from-amber-50 to-white p-4 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300">
                  <div className="flex items-center gap-2 mb-1">
                    <Search size={14} className="text-amber-600" />
                    <span className="text-[10px] font-semibold uppercase text-amber-600">Scan Progress</span>
                  </div>
                  <p className="text-2xl font-extrabold text-amber-700">{scanPct}%</p>
                  <div className="mt-1 flex items-center gap-2">
                    <span className="text-[10px] text-amber-500">{pipelineTotal.toLocaleString()} of {totalSubmitted.toLocaleString()}</span>
                    <DeltaBadge current={today?.total_urls} previous={yesterday?.total_urls} suffix=" new" />
                  </div>
                </div>
              </div>
            </div>

            {/* Progress bars */}
            <div className="mt-4 space-y-2.5">
              <div>
                <div className="mb-1.5 flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-600">Inspection Progress</span>
                  <span className="text-xs text-slate-500">{pipelineTotal.toLocaleString()} / {totalSubmitted.toLocaleString()} ({scanPct}%)</span>
                </div>
                <div className="h-3.5 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-gradient-to-r from-blue-500 via-blue-400 to-cyan-500 transition-all duration-700"
                    style={{ width: `${Math.min(scanPct, 100)}%` }} />
                </div>
              </div>
              <div>
                <div className="mb-1.5 flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-600">Index Rate</span>
                  <span className="text-xs font-semibold text-emerald-700">{pipelineRate}% indexed</span>
                </div>
                <div className="h-2.5 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-gradient-to-r from-emerald-500 via-emerald-400 to-cyan-500 transition-all duration-700"
                    style={{ width: `${pipelineRate}%` }} />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Daily Trend — mini chart */}
        {historyLast7.length > 1 && (
          <div>
            <h2 className="mb-3 flex items-center gap-2 text-base font-semibold uppercase tracking-wider text-slate-400">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              Daily Progress (Last 7 runs)
            </h2>
            <div className="grid gap-3 lg:grid-cols-2">
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300">
                <h3 className="mb-2 text-xs font-semibold text-slate-600">Indexed vs Not Indexed</h3>
                <ResponsiveContainer width="100%" height={180}>
                  <AreaChart data={historyLast7}>
                    <defs>
                      <linearGradient id="idxGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#22c55e" stopOpacity={0.3} />
                        <stop offset="100%" stopColor="#22c55e" stopOpacity={0.02} />
                      </linearGradient>
                      <linearGradient id="notIdxGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#ef4444" stopOpacity={0.3} />
                        <stop offset="100%" stopColor="#ef4444" stopOpacity={0.02} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#94a3b8' }} tickFormatter={d => d.slice(5)} axisLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Area type="monotone" dataKey="indexed" stroke="#22c55e" fill="url(#idxGrad)" name="Indexed" strokeWidth={2} dot={{ r: 3, fill: '#22c55e' }} />
                    <Area type="monotone" dataKey="not_indexed" stroke="#ef4444" fill="url(#notIdxGrad)" name="Not Indexed" strokeWidth={2} dot={{ r: 3, fill: '#ef4444' }} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300">
                <h3 className="mb-2 text-xs font-semibold text-slate-600">Daily Inspections & Submissions</h3>
                <ResponsiveContainer width="100%" height={180}>
                  <BarChart data={historyLast7}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                    <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#94a3b8' }} tickFormatter={d => d.slice(5)} axisLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Bar dataKey="checked" name="Inspected" fill="#3b82f6" radius={[4, 4, 0, 0]} barSize={20} />
                    <Bar dataKey="submitted" name="Submitted" fill="#f97316" radius={[4, 4, 0, 0]} barSize={20} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Daily changes table */}
            {yesterday && today && (
              <div className="mt-3 rounded-2xl border border-slate-200 bg-white overflow-hidden shadow-sm">
                <div className="border-b border-slate-100 bg-slate-50 px-4 py-2.5">
                  <h3 className="text-xs font-semibold text-slate-600">Today vs Yesterday</h3>
                </div>
                <div className="grid grid-cols-2 divide-x divide-slate-100 sm:grid-cols-4">
                  {[
                    { label: 'Indexed', today: today.indexed, yesterday: yesterday.indexed, color: 'text-emerald-700', bg: 'bg-emerald-50/50' },
                    { label: 'Not Indexed', today: today.not_indexed, yesterday: yesterday.not_indexed, color: 'text-red-600', bg: 'bg-red-50/50', invert: true },
                    { label: 'Inspected', today: today.checked, yesterday: yesterday.checked, color: 'text-blue-700', bg: 'bg-blue-50/50' },
                    { label: 'Submitted', today: today.submitted, yesterday: yesterday.submitted, color: 'text-orange-700', bg: 'bg-orange-50/50' },
                  ].map(m => (
                    <div key={m.label} className={`px-4 py-3.5 text-center ${m.bg}`}>
                      <p className="text-[10px] font-semibold uppercase text-slate-400">{m.label}</p>
                      <p className={`text-lg font-extrabold ${m.color}`}>{(m.today || 0).toLocaleString()}</p>
                      <DeltaBadge current={m.today || 0} previous={m.yesterday || 0} invert={m.invert} />
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Rich Results Detected — Pipeline + GSC */}
        {Object.keys(richBreakdown).length > 0 && (
          <div>
            <h2 className="mb-3 flex items-center gap-2 text-base font-semibold uppercase tracking-wider text-slate-400">
              <span className="h-2 w-2 rounded-full bg-purple-500" />
              Rich Results Detected
              <DataSourceBadge source="pipeline_db" className="ml-2" />
            </h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                { key: 'Product', gscKey: 'product_snippets', label: 'Product Snippets', icon: Package, gradient: 'from-purple-500 to-indigo-500', border: 'border-purple-200', bg: 'bg-gradient-to-br from-purple-50 to-white', text: 'text-purple-700' },
                { key: 'MerchantListing', gscKey: 'merchant_listings', label: 'Merchant Listings', icon: ShoppingCart, gradient: 'from-cyan-500 to-teal-500', border: 'border-cyan-200', bg: 'bg-gradient-to-br from-cyan-50 to-white', text: 'text-cyan-700' },
                { key: 'Review', gscKey: 'review_snippets', label: 'Review Snippets', icon: Star, gradient: 'from-amber-500 to-orange-500', border: 'border-amber-200', bg: 'bg-gradient-to-br from-amber-50 to-white', text: 'text-amber-700' },
                { key: 'None', gscKey: null, label: 'No Rich Results', icon: AlertTriangle, gradient: 'from-slate-400 to-slate-500', border: 'border-slate-200', bg: 'bg-gradient-to-br from-slate-50 to-white', text: 'text-slate-600' },
              ].map(rc => {
                const count = richBreakdown[rc.key] || 0;
                const total = Object.values(richBreakdown).reduce((s, v) => s + v, 0);
                const pct = total ? (count / total * 100).toFixed(1) : 0;
                const gscValid = rc.gscKey ? (gscEnh[rc.gscKey]?.valid || 0) : 0;
                return (
                  <div key={rc.key} className={`rounded-2xl border ${rc.border} ${rc.bg} p-4 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300`}>
                    <div className="flex items-center gap-2 mb-3">
                      <div className={`flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br ${rc.gradient} text-white shadow-sm`}>
                        <rc.icon size={15} />
                      </div>
                      <span className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{rc.label}</span>
                    </div>
                    <p className={`text-2xl font-extrabold ${rc.text}`}>{count.toLocaleString()}</p>
                    {gscValid > 0 && (
                      <p className="mt-1 text-[10px] text-emerald-600 font-semibold">{gscValid.toLocaleString()} valid in GSC</p>
                    )}
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/50">
                      <div className={`h-full rounded-full bg-gradient-to-r ${rc.gradient}`} style={{ width: `${pct}%` }} />
                    </div>
                    <p className="mt-1.5 text-[10px] text-slate-500">{pct}% of inspected</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Search Performance — LIVE */}
        {perfDaily.length > 0 && (
          <div>
            <h2 className="mb-3 flex items-center gap-2 text-base font-semibold uppercase tracking-wider text-slate-400">
              <span className="h-2 w-2 rounded-full bg-indigo-500" />
              Search Performance (28 days) <DataSourceBadge source="live" className="ml-1" />
            </h2>
            <div className="grid grid-cols-3 gap-2.5 mb-3">
              <div className="rounded-2xl border border-blue-200 bg-gradient-to-br from-blue-50 to-white p-4 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300">
                <div className="flex items-center gap-2 mb-1">
                  <MousePointerClick size={14} className="text-blue-600" />
                  <span className="text-[10px] font-semibold uppercase text-blue-500">Total Clicks</span>
                </div>
                <p className="text-2xl font-extrabold text-blue-700">{(perf.total_clicks || 0).toLocaleString()}</p>
              </div>
              <div className="rounded-2xl border border-purple-200 bg-gradient-to-br from-purple-50 to-white p-4 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300">
                <div className="flex items-center gap-2 mb-1">
                  <Eye size={14} className="text-purple-600" />
                  <span className="text-[10px] font-semibold uppercase text-purple-500">Impressions</span>
                </div>
                <p className="text-2xl font-extrabold text-purple-700">{(perf.total_impressions || 0).toLocaleString()}</p>
              </div>
              <div className="rounded-2xl border border-emerald-200 bg-gradient-to-br from-emerald-50 to-white p-4 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300">
                <div className="flex items-center gap-2 mb-1">
                  <TrendingUp size={14} className="text-emerald-600" />
                  <span className="text-[10px] font-semibold uppercase text-emerald-500">Avg CTR</span>
                </div>
                <p className="text-2xl font-extrabold text-emerald-700">{perf.avg_ctr || 0}%</p>
              </div>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <ResponsiveContainer width="100%" height={280}>
                <AreaChart data={perfDaily}>
                  <defs>
                    <linearGradient id="clicksGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.02} />
                    </linearGradient>
                    <linearGradient id="imprGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#a855f7" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#a855f7" stopOpacity={0.02} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#94a3b8' }} tickFormatter={d => d.slice(5)} axisLine={false} />
                  <YAxis yAxisId="left" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} />
                  <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Area yAxisId="left" type="monotone" dataKey="clicks" stroke="#3b82f6" fill="url(#clicksGrad)" name="Clicks" strokeWidth={2.5} dot={false} activeDot={{ r: 5, stroke: '#3b82f6', strokeWidth: 2, fill: '#fff' }} />
                  <Area yAxisId="right" type="monotone" dataKey="impressions" stroke="#a855f7" fill="url(#imprGrad)" name="Impressions" strokeWidth={2.5} dot={false} activeDot={{ r: 5, stroke: '#a855f7', strokeWidth: 2, fill: '#fff' }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Rich Results Performance — LIVE */}
        {snippets && Object.keys(snippets).length > 0 && (
          <div>
            <h2 className="mb-3 flex items-center gap-2 text-base font-semibold uppercase tracking-wider text-slate-400">
              <span className="h-2 w-2 rounded-full bg-amber-500" />
              Rich Results Performance <DataSourceBadge source="search_analytics" className="ml-1" />
            </h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {[
                { key: 'PRODUCT_SNIPPETS', label: 'Product Snippets', icon: Package, gradient: 'from-purple-500 to-indigo-500', border: 'border-purple-200', bg: 'bg-gradient-to-br from-purple-50 to-white' },
                { key: 'MERCHANT_LISTINGS', label: 'Merchant Listings', icon: ShoppingCart, gradient: 'from-cyan-500 to-teal-500', border: 'border-cyan-200', bg: 'bg-gradient-to-br from-cyan-50 to-white' },
                { key: 'REVIEW_SNIPPET', label: 'Review Snippets', icon: Star, gradient: 'from-amber-500 to-orange-500', border: 'border-amber-200', bg: 'bg-gradient-to-br from-amber-50 to-white' },
              ].map(sc => {
                const s = snippets[sc.key] || {};
                return (
                  <div key={sc.key} className={`rounded-2xl border ${sc.border} ${sc.bg} p-5 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300`}>
                    <div className="flex items-center gap-2 mb-3">
                      <div className={`flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br ${sc.gradient} text-white shadow-sm`}>
                        <sc.icon size={16} />
                      </div>
                      <span className="text-xs font-semibold text-slate-600">{sc.label}</span>
                    </div>
                    <p className="text-2xl font-extrabold text-slate-800">{(s.impressions || 0).toLocaleString()}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">impressions</p>
                    <div className="mt-3 grid grid-cols-2 gap-2">
                      <div className="rounded-lg bg-white/80 border border-slate-100 p-2 text-center">
                        <p className="text-sm font-bold text-slate-700">{(s.clicks || 0).toLocaleString()}</p>
                        <p className="text-[9px] text-slate-400">clicks</p>
                      </div>
                      <div className="rounded-lg bg-white/80 border border-slate-100 p-2 text-center">
                        <p className="text-sm font-bold text-slate-700">{s.ctr || 0}%</p>
                        <p className="text-[9px] text-slate-400">CTR</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Device + Country split */}
        <div className="grid gap-3 lg:grid-cols-2">
          {devices && Object.keys(devices).length > 0 && (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300">
              <h3 className="mb-4 text-sm font-semibold text-slate-700">
                Device Split <DataSourceBadge source="live" className="ml-1" />
              </h3>
              <div className="flex gap-6">
                <div className="flex-shrink-0">
                  <ResponsiveContainer width={100} height={100}>
                    <PieChart>
                      <Pie
                        data={Object.entries(devices).map(([d, s]) => ({ name: d, value: s.clicks || 0 }))}
                        dataKey="value" cx="50%" cy="50%" innerRadius={28} outerRadius={45}
                        paddingAngle={3} strokeWidth={0}
                      >
                        {Object.keys(devices).map((d, i) => (
                          <Cell key={i} fill={DEVICE_COLORS[d] || '#6366f1'} />
                        ))}
                      </Pie>
                    </PieChart>
                  </ResponsiveContainer>
                </div>
                <div className="flex-1 space-y-3">
                  {Object.entries(devices).map(([device, stats]) => {
                    const Icon = DEVICE_ICONS[device] || Monitor;
                    const total = Object.values(devices).reduce((s, d) => s + (d.clicks || 0), 0);
                    const pct = total ? (stats.clicks / total * 100).toFixed(0) : 0;
                    return (
                      <div key={device}>
                        <div className="flex items-center justify-between text-xs mb-1">
                          <span className="flex items-center gap-2 font-semibold text-slate-700">
                            <Icon size={14} style={{ color: DEVICE_COLORS[device] || '#6366f1' }} />
                            {device}
                          </span>
                          <span className="text-slate-500">{(stats.clicks || 0).toLocaleString()} clicks &bull; {stats.ctr || 0}% CTR</span>
                        </div>
                        <div className="h-2.5 overflow-hidden rounded-full bg-slate-100">
                          <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: DEVICE_COLORS[device] || '#6366f1' }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          )}

          {countries && countries.length > 0 && (
            <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300">
              <h3 className="mb-4 text-sm font-semibold text-slate-700">
                Top Countries <DataSourceBadge source="live" className="ml-1" />
              </h3>
              <div className="space-y-2">
                {countries.slice(0, 8).map((c, i) => {
                  const maxClicks = countries[0]?.clicks || 1;
                  const pct = (c.clicks / maxClicks * 100).toFixed(0);
                  return (
                    <div key={c.country} className="group flex items-center gap-3 rounded-lg px-2 py-1.5 transition-colors hover:bg-slate-50">
                      <span className="flex h-6 w-6 items-center justify-center rounded-full bg-slate-100 text-[10px] font-bold text-slate-500 group-hover:bg-blue-100 group-hover:text-blue-600">
                        {i + 1}
                      </span>
                      <span className="w-16 text-xs font-semibold text-slate-700">{c.country}</span>
                      <div className="flex-1 h-2 overflow-hidden rounded-full bg-slate-100">
                        <div className="h-full rounded-full bg-blue-400 transition-all duration-300" style={{ width: `${pct}%` }} />
                      </div>
                      <span className="text-[10px] text-slate-500 w-24 text-right">{(c.clicks || 0).toLocaleString()} / {(c.impressions || 0).toLocaleString()}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {/* Daily API Quotas */}
        {accounts && accounts.length > 0 && (() => {
          const totalInspUsed = accounts.reduce((s, a) => s + (a.inspect_used || 0), 0);
          const totalIdxUsed = accounts.reduce((s, a) => s + (a.index_used || 0), 0);
          const totalIdxLimit = 200;
          const inspPct = Math.min(100, totalInspUsed / 2000 * 100);
          const idxPct = totalIdxLimit ? Math.min(100, totalIdxUsed / totalIdxLimit * 100) : 0;
          return (
            <div>
              <h2 className="mb-3 flex items-center gap-2 text-base font-semibold uppercase tracking-wider text-slate-400">
                <span className="h-2 w-2 rounded-full bg-orange-500" />
                Daily API Quotas ({accounts.length} accounts)
              </h2>
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-blue-200 bg-gradient-to-br from-blue-100 via-blue-50 to-white p-4 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="font-semibold text-blue-800">URL Inspection (per property)</span>
                    <span className="font-bold text-blue-900">{totalInspUsed.toLocaleString()} / 2,000</span>
                  </div>
                  <div className="h-3 overflow-hidden rounded-full bg-blue-200/60">
                    <div className={`h-full rounded-full transition-all ${inspPct >= 90 ? 'bg-gradient-to-r from-red-500 to-red-400' : inspPct >= 60 ? 'bg-gradient-to-r from-amber-500 to-amber-400' : 'bg-gradient-to-r from-blue-600 to-blue-500'}`} style={{ width: `${inspPct}%` }} />
                  </div>
                  <p className="mt-1.5 text-[10px] text-blue-600">{(2000 - totalInspUsed).toLocaleString()} remaining &middot; Shared across all accounts</p>
                </div>
                <div className="rounded-2xl border border-orange-200 bg-gradient-to-br from-orange-100 via-orange-50 to-white p-4 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300">
                  <div className="flex justify-between text-xs mb-1">
                    <span className="font-semibold text-orange-800">Indexing API (per project)</span>
                    <span className="font-bold text-orange-900">{totalIdxUsed.toLocaleString()} / {totalIdxLimit.toLocaleString()}</span>
                  </div>
                  <div className="h-3 overflow-hidden rounded-full bg-orange-200/60">
                    <div className={`h-full rounded-full transition-all ${idxPct >= 90 ? 'bg-gradient-to-r from-red-500 to-red-400' : idxPct >= 60 ? 'bg-gradient-to-r from-amber-500 to-amber-400' : 'bg-gradient-to-r from-orange-500 to-orange-400'}`} style={{ width: `${idxPct}%` }} />
                  </div>
                  <p className="mt-1.5 text-[10px] text-orange-600">{Math.max(0, totalIdxLimit - totalIdxUsed).toLocaleString()} remaining &middot; 200/day per GCP project</p>
                </div>
              </div>
            </div>
          );
        })()}
      </div>
    </div>
  );
}
