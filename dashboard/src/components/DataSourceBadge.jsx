const SOURCES = {
  gsc_pages: { label: 'GSC Pages', bg: 'bg-emerald-50 border-emerald-200', text: 'text-emerald-700' },
  gsc_report: { label: 'GSC Pages', bg: 'bg-emerald-50 border-emerald-200', text: 'text-emerald-700' },
  search_analytics: { label: 'Analytics', bg: 'bg-blue-50 border-blue-200', text: 'text-blue-700' },
  pipeline_db: { label: 'Pipeline', bg: 'bg-amber-50 border-amber-200', text: 'text-amber-700' },
  sitemaps_api: { label: 'Sitemaps', bg: 'bg-purple-50 border-purple-200', text: 'text-purple-700' },
  sitemaps: { label: 'Sitemaps', bg: 'bg-purple-50 border-purple-200', text: 'text-purple-700' },
  live: { label: 'LIVE', bg: 'bg-emerald-50 border-emerald-200', text: 'text-emerald-700' },
  extension: { label: 'Extension', bg: 'bg-indigo-50 border-indigo-200', text: 'text-indigo-700' },
};

export default function DataSourceBadge({ source, className = '' }) {
  const s = SOURCES[source] || { label: source || 'Unknown', bg: 'bg-slate-50 border-slate-200', text: 'text-slate-600' };
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[10px] font-semibold ${s.bg} ${s.text} ${className}`}>
      {s.label}
    </span>
  );
}
