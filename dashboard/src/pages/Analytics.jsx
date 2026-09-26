import { useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend, PieChart, Pie, Cell } from 'recharts';
import { TrendingUp, MousePointerClick, Eye, ArrowUpDown, ExternalLink, Search, Monitor, Smartphone, Tablet } from 'lucide-react';
import Header from '../components/Header';
import StatCard from '../components/StatCard';
import DataSourceBadge from '../components/DataSourceBadge';

const DEVICE_COLORS = { DESKTOP: '#3b82f6', MOBILE: '#22c55e', TABLET: '#a855f7' };
const DEVICE_ICONS = { DESKTOP: Monitor, MOBILE: Smartphone, TABLET: Tablet };
const DEVICE_GRADIENTS = { DESKTOP: 'from-blue-500 to-cyan-500', MOBILE: 'from-emerald-500 to-teal-500', TABLET: 'from-purple-500 to-indigo-500' };

function ChartTooltip({ active, payload, label }) {
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

export default function Analytics({ data, loading, refresh }) {
  const [tab, setTab] = useState('queries');
  const [sortCol, setSortCol] = useState('clicks');
  const [sortDir, setSortDir] = useState('desc');
  const [search, setSearch] = useState('');

  if (!data) return <div className="flex h-96 items-center justify-center text-slate-400">Loading live data from GSC...</div>;

  const perf = data.search_performance || {};
  const perfDaily = (perf.daily || []).slice(-28);
  const queries = data.top_queries || [];
  const pages = data.top_pages || [];
  const devices = data.devices || {};
  const countries = data.countries || [];

  const toggleSort = (col) => {
    if (sortCol === col) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortCol(col); setSortDir('desc'); }
  };

  const currentList = tab === 'queries' ? queries : pages;
  const filtered = search
    ? currentList.filter(r => (r.query || r.page || '').toLowerCase().includes(search.toLowerCase()))
    : currentList;
  const sorted = [...filtered].sort((a, b) => {
    const av = a[sortCol], bv = b[sortCol];
    if (typeof av === 'string') return sortDir === 'desc' ? (bv || '').localeCompare(av || '') : (av || '').localeCompare(bv || '');
    return sortDir === 'desc' ? (bv - av || 0) : (av - bv || 0);
  });

  const maxCountryClicks = countries.length > 0 ? Math.max(...countries.slice(0, 10).map(c => c.clicks || 0)) : 1;

  const SortTh = ({ col, children, align = 'left' }) => (
    <th className={`cursor-pointer px-3 py-2.5 font-semibold text-slate-600 select-none hover:text-slate-900 transition-colors ${align === 'right' ? 'text-right' : 'text-left'}`} onClick={() => toggleSort(col)}>
      <span className={`flex items-center gap-1 ${align === 'right' ? 'justify-end' : ''}`}>{children}<ArrowUpDown size={12} className={`transition-colors ${sortCol === col ? 'text-orange-500' : 'text-slate-300'}`} /></span>
    </th>
  );

  return (
    <div>
      <Header title="Search Analytics" onRefresh={() => refresh(true)} loading={loading} />
      <div className="space-y-5 px-5 py-5">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <DataSourceBadge source="search_analytics" />
          Google Search Console — last 28 days
        </div>

        {/* Summary stats */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Total Clicks" value={perf.total_clicks || 0} color="blue" icon={MousePointerClick} subtitle="28 days" />
          <StatCard label="Total Impressions" value={perf.total_impressions || 0} color="purple" icon={Eye} subtitle="28 days" />
          <StatCard label="Avg CTR" value={`${perf.avg_ctr || 0}%`} color="green" icon={TrendingUp} />
          <StatCard label="Queries Found" value={queries.length} color="orange" icon={Search} subtitle="Top 100" />
        </div>

        {/* Performance chart */}
        {perfDaily.length > 0 && (
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-700">
              <span className="h-4 w-1 rounded-full bg-gradient-to-b from-blue-400 to-blue-600" />
              Daily Performance (28 days)
            </h3>
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={perfDaily}>
                <defs>
                  <linearGradient id="aClicksGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.35} />
                    <stop offset="50%" stopColor="#3b82f6" stopOpacity={0.1} />
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.01} />
                  </linearGradient>
                  <linearGradient id="aImprGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#a855f7" stopOpacity={0.35} />
                    <stop offset="50%" stopColor="#a855f7" stopOpacity={0.1} />
                    <stop offset="100%" stopColor="#a855f7" stopOpacity={0.01} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#94a3b8' }} tickFormatter={d => d.slice(5)} axisLine={false} />
                <YAxis yAxisId="left" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} />
                <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} />
                <Tooltip content={<ChartTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Area yAxisId="left" type="monotoneX" dataKey="clicks" stroke="#3b82f6" fill="url(#aClicksGrad)" name="Clicks" strokeWidth={2.5} dot={false} activeDot={{ r: 5, stroke: '#3b82f6', strokeWidth: 2, fill: '#fff' }} />
                <Area yAxisId="right" type="monotoneX" dataKey="impressions" stroke="#a855f7" fill="url(#aImprGrad)" name="Impressions" strokeWidth={2.5} dot={false} activeDot={{ r: 5, stroke: '#a855f7', strokeWidth: 2, fill: '#fff' }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Device breakdown */}
        {Object.keys(devices).length > 0 && (
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-700">
              <span className="h-4 w-1 rounded-full bg-gradient-to-b from-green-400 to-green-600" />
              Device Breakdown
              <DataSourceBadge source="live" className="ml-1" />
            </h3>
            <div className="flex gap-6 items-center">
              <div className="flex-shrink-0">
                <ResponsiveContainer width={110} height={110}>
                  <PieChart>
                    <Pie data={Object.entries(devices).map(([d, s]) => ({ name: d, value: s.clicks }))}
                      dataKey="value" cx="50%" cy="50%" innerRadius={30} outerRadius={48}
                      paddingAngle={3} strokeWidth={0}>
                      {Object.keys(devices).map((d, i) => <Cell key={i} fill={DEVICE_COLORS[d] || '#6366f1'} />)}
                    </Pie>
                    <Tooltip formatter={v => (v ?? 0).toLocaleString()} contentStyle={{ fontSize: 11, borderRadius: 8 }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex-1 grid grid-cols-1 sm:grid-cols-3 gap-3">
                {Object.entries(devices).map(([device, stats]) => {
                  const Icon = DEVICE_ICONS[device] || Monitor;
                  const gradient = DEVICE_GRADIENTS[device] || 'from-indigo-500 to-purple-500';
                  const totalClicks = Object.values(devices).reduce((s, d) => s + (d.clicks || 0), 0);
                  const pct = totalClicks ? (stats.clicks / totalClicks * 100).toFixed(1) : 0;
                  return (
                    <div key={device} className="rounded-xl border border-slate-100 bg-gradient-to-br from-slate-50 to-white p-3 shadow-sm transition-all duration-200 hover:shadow-md hover:-translate-y-0.5">
                      <div className="flex items-center gap-2 mb-1.5">
                        <div className={`flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br ${gradient} text-white shadow-sm`}>
                          <Icon size={13} />
                        </div>
                        <span className="text-xs font-semibold text-slate-600">{device}</span>
                        <span className="ml-auto text-[10px] font-bold" style={{ color: DEVICE_COLORS[device] }}>{pct}%</span>
                      </div>
                      <p className="text-lg font-extrabold text-slate-800">{(stats.clicks || 0).toLocaleString()}</p>
                      <p className="text-[10px] text-slate-500">{(stats.impressions || 0).toLocaleString()} impr &bull; {stats.ctr || 0}% CTR &bull; pos {stats.position || '—'}</p>
                      <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-200">
                        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: `linear-gradient(90deg, ${DEVICE_COLORS[device]}, ${DEVICE_COLORS[device]}99)` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        )}

        {/* Tab toggle + search */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex gap-1 rounded-xl bg-slate-100 p-1">
            {['queries', 'pages'].map(t => (
              <button key={t} onClick={() => { setTab(t); setSearch(''); setSortCol('clicks'); setSortDir('desc'); }}
                className={`rounded-lg px-5 py-2 text-sm font-semibold transition-all duration-200 ${tab === t ? 'bg-white text-slate-900 shadow-md' : 'text-slate-500 hover:text-slate-700 hover:bg-white/50'}`}>
                {t === 'queries' ? `Top Queries (${queries.length})` : `Top Pages (${pages.length})`}
              </button>
            ))}
          </div>
          <div className="relative flex-1 min-w-[200px]">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input type="text" placeholder={`Search ${tab}...`} value={search} onChange={e => setSearch(e.target.value)}
              className="w-full rounded-xl border border-slate-200 bg-white py-2 pl-8 pr-3 text-sm outline-none transition-all duration-200 focus:border-orange-300 focus:ring-2 focus:ring-orange-100 shadow-sm" />
          </div>
        </div>

        {/* Data table */}
        <div className="overflow-x-auto rounded-2xl border border-slate-200 bg-white shadow-sm">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50">
                <SortTh col={tab === 'queries' ? 'query' : 'page'}>{tab === 'queries' ? 'Query' : 'Page'}</SortTh>
                <SortTh col="clicks" align="right">Clicks</SortTh>
                <SortTh col="impressions" align="right">Impressions</SortTh>
                <SortTh col="ctr" align="right">CTR</SortTh>
                <SortTh col="position" align="right">Position</SortTh>
              </tr>
            </thead>
            <tbody>
              {sorted.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-slate-400">{loading ? 'Loading...' : 'No data'}</td></tr>
              )}
              {sorted.slice(0, 200).map((r, i) => (
                <tr key={i} className={`border-b border-slate-50 transition-colors duration-150 hover:bg-slate-50/80 ${i % 2 === 1 ? 'bg-slate-50/40' : ''}`}>
                  <td className="max-w-xs truncate px-3 py-2.5">
                    {tab === 'pages' ? (
                      <a href={r.page} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-blue-600 hover:underline">
                        <span className="truncate">{r.page?.replace('https://www.rudraretails.com/', '/').replace('https://rudraretails.com/', '/')}</span>
                        <ExternalLink size={12} className="flex-shrink-0" />
                      </a>
                    ) : (
                      <span className="text-slate-800">{r.query}</span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-right font-semibold text-blue-700">{(r.clicks || 0).toLocaleString()}</td>
                  <td className="px-3 py-2.5 text-right">{(r.impressions || 0).toLocaleString()}</td>
                  <td className="px-3 py-2.5 text-right">{r.ctr || 0}%</td>
                  <td className="px-3 py-2.5 text-right">
                    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold shadow-sm ${
                      (r.position || 0) <= 10
                        ? 'bg-gradient-to-r from-emerald-100 to-emerald-50 text-emerald-700'
                        : (r.position || 0) <= 20
                          ? 'bg-gradient-to-r from-amber-100 to-amber-50 text-amber-700'
                          : 'bg-gradient-to-r from-red-100 to-red-50 text-red-700'
                    }`}>
                      {r.position || '—'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Top countries */}
        {countries.length > 0 && (
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="mb-4 flex items-center gap-2 text-sm font-semibold text-slate-700">
              <span className="h-4 w-1 rounded-full bg-gradient-to-b from-orange-400 to-orange-600" />
              Top Countries
              <DataSourceBadge source="live" />
            </h3>
            <div className="grid gap-2.5 sm:grid-cols-2">
              {countries.slice(0, 10).map((c, i) => {
                const pct = maxCountryClicks ? ((c.clicks || 0) / maxCountryClicks * 100) : 0;
                const rankColors = i < 3 ? 'bg-gradient-to-br from-amber-400 to-orange-500 text-white' : 'bg-slate-200 text-slate-600';
                return (
                  <div key={c.country} className="relative overflow-hidden rounded-xl border border-slate-100 bg-gradient-to-br from-slate-50 to-white px-3 py-2.5 text-xs transition-all duration-200 hover:shadow-md hover:-translate-y-0.5">
                    <div className="absolute inset-y-0 left-0 bg-gradient-to-r from-blue-50 to-transparent transition-all duration-500" style={{ width: `${pct}%` }} />
                    <div className="relative flex items-center justify-between">
                      <span className="flex items-center gap-2.5">
                        <span className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-bold ${rankColors}`}>{i + 1}</span>
                        <span className="font-semibold text-slate-700">{c.country}</span>
                      </span>
                      <span className="text-slate-500">{(c.clicks || 0).toLocaleString()} clicks &bull; {(c.impressions || 0).toLocaleString()} impr &bull; {c.ctr || 0}% CTR</span>
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
