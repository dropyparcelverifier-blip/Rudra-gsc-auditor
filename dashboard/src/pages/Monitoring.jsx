import { useState, useEffect, useCallback } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend, LineChart, Line, Cell } from 'recharts';
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
    { icon: Eye, label: 'Need Inspection', value: action_counts?.inspect || 0, color: 'text-blue-700', bg: 'bg-blue-50', border: 'border-blue-200', desc: 'URLs that should be checked via URL Inspection API' },
    { icon: Send, label: 'Submit for Indexing', value: action_counts?.submit || 0, color: 'text-purple-700', bg: 'bg-purple-50', border: 'border-purple-200', desc: 'Not-indexed URLs eligible for Indexing API submission' },
    { icon: Zap, label: 'Track Snippets', value: action_counts?.snippet || 0, color: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200', desc: 'Indexed product pages — track rich result / product snippet status' },
    { icon: Search, label: 'Search Analytics', value: action_counts?.search || 0, color: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200', desc: 'Indexed pages — track clicks, impressions, CTR, position' },
  ];

  const coverageRows = Object.entries(coverage_actions || {})
    .sort((a, b) => (b[1].count || 0) - (a[1].count || 0))
    .slice(0, 12);

  return (
    <div>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
        <Filter size={14} className="mr-1 inline" />
        Smart URL Classification
        <span className="ml-2 rounded bg-indigo-100 px-1.5 py-0.5 text-[10px] font-semibold text-indigo-700 normal-case">
          {(total_tracked || 0).toLocaleString()} tracked
        </span>
      </h2>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 mb-4">
        {items.map(({ icon: Icon, label, value, color, bg, border, desc }) => (
          <div key={label} className={`rounded-xl border ${border} ${bg} p-4`}>
            <div className={`flex items-center gap-2 ${color}`}>
              <Icon size={16} />
              <span className="text-[11px] font-semibold uppercase tracking-wide">{label}</span>
            </div>
            <p className={`mt-2 text-2xl font-extrabold ${color}`}>{value.toLocaleString()}</p>
            <p className="mt-1 text-[10px] text-slate-500 leading-tight">{desc}</p>
          </div>
        ))}
      </div>

      {coverageRows.length > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white">
          <div className="border-b border-slate-100 px-4 py-2.5">
            <h3 className="text-xs font-semibold text-slate-600">Coverage Status → Actions</h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-slate-100 bg-slate-50 text-left">
                  <th className="px-3 py-2 font-semibold text-slate-600">Coverage Status</th>
                  <th className="px-3 py-2 font-semibold text-slate-600 text-right">Count</th>
                  <th className="px-3 py-2 font-semibold text-slate-600 text-center">Inspect</th>
                  <th className="px-3 py-2 font-semibold text-slate-600 text-center">Submit</th>
                  <th className="px-3 py-2 font-semibold text-slate-600 text-center">Snippets</th>
                </tr>
              </thead>
              <tbody>
                {coverageRows.map(([cov, info]) => {
                  const isIndexed = cov.toLowerCase().includes('indexed') && !cov.toLowerCase().includes('not');
                  const rowBg = isIndexed ? 'bg-emerald-50/40' : '';
                  return (
                    <tr key={cov} className={`border-b border-slate-50 ${rowBg}`}>
                      <td className="px-3 py-1.5 font-medium text-slate-700">{cov}</td>
                      <td className="px-3 py-1.5 text-right font-semibold text-slate-800">{(info.count || 0).toLocaleString()}</td>
                      <td className="px-3 py-1.5 text-center">
                        {info.inspect !== false ? <CheckCircle size={14} className="mx-auto text-blue-500" /> : <SkipForward size={14} className="mx-auto text-slate-300" />}
                      </td>
                      <td className="px-3 py-1.5 text-center">
                        {info.submit ? <CheckCircle size={14} className="mx-auto text-purple-500" /> : <SkipForward size={14} className="mx-auto text-slate-300" />}
                      </td>
                      <td className="px-3 py-1.5 text-center">
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
      <div className="border-b border-slate-200 bg-white px-6">
        <nav className="flex gap-1 -mb-px">
          {tabs.map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2.5 text-xs font-semibold border-b-2 transition-colors ${activeTab === tab.id
                ? 'border-orange-500 text-orange-700'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
              }`}>
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      <div className="space-y-6 p-6">

        {/* ─── OVERVIEW TAB ─── */}
        {activeTab === 'overview' && (
          <>
            {/* Scan Progress */}
            <div>
              <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
                Scan Progress
                <span className="ml-1 rounded bg-blue-100 px-1.5 py-0.5 text-[10px] text-blue-700">URL Inspection API</span>
              </h2>
              <div className="rounded-xl border border-slate-200 bg-white p-5">
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4 mb-4">
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
                  <div className="rounded-lg bg-slate-50 p-2">
                    <p className="font-semibold text-slate-700">{(sp.daily_capacity || 0).toLocaleString()}</p>
                    <p className="text-slate-400">inspections/day</p>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-2">
                    <p className="font-semibold text-slate-700">{(sp.remaining || 0).toLocaleString()}</p>
                    <p className="text-slate-400">remaining</p>
                  </div>
                  <div className="rounded-lg bg-orange-50 p-2">
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
                <span className="ml-1 rounded bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-700">{changes_today?.total || 0} detected</span>
              </h2>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <StatCard icon={TrendingUp} color="green" label="Newly Indexed" value={changes_today?.newly_indexed || 0} />
                <StatCard icon={TrendingDown} color="red" label="Dropped" value={changes_today?.dropped || 0} />
                <StatCard icon={Activity} color="yellow" label="Status Changes" value={changes_today?.status_changes || 0} />
                <StatCard icon={Zap} color="blue" label="Total Changes" value={changes_today?.total || 0} />
              </div>
            </div>

            {/* Data Freshness + Coverage */}
            <div className="grid gap-4 lg:grid-cols-2">
              <div className="rounded-xl border border-slate-200 bg-white p-4">
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

              <div className="rounded-xl border border-slate-200 bg-white p-4">
                <h3 className="mb-3 text-sm font-semibold text-slate-700">
                  Coverage Breakdown ({(sp.inspected || 0).toLocaleString()} inspected)
                </h3>
                {coverageData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={Math.max(180, coverageData.length * 32)}>
                    <BarChart data={coverageData} layout="vertical" margin={{ left: 10, right: 20 }}>
                      <XAxis type="number" tick={{ fontSize: 10 }} />
                      <YAxis type="category" dataKey="name" width={180} tick={{ fontSize: 10 }} />
                      <Tooltip formatter={(v) => (v ?? 0).toLocaleString()} />
                      <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20}>
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
                  <p className="text-xs text-slate-400 text-center py-8">No data yet — run the pipeline first</p>
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
                <div className="rounded-xl border-2 border-red-200 bg-red-50 p-4 mb-4">
                  <div className="flex items-center gap-2 mb-2">
                    <AlertTriangle size={18} className="text-red-600" />
                    <h3 className="text-sm font-bold text-red-800">De-indexed URLs Detected ({dropped.length})</h3>
                  </div>
                  <p className="text-xs text-red-700 mb-3">These URLs were previously indexed but Google dropped them. They will be re-checked and auto-submitted on the next pipeline run.</p>
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {dropped.slice(0, 20).map((ch, i) => {
                      const urlShort = (ch.url || '').replace('https://rudraretails.com/', '/').replace('https://www.rudraretails.com/', '/');
                      return (
                        <div key={i} className="flex items-center justify-between text-xs bg-white rounded px-3 py-1.5 border border-red-100">
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
              <div className="rounded-xl border border-slate-200 bg-white">
                <div className="border-b border-slate-100 px-4 py-3 flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-slate-700">Recent Changes ({recent_changes.length})</h3>
                  <span className="text-[10px] text-slate-400">Auto-refreshes every 30s</span>
                </div>
                <div className="max-h-[600px] overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="sticky top-0">
                      <tr className="border-b border-slate-100 bg-slate-50 text-left">
                        <th className="px-3 py-2 font-semibold text-slate-600">Date</th>
                        <th className="px-3 py-2 font-semibold text-slate-600">Type</th>
                        <th className="px-3 py-2 font-semibold text-slate-600">URL</th>
                        <th className="px-3 py-2 font-semibold text-slate-600">Change</th>
                      </tr>
                    </thead>
                    <tbody>
                      {recent_changes.slice(0, 50).map((ch, i) => {
                        const color = ch.type === 'newly_indexed' ? 'text-emerald-700 bg-emerald-50'
                          : ch.type === 'dropped_from_index' ? 'text-red-700 bg-red-50'
                          : 'text-amber-700 bg-amber-50';
                        const typeLabel = ch.type === 'newly_indexed' ? 'INDEXED'
                          : ch.type === 'dropped_from_index' ? 'DROPPED' : 'CHANGED';
                        const urlShort = (ch.url || '').replace('https://rudraretails.com/', '/').replace('https://www.rudraretails.com/', '/');
                        return (
                          <tr key={i} className="border-b border-slate-50 hover:bg-slate-50">
                            <td className="px-3 py-1.5 text-slate-500 whitespace-nowrap">{ch.date}</td>
                            <td className="px-3 py-1.5">
                              <span className={`rounded-full px-2 py-0.5 text-[10px] font-semibold ${color}`}>
                                {typeLabel}
                              </span>
                            </td>
                            <td className="px-3 py-1.5 max-w-xs truncate text-slate-700" title={ch.url || ''}>{urlShort}</td>
                            <td className="px-3 py-1.5 text-slate-500">
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
              <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-400">
                <Activity size={40} className="mx-auto mb-3 text-slate-300" />
                <p className="text-sm">No changes detected yet.</p>
                <p className="text-xs mt-1">Run <code className="bg-slate-100 px-1 rounded">python indexing_pipeline.py daily</code> to start monitoring.</p>
              </div>
            )}
          </>
        )}

        {/* ─── TREND TAB ─── */}
        {activeTab === 'trend' && (
          <>
            {historyData.length > 1 ? (
              <div className="rounded-xl border border-slate-200 bg-white p-5">
                <h3 className="mb-4 text-sm font-semibold text-slate-700">Indexing Trend (last 14 days)</h3>
                <ResponsiveContainer width="100%" height={300}>
                  <LineChart data={historyData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={d => d.slice(5)} />
                    <YAxis tick={{ fontSize: 10 }} />
                    <Tooltip contentStyle={{ fontSize: 12 }} />
                    <Legend />
                    <Line type="monotone" dataKey="indexed" stroke="#22c55e" name="Indexed" strokeWidth={2.5} dot={{ r: 3 }} />
                    <Line type="monotone" dataKey="not_indexed" stroke="#ef4444" name="Not Indexed" strokeWidth={2.5} dot={{ r: 3 }} />
                    <Line type="monotone" dataKey="checked" stroke="#3b82f6" name="Checked Today" strokeWidth={1.5} dot={false} strokeDasharray="5 5" />
                    <Line type="monotone" dataKey="newly_indexed" stroke="#a3e635" name="Newly Indexed" strokeWidth={1.5} dot={false} />
                  </LineChart>
                </ResponsiveContainer>

                {/* Daily stats table */}
                <div className="mt-4 overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-slate-100 bg-slate-50 text-left">
                        <th className="px-3 py-2 font-semibold text-slate-600">Date</th>
                        <th className="px-3 py-2 font-semibold text-emerald-600 text-right">Indexed</th>
                        <th className="px-3 py-2 font-semibold text-red-600 text-right">Not Indexed</th>
                        <th className="px-3 py-2 font-semibold text-blue-600 text-right">Checked</th>
                        <th className="px-3 py-2 font-semibold text-lime-600 text-right">New+</th>
                        <th className="px-3 py-2 font-semibold text-red-600 text-right">Drop-</th>
                      </tr>
                    </thead>
                    <tbody>
                      {[...historyData].reverse().map((d, i) => (
                        <tr key={i} className="border-b border-slate-50 hover:bg-slate-50">
                          <td className="px-3 py-1.5 font-medium text-slate-700">{d.date}</td>
                          <td className="px-3 py-1.5 text-right text-emerald-700">{(d.indexed || 0).toLocaleString()}</td>
                          <td className="px-3 py-1.5 text-right text-red-700">{(d.not_indexed || 0).toLocaleString()}</td>
                          <td className="px-3 py-1.5 text-right text-blue-700">{(d.checked || 0).toLocaleString()}</td>
                          <td className="px-3 py-1.5 text-right text-lime-700">{d.newly_indexed ? `+${d.newly_indexed}` : '-'}</td>
                          <td className="px-3 py-1.5 text-right text-red-700">{d.dropped ? `-${d.dropped}` : '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-400">
                <TrendingUp size={40} className="mx-auto mb-3 text-slate-300" />
                <p className="text-sm">Need at least 2 daily snapshots to show trends.</p>
                <p className="text-xs mt-1">Run <code className="bg-slate-100 px-1 rounded">python indexing_pipeline.py daily</code> each day.</p>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
