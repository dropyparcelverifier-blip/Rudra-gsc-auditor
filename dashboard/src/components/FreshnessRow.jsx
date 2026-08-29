export default function FreshnessRow({ label, count, total, color }) {
  const pct = total ? (count / total * 100).toFixed(1) : 0;
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1">
        <span className="font-medium text-slate-700">{label}</span>
        <span className="tabular-nums text-slate-500">{count.toLocaleString()} <span className="font-semibold">({pct}%)</span></span>
      </div>
      <div className="h-3 overflow-hidden rounded-full bg-slate-100 shadow-inner">
        <div className={`h-full rounded-full bg-gradient-to-r ${color} transition-all duration-500 ease-out`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
