import { RefreshCw, Zap } from 'lucide-react';

export default function Header({ title, subtitle, onRefresh, onSmartSync, loading, lastFetched }) {
  const timeAgo = lastFetched ? formatTimeAgo(lastFetched) : null;

  return (
    <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200/60 bg-white/80 backdrop-blur-xl px-6 py-4">
      <div className="flex items-center gap-3">
        <div className="h-7 w-1.5 rounded-full bg-gradient-to-b from-orange-500 to-red-500 shadow-sm shadow-orange-200" />
        <div>
          <h1 className="text-xl font-extrabold text-slate-900 tracking-tight">{title}</h1>
          {subtitle && <p className="text-xs text-slate-400 mt-0.5">{subtitle}</p>}
        </div>
      </div>
      <div className="flex items-center gap-3">
        {timeAgo && (
          <span className="text-[11px] text-slate-400 bg-slate-50 rounded-lg px-2.5 py-1">Updated {timeAgo}</span>
        )}
        {onSmartSync && (
          <button onClick={onSmartSync} disabled={loading}
            className="flex items-center gap-1.5 rounded-xl bg-gradient-to-r from-emerald-600 to-teal-600 px-4 py-2 text-xs font-bold text-white shadow-sm shadow-emerald-200/50 transition-all hover:shadow-md hover:-translate-y-0.5 disabled:opacity-50">
            <Zap size={14} /> Smart Sync
          </button>
        )}
        {onRefresh && (
          <button onClick={onRefresh} disabled={loading}
            className="flex items-center gap-1.5 rounded-xl border border-slate-200 bg-white px-4 py-2 text-xs font-bold text-slate-700 transition-all hover:bg-slate-50 hover:shadow-sm hover:-translate-y-0.5 disabled:opacity-50">
            <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
          </button>
        )}
      </div>
    </header>
  );
}

function formatTimeAgo(date) {
  const seconds = Math.floor((Date.now() - new Date(date).getTime()) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}
