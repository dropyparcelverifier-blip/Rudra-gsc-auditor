import clsx from 'clsx';

const colorMap = {
  green: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  red: 'bg-red-50 text-red-700 border-red-200',
  blue: 'bg-blue-50 text-blue-700 border-blue-200',
  orange: 'bg-orange-50 text-orange-700 border-orange-200',
  purple: 'bg-purple-50 text-purple-700 border-purple-200',
  cyan: 'bg-cyan-50 text-cyan-700 border-cyan-200',
  yellow: 'bg-amber-50 text-amber-700 border-amber-200',
  gray: 'bg-slate-50 text-slate-600 border-slate-200',
};

const iconBgMap = {
  green: 'bg-emerald-100', red: 'bg-red-100', blue: 'bg-blue-100',
  orange: 'bg-orange-100', purple: 'bg-purple-100', cyan: 'bg-cyan-100',
  yellow: 'bg-amber-100', gray: 'bg-slate-100',
};

export default function StatCard({ label, value, color = 'blue', icon: Icon, delta, subtitle }) {
  return (
    <div className={clsx(
      'group rounded-2xl border p-4 shadow-sm hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300 cursor-default',
      colorMap[color]
    )}>
      <div className="flex items-start justify-between">
        <div className="min-w-0">
          <p className="text-[11px] font-semibold uppercase tracking-wider opacity-70">{label}</p>
          <p className="mt-1 text-2xl font-extrabold tabular-nums tracking-tight">
            {typeof value === 'number' ? value.toLocaleString() : (value ?? '—')}
          </p>
          {subtitle && <p className="mt-0.5 text-[10px] opacity-60 truncate">{subtitle}</p>}
          {delta && (
            <p className={clsx('mt-1 text-xs font-semibold', delta.startsWith('+') ? 'text-emerald-600' : delta.startsWith('-') ? 'text-red-600' : '')}>
              {delta}
            </p>
          )}
        </div>
        {Icon && (
          <div className={clsx('rounded-xl p-2.5 shadow-sm transition-transform duration-200 group-hover:scale-110', iconBgMap[color])}>
            <Icon size={18} />
          </div>
        )}
      </div>
    </div>
  );
}
