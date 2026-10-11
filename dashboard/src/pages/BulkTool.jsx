import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { api } from '../lib/api';
import { STATUS_HEX, STATUS_COLORS, STATUS_LABELS, STATUS_ICON } from '../lib/statusConstants';
import {
  Play, Pause, Square, Trash2, Upload, Download, Loader, CheckCircle,
  XCircle, Search, Clock, FileText, Zap, Link2,
  RefreshCw, ChevronDown, ChevronUp, ExternalLink, Globe, Monitor,
} from 'lucide-react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';
import Header from '../components/Header';

/* ------------------------------------------------------------------ */
/*  Constants & helpers                                                */
/* ------------------------------------------------------------------ */

const RICH_COLORS = {
  Product: 'bg-violet-50 text-violet-700 border-violet-200',
  'Review snippet': 'bg-amber-50 text-amber-700 border-amber-200',
  Video: 'bg-rose-50 text-rose-700 border-rose-200',
  'Merchant listing': 'bg-cyan-50 text-cyan-700 border-cyan-200',
  Shopping: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  'Product snippet': 'bg-fuchsia-50 text-fuchsia-700 border-fuchsia-200',
  Review: 'bg-teal-50 text-teal-700 border-teal-200',
};
const RICH_FALLBACK = 'bg-slate-50 text-slate-600 border-slate-200';

const SHORT_TAG = {
  Product: 'Prod', 'Review snippet': 'Rev', Video: 'Vid',
  'Merchant listing': 'Merch', Shopping: 'Shop', 'Product snippet': 'Snip', Review: 'Rev',
};

const SHORT_COV = {
  'Submitted and indexed': 'Indexed',
  'Crawled - currently not indexed': 'Crawled',
  'URL is unknown to Google': 'Unknown',
  'Discovered - currently not indexed': 'Discovered',
  'Blocked by robots.txt': 'Blocked',
};

function countStatuses(results) {
  const c = { indexed: 0, requested: 0, submitted: 0, not_indexed: 0, error: 0 };
  results.forEach(r => { const k = r.status === 'inspect_only' ? 'not_indexed' : r.status; if (c[k] !== undefined) c[k]++; });
  return c;
}

function buildDonutData(c) {
  return [
    { name: 'Indexed', value: c.indexed, color: STATUS_HEX.indexed },
    { name: 'Requested', value: c.requested + (c.submitted || 0), color: STATUS_HEX.requested },
    { name: 'Not Indexed', value: c.not_indexed, color: STATUS_HEX.not_indexed },
    { name: 'Errors', value: c.error, color: STATUS_HEX.error },
  ].filter(d => d.value > 0);
}

function shortUrl(u) { return (u || '').replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, ''); }

/* ------------------------------------------------------------------ */
/*  Small UI pieces                                                    */
/* ------------------------------------------------------------------ */

function StatusBadge({ status }) {
  const Icon = STATUS_ICON[status] || Clock;
  return (
    <span className={`inline-flex items-center gap-0.5 whitespace-nowrap rounded-full border px-1.5 text-[9px] font-semibold leading-[18px] ${STATUS_COLORS[status] || 'text-slate-500 bg-slate-50 border-slate-200'}`}>
      <Icon size={9} /> {STATUS_LABELS[status] || status}
    </span>
  );
}

function MiniDonut({ data, total }) {
  if (!data.length) return null;
  return (
    <div className="flex items-center gap-3">
      <div className="relative h-14 w-14 flex-shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart><Pie data={data} dataKey="value" cx="50%" cy="50%" innerRadius={18} outerRadius={26} paddingAngle={2} strokeWidth={0}>
            {data.map((d, i) => <Cell key={i} fill={d.color} />)}
          </Pie><Tooltip formatter={(v, n) => [`${v}`, n]} contentStyle={{ fontSize: 10, borderRadius: 6, border: '1px solid #e2e8f0', padding: '3px 6px' }} /></PieChart>
        </ResponsiveContainer>
        <span className="absolute inset-0 flex items-center justify-center text-[10px] font-bold text-slate-700">{total}</span>
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-0.5">
        {data.map((d, i) => (
          <span key={i} className="flex items-center gap-1 text-[10px] text-slate-600">
            <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: d.color }} />
            {d.name}: <b>{d.value}</b>
          </span>
        ))}
      </div>
    </div>
  );
}

