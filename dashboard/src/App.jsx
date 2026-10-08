import { useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import { AlertTriangle, X } from 'lucide-react';
import Sidebar from './components/Sidebar';
import PipelineNotification from './components/PipelineNotification';
import { useLiveData } from './hooks/useDashboard';
import Overview from './pages/Overview';
import Indexing from './pages/Indexing';
import Snippets from './pages/Snippets';
import Analytics from './pages/Analytics';
import UrlBrowser from './pages/UrlBrowser';
import Monitoring from './pages/Monitoring';

import Settings from './pages/Settings';
import BulkTool from './pages/BulkTool';
import ExtensionData from './pages/ExtensionData';

export default function App() {
  const { data, loading, error, refresh, lastFetched } = useLiveData();
  const [dismissed, setDismissed] = useState(false);

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="ml-60 flex-1">
        {error && !dismissed && (
          <div className="mx-4 mt-4 flex items-center gap-3 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 shadow-sm">
            <AlertTriangle size={16} className="flex-shrink-0" />
            <span className="flex-1 font-medium">API Error: {error}</span>
            <button onClick={() => setDismissed(true)} className="rounded-md p-1 hover:bg-red-100 transition-colors">
              <X size={14} />
            </button>
          </div>
        )}
        <Routes>
          <Route path="/" element={<Overview data={data} loading={loading} refresh={refresh} />} />
          <Route path="/indexing" element={<Indexing data={data} loading={loading} refresh={refresh} />} />
          <Route path="/snippets" element={<Snippets data={data} loading={loading} refresh={refresh} />} />
          <Route path="/analytics" element={<Analytics data={data} loading={loading} refresh={refresh} />} />
          <Route path="/urls" element={<UrlBrowser />} />
          <Route path="/monitoring" element={<Monitoring />} />

          <Route path="/settings" element={<Settings />} />
          <Route path="/bulk-tool" element={<BulkTool />} />
          <Route path="/extension" element={<ExtensionData />} />
        </Routes>
      </main>
      <PipelineNotification />
    </div>
  );
}
