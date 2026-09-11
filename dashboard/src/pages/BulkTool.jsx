import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { api } from '../lib/api';
import {
  Play, Pause, Square, Trash2, Upload, Download, Loader, CheckCircle,
  XCircle, AlertTriangle, Search, Clock, FileText, Link2, Zap, Tag,
  RefreshCw, ChevronDown, ChevronUp, ExternalLink,
} from 'lucide-react';
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from 'recharts';

/* ------------------------------------------------------------------ */
/*  Constants                                                         */
/* ------------------------------------------------------------------ */

const STATUS_HEX = {
  indexed: '#22c55e',
  requested: '#3b82f6',
  submitted: '#3b82f6',
  not_indexed: '#f59e0b',
  inspect_only: '#f59e0b',
  error: '#ef4444',
  pending: '#94a3b8',
};

const STATUS_COLORS = {
  indexed: 'text-green-600 bg-green-50 border-green-200',
  requested: 'text-blue-600 bg-blue-50 border-blue-200',
  submitted: 'text-blue-600 bg-blue-50 border-blue-200',
  not_indexed: 'text-amber-600 bg-amber-50 border-amber-200',
  inspect_only: 'text-amber-600 bg-amber-50 border-amber-200',
  error: 'text-red-600 bg-red-50 border-red-200',
  pending: 'text-slate-400 bg-slate-50 border-slate-200',
};

const STATUS_LABELS = {
  indexed: 'Indexed',
  requested: 'Requested',
  submitted: 'Submitted',
  not_indexed: 'Not Indexed',
  inspect_only: 'Not Indexed',
  error: 'Error',
  pending: 'Pending',
};

const STATUS_ICON = {
  indexed: CheckCircle,
  requested: Upload,
  submitted: Upload,
  not_indexed: AlertTriangle,
  inspect_only: AlertTriangle,
  error: XCircle,
  pending: Clock,
};

const RICH_TAG_COLORS = [
  'bg-violet-50 text-violet-700 border-violet-200',
  'bg-cyan-50 text-cyan-700 border-cyan-200',
  'bg-emerald-50 text-emerald-700 border-emerald-200',
  'bg-fuchsia-50 text-fuchsia-700 border-fuchsia-200',
  'bg-rose-50 text-rose-700 border-rose-200',
  'bg-teal-50 text-teal-700 border-teal-200',
  'bg-sky-50 text-sky-700 border-sky-200',
];

/* ------------------------------------------------------------------ */
/*  Helpers                                                           */
/* ------------------------------------------------------------------ */

function countStatuses(results) {
  const counts = { indexed: 0, requested: 0, submitted: 0, not_indexed: 0, error: 0 };
  results.forEach(r => {
    const k = r.status === 'inspect_only' ? 'not_indexed' : r.status;
    if (counts[k] !== undefined) counts[k]++;
  });
  return counts;
}

function buildDonutData(counts) {
  return [
    { name: 'Indexed', value: counts.indexed, color: STATUS_HEX.indexed },
    { name: 'Requested', value: counts.requested + (counts.submitted || 0), color: STATUS_HEX.requested },
    { name: 'Not Indexed', value: counts.not_indexed, color: STATUS_HEX.not_indexed },
    { name: 'Errors', value: counts.error, color: STATUS_HEX.error },
  ].filter(d => d.value > 0);
}

