import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, Globe, FileSearch, Settings,
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
      { to: '/settings', label: 'Settings', icon: Settings },
    ],
  },
];

export default function Sidebar() {
  return (
    <aside className="fixed left-0 top-0 z-40 flex h-screen w-60 flex-col border-r border-slate-200/60 bg-white/80 backdrop-blur-xl">
      {/* Brand */}
      <div className="flex items-center gap-3.5 px-5 py-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-orange-500 via-red-500 to-rose-600 shadow-lg shadow-orange-300/40 ring-2 ring-orange-100">
          <span className="text-sm font-black text-white tracking-tight">R</span>
        </div>
        <div>
          <div className="text-[15px] font-extrabold text-slate-900 tracking-tight">Rudra Retail</div>
          <div className="text-[10px] font-semibold text-slate-400 tracking-wide uppercase">GSC Dashboard</div>
        </div>
      </div>

      <div className="mx-5 h-px bg-gradient-to-r from-transparent via-slate-200 to-transparent" />

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        {sections.map((section) => (
          <div key={section.label} className="mb-4">
            <div className="mb-2 px-3 text-[10px] font-bold uppercase tracking-[0.15em] text-slate-400/80">
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
                      'group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-medium transition-all duration-200',
                      isActive
                        ? 'bg-gradient-to-r from-orange-50 to-amber-50/80 text-orange-700 shadow-sm shadow-orange-100/50'
                        : 'text-slate-600 hover:bg-slate-50/80 hover:text-slate-900'
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      {isActive && (
                        <span className="absolute left-0 top-1/2 -translate-y-1/2 h-6 w-1 rounded-r-full bg-gradient-to-b from-orange-500 to-red-500 shadow-sm shadow-orange-300/50" />
                      )}
                      <span
                        className={clsx(
                          'flex h-8 w-8 items-center justify-center rounded-xl transition-all duration-200',
                          isActive
                            ? 'bg-gradient-to-br from-orange-100 to-amber-100 text-orange-600 shadow-sm'
                            : 'bg-slate-100/80 text-slate-500 group-hover:bg-slate-200/80 group-hover:text-slate-700 group-hover:scale-105'
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
      <div className="mx-5 h-px bg-gradient-to-r from-transparent via-slate-200 to-transparent" />
      <div className="px-5 py-4">
        <div className="flex items-center gap-2.5">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500" />
          </span>
          <p className="text-[11px] font-semibold text-slate-600">rudraretails.com</p>
        </div>
        <p className="mt-1 text-[9px] text-slate-400 pl-5">Rudra GSC Auditor v2</p>
      </div>
    </aside>
  );
}
