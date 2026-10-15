const SOURCES = {
  gsc_pages: { label: 'GSC Pages Report', bg: 'bg-emerald-100', text: 'text-emerald-700' },
  gsc_report: { label: 'GSC Pages Report', bg: 'bg-emerald-100', text: 'text-emerald-700' },
  search_analytics: { label: 'Search Analytics', bg: 'bg-blue-100', text: 'text-blue-700' },
  pipeline_db: { label: 'Pipeline DB', bg: 'bg-amber-100', text: 'text-amber-700' },
  sitemaps_api: { label: 'Sitemaps API', bg: 'bg-purple-100', text: 'text-purple-700' },
  sitemaps: { label: 'Sitemaps API', bg: 'bg-purple-100', text: 'text-purple-700' },
  live: { label: 'LIVE', bg: 'bg-emerald-100', text: 'text-emerald-700' },
};

export default function DataSourceBadge({ source, className = '' }) {
  const s = SOURCES[source] || { label: source || 'Unknown', bg: 'bg-slate-100', text: 'text-slate-600' };
  return (
    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold ${s.bg} ${s.text} ${className}`}>
      {s.label}
    </span>
  );
}