function shortUrl(url) {
  return (url || '').replace(/^https?:\/\//, '').replace(/\/$/, '');
}

/* ------------------------------------------------------------------ */
/*  Tiny components                                                   */
/* ------------------------------------------------------------------ */

function StatusBadge({ status }) {
  const Icon = STATUS_ICON[status] || Clock;
  return (
    <span className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[status] || 'text-slate-500 bg-slate-50 border-slate-200'}`}>
      <Icon size={10} />
      {STATUS_LABELS[status] || status}
    </span>
  );
}

function SummaryDonut({ data, total, label }) {
  if (!data.length) return null;
  return (
    <div className="flex items-center gap-4">
      <div className="relative h-20 w-20 flex-shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              dataKey="value"
              cx="50%"
              cy="50%"
              innerRadius={24}
              outerRadius={36}
              paddingAngle={2}
              strokeWidth={0}
            >
              {data.map((d, i) => (
                <Cell key={i} fill={d.color} />
              ))}
            </Pie>
            <Tooltip
              formatter={(value, name) => [`${value} URLs`, name]}
              contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #e2e8f0' }}
            />
          </PieChart>
        </ResponsiveContainer>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className="text-xs font-bold text-slate-700">{total}</span>
        </div>
      </div>
      <div className="flex flex-wrap gap-x-4 gap-y-1">
        {data.map((d, i) => (
          <div key={i} className="flex items-center gap-1.5 text-xs text-slate-600">
            <span className="inline-block h-2 w-2 rounded-full" style={{ backgroundColor: d.color }} />
            {d.name}: <span className="font-semibold">{d.value}</span>
          </div>
        ))}
      </div>
      {label && <span className="ml-auto text-[10px] text-slate-400">{label}</span>}
    </div>
  );
}

function CompletionRing({ pct, state }) {
  const color = state === 'done' ? STATUS_HEX.indexed : STATUS_HEX.requested;
  const data = [
    { value: pct, fill: color },
    { value: 100 - pct, fill: '#f1f5f9' },
  ];
  return (
    <div className="relative h-28 w-28 flex-shrink-0">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            cx="50%"
            cy="50%"
            innerRadius={38}
            outerRadius={50}
            startAngle={90}
            endAngle={-270}
            paddingAngle={0}
            strokeWidth={0}
          >
            {data.map((d, i) => (
              <Cell key={i} fill={d.fill} />
            ))}
          </Pie>
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-lg font-bold text-slate-800">{pct}%</span>
        <span className="text-[10px] text-slate-400">complete</span>
      </div>
    </div>
  );
}

function EmptyState({ icon: Icon, title, subtitle }) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-slate-100">
        <Icon size={22} className="text-slate-400" />
      </div>
      <p className="text-sm font-medium text-slate-600">{title}</p>
      {subtitle && <p className="mt-1 text-xs text-slate-400 max-w-xs">{subtitle}</p>}
    </div>
  );
}

function UrlTooltipCell({ url }) {
  const [show, setShow] = useState(false);
  const display = shortUrl(url).slice(0, 60);
  return (
    <td className="relative px-2 py-2.5 font-mono text-xs text-slate-600 max-w-xs">
      <span
        className="block truncate cursor-default"
        onMouseEnter={() => setShow(true)}
        onMouseLeave={() => setShow(false)}
      >
        {display}
      </span>
      {show && url && (
        <div className="absolute left-2 -top-8 z-30 max-w-md rounded-lg border border-slate-200 bg-slate-800 px-3 py-1.5 text-xs text-white shadow-lg">
          {url}
        </div>
      )}
    </td>
  );
}

/* ------------------------------------------------------------------ */
/*  Main component                                                    */
/* ------------------------------------------------------------------ */

export default function BulkTool() {
  const [urlText, setUrlText] = useState('');
  const [queue, setQueue] = useState(null);
  const [polling, setPolling] = useState(false);
  const [error, setError] = useState('');
  const [extResults, setExtResults] = useState(null);
  const [extCollapsed, setExtCollapsed] = useState(false);
  const pollRef = useRef(null);
  const resultsEndRef = useRef(null);
  const startTime = useRef(null);
  const [etaText, setEtaText] = useState('');

  /* ----- Fetching ----- */

  const fetchStatus = useCallback(async () => {
    try {
      const data = await api.bulkQueueStatus();
      setQueue(data);
      if (data.state === 'done' || data.state === 'stopped' || data.state === 'idle') {
        setPolling(false);
        startTime.current = null;
      }
    } catch {
      // ignore poll errors
    }
  }, []);

  useEffect(() => {
    fetchStatus();
    api.getBulkResults().then(setExtResults).catch(() => {});
  }, [fetchStatus]);

  useEffect(() => {
    if (polling) {
      pollRef.current = setInterval(fetchStatus, 1500);
    }
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [polling, fetchStatus]);

  /* ----- ETA ----- */
  useEffect(() => {
    if (queue?.state === 'running' && queue.processed > 0) {
      if (!startTime.current) startTime.current = Date.now();
      const elapsed = (Date.now() - startTime.current) / 1000;
      const rate = queue.processed / elapsed;
      const remaining = queue.total - queue.processed;
      if (rate > 0) {
        const secs = Math.round(remaining / rate);
        if (secs < 60) setEtaText(`~${secs}s remaining`);
        else if (secs < 3600) setEtaText(`~${Math.ceil(secs / 60)}m remaining`);
        else setEtaText(`~${Math.round(secs / 3600 * 10) / 10}h remaining`);
      }
    } else if (queue?.state === 'done') {
      setEtaText('');
    }
  }, [queue]);

  /* ----- Derived ----- */

  const isActive = queue && (queue.state === 'running' || queue.state === 'paused');

  const urlCount = useMemo(() => {
    return urlText.split('\n').map(u => u.trim()).filter(u => u.startsWith('http')).length;
  }, [urlText]);

  const processed = queue?.processed || 0;
  const total = queue?.total || 0;
  const errors = queue?.errors || 0;
  const queued = total - processed;
  const results = queue?.results || [];
  const pct = total > 0 ? Math.round((processed / total) * 100) : 0;

  const resultCounts = useMemo(() => countStatuses(results), [results]);
  const resultDonut = useMemo(() => buildDonutData(resultCounts), [resultCounts]);

  const extCounts = useMemo(() => extResults?.results ? countStatuses(extResults.results) : null, [extResults]);
  const extDonut = useMemo(() => extCounts ? buildDonutData(extCounts) : [], [extCounts]);

  /* ----- Handlers ----- */

  const handleStart = async () => {
    setError('');
    const urls = urlText.split('\n').map(u => u.trim()).filter(u => u.startsWith('http'));
    if (!urls.length) { setError('Paste at least one valid URL'); return; }
    try {
      startTime.current = Date.now();
      await api.bulkQueueStart(urls);
      setPolling(true);
      fetchStatus();
    } catch (e) {
      setError(e.message || 'Failed to start queue');
    }
  };

  const handlePause = async () => {
    try { await api.bulkQueuePause(); fetchStatus(); } catch {}
  };

  const handleResume = async () => {
    try { await api.bulkQueueResume(); setPolling(true); fetchStatus(); } catch {}
  };

  const handleStop = async () => {
    try { await api.bulkQueueStop(); setPolling(false); fetchStatus(); } catch {}
  };

  const handleClear = async () => {
    try { await api.bulkQueueClear(); setQueue(null); setUrlText(''); setEtaText(''); startTime.current = null; fetchStatus(); } catch {}
  };

  const handleImportCSV = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.csv,.txt';
    input.onchange = (e) => {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        const text = ev.target.result;
        const urls = text.split(/[\r\n,]+/).map(u => u.trim()).filter(u => u.startsWith('http'));
        setUrlText(prev => prev ? prev + '\n' + urls.join('\n') : urls.join('\n'));
      };
      reader.readAsText(file);
    };
    input.click();
  };

  const handleDownloadSample = () => {
    const sample = 'url\nhttps://example.com/page-1\nhttps://example.com/page-2\nhttps://example.com/page-3\n';
    const blob = new Blob([sample], { type: 'text/csv' });
    const a = document.createElement('a');
    const url = URL.createObjectURL(blob);
    a.href = url;
    a.download = 'sample_urls.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  /* ----- State badge map ----- */

  const stateLabel = { idle: 'Ready', running: 'Running', paused: 'Paused', done: 'Complete', stopped: 'Stopped' };

  const stateDotClass = {
    idle: 'bg-slate-400',
    running: 'bg-green-500 animate-pulse',
    paused: 'bg-amber-500',
    done: 'bg-blue-500',
    stopped: 'bg-red-500',
  };

  const stateBadgeBg = {
    idle: 'bg-slate-50 border-slate-200',
    running: 'bg-green-50 border-green-200',
    paused: 'bg-amber-50 border-amber-200',
    done: 'bg-blue-50 border-blue-200',
    stopped: 'bg-red-50 border-red-200',
  };

  /* ================================================================ */
  /*  RENDER                                                          */
  /* ================================================================ */

  return (
    <div className="p-6 max-w-5xl mx-auto space-y-5">

      {/* ---- Header ---- */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 shadow-md shadow-blue-500/20">
            <Zap size={20} className="text-white" />
          </div>
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-xl font-bold text-slate-900">GSC Bulk Indexing Tool</h1>
              {queue?.state && (
                <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold ${stateBadgeBg[queue.state] || 'bg-slate-50 border-slate-200'}`}>
                  <span className={`inline-block h-2 w-2 rounded-full ${stateDotClass[queue.state] || 'bg-slate-400'}`} />
                  <span className="text-slate-700">{stateLabel[queue.state] || queue.state}</span>
                </span>
              )}
            </div>
            <p className="text-xs text-slate-500">Automated URL inspection &amp; indexing requests</p>
          </div>
        </div>
      </div>

      {/* ---- URL Management Card ---- */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-blue-500" />
            <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wide">URL Management</h2>
          </div>
          {urlText.trim() && (
            <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 border border-blue-200 px-2 py-0.5 text-xs font-semibold text-blue-700">
              <Link2 size={10} />
              {urlCount} URL{urlCount !== 1 ? 's' : ''}
            </span>
          )}
        </div>

        <div className="group relative rounded-lg border border-slate-200 focus-within:border-transparent focus-within:ring-2 focus-within:ring-blue-400 transition-all">
          <div className="absolute -inset-px rounded-lg bg-gradient-to-r from-blue-400 via-indigo-400 to-purple-400 opacity-0 group-focus-within:opacity-100 transition-opacity -z-10 blur-[1px]" />
          <textarea
            className="w-full h-32 rounded-lg bg-slate-50 px-3 py-2.5 text-sm font-mono text-slate-700 placeholder:text-slate-400 focus:bg-white focus:outline-none resize-y disabled:opacity-50 transition-colors"
            placeholder={'Paste URLs, one per line\nhttps://www.example.com/page-1\nhttps://www.example.com/page-2'}
            value={urlText}
            onChange={e => setUrlText(e.target.value)}
            disabled={isActive}
          />
        </div>

        {error && (
          <div className="mt-2 flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-600">
            <XCircle size={14} className="flex-shrink-0" />
            {error}
          </div>
        )}

        {/* Action buttons */}
        <div className="flex flex-wrap items-center gap-2 mt-4">
          <button onClick={handleStart} disabled={isActive || !urlText.trim()}
            className="flex items-center gap-1.5 rounded-lg bg-gradient-to-r from-blue-600 to-indigo-600 px-4 py-2 text-sm font-medium text-white shadow-sm shadow-blue-500/20 hover:from-blue-700 hover:to-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed disabled:shadow-none transition-all">
            <Play size={14} /> Start Queue
          </button>

          {isActive && (
            <>
              {queue.state === 'running' ? (
                <button onClick={handlePause}
                  className="flex items-center gap-1.5 rounded-lg bg-amber-500 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-amber-600 transition-colors">
                  <Pause size={14} /> Pause
                </button>
              ) : (
                <button onClick={handleResume}
                  className="flex items-center gap-1.5 rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-green-700 transition-colors">
                  <Play size={14} /> Resume
                </button>
              )}
              <button onClick={handleStop}
                className="flex items-center gap-1.5 rounded-lg bg-red-500 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-red-600 transition-colors">
                <Square size={14} /> Stop
              </button>
            </>
          )}

          <div className="h-5 w-px bg-slate-200 mx-1" />

          <button onClick={handleImportCSV} disabled={isActive}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40 transition-colors">
            <Upload size={14} /> Import CSV
          </button>
          <button onClick={handleClear} disabled={isActive}
            className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 hover:text-red-600 hover:border-red-200 disabled:opacity-40 transition-colors">
            <Trash2 size={14} /> Clear
          </button>
        </div>

        <p className="mt-3 text-xs text-slate-400">
          Need the format?{' '}
          <button onClick={handleDownloadSample} className="text-blue-500 hover:text-blue-600 hover:underline transition-colors">
            <Download size={10} className="inline mr-0.5 -mt-0.5" />Download sample CSV
          </button>
        </p>
      </div>

      {/* ---- Processing Stats ---- */}
      {total > 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <span className={`h-2 w-2 rounded-full ${queue?.state === 'running' ? 'bg-blue-500 animate-pulse' : 'bg-blue-500'}`} />
            <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wide">Processing Stats</h2>
            {etaText && queue?.state === 'running' && (
              <span className="ml-auto flex items-center gap-1 text-xs text-slate-400">
                <Clock size={11} /> {etaText}
              </span>
            )}
          </div>

          <div className="flex items-center gap-6">
            {/* Completion ring */}
            <CompletionRing pct={pct} state={queue?.state} />

            {/* Stat cards */}
            <div className="flex-1 grid grid-cols-3 gap-3">
              <div className="rounded-lg border border-slate-100 bg-gradient-to-br from-slate-50 to-white p-4 text-center">
                <div className="text-2xl font-bold text-blue-600">{queued}</div>
                <div className="text-xs text-slate-500 mt-1 flex items-center justify-center gap-1"><FileText size={11} /> {queue?.state === 'idle' ? 'Total' : 'Remaining'}</div>
              </div>
              <div className="rounded-lg border border-green-100 bg-gradient-to-br from-green-50 to-white p-4 text-center">
                <div className="text-2xl font-bold text-green-600">{processed}</div>
                <div className="text-xs text-slate-500 mt-1 flex items-center justify-center gap-1"><CheckCircle size={11} /> Processed</div>
              </div>
              <div className="rounded-lg border border-red-100 bg-gradient-to-br from-red-50 to-white p-4 text-center">
                <div className="text-2xl font-bold text-red-500">{errors}</div>
                <div className="text-xs text-slate-500 mt-1 flex items-center justify-center gap-1"><XCircle size={11} /> Errors</div>
              </div>
            </div>
          </div>

          {/* Progress bar */}
          <div className="mt-5">
            <div className="w-full bg-slate-100 rounded-full h-2 overflow-hidden">
              <div
                className={`h-2 rounded-full transition-all duration-700 ease-out ${queue?.state === 'done' ? 'bg-gradient-to-r from-green-400 to-green-500' : 'bg-gradient-to-r from-blue-500 to-indigo-500'}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <div className="flex justify-between items-center mt-1.5 text-xs text-slate-500">
              <span>{processed} of {total} URLs processed</span>
              <span className="font-medium">{pct}%</span>
            </div>
          </div>

          {/* Current URL */}
          {queue?.current_url && (
            <div className="mt-3 flex items-center gap-2 rounded-lg border border-blue-100 bg-blue-50/50 px-3 py-2">
              <div className="relative flex-shrink-0">
                <Loader size={14} className="animate-spin text-blue-500" />
                <span className="absolute -inset-1 rounded-full bg-blue-400/20 animate-ping" />
              </div>
              <span className="text-xs text-slate-500">Processing:</span>
              <span className="font-mono text-xs text-blue-700 truncate">{queue.current_url}</span>
            </div>
          )}
        </div>
      )}

      {/* ---- Results Table ---- */}
      {results.length > 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-100">
            <div className="flex items-center gap-2 mb-3">
              <span className="h-2 w-2 rounded-full bg-indigo-500" />
              <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wide">Results</h2>
              <span className="ml-1 rounded-full bg-indigo-50 border border-indigo-200 px-2 py-0.5 text-xs font-semibold text-indigo-600">{results.length}</span>
            </div>
            <SummaryDonut data={resultDonut} total={results.length} />
          </div>

          <div className="max-h-96 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-slate-50/95 backdrop-blur text-xs text-slate-500 border-b border-slate-100">
                <tr>
                  <th className="text-left px-5 py-2.5 font-medium w-10">#</th>
                  <th className="text-left px-2 py-2.5 font-medium">URL</th>
                  <th className="text-left px-2 py-2.5 font-medium w-28">Coverage</th>
                  <th className="text-left px-2 py-2.5 font-medium w-28">Status</th>
                  <th className="text-left px-2 py-2.5 font-medium w-36">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {results.map((r, i) => (
                  <tr key={i} className="hover:bg-slate-50/70 transition-colors">
                    <td className="px-5 py-2.5 text-slate-400 text-xs tabular-nums">{i + 1}</td>
                    <UrlTooltipCell url={r.url} />
                    <td className="px-2 py-2.5 text-xs text-slate-500">{r.coverage || '—'}</td>
                    <td className="px-2 py-2.5"><StatusBadge status={r.status} /></td>
                    <td className="px-2 py-2.5 text-xs text-slate-500">{r.action || r.error || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div ref={resultsEndRef} />
          </div>
        </div>
      ) : (
        total === 0 && !isActive && queue?.state !== 'done' && (
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <EmptyState
              icon={Search}
              title="No results yet"
              subtitle="Paste URLs above and start the queue to begin bulk indexing inspection."
            />
          </div>
        )
      )}

      {/* ---- Extension Bulk Results ---- */}
      {extResults?.results?.length > 0 ? (
        <div className="rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
          <button
            onClick={() => setExtCollapsed(c => !c)}
            className="w-full px-5 py-4 border-b border-slate-100 flex items-center justify-between hover:bg-slate-50/50 transition-colors"
          >
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-purple-500" />
              <h2 className="text-sm font-bold text-slate-800 uppercase tracking-wide">Extension Bulk Results</h2>
              <span className="rounded-full bg-purple-50 border border-purple-200 px-2 py-0.5 text-xs font-semibold text-purple-600">{extResults.results.length}</span>
            </div>
            <div className="flex items-center gap-3">
              {extResults.received_at && (
                <span className="text-[10px] text-slate-400 flex items-center gap-1">
                  <RefreshCw size={9} /> Synced: {extResults.received_at}
                </span>
              )}
              {extCollapsed ? <ChevronDown size={16} className="text-slate-400" /> : <ChevronUp size={16} className="text-slate-400" />}
            </div>
          </button>

          {!extCollapsed && (
            <>
              <div className="px-5 py-3 border-b border-slate-50">
                <SummaryDonut data={extDonut} total={extResults.results.length} />
              </div>

              <div className="max-h-96 overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="sticky top-0 bg-slate-50/95 backdrop-blur text-xs text-slate-500 border-b border-slate-100">
                    <tr>
                      <th className="text-left px-5 py-2.5 font-medium w-10">#</th>
                      <th className="text-left px-2 py-2.5 font-medium">URL</th>
                      <th className="text-left px-2 py-2.5 font-medium w-24">Coverage</th>
                      <th className="text-left px-2 py-2.5 font-medium w-28">Status</th>
                      <th className="text-left px-2 py-2.5 font-medium">Rich Results</th>
                      <th className="text-left px-2 py-2.5 font-medium w-32">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-50">
                    {extResults.results.map((r, i) => (
                      <tr key={i} className="hover:bg-slate-50/70 transition-colors">
                        <td className="px-5 py-2.5 text-slate-400 text-xs tabular-nums">{i + 1}</td>
                        <UrlTooltipCell url={r.url} />
                        <td className="px-2 py-2.5 text-xs text-slate-500">{r.coverage || '—'}</td>
                        <td className="px-2 py-2.5"><StatusBadge status={r.status} /></td>
                        <td className="px-2 py-2.5">
                          {(r.richResults && r.richResults.length > 0) ? (
                            <div className="flex flex-wrap gap-1">
                              {r.richResults.map((tag, ti) => (
                                <span
                                  key={ti}
                                  className={`inline-flex items-center gap-0.5 rounded-full border px-2 py-0.5 text-[10px] font-medium ${RICH_TAG_COLORS[ti % RICH_TAG_COLORS.length]}`}
                                >
                                  <Tag size={8} /> {tag}
                                </span>
                              ))}
                            </div>
                          ) : (
                            <span className="text-xs text-slate-300">&mdash;</span>
                          )}
                        </td>
                        <td className="px-2 py-2.5 text-xs text-slate-500">{r.action || r.error || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>
      ) : (
        extResults && extResults.results && extResults.results.length === 0 && (
          <div className="rounded-xl border border-slate-200 bg-white shadow-sm">
            <EmptyState
              icon={ExternalLink}
              title="No extension results"
              subtitle="Bulk results synced from the Chrome extension will appear here."
            />
          </div>
        )
      )}
    </div>
  );
}
