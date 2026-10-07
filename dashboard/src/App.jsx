import { Routes, Route } from 'react-router-dom';
import Sidebar from './components/Sidebar';
import PipelineNotification from './components/PipelineNotification';
import { useDashboard } from './hooks/useDashboard';
import Overview from './pages/Overview';
import Indexing from './pages/Indexing';
import Snippets from './pages/Snippets';
import Analytics from './pages/Analytics';
import UrlBrowser from './pages/UrlBrowser';
import Monitoring from './pages/Monitoring';
import Accounts from './pages/Accounts';
import Settings from './pages/Settings';

export default function App() {
  const { data, loading, error, refresh, lastFetched } = useDashboard();

  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="ml-56 flex-1">
        {error && (
          <div className="m-4 rounded-lg border border-red-200 bg-red-50 px-4 py-2 text-sm text-red-700">
            API Error: {error}
          </div>
        )}
        <Routes>
          <Route path="/" element={<Overview data={data} loading={loading} refresh={refresh} />} />
          <Route path="/indexing" element={<Indexing data={data} loading={loading} refresh={refresh} />} />
          <Route path="/snippets" element={<Snippets data={data} loading={loading} refresh={refresh} />} />
          <Route path="/analytics" element={<Analytics data={data} loading={loading} refresh={refresh} />} />
          <Route path="/urls" element={<UrlBrowser />} />
          <Route path="/monitoring" element={<Monitoring />} />
          <Route path="/accounts" element={<Accounts />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
      <PipelineNotification />
    </div>
  );
}
