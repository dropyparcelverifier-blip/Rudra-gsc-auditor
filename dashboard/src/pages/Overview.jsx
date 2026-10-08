import { Globe, CheckCircle, AlertTriangle, Package, ShoppingCart, Star, TrendingUp, MousePointerClick, Eye, Monitor, Smartphone, Tablet, Search, Zap, Send } from 'lucide-react';
import { ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid, Legend } from 'recharts';
import StatCard from '../components/StatCard';
import Header from '../components/Header';
import DataSourceBadge from '../components/DataSourceBadge';

const DEVICE_ICONS = { DESKTOP: Monitor, MOBILE: Smartphone, TABLET: Tablet };

export default function Overview({ data, loading, refresh }) {
  if (!data) return <div className="flex h-96 items-center justify-center text-slate-400">Loading live data from GSC...</div>;

  const { sitemaps, snippets, search_performance, devices, countries, pipeline, accounts, is_live, fetched_at, errors } = data;
  const sm = sitemaps || {};
  const perf = search_performance || {};
  const perfDaily = (perf.daily || []).slice(-28);
  const pl = pipeline || {};
  const richBreakdown = pl.rich_breakdown || {};

  const pipelineTotal = pl.total_tracked || 0;
  const pipelineIndexed = pl.indexed || 0;
  const pipelineRate = pipelineTotal > 0 ? (pipelineIndexed / pipelineTotal * 100).toFixed(1) : 0;
  const totalSubmitted = sm.total_submitted || 0;
  const scanPct = totalSubmitted > 0 ? (pipelineTotal / totalSubmitted * 100).toFixed(1) : 0;

  return (
    <div>
      <Header title="Overview" onRefresh={() => refresh(true)} loading={loading} />

      <div className="space-y-6 p-6">
        {/* Live status badge */}
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 font-semibold ${is_live ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
            <span className={`h-1.5 w-1.5 rounded-full ${is_live ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
            {is_live ? 'LIVE' : 'OFFLINE'}
          </span>
          {fetched_at && <span>Last updated: {fetched_at}</span>}
          {Object.keys(errors || {}).length > 0 && <span className="text-amber-600">{Object.keys(errors).length} API warning(s)</span>}
        </div>

        {/* Indexing Status — Pipeline Inspection Results */}
        <div>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
            Indexing Status
            <DataSourceBadge source="pipeline_db" className="ml-2" />
          </h2>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 mb-3">
            <StatCard label="Indexed" value={pipelineIndexed} color="green" icon={CheckCircle}
              subtitle="URL Inspection API" delta={`${pipelineRate}%`} />
            <StatCard label="Not Indexed" value={pl.not_indexed || 0} color="red" icon={AlertTriangle}
              delta={`${pipelineTotal ? (100 - pipelineRate).toFixed(1) : 0}% gap`} />
            <StatCard label="In Sitemaps" value={totalSubmitted} color="blue" icon={Globe}
              subtitle="Sitemaps API (LIVE)" />
            <StatCard label="Scan Progress" value={`${scanPct}%`} color="yellow" icon={Search}
              subtitle={`${pipelineTotal.toLocaleString()} of ${totalSubmitted.toLocaleString()}`} />
          </div>
          {/* Scan progress bar */}
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="text-sm font-semibold text-slate-700">Inspection Progress</span>
              <span className="text-xs text-slate-500">{pipelineTotal.toLocaleString()} / {totalSubmitted.toLocaleString()} ({scanPct}%)</span>
            </div>
            <div className="h-3 overflow-hidden rounded-full bg-slate-100">
              <div className="h-full rounded-full bg-gradient-to-r from-blue-500 to-cyan-500 transition-all duration-700"
                style={{ width: `${Math.min(scanPct, 100)}%` }} />
            </div>
            <div className="mt-2 flex items-center justify-between">
              <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100 mr-2">
                <div className="h-full rounded-full bg-gradient-to-r from-emerald-500 to-cyan-500"
                  style={{ width: `${pipelineRate}%` }} />
              </div>
              <span className="text-xs font-semibold text-emerald-700">{pipelineRate}% indexed</span>
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
                { key: 'Product', label: 'Product Snippets', icon: Package, border: 'border-purple-200', bg: 'bg-purple-50', text: 'text-purple-700' },
                { key: 'MerchantListing', label: 'Merchant Listings', icon: ShoppingCart, border: 'border-cyan-200', bg: 'bg-cyan-50', text: 'text-cyan-700' },
                { key: 'Review', label: 'Review Snippets', icon: Star, border: 'border-amber-200', bg: 'bg-amber-50', text: 'text-amber-700' },
                { key: 'None', label: 'No Rich Results', icon: AlertTriangle, border: 'border-slate-200', bg: 'bg-slate-50', text: 'text-slate-600' },
              ].map(rc => (
                <div key={rc.key} className={`rounded-xl border ${rc.border} ${rc.bg} p-4`}>
                  <div className={`flex items-center gap-2 mb-1 ${rc.text}`}>
                    <rc.icon size={14} />
                    <span className="text-[10px] font-semibold uppercase">{rc.label}</span>
                  </div>
                  <p className={`text-xl font-extrabold ${rc.text}`}>{(richBreakdown[rc.key] || 0).toLocaleString()}</p>
                </div>
              ))}
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
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <ResponsiveContainer width="100%" height={250}>
                <AreaChart data={perfDaily}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={d => d.slice(5)} />
                  <YAxis yAxisId="left" tick={{ fontSize: 10 }} />
                  <YAxis yAxisId="right" orientation="right" tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Legend />
                  <Area yAxisId="left" type="monotone" dataKey="clicks" stroke="#3b82f6" fill="#dbeafe" name="Clicks" />
                  <Area yAxisId="right" type="monotone" dataKey="impressions" stroke="#a855f7" fill="#f3e8ff" name="Impressions" />
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
                { key: 'PRODUCT_SNIPPETS', label: 'Product Snippets', icon: Package },
                { key: 'MERCHANT_LISTINGS', label: 'Merchant Listings', icon: ShoppingCart },
                { key: 'REVIEW_SNIPPET', label: 'Review Snippets', icon: Star },
              ].map(sc => {
                const s = snippets[sc.key] || {};
                return (
                  <div key={sc.key} className="rounded-xl border border-slate-200 bg-white p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <sc.icon size={16} className="text-slate-500" />
                      <span className="text-xs font-semibold text-slate-600">{sc.label}</span>
                    </div>
                    <p className="text-xl font-extrabold text-slate-800">{(s.impressions || 0).toLocaleString()}</p>
                    <p className="text-[10px] text-slate-500">impressions &bull; {(s.clicks || 0).toLocaleString()} clicks &bull; {s.ctr || 0}% CTR</p>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Device + Country split */}
        <div className="grid gap-4 lg:grid-cols-2">
          {devices && Object.keys(devices).length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h3 className="mb-3 text-sm font-semibold text-slate-700">Device Split <DataSourceBadge source="live" className="ml-1" /></h3>
              <div className="space-y-3">
                {Object.entries(devices).map(([device, stats]) => {
                  const Icon = DEVICE_ICONS[device] || Monitor;
                  const total = Object.values(devices).reduce((s, d) => s + d.clicks, 0);
                  const pct = total ? (stats.clicks / total * 100).toFixed(0) : 0;
                  return (
                    <div key={device}>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="flex items-center gap-2 font-semibold text-slate-700"><Icon size={14} />{device}</span>
                        <span className="text-slate-500">{stats.clicks.toLocaleString()} clicks &bull; {stats.ctr}% CTR</span>
                      </div>
                      <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                        <div className="h-full rounded-full bg-blue-500" style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {countries && countries.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white p-4">
              <h3 className="mb-3 text-sm font-semibold text-slate-700">Top Countries <DataSourceBadge source="live" className="ml-1" /></h3>
              <div className="space-y-2">
                {countries.slice(0, 8).map((c, i) => (
                  <div key={c.country} className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-2">
                      <span className="w-5 text-center font-bold text-slate-400">{i + 1}</span>
                      <span className="font-semibold text-slate-700">{c.country}</span>
                    </span>
                    <span className="text-slate-500">{c.clicks.toLocaleString()} clicks &bull; {c.impressions.toLocaleString()} impr</span>
                  </div>
                ))}
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
              {accounts.map(a => (
                <div key={a.name} className="rounded-xl border border-slate-200 bg-white p-3">
                  <p className="mb-2 text-xs font-semibold text-slate-800">{a.name}</p>
                  <div className="space-y-1.5">
                    <div>
                      <div className="flex justify-between text-[10px] text-slate-500"><span>Inspect</span><span>{a.inspect_used}/{a.inspect_limit}</span></div>
                      <div className="mt-0.5 h-1 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-blue-500" style={{ width: `${a.inspect_limit ? (a.inspect_used / a.inspect_limit * 100) : 0}%` }} /></div>
                    </div>
                    <div>
                      <div className="flex justify-between text-[10px] text-slate-500"><span>Index</span><span>{a.index_used}/{a.index_limit}</span></div>
                      <div className="mt-0.5 h-1 overflow-hidden rounded-full bg-slate-200"><div className="h-full rounded-full bg-orange-500" style={{ width: `${a.index_limit ? (a.index_used / a.index_limit * 100) : 0}%` }} /></div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
