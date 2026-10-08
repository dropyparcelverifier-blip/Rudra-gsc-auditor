import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../lib/api';

const AUTO_REFRESH_MS = 5 * 60 * 1000; // 5 minutes

export function useLiveData() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [lastFetched, setLastFetched] = useState(null);
  const timerRef = useRef(null);

  const refresh = useCallback(async (force = false) => {
    setLoading(true);
    try {
      if (force) await api.clearCache().catch(() => {});
      const ctrl = new AbortController();
      const timer = setTimeout(() => ctrl.abort(), 15000);
      const d = await api.getLiveData(ctrl.signal);
      clearTimeout(timer);
      setData(d);
      setError(null);
      setLastFetched(new Date());
    } catch (e) {
      if (e.name !== 'AbortError') setError(e.message);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    refresh();
    timerRef.current = setInterval(() => refresh(), AUTO_REFRESH_MS);
    return () => clearInterval(timerRef.current);
  }, [refresh]);

  return { data, loading, error, refresh, lastFetched };
}
