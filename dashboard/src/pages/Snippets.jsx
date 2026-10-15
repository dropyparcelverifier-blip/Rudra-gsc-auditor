import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell, PieChart, Pie } from 'recharts';
import { Package, ShoppingCart, Star, TrendingUp, Eye, MousePointerClick, Search, Info } from 'lucide-react';
import Header from '../components/Header';
import StatCard from '../components/StatCard';
import DataSourceBadge from '../components/DataSourceBadge';

const COLORS = ['#a855f7', '#06b6d4', '#eab308', '#22c55e', '#ef4444', '#f97316', '#6366f1'];

const SNIPPET_NAMES = {
  PRODUCT_SNIPPETS: 'Product Snippets',
  PRODUCT_SNIPPET: 'Product Snippets',
  MERCHANT_LISTINGS: 'Merchant Listings',
  REVIEW_SNIPPET: 'Review Snippets',
  AMP_BLUE_LINK: 'AMP Blue Link',
  PRODUCT_IMAGE_SNIPPET: 'Product Image Snippet',
  SHOPPING_TAB: 'Shopping Tab',
};

export default function Snippets({ data, loading, refresh }) {
  if (!data) return <div className="flex h-96 items-center justify-center text-slate-400">Loading...</div>;

  const liveSnippets = data.snippets || {};
  const pipeline = data.pipeline || {};
  const richBreakdown = pipeline.rich_breakdown || {};

  const snippetData = Object.entries(liveSnippets)
    .filter(([, stats]) => stats && typeof stats === 'object')
    .map(([key, stats], idx) => ({
      name: SNIPPET_NAMES[key] || key,
      key,
      impressions: stats.impressions || 0,
      clicks: stats.clicks || 0,
      ctr: stats.ctr || 0,
      position: stats.avg_position || 0,
      color: COLORS[idx % COLORS.length],
    }));

  const totalImpressions = snippetData.reduce((s, d) => s + d.impressions, 0);
  const totalClicks = snippetData.reduce((s, d) => s + d.clicks, 0);
  const pieData = snippetData.map(d => ({ name: d.name, value: d.impressions, color: d.color }));

  const richCards = [
    { key: 'Product', label: 'Product Snippets', icon: Package, color: 'purple', border: 'border-purple-200', bg: 'bg-purple-50', text: 'text-purple-700' },
    { key: 'MerchantListing', label: 'Merchant Listings', icon: ShoppingCart, color: 'cyan', border: 'border-cyan-200', bg: 'bg-cyan-50', text: 'text-cyan-700' },
    { key: 'Review', label: 'Review Snippets', icon: Star, color: 'yellow', border: 'border-amber-200', bg: 'bg-amber-50', text: 'text-amber-700' },
    { key: 'None', label: 'No Rich Results', icon: Search, color: 'slate', border: 'border-slate-200', bg: 'bg-slate-50', text: 'text-slate-600' },
  ];

  const totalRich = Object.values(richBreakdown).reduce((s, v) => s + v, 0);

  return (
    <div>
      <Header title="Rich Results" onRefresh={() => refresh(true)} loading={loading} />
      <div className="space-y-6 p-6">

        {/* URL Inspection detected rich results */}
        {totalRich > 0 && (
          <div>
            <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
              Detected Rich Results (URL Inspection)
              <DataSourceBadge source="pipeline_db" className="ml-2" />
            </h2>
            <p className="mb-3 text-xs text-slate-500">
              URLs where the URL Inspection API detected structured data. From {totalRich.toLocaleString()} inspected URLs.
            </p>
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {richCards.map(rc => (
                <div key={rc.key} className={`rounded-xl border ${rc.border} ${rc.bg} p-4`}>
                  <div className={`flex items-center gap-2 ${rc.text}`}>
                    <rc.icon size={16} />
                    <span className="text-[11px] font-semibold uppercase">{rc.label}</span>
                  </div>
                  <p className={`mt-2 text-2xl font-extrabold ${rc.text}`}>
                    {(richBreakdown[rc.key] || 0).toLocaleString()}
                  </p>
                  <p className="mt-1 text-[10px] text-slate-500">
                    {totalRich ? ((richBreakdown[rc.key] || 0) / totalRich * 100).toFixed(1) : 0}% of inspected
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Search Analytics performance */}
        <div>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">
            Search Performance by Snippet Type
            <DataSourceBadge source="search_analytics" className="ml-2" />
          </h2>
          <p className="mb-3 text-xs text-slate-500">
            How each rich result type performs in Google Search (last 90 days).
          </p>

          {/* Summary cards */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 mb-4">
            <StatCard label="Total Impressions" value={totalImpressions} color="purple" icon={Eye} subtitle="90 days" />
            <StatCard label="Total Clicks" value={totalClicks} color="blue" icon={MousePointerClick} subtitle="90 days" />
            <StatCard label="Snippet Types" value={snippetData.length} color="green" icon={TrendingUp} />
          </div>

          {/* Individual snippet type cards */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {snippetData.map((s, i) => (
              <div key={s.key} className="rounded-xl border border-slate-200 bg-white p-5">
                <div className="mb-3 flex items-center gap-2">
                  <div className="h-3 w-3 rounded-full" style={{ background: s.color }} />
                  <span className="text-sm font-semibold text-slate-700">{s.name}</span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg bg-slate-50 p-2 text-center">
                    <p className="text-lg font-extrabold text-slate-800">{s.impressions.toLocaleString()}</p>
                    <p className="text-[10px] text-slate-500">Impressions</p>
                  </div>
                  <div className="rounded-lg bg-slate-50 p-2 text-center">
                    <p className="text-lg font-extrabold text-slate-800">{s.clicks.toLocaleString()}</p>
                    <p className="text-[10px] text-slate-500">Clicks</p>
                  </div>
                </div>
                <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
                  <span>CTR: <span className="font-semibold text-slate-700">{s.ctr}%</span></span>
                  <span>Avg Pos: <span className="font-semibold text-slate-700">{s.position}</span></span>
                </div>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
                  <div className="h-full rounded-full" style={{ background: s.color, width: `${totalImpressions ? (s.impressions / totalImpressions * 100) : 0}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Charts */}
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-700">Impression Share</h3>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" innerRadius={50} outerRadius={95} paddingAngle={2}>
                  {pieData.map((d, i) => <Cell key={i} fill={d.color} />)}
                </Pie>
                <Tooltip formatter={(v) => v.toLocaleString()} />
              </PieChart>
            </ResponsiveContainer>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4">
            <h3 className="mb-3 text-sm font-semibold text-slate-700">Clicks by Type</h3>
            <ResponsiveContainer width="100%" height={250}>
              <BarChart data={snippetData} layout="vertical" margin={{ left: 10 }}>
                <XAxis type="number" tick={{ fontSize: 11 }} />
                <YAxis type="category" dataKey="name" width={140} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v) => v.toLocaleString()} />
                <Bar dataKey="clicks" radius={[0, 6, 6, 0]} barSize={26}>
                  {snippetData.map((d, i) => <Cell key={i} fill={d.color} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Comparison table */}
        <div className="rounded-xl border border-slate-200 bg-white">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50 text-left">
                <th className="px-4 py-2.5 font-semibold text-slate-600">Type</th>
                <th className="px-4 py-2.5 text-right font-semibold text-slate-600">Impressions</th>
                <th className="px-4 py-2.5 text-right font-semibold text-slate-600">Clicks</th>
                <th className="px-4 py-2.5 text-right font-semibold text-slate-600">CTR</th>
                <th className="px-4 py-2.5 text-right font-semibold text-slate-600">Avg Position</th>
                <th className="px-4 py-2.5 text-right font-semibold text-slate-600">Share%</th>
              </tr>
            </thead>
            <tbody>
              {[...snippetData].sort((a, b) => b.impressions - a.impressions).map((d) => (
                <tr key={d.key} className="border-b border-slate-50 hover:bg-slate-50">
                  <td className="px-4 py-2.5 flex items-center gap-2">
                    <div className="h-2.5 w-2.5 rounded-full" style={{ background: d.color }} />
                    {d.name}
                  </td>
                  <td className="px-4 py-2.5 text-right font-semibold">{d.impressions.toLocaleString()}</td>
                  <td className="px-4 py-2.5 text-right">{d.clicks.toLocaleString()}</td>
                  <td className="px-4 py-2.5 text-right">{d.ctr}%</td>
                  <td className="px-4 py-2.5 text-right">{d.position}</td>
                  <td className="px-4 py-2.5 text-right text-slate-500">{totalImpressions ? (d.impressions / totalImpressions * 100).toFixed(1) : 0}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Note */}
        <div className="flex gap-2 rounded-lg border border-slate-200 bg-slate-50 p-4 text-xs text-slate-600">
          <Info size={16} className="mt-0.5 shrink-0 text-slate-400" />
          <div>
            <p><strong>Two data sources shown:</strong></p>
            <p className="mt-1"><strong>URL Inspection (top)</strong> — which specific URLs have Product/Merchant/Review structured data detected. See exact URLs in URL Browser (filter by rich result type).</p>
            <p className="mt-1"><strong>Search Analytics (below)</strong> — aggregate performance (impressions, clicks, CTR) for each rich result type across your site.</p>
          </div>
        </div>
      </div>
    </div>
  );
}
