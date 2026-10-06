export default function ProgressBar({ current, total, label, color = 'from-blue-500 to-cyan-500' }) {
  const pct = total > 0 ? Math.round((current / total) * 100 * 10) / 10 : 0;
  return (
    <div>
      <div className="flex items-center justify-between text-xs text-slate-500 mb-1">
        <span className="font-medium">{label}</span>
        <span>{current.toLocaleString()} / {total.toLocaleString()} ({pct}%)</span>
      </div>
      <div className="h-5 overflow-hidden rounded-full bg-slate-100">
        <div className={`h-full rounded-full bg-gradient-to-r ${color} transition-all duration-700 flex items-center justify-center text-[10px] font-bold text-white`}
          style={{ width: `${Math.max(2, pct)}%` }}>
          {pct > 8 ? `${pct}%` : ''}
        </div>
      </div>
    </div>
  );
}
