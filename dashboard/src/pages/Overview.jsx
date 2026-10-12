import { Globe, CheckCircle, AlertTriangle, Package, ShoppingCart, Star, TrendingUp, MousePointerClick, Eye, Monitor, Smartphone, Tablet, Search, Zap, Send } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, Legend, PieChart, Pie, Cell } from 'recharts';
import StatCard from '../components/StatCard';
import Header from '../components/Header';
import DataSourceBadge from '../components/DataSourceBadge';

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

function IndexDonut({ indexed, notIndexed }) {
  const total = indexed + notIndexed;
  if (!total) return null;
  const pct = (indexed / total * 100).toFixed(1);
  const data = [
    { name: 'Indexed', value: indexed },
    { name: 'Not Indexed', value: notIndexed },
  ];
  const COLORS = ['#22c55e', '#ef4444'];

  return (
    <div className="relative flex items-center justify-center">
      <ResponsiveContainer width={160} height={160}>
        <PieChart>
          <Pie data={data} dataKey="value" cx="50%" cy="50%" innerRadius={50} outerRadius={72}
            paddingAngle={3} startAngle={90} endAngle={-270} strokeWidth={0}>
            {data.map((_, i) => <Cell key={i} fill={COLORS[i]} />)}
          </Pie>
          <Tooltip formatter={v => v.toLocaleString()} contentStyle={{ fontSize: 12, borderRadius: 8 }} />
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
        <span className="text-2xl font-extrabold text-emerald-700">{pct}%</span>
        <span className="text-[10px] text-slate-400 font-medium">indexed</span>
      </div>
    </div>
  );
}

