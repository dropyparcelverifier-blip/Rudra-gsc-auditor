import { useState, useEffect } from 'react';
import { Server, RefreshCw } from 'lucide-react';
import Header from '../components/Header';
import { api } from '../lib/api';

export default function Accounts() {
  const [accounts, setAccounts] = useState([]);
  const [sharedQuota, setSharedQuota] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchAccounts = async () => {
    setLoading(true);
    try {
      const d = await api.getAccounts();
      setAccounts(d.accounts || []);
      setSharedQuota(d.shared_quota || null);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  useEffect(() => { fetchAccounts(); }, []);

  const pct = (used, limit) => limit ? Math.min(100, (used / limit * 100)).toFixed(0) : 0;
  const barColor = (used, limit) => {
    const p = limit ? used / limit * 100 : 0;
    if (p >= 90) return 'from-red-400 to-red-600';
    if (p >= 60) return 'from-amber-400 to-amber-600';
    return 'from-emerald-400 to-emerald-600';
  };

  return (
    <div>
      <Header title="Service Accounts" onRefresh={fetchAccounts} loading={loading} />
      <div className="space-y-6 p-6">
        <p className="text-sm text-slate-500">
          {accounts.length} service account{accounts.length !== 1 ? 's' : ''} configured. Quotas reset at midnight Pacific Time (~12:30 PM IST).
        </p>

        {/* Shared Inspection Quota */}
        {sharedQuota && (
          <div className="relative rounded-2xl border border-blue-200 bg-gradient-to-br from-blue-50 via-blue-50 to-indigo-50 p-5 shadow-sm ring-1 ring-blue-100/50">
            <div className="absolute inset-0 rounded-2xl bg-gradient-to-r from-blue-400/5 to-indigo-400/5 pointer-events-none" />
            <h3 className="mb-1 text-sm font-bold text-blue-900">URL Inspection Quota (Shared per Property)</h3>
            <p className="mb-3 text-[11px] text-blue-600">This quota is shared across ALL service accounts for rudraretails.com</p>
            <div className="mb-1.5 flex justify-between text-xs">
              <span className="font-semibold text-blue-800">Used today</span>
              <span className="font-bold text-blue-900">{sharedQuota.inspect_used.toLocaleString()} / {sharedQuota.inspect_limit.toLocaleString()}</span>
            </div>
            <div className="h-4 overflow-hidden rounded-full bg-blue-200/60 shadow-inner">
              <div className={`h-full rounded-full bg-gradient-to-r transition-all ${sharedQuota.inspect_used >= sharedQuota.inspect_limit * 0.9 ? 'from-red-400 to-red-600' : sharedQuota.inspect_used >= sharedQuota.inspect_limit * 0.6 ? 'from-amber-400 to-amber-600' : 'from-blue-500 to-indigo-600'}`}
                style={{ width: `${Math.min(100, sharedQuota.inspect_limit ? (sharedQuota.inspect_used / sharedQuota.inspect_limit * 100) : 0)}%` }} />
            </div>
            <p className="mt-1.5 text-[11px] text-blue-600">{(sharedQuota.inspect_limit - sharedQuota.inspect_used).toLocaleString()} remaining &middot; Resets at midnight PT</p>
          </div>
        )}

        {accounts.length === 0 && !loading && (
          <div className="rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
            <div className="flex h-14 w-14 items-center justify-center rounded-xl bg-gradient-to-br from-slate-100 to-slate-200 mx-auto mb-3">
              <Server size={28} className="text-slate-400" />
            </div>
            <p className="text-sm text-slate-500">No service accounts found. Add credentials JSON files and run the pipeline.</p>
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-2">
          {accounts.map((a, i) => (
            <div key={a.name || i} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
              <div className="mb-4 flex items-center gap-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 text-sm font-bold text-white shadow-sm">
                  {i + 1}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-slate-800 truncate">{a.name}</p>
                  <p className="text-[10px] text-slate-400 truncate">{a.email || ''}</p>
                </div>
              </div>

              <div className="space-y-4">
                {/* Inspections done by this account */}
                <div>
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="font-semibold text-slate-600">Inspections (this account)</span>
                    <span className="text-slate-500">{a.inspect_used || 0} done today</span>
                  </div>
                  <p className="text-[10px] text-slate-400">Shares the property-wide 2,000/day pool</p>
                </div>

                {/* Index quota — this IS per-account */}
                <div>
                  <div className="mb-1.5 flex justify-between text-xs">
                    <span className="font-semibold text-slate-600">Indexing API (per account)</span>
                    <span className="text-slate-500">{a.index_used || 0} / {a.index_limit || 0} ({pct(a.index_used, a.index_limit)}%)</span>
                  </div>
                  <div className="h-3.5 overflow-hidden rounded-full bg-slate-100 shadow-inner">
                    <div className={`h-full rounded-full bg-gradient-to-r transition-all ${barColor(a.index_used, a.index_limit)}`}
                      style={{ width: `${pct(a.index_used, a.index_limit)}%` }} />
                  </div>
                  <p className="mt-1 text-[10px] text-slate-400">{(a.index_limit || 0) - (a.index_used || 0)} remaining</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Totals */}
        {accounts.length > 1 && sharedQuota && (
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-slate-700">Daily Quota Summary</h3>
            <div className="grid grid-cols-2 gap-4 text-center">
              <div>
                <p className="text-3xl font-extrabold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">{(sharedQuota.inspect_limit - sharedQuota.inspect_used).toLocaleString()}</p>
                <p className="text-xs text-slate-500 mt-1">Inspections remaining (shared)</p>
                <p className="text-[10px] text-slate-400">2,000/day for entire property</p>
              </div>
              <div>
                <p className="text-3xl font-extrabold bg-gradient-to-r from-orange-500 to-red-500 bg-clip-text text-transparent">{(sharedQuota.index_limit - sharedQuota.index_used).toLocaleString()}</p>
                <p className="text-xs text-slate-500 mt-1">Index submissions remaining</p>
                <p className="text-[10px] text-slate-400">200/day per GCP project (shared)</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
