import { useState, useEffect, useCallback } from 'react';
import { CheckCircle, AlertTriangle, Loader, X, Zap } from 'lucide-react';
import { api } from '../lib/api';

const PHASE_LABELS = {
  starting: 'Starting pipeline...',
  classify: 'Classifying URLs...',
  inspect: 'Inspecting URLs...',
  submit: 'Submitting for indexing...',
  reclassify: 'Re-classifying...',
  snapshot: 'Saving snapshot...',
  done: 'Pipeline complete!',
  error: 'Pipeline failed',
};

const borderGradientMap = {
  running: 'from-blue-400 to-cyan-400',
  completed: 'from-emerald-400 to-green-400',
  failed: 'from-red-400 to-orange-400',
};

export default function PipelineNotification() {
  const [status, setStatus] = useState(null);
  const [dismissed, setDismissed] = useState({});
  const [lastCompleted, setLastCompleted] = useState(null);

  const poll = useCallback(async () => {
    try {
      const data = await api.getPipelineStatus();
      if (!data || !data.state) return;
      setStatus(data);

      if (data.state === 'completed' && data.completed_at !== lastCompleted) {
        setLastCompleted(data.completed_at);
        setDismissed(prev => ({ ...prev, [data.completed_at]: false }));
      }
    } catch {
      // silent — pipeline status is optional
    }
  }, [lastCompleted]);

  useEffect(() => {
    poll();
    const id = setInterval(poll, 10000);
    return () => clearInterval(id);
  }, [poll]);

  if (!status || !status.state) return null;

  const { state, phase, step, inspected, inspect_total, error, completed_at,
          total_tracked, indexed, not_indexed, changes_today } = status;

  const isRunning = state === 'running';
  const isComplete = state === 'completed';
  const isFailed = state === 'failed';

  if (isComplete && dismissed[completed_at]) return null;
  if (!isRunning && !isComplete && !isFailed) return null;

  const bgClass = isFailed ? 'bg-red-50 border-red-200'
    : isComplete ? 'bg-emerald-50 border-emerald-200'
    : 'bg-blue-50 border-blue-200';

  const iconColor = isFailed ? 'text-red-600'
    : isComplete ? 'text-emerald-600'
    : 'text-blue-600';

  const Icon = isFailed ? AlertTriangle : isComplete ? CheckCircle : Loader;

  const gradientBorder = borderGradientMap[state] || borderGradientMap.running;

  return (
    <div className={`fixed bottom-4 right-4 z-50 w-80 rounded-2xl border shadow-xl ${bgClass} p-4 overflow-hidden`}>
      {/* Gradient left border accent */}
      <div className={`absolute left-0 top-0 bottom-0 w-1 bg-gradient-to-b ${gradientBorder}`} />
      <div className="flex items-start gap-3">
        <Icon size={20} className={`${iconColor} mt-0.5 ${isRunning ? 'animate-spin' : ''}`} />
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <p className={`text-sm font-semibold ${iconColor}`}>
              {isFailed ? 'Pipeline Error' : isComplete ? 'Pipeline Done' : 'Pipeline Running'}
            </p>
            {(isComplete || isFailed) && (
              <button onClick={() => setDismissed(prev => ({ ...prev, [completed_at || 'err']: true }))}
                className="p-0.5 rounded hover:bg-black/5">
                <X size={14} className="text-slate-400" />
              </button>
            )}
          </div>

          <p className="text-xs text-slate-600 mt-1">
            {PHASE_LABELS[phase] || phase}
            {step && <span className="ml-1 text-slate-400">({step})</span>}
          </p>

          {isRunning && phase === 'inspect' && inspect_total > 0 && (
            <div className="mt-2">
              <div className="flex justify-between text-[10px] text-slate-500 mb-0.5">
                <span>{(inspected || 0).toLocaleString()} inspected</span>
                <span>{inspect_total.toLocaleString()} total</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-blue-100">
                <div className="h-full rounded-full bg-blue-500 transition-all duration-500"
                  style={{ width: `${Math.min(100, (inspected || 0) / inspect_total * 100)}%` }} />
              </div>
            </div>
          )}

          {isComplete && (
            <div className="mt-2 space-y-0.5 text-[11px] text-slate-600">
              <div className="flex justify-between">
                <span>Tracked</span>
                <span className="font-semibold">{(total_tracked || 0).toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-emerald-700">Indexed</span>
                <span className="font-semibold text-emerald-700">{(indexed || 0).toLocaleString()}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-red-600">Not indexed</span>
                <span className="font-semibold text-red-600">{(not_indexed || 0).toLocaleString()}</span>
              </div>
              {changes_today > 0 && (
                <div className="flex items-center gap-1 mt-1 text-amber-700">
                  <Zap size={10} />
                  <span>{changes_today} changes detected today</span>
                </div>
              )}
            </div>
          )}

          {isFailed && error && (
            <p className="mt-1 text-[11px] text-red-600 truncate" title={error}>{error}</p>
          )}
        </div>
      </div>
    </div>
  );
}
