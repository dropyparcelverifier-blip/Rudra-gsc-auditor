import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Globe, FileSearch, Server, Settings,
  BarChart3, TrendingUp, Activity, Zap, Chrome,
} from 'lucide-react';
import clsx from 'clsx';

const sections = [
  {
    label: 'Dashboard',
    items: [
      { to: '/', label: 'Overview', icon: LayoutDashboard },
      { to: '/indexing', label: 'Page Indexing', icon: Globe },
      { to: '/snippets', label: 'Rich Results', icon: BarChart3 },
      { to: '/analytics', label: 'Search Analytics', icon: TrendingUp },
    ],
  },
  {
    label: 'Tools',
    items: [
      { to: '/urls', label: 'URL Browser', icon: FileSearch },
      { to: '/monitoring', label: 'Monitoring', icon: Activity },
      { to: '/extension', label: 'Extension Data', icon: Chrome },
      { to: '/bulk-tool', label: 'Bulk Indexing', icon: Zap },
    ],
  },
  {
    label: 'System',
    items: [
      { to: '/accounts', label: 'Accounts', icon: Server },
      { to: '/settings', label: 'Settings', icon: Settings },
    ],
  },
];

export default function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-56 flex-col border-r border-slate-200 bg-white">
      {/* Brand */}
      <div className="flex items-center gap-3 border-b border-slate-100 px-5 py-4">
        <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-orange-500 to-red-600 shadow-lg shadow-orange-200/50 transition-transform duration-200 hover:scale-105">
          <span className="text-sm font-extrabold text-white tracking-tight">R</span>
        </div>
        <div>
          <div className="text-sm font-bold text-slate-900 tracking-tight">Rudra Retail</div>
          <div className="text-[10px] font-medium text-slate-400">SEO Dashboard</div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-3 space-y-1">
        {sections.map((section) => (
          <div key={section.label} className="mb-3">
            <div className="mb-1.5 px-3 text-[10px] font-bold uppercase tracking-widest text-slate-400">
              {section.label}
            </div>
            <div className="space-y-0.5">
              {section.items.map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={to === '/'}
                  className={({ isActive }) =>
                    clsx(
                      'group relative flex items-center gap-3 rounded-lg px-3 py-2 text-[13px] font-medium transition-all duration-150',
                      isActive
                        ? 'bg-gradient-to-r from-orange-50 to-amber-50 text-orange-700 shadow-sm'
                        : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-1 rounded-r-full bg-gradient-to-b from-orange-500 to-red-500" />
                      )}
                      <span
                        className={clsx(
                          'flex h-7 w-7 items-center justify-center rounded-lg transition-all duration-150',
                          isActive
                            ? 'bg-orange-100 text-orange-600'
                            : 'bg-slate-100 text-slate-500 group-hover:bg-slate-200 group-hover:text-slate-700 group-hover:scale-105'
                        )}
                      >
                        <Icon size={15} />
                      </span>
                      {label}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="border-t border-slate-100 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="h-2 w-2 rounded-full bg-emerald-500 animate-pulse" />
          <p className="text-[10px] font-medium text-slate-500">rudraretails.com</p>
        </div>
        <p className="mt-1 text-[9px] text-slate-300 pl-4">Rudra GSC Auditor</p>
      </div>
    </aside>
  );
}
