import { useState, useEffect } from 'react';
import { RefreshCw, CheckCircle, Database, Globe, Cpu, Shield, Clock } from 'lucide-react';
import Header from '../components/Header';
import { api } from '../lib/api';

export default function Settings() {
  const [reports, setReports] = useState(null);
  const [extData, setExtData] = useState(null);
  const [pipelineStatus, setPipelineStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchAll = async () => {
    setLoading(true);
    try {
      const [r, e, p] = await Promise.allSettled([
        api.getGscReports(),
        api.getExtensionGscData(),
        api.getPipelineStatus(),
      ]);
      if (r.status === 'fulfilled') setReports(r.value);
      if (e.status === 'fulfilled') setExtData(e.value);
      if (p.status === 'fulfilled') setPipelineStatus(p.value);
    } catch {}
    setLoading(false);
  };

  useEffect(() => { fetchAll(); }, []);

  const rpt = reports || {};
  const ext = extData || {};

  return (
    <div>
      <Header title="Settings" loading={loading} />
      <div className="space-y-5 px-5 py-5 max-w-5xl">

        {/* Data Sources Status */}
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <div className="bg-gradient-to-r from-blue-50 via-indigo-50 to-blue-50 px-6 py-4 border-b border-blue-100/60 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-800">Data Sources</h3>
              <p className="text-xs text-slate-500 mt-0.5">All data is synced automatically — no manual entry needed</p>
            </div>
            <button onClick={fetchAll} disabled={loading}
              className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-semibold text-slate-600 hover:bg-slate-50 transition-colors disabled:opacity-40">
              <RefreshCw size={12} className={loading ? 'animate-spin' : ''} /> Refresh
            </button>
          </div>

          <div className="p-5 grid gap-4 md:grid-cols-3">
            {/* Extension Data */}
            <SourceCard
              icon={Globe} color="indigo"
              title="Chrome Extension"
              status={ext.received_at ? 'connected' : 'waiting'}
              lastSync={ext.received_at}
              details={[
                { label: 'Pages Indexed', value: rpt.pages_indexed?.toLocaleString() || '—' },
                { label: 'Pages Not Indexed', value: rpt.pages_not_indexed?.toLocaleString() || '—' },
                { label: 'Enhancements', value: `${(rpt.merchant_listings_valid || 0) + (rpt.product_snippets_valid || 0) + (rpt.review_snippets_valid || 0)} valid` },
              ]}
              hint='Use "Fetch All" in the Chrome extension to sync'
            />

            {/* Pipeline */}
            <SourceCard
              icon={Cpu} color="emerald"
              title="Indexing Pipeline"
              status={pipelineStatus?.state === 'completed' ? 'connected' : pipelineStatus?.state === 'running' ? 'running' : 'idle'}
              lastSync={pipelineStatus?.completed_at}
              details={[
                { label: 'Tracked URLs', value: pipelineStatus?.total_tracked?.toLocaleString() || '—' },
                { label: 'Indexed', value: pipelineStatus?.indexed?.toLocaleString() || '—' },
                { label: 'Not Indexed', value: pipelineStatus?.not_indexed?.toLocaleString() || '—' },
              ]}
              hint="Run indexing_pipeline.py to inspect & submit URLs"
            />

            {/* GSC API */}
            <SourceCard
              icon={Database} color="blue"
              title="GSC API (Live)"
              status="connected"
              details={[
                { label: 'Credentials', value: '10 service accounts' },
                { label: 'Inspect Quota', value: '2,000/day per account' },
                { label: 'Submit Quota', value: '200/day per account' },
              ]}
              hint="Live API calls for sitemaps, analytics & inspections"
            />
          </div>
        </div>

        {/* GSC Report Numbers (read-only) */}
        <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <div className="bg-gradient-to-r from-orange-50 via-amber-50 to-orange-50 px-6 py-4 border-b border-orange-100/60">
            <h3 className="text-sm font-semibold text-slate-800">Current GSC Numbers</h3>
            <p className="text-xs text-slate-500 mt-0.5">
              Auto-synced from Chrome extension &middot; Last updated: {rpt.last_updated || '—'}
            </p>
          </div>
          <div className="p-5">
            <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
              <StatBox label="Pages Indexed" value={rpt.pages_indexed} color="emerald" />
              <StatBox label="Pages Not Indexed" value={rpt.pages_not_indexed} color="red" />
              <StatBox label="Product Snippets" value={rpt.product_snippets_valid} color="purple" />
              <StatBox label="Merchant Listings" value={rpt.merchant_listings_valid} color="cyan" />
              <StatBox label="Review Snippets" value={rpt.review_snippets_valid} color="amber" />
              <StatBox label="Product Invalid" value={rpt.product_snippets_invalid} color="red" />
              <StatBox label="Merchant Invalid" value={rpt.merchant_listings_invalid} color="red" />
              <StatBox label="Review Invalid" value={rpt.review_snippets_invalid} color="red" />
            </div>
          </div>
        </div>

        {/* About */}
        <div className="rounded-2xl border border-slate-200 bg-gradient-to-br from-slate-50 via-white to-slate-50 p-5 shadow-sm">
          <h3 className="mb-1 text-sm font-semibold text-slate-800">About</h3>
          <p className="text-xs text-slate-500 leading-relaxed">
            Rudra Retail GSC Auditor &mdash; SEO Pipeline Dashboard<br />
            Site: rudraretails.com &bull; 105K+ products<br />
            10 service accounts &bull; 20,000 inspections/day &bull; 2,000 submissions/day
          </p>
        </div>
      </div>
    </div>
  );
}

function SourceCard({ icon: Icon, color, title, status, lastSync, details, hint }) {
  const colors = {
    indigo: { bg: 'bg-indigo-100', icon: 'text-indigo-600', ring: 'border-indigo-200' },
    emerald: { bg: 'bg-emerald-100', icon: 'text-emerald-600', ring: 'border-emerald-200' },
    blue: { bg: 'bg-blue-100', icon: 'text-blue-600', ring: 'border-blue-200' },
  };
  const c = colors[color] || colors.blue;

  const statusMap = {
    connected: { dot: 'bg-emerald-500', label: 'Connected', text: 'text-emerald-700' },
    running: { dot: 'bg-blue-500 animate-pulse', label: 'Running', text: 'text-blue-700' },
    waiting: { dot: 'bg-amber-400', label: 'Waiting for data', text: 'text-amber-700' },
    idle: { dot: 'bg-slate-400', label: 'Idle', text: 'text-slate-600' },
  };
  const s = statusMap[status] || statusMap.idle;

  return (
    <div className={`rounded-xl border ${c.ring} bg-white p-4`}>
      <div className="flex items-center gap-3 mb-3">
        <div className={`flex h-9 w-9 items-center justify-center rounded-lg ${c.bg}`}>
          <Icon size={16} className={c.icon} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-bold text-slate-800">{title}</div>
          <div className="flex items-center gap-1.5 mt-0.5">
            <span className={`h-2 w-2 rounded-full ${s.dot}`} />
            <span className={`text-[10px] font-semibold ${s.text}`}>{s.label}</span>
          </div>
        </div>
      </div>
      <div className="space-y-1.5 mb-3">
        {details.map((d, i) => (
          <div key={i} className="flex justify-between text-xs">
            <span className="text-slate-500">{d.label}</span>
            <span className="font-semibold text-slate-700">{d.value}</span>
          </div>
        ))}
      </div>
      {lastSync && (
        <div className="flex items-center gap-1 text-[10px] text-slate-400 mb-2">
          <Clock size={10} /> Last sync: {lastSync}
        </div>
      )}
      <p className="text-[10px] text-slate-400 leading-relaxed">{hint}</p>
    </div>
  );
}

function StatBox({ label, value, color }) {
  const colorMap = {
    emerald: 'text-emerald-700 bg-emerald-50 border-emerald-200',
    red: 'text-red-600 bg-red-50 border-red-200',
    purple: 'text-purple-700 bg-purple-50 border-purple-200',
    cyan: 'text-cyan-700 bg-cyan-50 border-cyan-200',
    amber: 'text-amber-700 bg-amber-50 border-amber-200',
  };
  const cls = colorMap[color] || colorMap.emerald;
  const display = value != null && value !== '' ? Number(value).toLocaleString() : '—';

  return (
    <div className={`rounded-xl border p-3 text-center ${cls}`}>
      <div className="text-lg font-extrabold">{display}</div>
      <div className="text-[10px] font-semibold opacity-70 mt-0.5">{label}</div>
    </div>
  );
}
