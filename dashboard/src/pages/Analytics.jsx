import { useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend, PieChart, Pie, Cell } from 'recharts';
import { TrendingUp, MousePointerClick, Eye, ArrowUpDown, ExternalLink, Search, Monitor, Smartphone, Tablet } from 'lucide-react';
import Header from '../components/Header';
import StatCard from '../components/StatCard';
import DataSourceBadge from '../components/DataSourceBadge';

const DEVICE_COLORS = { DESKTOP: '#3b82f6', MOBILE: '#22c55e', TABLET: '#a855f7' };
const DEVICE_ICONS = { DESKTOP: Monitor, MOBILE: Smartphone, TABLET: Tablet };

function ChartTooltip({ active, payload, label }) {
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

  const SortTh = ({ col, children, align = 'left' }) => (
    <th className={`cursor-pointer px-3 py-2.5 font-semibold text-slate-600 select-none hover:text-slate-900 ${align === 'right' ? 'text-right' : 'text-left'}`} onClick={() => toggleSort(col)}>
      <span className={`flex items-center gap-1 ${align === 'right' ? 'justify-end' : ''}`}>{children}<ArrowUpDown size={12} className={sortCol === col ? 'text-orange-500' : 'text-slate-300'} /></span>
    </th>
  );

  return (
    <div>
      <Header title="Search Analytics" onRefresh={() => refresh(true)} loading={loading} />
      <div className="space-y-6 p-6">
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
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h3 className="mb-3 text-sm font-semibold text-slate-700">Daily Performance (28 days)</h3>
            <ResponsiveContainer width="100%" height={280}>
              <AreaChart data={perfDaily}>
                <defs>
                  <linearGradient id="aClicksGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity={0.02} />
                  </linearGradient>
                  <linearGradient id="aImprGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#a855f7" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#a855f7" stopOpacity={0.02} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="date" tick={{ fontSize: 10, fill: '#94a3b8' }} tickFormatter={d => d.slice(5)} axisLine={false} />
                <YAxis yAxisId="left" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} />
                <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} />
                <Tooltip content={<ChartTooltip />} />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Area yAxisId="left" type="monotone" dataKey="clicks" stroke="#3b82f6" fill="url(#aClicksGrad)" name="Clicks" strokeWidth={2.5} dot={false} activeDot={{ r: 5, stroke: '#3b82f6', strokeWidth: 2, fill: '#fff' }} />
                <Area yAxisId="right" type="monotone" dataKey="impressions" stroke="#a855f7" fill="url(#aImprGrad)" name="Impressions" strokeWidth={2.5} dot={false} activeDot={{ r: 5, stroke: '#a855f7', strokeWidth: 2, fill: '#fff' }} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Device breakdown */}
        {Object.keys(devices).length > 0 && (
          <div className="rounded-xl border border-slate-200 bg-white p-5">
            <h3 className="mb-4 text-sm font-semibold text-slate-700">Device Breakdown <DataSourceBadge source="live" className="ml-1" /></h3>
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
                  const totalClicks = Object.values(devices).reduce((s, d) => s + (d.clicks || 0), 0);
                  const pct = totalClicks ? (stats.clicks / totalClicks * 100).toFixed(1) : 0;
                  return (
                    <div key={device} className="rounded-lg border border-slate-100 bg-slate-50 p-3">
                      <div className="flex items-center gap-2 mb-1">
                        <Icon size={14} style={{ color: DEVICE_COLORS[device] }} />
                        <span className="text-xs font-semibold text-slate-600">{device}</span>
                        <span className="ml-auto text-[10px] font-bold" style={{ color: DEVICE_COLORS[device] }}>{pct}%</span>
                      </div>
                      <p className="text-lg font-extrabold text-slate-800">{(stats.clicks || 0).toLocaleString()}</p>
                      <p className="text-[10px] text-slate-500">{(stats.impressions || 0).toLocaleString()} impr &bull; {stats.ctr || 0}% CTR &bull; pos {stats.position || '—'}</p>
                      <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200">
                        <div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: DEVICE_COLORS[device] }} />
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
          <div className="flex gap-1 rounded-lg bg-slate-100 p-0.5">
            {['queries', 'pages'].map(t => (
              <button key={t} onClick={() => { setTab(t); setSearch(''); setSortCol('clicks'); setSortDir('desc'); }}
                className={`rounded-md px-4 py-1.5 text-xs font-semibold transition ${tab === t ? 'bg-white text-slate-900 shadow-sm' : 'text-slate-500 hover:text-slate-700'}`}>
                {t === 'queries' ? `Top Queries (${queries.length})` : `Top Pages (${pages.length})`}
              </button>
            ))}
          </div>
          <div className="relative flex-1 min-w-[200px]">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input type="text" placeholder={`Search ${tab}...`} value={search} onChange={e => setSearch(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-white py-1.5 pl-8 pr-3 text-sm outline-none focus:border-orange-300" />
          </div>
        </div>

        {/* Data table */}
        <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white">
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
                <tr key={i} className="border-b border-slate-50 hover:bg-slate-50">
                  <td className="max-w-xs truncate px-3 py-2">
                    {tab === 'pages' ? (
                      <a href={r.page} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-blue-600 hover:underline">
                        <span className="truncate">{r.page?.replace('https://www.rudraretails.com/', '/').replace('https://rudraretails.com/', '/')}</span>
                        <ExternalLink size={12} className="flex-shrink-0" />
                      </a>
                    ) : (
                      <span className="text-slate-800">{r.query}</span>
                    )}
                  </td>
                  <td className="px-3 py-2 text-right font-semibold text-blue-700">{(r.clicks || 0).toLocaleString()}</td>
                  <td className="px-3 py-2 text-right">{(r.impressions || 0).toLocaleString()}</td>
                  <td className="px-3 py-2 text-right">{r.ctr || 0}%</td>
                  <td className="px-3 py-2 text-right">
                    <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${(r.position || 0) <= 10 ? 'bg-emerald-100 text-emerald-700' : (r.position || 0) <= 20 ? 'bg-amber-100 text-amber-700' : 'bg-red-100 text-red-700'}`}>
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
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-700">Top Countries <DataSourceBadge source="live" /></h3>
            <div className="grid gap-2 sm:grid-cols-2">
              {countries.slice(0, 10).map((c, i) => (
                <div key={c.country} className="flex items-center justify-between rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-xs">
                  <span className="flex items-center gap-2">
                    <span className="w-5 text-center font-bold text-slate-400">{i + 1}</span>
                    <span className="font-semibold text-slate-700">{c.country}</span>
                  </span>
                  <span className="text-slate-500">{(c.clicks || 0).toLocaleString()} clicks &bull; {(c.impressions || 0).toLocaleString()} impr &bull; {c.ctr || 0}% CTR</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
