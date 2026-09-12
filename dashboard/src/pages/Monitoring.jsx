import { useState, useEffect, useCallback } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend, Line, Cell, Area, AreaChart } from 'recharts';
import { Activity, CheckCircle, AlertTriangle, Clock, TrendingUp, TrendingDown, ArrowRight, Zap, Filter, Eye, Send, Search, SkipForward } from 'lucide-react';
import Header from '../components/Header';
import StatCard from '../components/StatCard';
import ProgressBar from '../components/ProgressBar';
import FreshnessRow from '../components/FreshnessRow';
import { api } from '../lib/api';

// ─── Classification summary section ───
function ClassificationPanel({ classData }) {
  if (!classData) return null;

  const { action_counts, coverage_actions, total_tracked, indexed, not_indexed } = classData;
  const items = [
    { icon: Eye, label: 'Need Inspection', value: action_counts?.inspect || 0, color: 'text-blue-700', bg: 'bg-blue-50', border: 'border-blue-200', desc: 'URLs that should be checked via URL Inspection API', gradient: 'from-blue-500 to-blue-600' },
    { icon: Send, label: 'Submit for Indexing', value: action_counts?.submit || 0, color: 'text-purple-700', bg: 'bg-purple-50', border: 'border-purple-200', desc: 'Not-indexed URLs eligible for Indexing API submission', gradient: 'from-purple-500 to-purple-600' },
    { icon: Zap, label: 'Track Snippets', value: action_counts?.snippet || 0, color: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200', desc: 'Indexed product pages — track rich result / product snippet status', gradient: 'from-amber-500 to-amber-600' },
    { icon: Search, label: 'Search Analytics', value: action_counts?.search || 0, color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200', desc: 'Indexed pages — track clicks, impressions, CTR, position', gradient: 'from-emerald-500 to-emerald-600' },
  ];

  const coverageRows = Object.entries(coverage_actions || {})
    .sort((a, b) => (b[1].count || 0) - (a[1].count || 0))
    .slice(0, 12);

  return (
    <div>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
        <Filter size={14} className="mr-1 inline" />
        Smart URL Classification
        <span className="ml-2 rounded-lg bg-indigo-100 px-2 py-0.5 text-[10px] font-semibold text-indigo-700 normal-case">
          {(total_tracked || 0).toLocaleString()} tracked
        </span>
      </h2>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 mb-4">
        {items.map(({ icon: Icon, label, value, color, bg, border, desc, gradient }) => (
          <div key={label} className={`rounded-2xl border ${border} ${bg} p-4 shadow-sm`}>
            <div className={`flex items-center gap-2 ${color}`}>
              <div className={`flex h-7 w-7 items-center justify-center rounded-lg bg-gradient-to-br ${gradient} text-white shadow-sm`}>
                <Icon size={14} />
              </div>
              <span className="text-[11px] font-semibold uppercase tracking-wide">{label}</span>
            </div>
            <p className={`mt-2 text-2xl font-extrabold ${color}`}>{value.toLocaleString()}</p>
            <p className="mt-1 text-[10px] text-slate-500 leading-tight">{desc}</p>
          </div>
        ))}
      </div>

      {coverageRows.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <div className="border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white px-4 py-3">
            <h3 className="text-xs font-semibold text-slate-700">Coverage Status → Actions</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/80 text-left">
                  <th className="px-4 py-2.5 font-semibold text-slate-600">Coverage Status</th>
                  <th className="px-4 py-2.5 font-semibold text-slate-600 text-right">Count</th>
                  <th className="px-4 py-2.5 font-semibold text-slate-600 text-center">Inspect</th>
                  <th className="px-4 py-2.5 font-semibold text-slate-600 text-center">Submit</th>
                  <th className="px-4 py-2.5 font-semibold text-slate-600 text-center">Snippets</th>
                </tr>
              </thead>
              <tbody>
                {coverageRows.map(([cov, info], idx) => {
                  const isIndexed = cov.toLowerCase().includes('indexed') && !cov.toLowerCase().includes('not');
                  const rowBg = isIndexed ? 'bg-emerald-50/40' : (idx % 2 === 0 ? 'bg-white' : 'bg-slate-50/50');
                  return (
                    <tr key={cov} className={`border-b border-slate-50 ${rowBg} hover:bg-slate-100/50 transition-colors`}>
                      <td className="px-4 py-2 font-medium text-slate-700">{cov}</td>
                      <td className="px-4 py-2 text-right font-semibold text-slate-800">{(info.count || 0).toLocaleString()}</td>
                      <td className="px-4 py-2 text-center">
                        {info.inspect !== false ? <CheckCircle size={14} className="mx-auto text-blue-500" /> : <SkipForward size={14} className="mx-auto text-slate-300" />}
                      </td>
                      <td className="px-4 py-2 text-center">
                        {info.submit ? <CheckCircle size={14} className="mx-auto text-purple-500" /> : <SkipForward size={14} className="mx-auto text-slate-300" />}
                      </td>
                      <td className="px-4 py-2 text-center">
                        {info.snippet ? <CheckCircle size={14} className="mx-auto text-amber-500" /> : <SkipForward size={14} className="mx-auto text-slate-300" />}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

// ─── Main Monitoring page ───
export default function Monitoring() {
  const [data, setData] = useState(null);
  const [classData, setClassData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [monitor, classifications] = await Promise.all([
        api.getMonitor(),
        api.getClassifications().catch(() => null),
      ]);
      setData(monitor);
      setClassData(classifications);
    } catch (e) { console.error(e); }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
    const t = setInterval(fetchData, 30000);
    return () => clearInterval(t);
  }, [fetchData]);

  if (!data) return <div className="flex h-96 items-center justify-center text-slate-400">Loading monitoring data...</div>;

  const { scan_progress: sp = {}, freshness, coverage_breakdown, changes_today, recent_changes, daily_history } = data;
  const coverageData = Object.entries(coverage_breakdown || {}).map(([name, value]) => ({ name, value })).sort((a, b) => b.value - a.value);
  const historyData = (daily_history || []).slice(-14);
  const freshTotal = Object.values(freshness || {}).reduce((s, v) => s + v, 0);

  const tabs = [
    { id: 'overview', label: 'Overview' },
    { id: 'classification', label: 'Classification' },
    { id: 'changes', label: `Changes (${changes_today?.total || 0})` },
    { id: 'trend', label: 'Trend' },
  ];

  return (
    <div>
      <Header title="Monitoring" onRefresh={fetchData} loading={loading} />

      {/* Tab navigation */}
      <div className="bg-white px-6 py-3">
        <nav className="flex gap-2">
          {tabs.map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className={`px-5 py-2 text-xs font-semibold rounded-xl transition-all ${activeTab === tab.id
                ? 'bg-orange-100 text-orange-700 shadow-sm'
                : 'text-slate-500 hover:text-slate-700 hover:bg-slate-100'
              }`}>
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      <div className="space-y-5 px-5 py-5">

        {/* ─── OVERVIEW TAB ─── */}
        {activeTab === 'overview' && (
          <>
            {/* Scan Progress */}
            <div>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
                Scan Progress
                <span className="ml-1 rounded-lg bg-blue-100 px-2 py-0.5 text-[10px] text-blue-700">URL Inspection API</span>
              </h2>
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 mb-4">
                  <div>
                    <p className="text-[10px] font-semibold uppercase text-slate-400">Total in Sitemap</p>
                    <p className="text-2xl font-extrabold text-slate-800">{(sp.total_in_sitemap || 0).toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold uppercase text-slate-400">Inspected</p>
                    <p className="text-2xl font-extrabold text-blue-700">{(sp.inspected || 0).toLocaleString()}</p>
                    <p className="text-[10px] text-blue-600">{sp.scan_pct}% complete</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold uppercase text-emerald-500">Indexed</p>
                    <p className="text-2xl font-extrabold text-emerald-700">{(sp.indexed || 0).toLocaleString()}</p>
                  </div>
                  <div>
                    <p className="text-[10px] font-semibold uppercase text-red-500">Not Indexed</p>
                    <p className="text-2xl font-extrabold text-red-700">{(sp.not_indexed || 0).toLocaleString()}</p>
                  </div>
                </div>

                <ProgressBar current={sp.inspected || 0} total={sp.total_in_sitemap || 0} label="Scan Progress" />

                <div className="mt-3 grid grid-cols-3 gap-3 text-center text-xs">
                  <div className="rounded-xl bg-slate-50 p-2.5">
                    <p className="font-semibold text-slate-700">{(sp.daily_capacity || 0).toLocaleString()}</p>
                    <p className="text-slate-400">inspections/day</p>
                  </div>
                  <div className="rounded-xl bg-slate-50 p-2.5">
                    <p className="font-semibold text-slate-700">{(sp.remaining || 0).toLocaleString()}</p>
                    <p className="text-slate-400">remaining</p>
                  </div>
                  <div className="rounded-xl bg-orange-50 p-2.5">
                    <p className="font-semibold text-orange-700">{sp.est_days_to_complete || 0}</p>
                    <p className="text-slate-400">days to complete</p>
                  </div>
                </div>
              </div>
            </div>

            {/* Today's Changes */}
            <div>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
                Today's Changes
                <span className="ml-1 rounded-lg bg-amber-100 px-2 py-0.5 text-[10px] text-amber-700">{changes_today?.total || 0} detected</span>
              </h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <StatCard icon={TrendingUp} color="green" label="Newly Indexed" value={changes_today?.newly_indexed || 0} />
                <StatCard icon={TrendingDown} color="red" label="Dropped" value={changes_today?.dropped || 0} />
                <StatCard icon={Activity} color="yellow" label="Status Changes" value={changes_today?.status_changes || 0} />
                <StatCard icon={Zap} color="blue" label="Total Changes" value={changes_today?.total || 0} />
              </div>
            </div>

            {/* Data Freshness + Coverage */}
            <div className="grid gap-3 lg:grid-cols-2">
              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <h3 className="mb-3 text-sm font-semibold text-slate-700">
                  <Clock size={14} className="mr-1 inline text-slate-400" />
                  Data Freshness
                </h3>
                <div className="space-y-3">
                  <FreshnessRow label="Fresh (≤3 days)" count={freshness?.fresh_3d || 0} total={freshTotal} color="bg-emerald-500" />
                  <FreshnessRow label="3-7 days old" count={freshness?.stale_3_7d || 0} total={freshTotal} color="bg-lime-500" />
                  <FreshnessRow label="7-14 days old" count={freshness?.stale_7_14d || 0} total={freshTotal} color="bg-amber-500" />
                  <FreshnessRow label="14-30 days old" count={freshness?.stale_14_30d || 0} total={freshTotal} color="bg-orange-500" />
                  <FreshnessRow label="30+ days old" count={freshness?.stale_30d_plus || 0} total={freshTotal} color="bg-red-500" />
                </div>
              </div>

              <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
                <h3 className="mb-3 text-sm font-semibold text-slate-700">
                  Coverage Breakdown ({(sp.inspected || 0).toLocaleString()} inspected)
                </h3>
                {coverageData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={Math.max(180, coverageData.length * 32)}>
                    <BarChart data={coverageData} layout="vertical" margin={{ left: 10, right: 20 }}>
                      <XAxis type="number" tick={{ fontSize: 10 }} />
                      <YAxis type="category" dataKey="name" width={180} tick={{ fontSize: 10 }} />
                      <Tooltip formatter={(v) => (v ?? 0).toLocaleString()} />
                      <Bar dataKey="value" radius={[0, 6, 6, 0]} barSize={20}>
                        {coverageData.map((entry, i) => {
                          const n = entry.name.toLowerCase();
                          let fill = '#6366f1';
                          if (n.includes('indexed') && !n.includes('not')) fill = '#22c55e';
                          else if (n.includes('crawled')) fill = '#f59e0b';
                          else if (n.includes('discovered')) fill = '#3b82f6';
                          else if (n.includes('unknown')) fill = '#ef4444';
                          else if (n.includes('blocked') || n.includes('forbidden')) fill = '#94a3b8';
                          return <Cell key={i} fill={fill} />;
                        })}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex flex-col items-center justify-center py-10">
                    <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-slate-100 to-slate-200 mb-3">
                      <Activity size={24} className="text-slate-400" />
                    </div>
                    <p className="text-xs text-slate-400">No data yet — run the pipeline first</p>
                  </div>
                )}
              </div>
            </div>
          </>
        )}

        {/* ─── CLASSIFICATION TAB ─── */}
        {activeTab === 'classification' && (
          <ClassificationPanel classData={classData} />
        )}

        {/* ─── CHANGES TAB ─── */}
        {activeTab === 'changes' && (
          <>
            {/* De-indexed alert */}
            {(() => {
              const dropped = (recent_changes || []).filter(c => c.type === 'dropped_from_index');
              if (!dropped.length) return null;
              return (
                <div className="rounded-2xl border-2 border-red-200 bg-red-50 p-4 mb-4 shadow-sm">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-red-500 to-red-600 text-white shadow-sm">
                      <AlertTriangle size={16} />
                    </div>
                    <h3 className="text-sm font-bold text-red-800">De-indexed URLs Detected ({dropped.length})</h3>
                  </div>
                  <p className="text-xs text-red-700 mb-3">These URLs were previously indexed but Google dropped them. They will be re-checked and auto-submitted on the next pipeline run.</p>
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {dropped.slice(0, 20).map((ch, i) => {
                      const urlShort = (ch.url || '').replace('https://rudraretails.com/', '/').replace('https://www.rudraretails.com/', '/');
                      return (
                        <div key={i} className="flex items-center justify-between text-xs bg-white rounded-lg px-3 py-1.5 border border-red-100">
                          <span className="text-red-800 font-medium truncate max-w-[60%]" title={ch.url || ''}>{urlShort}</span>
                          <span className="text-red-500 flex items-center gap-1">
                            <span>{ch.old}</span>
                            <ArrowRight size={10} />
                            <span className="font-semibold">{ch.new}</span>
                          </span>
                          <span className="text-red-400 text-[10px] ml-2">{ch.date}</span>
                        </div>
                      );
                    })}
                    {dropped.length > 20 && (
                      <p className="text-[10px] text-red-500 pl-3">+{dropped.length - 20} more</p>
                    )}
                  </div>
                </div>
              );
            })()}

            {recent_changes && recent_changes.length > 0 ? (
              <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
                <div className="border-b border-slate-100 bg-gradient-to-r from-slate-50 to-white px-4 py-3 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-700">Recent Changes ({recent_changes.length})</h3>
                  <span className="text-[10px] text-slate-400">Auto-refreshes every 30s</span>
                </div>
                <div className="max-h-[600px] overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0">
                      <tr className="border-b border-slate-200 bg-slate-50/95 backdrop-blur text-left">
                        <th className="px-4 py-2.5 font-semibold text-slate-600">Date</th>
                        <th className="px-4 py-2.5 font-semibold text-slate-600">Type</th>
                        <th className="px-4 py-2.5 font-semibold text-slate-600">URL</th>
                        <th className="px-4 py-2.5 font-semibold text-slate-600">Change</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recent_changes.slice(0, 50).map((ch, i) => {
                        const color = ch.type === 'newly_indexed' ? 'text-emerald-700 bg-emerald-100'
                          : ch.type === 'dropped_from_index' ? 'text-red-700 bg-red-100'
                          : 'text-amber-700 bg-amber-100';
                        const typeLabel = ch.type === 'newly_indexed' ? 'INDEXED'
                          : ch.type === 'dropped_from_index' ? 'DROPPED' : 'CHANGED';
                        const urlShort = (ch.url || '').replace('https://rudraretails.com/', '/').replace('https://www.rudraretails.com/', '/');
                        return (
                          <tr key={i} className={`border-b border-slate-50 hover:bg-slate-50 transition-colors ${i % 2 === 0 ? 'bg-white' : 'bg-slate-50/30'}`}>
                            <td className="px-4 py-2 text-slate-500 whitespace-nowrap">{ch.date}</td>
                            <td className="px-4 py-2">
                              <span className={`inline-block rounded-lg px-2.5 py-1 text-[11px] font-bold ${color}`}>
                                {typeLabel}
                              </span>
                            </td>
                            <td className="px-4 py-2 max-w-xs truncate text-slate-700" title={ch.url || ''}>{urlShort}</td>
                            <td className="px-4 py-2 text-slate-500">
                              <span className="inline-flex items-center gap-1">
                                <span className="truncate max-w-[140px]">{ch.old}</span>
                                <ArrowRight size={10} className="shrink-0" />
                                <span className="truncate max-w-[140px] font-semibold">{ch.new}</span>
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center text-slate-400 shadow-sm">
                <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br from-slate-100 to-slate-200 mx-auto mb-3">
                  <Activity size={28} className="text-slate-400" />
                </div>
                <p className="text-sm font-medium text-slate-500">No changes detected yet.</p>
                <p className="text-xs mt-1 text-slate-400">Run <code className="bg-slate-100 px-1.5 py-0.5 rounded-lg text-slate-600">python indexing_pipeline.py daily</code> to start monitoring.</p>
              </div>
            )}
          </>
        )}

        {/* ─── TREND TAB ─── */}
        {activeTab === 'trend' && (
          <>
            {historyData.length > 1 ? (
              <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
                <h3 className="mb-4 text-sm font-semibold text-slate-700">Indexing Trend (last 14 days)</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={historyData}>
                    <defs>
                      <linearGradient id="gradIndexed" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#22c55e" stopOpacity={0.2} />
                        <stop offset="95%" stopColor="#22c55e" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="gradNotIndexed" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#ef4444" stopOpacity={0.15} />
                        <stop offset="95%" stopColor="#ef4444" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="gradChecked" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#3b82f6" stopOpacity={0.1} />
                        <stop offset="95%" stopColor="#3b82f6" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={d => d.slice(5)} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip contentStyle={{ fontSize: 12, borderRadius: 12 }} />
                    <Legend />
                    <Area type="monotoneX" dataKey="indexed" stroke="#22c55e" fill="url(#gradIndexed)" name="Indexed" strokeWidth={2.5} dot={{ r: 3 }} />
                    <Area type="monotoneX" dataKey="not_indexed" stroke="#ef4444" fill="url(#gradNotIndexed)" name="Not Indexed" strokeWidth={2.5} dot={{ r: 3 }} />
                    <Area type="monotoneX" dataKey="checked" stroke="#3b82f6" fill="url(#gradChecked)" name="Checked Today" strokeWidth={1.5} dot={false} strokeDasharray="5 5" />
                    <Line type="monotoneX" dataKey="newly_indexed" stroke="#a3e635" name="Newly Indexed" strokeWidth={1.5} dot={false} />
                  </AreaChart>
                </ResponsiveContainer>

                {/* Daily stats table */}
                <div className="mt-4 overflow-x-auto rounded-xl border border-slate-100">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-slate-200 bg-gradient-to-r from-slate-50 to-white text-left">
                        <th className="px-4 py-2.5 font-semibold text-slate-600">Date</th>
                        <th className="px-4 py-2.5 font-semibold text-emerald-600 text-right">Indexed</th>
                        <th className="px-4 py-2.5 font-semibold text-red-600 text-right">Not Indexed</th>
                        <th className="px-4 py-2.5 font-semibold text-blue-600 text-right">Checked</th>
                        <th className="px-4 py-2.5 font-semibold text-lime-600 text-right">New+</th>
                        <th className="px-4 py-2.5 font-semibold text-red-600 text-right">Drop-</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...historyData].reverse().map((d, i) => (
                        <tr key={i} className={`border-b border-slate-50 hover:bg-slate-100/50 transition-colors ${i % 2 === 0 ? 'bg-white' : 'bg-slate-50/50'}`}>
                          <td className="px-4 py-2 font-medium text-slate-700">{d.date}</td>
                          <td className="px-4 py-2 text-right text-emerald-700">{(d.indexed || 0).toLocaleString()}</td>
                          <td className="px-4 py-2 text-right text-red-700">{(d.not_indexed || 0).toLocaleString()}</td>
                          <td className="px-4 py-2 text-right text-blue-700">{(d.checked || 0).toLocaleString()}</td>
                          <td className="px-4 py-2 text-right text-lime-700">{d.newly_indexed ? `+${d.newly_indexed}` : '-'}</td>
                          <td className="px-4 py-2 text-right text-red-700">{d.dropped ? `-${d.dropped}` : '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div className="rounded-2xl border border-slate-200 bg-white p-10 text-center text-slate-400 shadow-sm">
                <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br from-slate-100 to-slate-200 mx-auto mb-3">
                  <TrendingUp size={28} className="text-slate-400" />
                </div>
                <p className="text-sm font-medium text-slate-500">Need at least 2 daily snapshots to show trends.</p>
                <p className="text-xs mt-1 text-slate-400">Run <code className="bg-slate-100 px-1.5 py-0.5 rounded-lg text-slate-600">python indexing_pipeline.py daily</code> each day.</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