export default function Overview({ data, loading, refresh }) {
  if (!data) return (
    <div className="flex h-96 flex-col items-center justify-center gap-3 text-slate-400">
      <div className="h-10 w-10 rounded-full border-2 border-slate-200 border-t-blue-500 animate-spin" />
      <span className="text-sm font-medium">Loading live data from GSC...</span>
    </div>
  );

  const { sitemaps, snippets, search_performance, devices, countries, pipeline, accounts, is_live, fetched_at, errors } = data;
  const sm = sitemaps || {};
  const perf = search_performance || {};
  const perfDaily = (perf.daily || []).slice(-28);
  const pl = pipeline || {};
  const richBreakdown = pl.rich_breakdown || {};

  const pipelineTotal = pl.total_tracked || 0;
  const pipelineIndexed = pl.indexed || 0;
  const pipelineNotIndexed = pl.not_indexed || 0;
  const pipelineRate = pipelineTotal > 0 ? (pipelineIndexed / pipelineTotal * 100).toFixed(1) : 0;
  const totalSubmitted = sm.total_submitted || 0;
  const scanPct = totalSubmitted > 0 ? (pipelineTotal / totalSubmitted * 100).toFixed(1) : 0;

  return (
    <div>
      <Header title="Overview" onRefresh={() => refresh(true)} loading={loading} />

      <div className="space-y-6 p-6">
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
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
            Indexing Status
            <DataSourceBadge source="pipeline_db" className="ml-2" />
          </h2>
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <div className="flex flex-col lg:flex-row gap-6 items-center">
              {/* Donut chart */}
              <div className="flex-shrink-0">
                <IndexDonut indexed={pipelineIndexed} notIndexed={pipelineNotIndexed} />
              </div>

              {/* Stat cards */}
              <div className="flex-1 grid grid-cols-2 gap-3 w-full">
                <StatCard label="Indexed" value={pipelineIndexed} color="green" icon={CheckCircle}
                  subtitle="URL Inspection API" delta={`${pipelineRate}%`} />
                <StatCard label="Not Indexed" value={pipelineNotIndexed} color="red" icon={AlertTriangle}
                  delta={`${pipelineTotal ? (100 - pipelineRate).toFixed(1) : 0}% gap`} />
                <StatCard label="In Sitemaps" value={totalSubmitted} color="blue" icon={Globe}
                  subtitle="Sitemaps API (LIVE)" />
                <StatCard label="Scan Progress" value={`${scanPct}%`} color="yellow" icon={Search}
                  subtitle={`${pipelineTotal.toLocaleString()} of ${totalSubmitted.toLocaleString()}`} />
              </div>
            </div>

            {/* Progress bars */}
            <div className="mt-5 space-y-3">
              <div>
                <div className="mb-1.5 flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-600">Inspection Progress</span>
                  <span className="text-xs text-slate-500">{pipelineTotal.toLocaleString()} / {totalSubmitted.toLocaleString()} ({scanPct}%)</span>
                </div>
                <div className="h-3 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-gradient-to-r from-blue-500 to-cyan-500 transition-all duration-700"
                    style={{ width: `${Math.min(scanPct, 100)}%` }} />
                </div>
              </div>
              <div>
                <div className="mb-1.5 flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-600">Index Rate</span>
                  <span className="text-xs font-semibold text-emerald-700">{pipelineRate}% indexed</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-cyan-500 transition-all duration-700"
                    style={{ width: `${pipelineRate}%` }} />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Rich Results Detected — Pipeline */}
        {Object.keys(richBreakdown).length > 0 && (
          <div>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
              Rich Results Detected
              <DataSourceBadge source="pipeline_db" className="ml-2" />
            </h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                { key: 'Product', label: 'Product Snippets', icon: Package, border: 'border-purple-200', bg: 'bg-purple-50', text: 'text-purple-700', iconBg: 'bg-purple-100' },
                { key: 'MerchantListing', label: 'Merchant Listings', icon: ShoppingCart, border: 'border-cyan-200', bg: 'bg-cyan-50', text: 'text-cyan-700', iconBg: 'bg-cyan-100' },
                { key: 'Review', label: 'Review Snippets', icon: Star, border: 'border-amber-200', bg: 'bg-amber-50', text: 'text-amber-700', iconBg: 'bg-amber-100' },
                { key: 'None', label: 'No Rich Results', icon: AlertTriangle, border: 'border-slate-200', bg: 'bg-slate-50', text: 'text-slate-600', iconBg: 'bg-slate-100' },
              ].map(rc => {
                const count = richBreakdown[rc.key] || 0;
                const total = Object.values(richBreakdown).reduce((s, v) => s + v, 0);
                const pct = total ? (count / total * 100).toFixed(1) : 0;
                return (
                  <div key={rc.key} className={`rounded-xl border ${rc.border} ${rc.bg} p-4 transition-shadow hover:shadow-md`}>
                    <div className={`flex items-center gap-2 mb-2 ${rc.text}`}>
                      <span className={`flex h-7 w-7 items-center justify-center rounded-lg ${rc.iconBg}`}>
                        <rc.icon size={14} />
                      </span>
                      <span className="text-[10px] font-semibold uppercase">{rc.label}</span>
                    </div>
                    <p className={`text-xl font-extrabold ${rc.text}`}>{count.toLocaleString()}</p>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/50">
                      <div className={`h-full rounded-full ${rc.text.replace('text-', 'bg-')}`} style={{ width: `${pct}%` }} />
                    </div>
                    <p className="mt-1 text-[10px] opacity-60">{pct}% of inspected</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Search Performance — LIVE */}
        {perfDaily.length > 0 && (
          <div>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
              Search Performance (28 days) <DataSourceBadge source="live" className="ml-1" />
            </h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 mb-4">
              <StatCard label="Total Clicks" value={perf.total_clicks || 0} color="blue" icon={MousePointerClick} />
              <StatCard label="Total Impressions" value={perf.total_impressions || 0} color="purple" icon={Eye} />
              <StatCard label="Avg CTR" value={`${perf.avg_ctr || 0}%`} color="green" icon={TrendingUp} />
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5">
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
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
              Rich Results Performance <DataSourceBadge source="search_analytics" className="ml-1" />
            </h2>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              {[
                { key: 'PRODUCT_SNIPPETS', label: 'Product Snippets', icon: Package, gradient: 'from-purple-500 to-indigo-500' },
                { key: 'MERCHANT_LISTINGS', label: 'Merchant Listings', icon: ShoppingCart, gradient: 'from-cyan-500 to-teal-500' },
                { key: 'REVIEW_SNIPPET', label: 'Review Snippets', icon: Star, gradient: 'from-amber-500 to-orange-500' },
              ].map(sc => {
                const s = snippets[sc.key] || {};
                return (
                  <div key={sc.key} className="rounded-xl border border-slate-200 bg-white p-5 transition-shadow hover:shadow-md">
                    <div className="flex items-center gap-2 mb-3">
                      <div className={`flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br ${sc.gradient} text-white`}>
                        <sc.icon size={16} />
                      </div>
                      <span className="text-xs font-semibold text-slate-600">{sc.label}</span>
                    </div>
                    <p className="text-2xl font-extrabold text-slate-800">{(s.impressions || 0).toLocaleString()}</p>
                    <p className="text-[10px] text-slate-500 mt-1">
                      impressions &bull; {(s.clicks || 0).toLocaleString()} clicks &bull; {s.ctr || 0}% CTR
                    </p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Device + Country split */}
        <div className="grid gap-4 lg:grid-cols-2">
          {devices && Object.keys(devices).length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-5">
              <h3 className="mb-4 text-sm font-semibold text-slate-700">
                Device Split <DataSourceBadge source="live" className="ml-1" />
              </h3>
              <div className="flex gap-6">
                {/* Mini donut */}
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
                {/* Bars */}
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
            <div className="rounded-xl border border-slate-200 bg-white p-5">
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

        {/* Service Accounts */}
        {accounts && accounts.length > 0 && (
          <div>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
              Service Accounts ({accounts.length})
            </h2>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
              {accounts.map(a => {
                const inspPct = a.inspect_limit ? (a.inspect_used / a.inspect_limit * 100) : 0;
                const idxPct = a.index_limit ? (a.index_used / a.index_limit * 100) : 0;
                return (
                  <div key={a.name} className="rounded-xl border border-slate-200 bg-white p-3 transition-shadow hover:shadow-md">
                    <p className="mb-2.5 text-xs font-semibold text-slate-800 truncate">{a.name}</p>
                    <div className="space-y-2">
                      <div>
                        <div className="flex justify-between text-[10px] text-slate-500"><span>Inspect</span><span>{a.inspect_used}/{a.inspect_limit}</span></div>
                        <div className="mt-0.5 h-1.5 overflow-hidden rounded-full bg-slate-100">
                          <div className={`h-full rounded-full transition-all duration-300 ${inspPct > 80 ? 'bg-red-500' : 'bg-blue-500'}`} style={{ width: `${inspPct}%` }} />
                        </div>
                      </div>
                      <div>
                        <div className="flex justify-between text-[10px] text-slate-500"><span>Index</span><span>{a.index_used}/{a.index_limit}</span></div>
                        <div className="mt-0.5 h-1.5 overflow-hidden rounded-full bg-slate-100">
                          <div className={`h-full rounded-full transition-all duration-300 ${idxPct > 80 ? 'bg-red-500' : 'bg-orange-500'}`} style={{ width: `${idxPct}%` }} />
                        </div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
