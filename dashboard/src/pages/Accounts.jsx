import { useState, useEffect } from 'react';
import { Server, RefreshCw } from 'lucide-react';
import Header from '../components/Header';
import { api } from '../lib/api';

export default function Accounts() {
  const [accounts, setAccounts] = useState([]);
  const [loading, setLoading] = useState(true);

  const fetchAccounts = async () => {
    setLoading(true);
    try {
      const d = await api.getAccounts();
      setAccounts(d.accounts || []);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  useEffect(() => { fetchAccounts(); }, []);

  const pct = (used, limit) => limit ? Math.min(100, (used / limit * 100)).toFixed(0) : 0;
  const barColor = (used, limit) => {
    const p = limit ? used / limit * 100 : 0;
    if (p >= 90) return 'bg-red-500';
    if (p >= 60) return 'bg-amber-500';
    return 'bg-emerald-500';
  };

  return (
    <div>
      <Header title="Service Accounts" onRefresh={fetchAccounts} loading={loading} />
      <div className="space-y-6 p-6">
        <p className="text-sm text-slate-500">
          {accounts.length} service account{accounts.length !== 1 ? 's' : ''} configured. Quotas reset at midnight Pacific Time (~12:30 PM IST).
        </p>

        {accounts.length === 0 && !loading && (
          <div className="rounded-xl border border-slate-200 bg-white p-8 text-center">
            <Server size={40} className="mx-auto mb-3 text-slate-300" />
            <p className="text-sm text-slate-500">No service accounts found. Add credentials JSON files and run the pipeline.</p>
          </div>
        )}

        <div className="grid gap-4 lg:grid-cols-2">
          {accounts.map((a, i) => (
            <div key={a.name || i} className="rounded-xl border border-slate-200 bg-white p-5">
              <div className="mb-4 flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-blue-100 text-sm font-bold text-blue-700">
                  {i + 1}
                </div>
                <div>
                  <p className="text-sm font-semibold text-slate-800">{a.name}</p>
                  <p className="text-[10px] text-slate-400">{a.email || ''}</p>
                </div>
              </div>

              <div className="space-y-4">
                {/* Inspect quota */}
                <div>
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="font-semibold text-slate-600">URL Inspection</span>
                    <span className="text-slate-500">{a.inspect_used} / {a.inspect_limit} ({pct(a.inspect_used, a.inspect_limit)}%)</span>
                  </div>
                  <div className="h-2.5 overflow-hidden rounded-full bg-slate-100">
                    <div className={`h-full rounded-full transition-all ${barColor(a.inspect_used, a.inspect_limit)}`}
                      style={{ width: `${pct(a.inspect_used, a.inspect_limit)}%` }} />
                  </div>
                  <p className="mt-1 text-[10px] text-slate-400">{(a.inspect_limit || 0) - (a.inspect_used || 0)} remaining</p>
                </div>

                {/* Index quota */}
                <div>
                  <div className="mb-1 flex justify-between text-xs">
                    <span className="font-semibold text-slate-600">Indexing API</span>
                    <span className="text-slate-500">{a.index_used || 0} / {a.index_limit || 0} ({pct(a.index_used, a.index_limit)}%)</span>
                  </div>
                  <div className="h-2.5 overflow-hidden rounded-full bg-slate-100">
                    <div className={`h-full rounded-full transition-all ${barColor(a.index_used, a.index_limit)}`}
                      style={{ width: `${pct(a.index_used, a.index_limit)}%` }} />
                  </div>
                  <p className="mt-1 text-[10px] text-slate-400">{(a.index_limit || 0) - (a.index_used || 0)} remaining</p>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Totals */}
        {accounts.length > 1 && (
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="mb-2 text-sm font-semibold text-slate-700">Combined Quotas</h3>
            <div className="grid grid-cols-2 gap-4 text-center">
              <div>
                <p className="text-2xl font-extrabold text-blue-700">{accounts.reduce((s, a) => s + ((a.inspect_limit || 0) - (a.inspect_used || 0)), 0).toLocaleString()}</p>
                <p className="text-xs text-slate-500">Inspections remaining</p>
              </div>
              <div>
                <p className="text-2xl font-extrabold text-orange-700">{accounts.reduce((s, a) => s + ((a.index_limit || 0) - (a.index_used || 0)), 0).toLocaleString()}</p>
                <p className="text-xs text-slate-500">Index submissions remaining</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
