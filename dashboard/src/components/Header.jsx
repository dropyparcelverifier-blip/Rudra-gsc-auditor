import { RefreshCw, Zap } from 'lucide-react';

export default function Header({ title, onRefresh, onSmartSync, loading }) {
  return (
    <header className="flex items-center justify-between border-b border-slate-200 bg-white px-6 py-3.5">
      <div className="flex items-center gap-3">
        <div className="h-6 w-1 rounded-full bg-gradient-to-b from-orange-500 to-red-500" />
        <h1 className="text-lg font-bold text-slate-900">{title}</h1>
      </div>
      <div className="flex items-center gap-2">
        {onSmartSync && (
          <button onClick={onSmartSync} disabled={loading}
            className="flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-emerald-600 to-teal-600 px-3 py-1.5 text-xs font-semibold text-white shadow-sm transition hover:shadow-md disabled:opacity-50">
            <Zap size={14} /> Smart Sync
          </button>
        )}
        {onRefresh && (
          <button onClick={onRefresh} disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 hover:shadow-sm disabled:opacity-50">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        )}
      </div>
    </header>
  );
}
