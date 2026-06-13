import { useEffect, useState } from 'react';
import { TitleBar } from './components/TitleBar';
import { Sidebar } from './components/Sidebar';
import { TopBar } from './components/TopBar';
import { AppStateProvider, useApp } from './state/AppStateProvider';
import { ToastProvider } from './state/ToastProvider';
import { OnboardingModal } from './pages/Onboarding';
import { DashboardPage } from './pages/Dashboard';
import { StrategiesPage } from './pages/Strategies';
import { SettingsPage } from './pages/Settings';
import { PositionsPage } from './pages/Positions';
import { SignalsPage } from './pages/Signals';
import { HistoryPage } from './pages/History';
import { ProfilesPage } from './pages/Profiles';
import { LogsPage } from './pages/Logs';
import { ApiKeysPage } from './pages/ApiKeys';
import { AboutPage } from './pages/About';
import { GuidePage } from './pages/Guide';
import { VisualizerPage } from './pages/Visualizer';
import { Crypto15mPage } from './pages/Crypto15m';

export type PageId =
  | 'dashboard' | 'strategies' | 'positions' | 'signals' | 'history'
  | 'profiles' | 'settings' | 'api' | 'logs' | 'guide' | 'about'
  | 'visualizer' | 'crypto15m';

export default function App() {
  return (
    <ToastProvider>
      <AppStateProvider>
        <Shell />
      </AppStateProvider>
    </ToastProvider>
  );
}

function Shell() {
  const [page, setPage] = useState<PageId>('dashboard');
  const { state } = useApp();

  const showOnboarding = state ? !state.acceptedDisclaimer : false;

  useEffect(() => {
    if (!state) return;
    if (!state.acceptedDisclaimer) return;
  }, [state]);

  return (
    <div className="flex h-full w-full flex-col bg-krypt-radial bg-krypt-void">
      <TitleBar />
      <div className="flex h-[calc(100%-2.25rem)] w-full">
        <Sidebar page={page} setPage={setPage} />
        <main className="relative flex flex-1 flex-col overflow-hidden">
          <TopBar />
          <div className="flex-1 overflow-hidden bg-krypt-radial-r">
            <PageRouter page={page} setPage={setPage} />
          </div>
        </main>
      </div>
      {showOnboarding && <OnboardingModal onDone={() => setPage('api')} />}
    </div>
  );
}

function PageRouter({ page, setPage }: { page: PageId; setPage: (p: PageId) => void }) {
  switch (page) {
    case 'dashboard': return <DashboardPage onNav={setPage} />;
    case 'strategies': return <StrategiesPage />;
    case 'positions': return <PositionsPage />;
    case 'signals': return <SignalsPage />;
    case 'history': return <HistoryPage />;
    case 'profiles': return <ProfilesPage />;
    case 'settings': return <SettingsPage />;
    case 'api': return <ApiKeysPage />;
    case 'logs': return <LogsPage />;
    case 'guide': return <GuidePage />;
    case 'about': return <AboutPage />;
    case 'visualizer': return <VisualizerPage />;
    case 'crypto15m': return <Crypto15mPage />;
    default: return <DashboardPage onNav={setPage} />;
  }
}
