export default function CoverageBreakdown({ breakdown, totalTracked, title }) {
  if (!breakdown) return null;

  const reasons = Object.entries(breakdown)
    .filter(([k]) => k !== 'Submitted and indexed')
    .sort((a, b) => b[1] - a[1]);

  if (reasons.length === 0) return null;

  return (
    <div>
      {title && (
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
          {title}
        </h2>
      )}
      <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="space-y-3">
          {reasons.map(([reason, count]) => {
            const pct = totalTracked ? (count / totalTracked * 100).toFixed(1) : 0;
            const color = reason.includes('robots') ? 'from-red-400 to-red-600'
              : reason.includes('not indexed') ? 'from-amber-400 to-amber-600'
              : reason.includes('unknown') ? 'from-orange-400 to-orange-600'
              : 'from-slate-300 to-slate-500';
            return (
              <div key={reason}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium text-slate-700 truncate mr-2">{reason}</span>
                  <span className="tabular-nums text-slate-500 flex-shrink-0">{count.toLocaleString()} ({pct}%)</span>
                </div>
                <div className="h-3 overflow-hidden rounded-full bg-slate-100 shadow-inner">
                  <div className={`h-full rounded-full bg-gradient-to-r ${color} transition-all duration-500 ease-out`} style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