function CompletionRing({ pct, state }) {
  const color = state === 'done' ? STATUS_HEX.indexed : STATUS_HEX.requested;
  return (
    <div className="relative h-20 w-20 flex-shrink-0">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart><Pie data={[{ value: pct, fill: color }, { value: 100 - pct, fill: '#f1f5f9' }]} dataKey="value" cx="50%" cy="50%" innerRadius={28} outerRadius={38} startAngle={90} endAngle={-270} paddingAngle={0} strokeWidth={0}>
          {[color, '#f1f5f9'].map((f, i) => <Cell key={i} fill={f} />)}
        </Pie></PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-sm font-bold text-slate-800">{pct}%</span>
      </div>
    </div>
  );
}

function UrlCell({ url }) {
  const [tip, setTip] = useState(false);
  return (
    <td className="relative px-2 py-1 max-w-[300px]">
      <span className="block truncate font-mono text-[10px] text-slate-600 cursor-default"
        onMouseEnter={() => setTip(true)} onMouseLeave={() => setTip(false)}>
        {shortUrl(url)}
      </span>
      {tip && url && (
        <div className="absolute left-2 bottom-full mb-1 z-30 max-w-lg rounded border border-slate-700 bg-slate-800 px-2 py-0.5 text-[9px] text-white shadow-lg whitespace-nowrap">{url}</div>
      )}
    </td>
  );
}

