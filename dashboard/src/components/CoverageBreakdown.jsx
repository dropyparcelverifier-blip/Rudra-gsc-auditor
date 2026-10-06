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
      <div className="rounded-xl border border-slate-200 bg-white p-4">
        <div className="space-y-3">
          {reasons.map(([reason, count]) => {
            const pct = totalTracked ? (count / totalTracked * 100).toFixed(1) : 0;
            const color = reason.includes('robots') ? 'bg-red-500'
              : reason.includes('not indexed') ? 'bg-amber-500'
              : reason.includes('unknown') ? 'bg-orange-500'
              : 'bg-slate-400';
            return (
              <div key={reason}>
                <div className="flex items-center justify-between text-xs mb-1">
                  <span className="font-medium text-slate-700">{reason}</span>
                  <span className="text-slate-500">{count.toLocaleString()} ({pct}%)</span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                  <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
