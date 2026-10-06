import { NavLink } from 'react-router-dom';
import { LayoutDashboard, Globe, FileSearch, Server, Settings, BarChart3, Search, TrendingUp, Activity } from 'lucide-react';
import clsx from 'clsx';

const nav = [
  { to: '/', label: 'Overview', icon: LayoutDashboard },
  { to: '/indexing', label: 'Page Indexing', icon: Globe },
  { to: '/snippets', label: 'Rich Results', icon: BarChart3 },
  { to: '/analytics', label: 'Search Analytics', icon: TrendingUp },
  { to: '/urls', label: 'URL Browser', icon: FileSearch },
  { to: '/monitoring', label: 'Monitoring', icon: Activity },
  { to: '/accounts', label: 'Accounts', icon: Server },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export default function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-56 flex-col border-r border-slate-200 bg-white">
      <div className="flex items-center gap-3 border-b border-slate-200 px-5 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-to-br from-orange-500 to-red-500 text-sm font-extrabold text-white">R</div>
        <div>
          <div className="text-sm font-bold text-slate-900">Rudra Retail</div>
          <div className="text-[10px] text-slate-400">SEO Dashboard</div>
        </div>
      </div>
      <nav className="flex-1 space-y-0.5 px-3 py-4">
        {nav.map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} end={to === '/'}
            className={({ isActive }) => clsx(
              'flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors',
              isActive ? 'bg-orange-50 text-orange-700' : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
            )}>
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-slate-200 px-4 py-3">
        <p className="text-[10px] text-slate-400">rudraretails.com</p>
      </div>
    </aside>
  );
}