function RichTags({ tags }) {
  if (!tags?.length) return <span className="text-slate-300 text-[10px]">—</span>;
  return (
    <div className="flex flex-nowrap gap-[2px] overflow-hidden">
      {tags.map((t, i) => (
        <span key={i} title={t}
          className={`shrink-0 rounded border px-1 text-[8px] font-bold leading-[16px] ${RICH_COLORS[t] || RICH_FALLBACK}`}>
          {SHORT_TAG[t] || t}
        </span>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Main component                                                     */
/* ------------------------------------------------------------------ */

export default function BulkTool() {
  const [mode, setMode] = useState('extension');
  const [urlText, setUrlText] = useState('');
  const [queue, setQueue] = useState(null);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState('');
  const [extResults, setExtResults] = useState(null);
  const [extCollapsed, setExtCollapsed] = useState(false);
  const [extQueueState, setExtQueueState] = useState(null);
  const pollRef = useRef(null);
  const resultsEndRef = useRef(null);
  const startTime = useRef(null);
  const [etaText, setEtaText] = useState('');

  const fetchStatus = useCallback(async () => {
    try {
      if (mode === 'api') {
        const d = await api.bulkQueueStatus();
        setQueue(d);
        if (d.state === 'done' || d.state === 'stopped' || d.state === 'idle') { setPolling(false); startTime.current = null; }
      } else {
        const d = await api.extQueueStatus();
        setExtQueueState(d.queue || {});
        if (d.results?.results?.length) setExtResults(d.results);
        const q = d.queue || {};
        if (q.state !== 'pending' && q.state !== 'picked_up') setPolling(false);
      }
    } catch { /* ignore */ }
  }, [mode]);

  useEffect(() => { fetchStatus(); api.getBulkResults().then(setExtResults).catch(() => {}); }, [fetchStatus]);
  useEffect(() => {
    if (polling) pollRef.current = setInterval(fetchStatus, mode === 'api' ? 1500 : 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [polling, fetchStatus, mode]);
  useEffect(() => {
    if (queue?.state === 'running' && queue.processed > 0) {
      if (!startTime.current) startTime.current = Date.now();
      const elapsed = (Date.now() - startTime.current) / 1000;
      const rate = queue.processed / elapsed;
      const rem = queue.total - queue.processed;
      if (rate > 0) { const s = Math.round(rem / rate); setEtaText(s < 60 ? `~${s}s` : s < 3600 ? `~${Math.ceil(s / 60)}m` : `~${Math.round(s / 3600 * 10) / 10}h`); }
    } else if (queue?.state === 'done') setEtaText('');
  }, [queue]);

  const isApiActive = queue && (queue.state === 'running' || queue.state === 'paused');
  const isExtActive = extQueueState && (extQueueState.state === 'pending' || extQueueState.state === 'picked_up');
  const isActive = mode === 'api' ? isApiActive : isExtActive;

  const urlCount = useMemo(() => urlText.split('\n').map(u => u.trim()).filter(u => u.startsWith('http')).length, [urlText]);
  const processed = queue?.processed || 0, total = queue?.total || 0, errors = queue?.errors || 0;
  const results = queue?.results || [];
  const pct = total > 0 ? Math.round((processed / total) * 100) : 0;
  const resultDonut = useMemo(() => buildDonutData(countStatuses(results)), [results]);
  const extCounts = useMemo(() => extResults?.results ? countStatuses(extResults.results) : null, [extResults]);
  const extDonut = useMemo(() => extCounts ? buildDonutData(extCounts) : [], [extCounts]);

  const handleStart = async () => {
    setError('');
    const urls = urlText.split('\n').map(u => u.trim()).filter(u => u.startsWith('http'));
    if (!urls.length) { setError('Paste at least one valid URL'); return; }
    try {
      startTime.current = Date.now();
      if (mode === 'api') await api.bulkQueueStart(urls);
      else { await api.extQueueStart(urls); setExtQueueState({ state: 'pending', total: urls.length }); }
      setPolling(true); fetchStatus();
    } catch (e) { setError(e.message || 'Failed'); }
  };
  const handlePause = async () => { try { await api.bulkQueuePause(); fetchStatus(); } catch (e) { setError(e.message); } };
  const handleResume = async () => { try { await api.bulkQueueResume(); setPolling(true); fetchStatus(); } catch (e) { setError(e.message); } };
  const handleStop = async () => { try { await api.bulkQueueStop(); setPolling(false); fetchStatus(); } catch (e) { setError(e.message); } };
  const handleClear = async () => {
    try {
      if (mode === 'api') await api.bulkQueueClear(); else { await api.extQueueClear(); setExtQueueState(null); }
      setQueue(null); setUrlText(''); setEtaText(''); startTime.current = null; fetchStatus();
    } catch (e) { setError(e.message); }
  };
  const handleImportCSV = () => {
    const input = document.createElement('input'); input.type = 'file'; input.accept = '.csv,.txt';
    input.onchange = (e) => { const f = e.target.files[0]; if (!f) return; const r = new FileReader(); r.onload = (ev) => { const urls = ev.target.result.split(/[\r\n,]+/).map(u => u.trim()).filter(u => u.startsWith('http')); setUrlText(p => p ? p + '\n' + urls.join('\n') : urls.join('\n')); }; r.readAsText(f); };
    input.click();
  };
  const handleDownloadSample = () => { const b = new Blob(['url\nhttps://example.com/page-1\nhttps://example.com/page-2\n'], { type: 'text/csv' }); const a = document.createElement('a'); a.href = URL.createObjectURL(b); a.download = 'sample_urls.csv'; a.click(); };

  const SL = { idle: 'Ready', running: 'Running', paused: 'Paused', done: 'Complete', stopped: 'Stopped' };
  const SD = { idle: 'bg-slate-400', running: 'bg-green-500 animate-pulse', paused: 'bg-amber-500', done: 'bg-blue-500', stopped: 'bg-red-500' };
  const SB = { idle: 'bg-slate-50 border-slate-200', running: 'bg-green-50 border-green-200', paused: 'bg-amber-50 border-amber-200', done: 'bg-blue-50 border-blue-200', stopped: 'bg-red-50 border-red-200' };

  /* ================================================================ */

  return (
    <div>
      <Header title="Bulk Indexing" />

      <div className="space-y-4 px-5 py-5">

        {/* ─── Mode + URL Input (single card) ─── */}
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm space-y-3">
          <div className="flex items-center gap-3 flex-wrap">
            <div className="flex rounded-lg bg-slate-100 p-0.5 gap-0.5">
              <button onClick={() => { if (!isActive) setMode('extension'); }} disabled={isActive}
                className={`flex items-center gap-1 rounded-md px-3 py-1.5 text-[11px] font-bold transition-all ${mode === 'extension' ? 'bg-white text-purple-700 shadow-sm ring-1 ring-purple-200' : 'text-slate-500 hover:text-slate-700'} disabled:cursor-not-allowed`}>
                <Globe size={11} /> Extension
              </button>
              <button onClick={() => { if (!isActive) setMode('api'); }} disabled={isActive}
                className={`flex items-center gap-1 rounded-md px-3 py-1.5 text-[11px] font-bold transition-all ${mode === 'api' ? 'bg-white text-blue-700 shadow-sm ring-1 ring-blue-200' : 'text-slate-500 hover:text-slate-700'} disabled:cursor-not-allowed`}>
                <Monitor size={11} /> API
              </button>
            </div>
            <span className="text-[10px] text-slate-400">
              {mode === 'extension' ? 'Processes via GSC web UI — no quota limits' : 'GSC API — 2k inspections/day'}
            </span>
            {mode === 'api' && queue?.state && (
              <span className={`ml-auto inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[9px] font-semibold ${SB[queue.state]}`}>
                <span className={`h-1.5 w-1.5 rounded-full ${SD[queue.state]}`} /> {SL[queue.state]}
              </span>
            )}
          </div>

          {mode === 'extension' && extQueueState?.state === 'pending' && (
            <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 px-3 py-1.5">
              <Loader size={11} className="animate-spin text-amber-500" />
              <span className="text-[11px] text-amber-700 font-medium">Waiting for extension to pick up {extQueueState.total} URLs...</span>
            </div>
          )}
          {mode === 'extension' && extQueueState?.state === 'picked_up' && (
            <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 px-3 py-1.5">
              <CheckCircle size={11} className="text-green-500" />
              <span className="text-[11px] text-green-700 font-medium">Extension processing via browser</span>
            </div>
          )}

          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold text-slate-500">Paste URLs</span>
            {urlText.trim() && (
              <span className="rounded-full bg-blue-50 border border-blue-200 px-1.5 py-px text-[9px] font-bold text-blue-600 tabular-nums">
                {urlCount} URL{urlCount !== 1 ? 's' : ''}
              </span>
            )}
          </div>

          <textarea
            className="w-full h-20 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-[11px] font-mono text-slate-700 placeholder:text-slate-400 focus:bg-white focus:border-orange-300 focus:ring-2 focus:ring-orange-200 focus:outline-none resize-y disabled:opacity-50 transition-all"
            placeholder={'https://rudraretails.com/products/page-1\nhttps://rudraretails.com/products/page-2'}
            value={urlText} onChange={e => setUrlText(e.target.value)} disabled={isActive}
          />

          {error && (
            <div className="flex items-center gap-1.5 rounded-lg border border-red-200 bg-red-50 px-3 py-1 text-[11px] text-red-600">
              <XCircle size={11} /> {error}
            </div>
          )}

          <div className="flex flex-wrap items-center gap-1.5">
            {mode === 'extension' ? (
              <button onClick={handleStart}
                disabled={(extQueueState?.state && extQueueState.state !== 'empty') || !urlText.trim()}
                className="flex items-center gap-1 rounded-lg bg-gradient-to-r from-purple-600 to-indigo-600 px-4 py-1.5 text-[11px] font-bold text-white shadow-sm hover:shadow-md hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none disabled:hover:translate-y-0 transition-all">
                <Globe size={12} /> Send to Extension
              </button>
            ) : (
              <button onClick={handleStart} disabled={isActive || !urlText.trim()}
                className="flex items-center gap-1 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-1.5 text-[11px] font-bold text-white shadow-sm hover:shadow-md hover:-translate-y-0.5 active:translate-y-0 disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none disabled:hover:translate-y-0 transition-all">
                <Play size={12} /> Start Queue
              </button>
            )}

            {mode === 'api' && isApiActive && (
              <>
                {queue.state === 'running'
                  ? <button onClick={handlePause} className="flex items-center gap-1 rounded-lg bg-amber-500 px-3 py-1.5 text-[11px] font-bold text-white hover:bg-amber-600 transition-colors"><Pause size={12} /> Pause</button>
                  : <button onClick={handleResume} className="flex items-center gap-1 rounded-lg bg-green-600 px-3 py-1.5 text-[11px] font-bold text-white hover:bg-green-700 transition-colors"><Play size={12} /> Resume</button>
                }
                <button onClick={handleStop} className="flex items-center gap-1 rounded-lg bg-red-500 px-3 py-1.5 text-[11px] font-bold text-white hover:bg-red-600 transition-colors"><Square size={12} /> Stop</button>
              </>
            )}

            <div className="h-4 w-px bg-slate-200" />

            <button onClick={handleImportCSV} disabled={isActive}
              className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-semibold text-slate-600 hover:bg-slate-50 disabled:opacity-40 transition-colors">
              <Upload size={11} /> CSV
            </button>
            <button onClick={handleClear} disabled={isActive}
              className="flex items-center gap-1 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[11px] font-semibold text-slate-600 hover:bg-slate-50 hover:text-red-600 hover:border-red-200 disabled:opacity-40 transition-colors">
              <Trash2 size={11} /> Clear
            </button>

            <button onClick={handleDownloadSample}
              className="ml-auto text-[10px] text-slate-400 hover:text-blue-500 flex items-center gap-1 transition-colors">
              <Download size={9} /> sample.csv
            </button>
          </div>
        </div>

        {/* ─── API Processing Stats ─── */}
        {mode === 'api' && total > 0 && (
          <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <div className="flex items-center gap-2 mb-3">
              <span className={`h-2 w-2 rounded-full ${queue?.state === 'running' ? 'bg-blue-500 animate-pulse' : 'bg-blue-500'}`} />
              <span className="text-xs font-bold text-slate-700">Processing</span>
              {etaText && queue?.state === 'running' && (
                <span className="ml-auto text-[10px] text-slate-400 flex items-center gap-1"><Clock size={10} /> {etaText}</span>
              )}
            </div>
            <div className="flex items-center gap-5">
              <CompletionRing pct={pct} state={queue?.state} />
              <div className="flex-1 grid grid-cols-3 gap-3">
                <div className="rounded-xl border border-slate-100 bg-gradient-to-br from-slate-50 to-white p-3 text-center">
                  <div className="text-xl font-bold text-blue-600">{total - processed}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">{queue?.state === 'idle' ? 'Total' : 'Remaining'}</div>
                </div>
                <div className="rounded-xl border border-green-100 bg-gradient-to-br from-green-50 to-white p-3 text-center">
                  <div className="text-xl font-bold text-green-600">{processed}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Processed</div>
                </div>
                <div className="rounded-xl border border-red-100 bg-gradient-to-br from-red-50 to-white p-3 text-center">
                  <div className="text-xl font-bold text-red-500">{errors}</div>
                  <div className="text-[10px] text-slate-500 mt-0.5">Errors</div>
                </div>
              </div>
            </div>
            <div className="mt-3">
              <div className="w-full bg-slate-100 rounded-full h-1.5 overflow-hidden">
                <div className={`h-1.5 rounded-full transition-all duration-700 ${queue?.state === 'done' ? 'bg-green-500' : 'bg-indigo-500'}`} style={{ width: `${pct}%` }} />
              </div>
              <div className="flex justify-between mt-1 text-[10px] text-slate-400">
                <span>{processed}/{total}</span><span className="font-medium">{pct}%</span>
              </div>
            </div>
            {queue?.current_url && (
              <div className="mt-2 flex items-center gap-2 rounded-lg border border-blue-100 bg-blue-50/50 px-3 py-1.5">
                <Loader size={11} className="animate-spin text-blue-500" />
                <span className="font-mono text-[10px] text-blue-700 truncate">{queue.current_url}</span>
              </div>
            )}
          </div>
        )}

        {/* ─── API Results ─── */}
        {mode === 'api' && results.length > 0 && (
          <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-100 flex items-center gap-3">
              <span className="text-xs font-bold text-slate-700">API Results</span>
              <span className="rounded-full bg-indigo-50 border border-indigo-200 px-2 py-0.5 text-[10px] font-bold text-indigo-600">{results.length}</span>
              <div className="ml-3"><MiniDonut data={resultDonut} total={results.length} /></div>
            </div>
            <div className="max-h-[400px] overflow-y-auto">
              <table className="w-full">
                <thead className="sticky top-0 bg-slate-50/95 backdrop-blur border-b border-slate-100 text-[10px] text-slate-500">
                  <tr>
                    <th className="text-left pl-4 pr-2 py-2 font-medium w-8">#</th>
                    <th className="text-left px-3 py-2 font-medium">URL</th>
                    <th className="text-left px-3 py-2 font-medium w-20">Coverage</th>
                    <th className="text-left px-3 py-2 font-medium w-20">Status</th>
                    <th className="text-left px-3 pr-4 py-2 font-medium">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50 text-[11px]">
                  {results.map((r, i) => (
                    <tr key={i} className="hover:bg-orange-50/30 transition-colors">
                      <td className="pl-4 pr-2 py-1.5 text-slate-400 tabular-nums text-[10px]">{i + 1}</td>
                      <UrlCell url={r.url} />
                      <td className="px-3 py-1.5 text-[10px] text-slate-500 whitespace-nowrap">{SHORT_COV[r.coverage] || r.coverage || '—'}</td>
                      <td className="px-3 py-1.5"><StatusBadge status={r.status} /></td>
                      <td className="px-3 pr-4 py-1.5 text-[10px] text-slate-500 truncate max-w-[180px]">{r.action || r.error || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
              <div ref={resultsEndRef} />
            </div>
          </div>
        )}

        {mode === 'api' && !results.length && total === 0 && !isActive && queue?.state !== 'done' && (
          <div className="rounded-2xl border border-dashed border-slate-200 bg-slate-50/30 py-8 text-center">
            <Search size={16} className="text-slate-300 mx-auto mb-1" />
            <p className="text-[11px] font-medium text-slate-500">No API results yet</p>
            <p className="text-[10px] text-slate-400 mt-0.5">Paste URLs and start the queue</p>
          </div>
        )}

        {/* ─── Extension Results ─── */}
        {extResults?.results?.length > 0 && (
          <div className="rounded-2xl border border-slate-200 bg-white shadow-sm overflow-hidden">
            <button onClick={() => setExtCollapsed(c => !c)}
              className="w-full px-4 py-2.5 border-b border-slate-100 flex items-center justify-between hover:bg-slate-50/50 transition-colors">
              <div className="flex items-center gap-2">
                <span className="h-2 w-2 rounded-full bg-purple-500" />
                <span className="text-xs font-bold text-slate-700">Extension Results</span>
                <span className="rounded-full bg-purple-50 border border-purple-200 px-1.5 py-0.5 text-[10px] font-bold text-purple-600">{extResults.results.length}</span>
                <div className="ml-2 flex items-center gap-3 text-[10px] text-slate-400">
                  {extDonut.map((d, i) => (
                    <span key={i} className="flex items-center gap-1">
                      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: d.color }} />
                      {d.name}: {d.value}
                    </span>
                  ))}
                </div>
              </div>
              <div className="flex items-center gap-3">
                {extResults.received_at && <span className="text-[10px] text-slate-400">{extResults.received_at}</span>}
                {extCollapsed ? <ChevronDown size={14} className="text-slate-400" /> : <ChevronUp size={14} className="text-slate-400" />}
              </div>
            </button>

            {!extCollapsed && (
              <div className="max-h-[450px] overflow-y-auto">
                <table className="w-full table-fixed">
                  <colgroup>
                    <col className="w-[3%]" />
                    <col className="w-[40%]" />
                    <col className="w-[10%]" />
                    <col className="w-[12%]" />
                    <col className="w-[20%]" />
                    <col className="w-[15%]" />
                  </colgroup>
                  <thead className="sticky top-0 bg-slate-50/95 backdrop-blur border-b border-slate-100 text-[10px] text-slate-500">
                    <tr>
                      <th className="text-left pl-3 pr-1 py-1 font-medium">#</th>
                      <th className="text-left px-2 py-1 font-medium">URL</th>
                      <th className="text-left px-2 py-1 font-medium">Coverage</th>
                      <th className="text-left px-2 py-1 font-medium">Status</th>
                      <th className="text-left px-2 py-1 font-medium">Rich Results</th>
                      <th className="text-left px-2 pr-3 py-1 font-medium">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50 text-[11px]">
                    {extResults.results.map((r, i) => (
                      <tr key={i} className="hover:bg-orange-50/30 transition-colors h-7">
                        <td className="pl-3 pr-1 text-slate-400 tabular-nums text-[10px]">{i + 1}</td>
                        <td className="px-2 truncate font-mono text-[10px] text-slate-600" title={r.url}>{shortUrl(r.url)}</td>
                        <td className="px-2 text-[10px] text-slate-500">{SHORT_COV[r.coverage] || r.coverage || '—'}</td>
                        <td className="px-2"><StatusBadge status={r.status} /></td>
                        <td className="px-2"><RichTags tags={r.richResults} /></td>
                        <td className="px-2 pr-3 text-[10px] text-slate-500 truncate">{r.action || r.error || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

      </div>
    </div>
  );
}
