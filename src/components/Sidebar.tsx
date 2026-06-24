import {
  Activity, BarChart3, Bitcoin, BookOpen, Briefcase, FileText, Folder, Info, KeyRound,
  LayoutDashboard, ListChecks, Orbit, Settings, Sparkles, Wallet,
} from 'lucide-react';
import { useApp } from '../state/AppStateProvider';
import { cls, fmtUsd } from '../utils/format';
import type { PageId } from '../App';

const NAV: { id: PageId; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { id: 'strategies', label: 'Strategies', icon: Sparkles },
  { id: 'positions', label: 'Positions', icon: Briefcase },
  { id: 'signals', label: 'Signals', icon: Activity },
  { id: 'crypto15m', label: '15m Crypto', icon: Bitcoin },
  { id: 'history', label: 'History', icon: BarChart3 },
  { id: 'profiles', label: 'Profiles', icon: Folder },
  { id: 'settings', label: 'Settings', icon: Settings },
  { id: 'api', label: 'API Keys', icon: KeyRound },
  { id: 'logs', label: 'Logs', icon: ListChecks },
  { id: 'guide', label: 'Guide', icon: BookOpen },
  { id: 'about', label: 'About', icon: Info },
];

interface SidebarProps {
  page: PageId;
  setPage: (p: PageId) => void;
}

export function Sidebar({ page, setPage }: SidebarProps) {
  const { config, account, backend } = useApp();

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-krypt-border bg-krypt-void/40">
      <div className="px-4 py-4">
        <div className="flex items-center gap-2">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-krypt-glow text-white shadow-krypt-soft">
            <FileText className="h-4 w-4" />
          </div>
          <div>
            <div className="font-pixel text-[10px] uppercase tracking-[0.18em] text-white/90">
              Krypt
            </div>
            <div className="text-xs text-krypt-muted">Auto-trader v1</div>
          </div>
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-0.5 px-2">
        {NAV.map(({ id, label, icon: Icon }) => {
          const active = page === id;
          return (
            <button
              key={id}
              onClick={() => setPage(id)}
              className={cls(
                'group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                active
                  ? 'bg-white/[0.06] text-white shadow-[inset_0_0_0_1px_rgba(255,255,255,0.06)]'
                  : 'text-krypt-muted hover:bg-white/[0.03] hover:text-white',
              )}
            >
              <Icon className={cls('h-4 w-4', active && 'text-krypt-purple')} />
              <span>{label}</span>
              {active && <span className="ml-auto h-1.5 w-1.5 rounded-full bg-krypt-purple shadow-[0_0_8px_currentColor]" />}
            </button>
          );
        })}
      </nav>

      <div className="border-t border-krypt-border px-3 pt-3">
        <button
          onClick={() => setPage('visualizer')}
          className={cls(
            'group relative flex w-full items-center gap-2 overflow-hidden rounded-lg border px-3 py-2 text-sm transition-all',
            page === 'visualizer'
              ? 'border-krypt-purple/60 bg-krypt-purple/15 text-white shadow-[0_0_18px_rgba(168,85,247,0.25)]'
              : 'border-krypt-border bg-gradient-to-r from-krypt-purple/10 via-krypt-pink/5 to-transparent text-white hover:border-krypt-purple/40',
          )}
          title="Open the live trade visualizer"
        >
          <span className="relative grid h-7 w-7 place-items-center">
            <span className="absolute inset-0 rounded-full bg-krypt-purple/30 blur-md transition-opacity group-hover:opacity-80" />
            <Orbit className="relative h-4 w-4 text-krypt-purple animate-[spin_20s_linear_infinite]" />
          </span>
          <span className="text-xs font-medium uppercase tracking-wider">Live Visualizer</span>
          <span className="ml-auto h-1.5 w-1.5 rounded-full bg-krypt-purple shadow-[0_0_8px_currentColor]" />
        </button>
      </div>

      <div className="px-3 py-3">
        <div className="rounded-lg border border-krypt-border bg-krypt-surface p-3">
          <div className="flex items-center gap-2 text-xs text-krypt-muted">
            <Wallet className="h-3.5 w-3.5" />
            <span className="uppercase tracking-wider">Wallet</span>
            <span className={cls(
              'ml-auto rounded-full px-1.5 py-0.5 text-[10px] uppercase tracking-wider',
              config?.kalshiEnv === 'demo'
                ? 'border border-krypt-warn/40 bg-krypt-warn/10 text-krypt-warn'
                : 'border border-krypt-win/40 bg-krypt-win/10 text-krypt-win',
            )}>
              {config?.kalshiEnv ?? 'demo'}
            </span>
          </div>
          <div className="mt-1 font-mono text-lg text-white">
            {fmtUsd(account?.totalUsd)}
          </div>
          <div className="text-[11px] text-krypt-dim">
            cash {fmtUsd(account?.cashUsd)} · port {fmtUsd(account?.portfolioUsd)}
          </div>
          <div className="mt-2 flex items-center justify-between text-[11px] text-krypt-muted">
            <span>{config?.enableTrading ? (config?.kalshiEnv === 'production' ? 'LIVE' : 'DEMO') : 'PAUSED'}</span>
            <span className={cls(
              'h-1.5 w-1.5 rounded-full',
              backend.status === 'running' ? 'bg-krypt-win' : 'bg-krypt-warn',
            )} />
          </div>
        </div>
      </div>
    </aside>
  );
}
