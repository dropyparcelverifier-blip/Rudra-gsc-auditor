import { useState, useEffect } from 'react';
import { Save, RefreshCw } from 'lucide-react';
import Header from '../components/Header';

const FIELDS = [
  { key: 'pages_indexed', label: 'Pages Indexed' },
  { key: 'pages_not_indexed', label: 'Pages Not Indexed' },
  { key: 'product_snippets_valid', label: 'Product Snippets (Valid)' },
  { key: 'product_snippets_invalid', label: 'Product Snippets (Invalid)' },
  { key: 'merchant_listings_valid', label: 'Merchant Listings (Valid)' },
  { key: 'merchant_listings_invalid', label: 'Merchant Listings (Invalid)' },
  { key: 'review_snippets_valid', label: 'Review Snippets (Valid)' },
  { key: 'review_snippets_invalid', label: 'Review Snippets (Invalid)' },
  { key: 'merchant_opportunities_approved', label: 'Merchant Opportunities (Approved)' },
  { key: 'merchant_opportunities_not_approved', label: 'Merchant Opportunities (Not Approved)' },
];

export default function Settings() {
  const [form, setForm] = useState({});
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    (async () => {
      try {
        const res = await fetch('/api/gsc-reports');
        if (!res.ok) throw new Error(`Server error ${res.status}`);
        const d = await res.json();
        setForm(d);
      } catch (e) { console.error(e); }
    })();
  }, []);

  const handleSave = async () => {
    setLoading(true);
    setSaved(false);
    try {
      const res = await fetch('/api/gsc-reports', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(form),
      });
      if (!res.ok) throw new Error(`Server error ${res.status}`);
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (e) { alert('Error saving: ' + e.message); }
    setLoading(false);
  };

  return (
    <div>
      <Header title="Settings" loading={loading} />
      <div className="space-y-6 p-6">
        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h3 className="mb-1 text-sm font-semibold text-slate-800">GSC Report Numbers</h3>
          <p className="mb-5 text-xs text-slate-500">
            Manually enter the numbers from your Google Search Console dashboard. These drive the top-level stats in the Overview page.
          </p>

          <div className="grid gap-4 sm:grid-cols-2">
            {FIELDS.map(f => (
              <div key={f.key}>
                <label className="mb-1 block text-xs font-semibold text-slate-600">{f.label}</label>
                <input
                  type="number"
                  value={form[f.key] ?? ''}
                  onChange={e => setForm(prev => ({ ...prev, [f.key]: parseInt(e.target.value) || 0 }))}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-orange-300 focus:ring-2 focus:ring-orange-100"
                />
              </div>
            ))}
          </div>

          <div className="mt-6 flex items-center gap-3">
            <button onClick={handleSave} disabled={loading}
              className="flex items-center gap-2 rounded-lg bg-orange-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-orange-700 disabled:opacity-50">
              {loading ? <RefreshCw size={14} className="animate-spin" /> : <Save size={14} />}
              Save Reports
            </button>
            {saved && <span className="text-sm font-semibold text-emerald-600">Saved!</span>}
          </div>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-6">
          <h3 className="mb-1 text-sm font-semibold text-slate-800">About</h3>
          <p className="text-xs text-slate-500">
            Rudra Retail GSC Auditor &mdash; SEO Pipeline Dashboard<br />
            Site: rudraretails.com &bull; 105K+ products<br />
            10 service accounts &bull; 20,000 inspections/day &bull; 2,000 submissions/day
          </p>
        </div>
      </div>
    </div>
  );
}
