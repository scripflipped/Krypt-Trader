import { ExternalLink, FolderOpen, Gift, Globe, MessageCircle } from 'lucide-react';
import { useApp } from '../state/AppStateProvider';
import { Card, Page, Section } from '../components/common';
import {
  KALSHI_REFERRAL_URL, KRYPT_DISCORD, KRYPT_HOME, KRYPT_TOOLS, KRYPT_TRADER_PAGE,
} from '../utils/links';

export function AboutPage() {
  const { appVersion, backend, config } = useApp();

  const open = (url: string) => () => void window.krypt.app.openExternal(url);

  const showFolder = async (): Promise<void> => {
    const p = await window.krypt.app.getUserDataPath();
    await window.krypt.app.showItemInFolder(p);
  };

  return (
    <Page title="About" subtitle="Version, links, support, and credits.">
      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <div className="flex items-start gap-4">
            <div className="grid h-16 w-16 place-items-center rounded-2xl bg-krypt-glow shadow-krypt-strong">
              <span className="font-pixel text-sm">K</span>
            </div>
            <div>
              <div className="font-pixel text-sm">KRYPT TRADER</div>
              <div className="mt-1 text-sm text-krypt-muted">
                Free Kalshi auto-trading bot · v{appVersion}
              </div>
              <div className="mt-1 text-xs text-krypt-dim">
                Backend: {backend.status} · {config?.kalshiEnv?.toUpperCase()} · pid {backend.pid ?? '—'}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button onClick={open(KRYPT_TRADER_PAGE)} className="krypt-btn-default">
                  <Globe className="h-4 w-4" /> krypt.cc/tools/trader <ExternalLink className="h-3 w-3" />
                </button>
                <button onClick={open(KRYPT_DISCORD)} className="krypt-btn-default">
                  <MessageCircle className="h-4 w-4" /> Discord <ExternalLink className="h-3 w-3" />
                </button>
                <button onClick={showFolder} className="krypt-btn-default">
                  <FolderOpen className="h-4 w-4" /> Open data folder
                </button>
              </div>
            </div>
          </div>
          <p className="mt-6 text-sm text-krypt-muted">
            Krypt Trader is part of the <span className="text-white">Krypt</span> free
            tools suite — a collection of small, polished, no-bullshit Windows utilities
            we build because the existing options annoyed us. If you want to support
            development without paying anything, throw a follow at{' '}
            <a
              href="#"
              onClick={(e) => { e.preventDefault(); open(KRYPT_HOME)(); }}
              className="text-krypt-purple hover:underline"
            >
              krypt.cc
            </a>{' '}
            or use our Kalshi referral when signing up.
          </p>
        </Card>

        <Card>
          <div className="text-sm text-white">Quick links</div>
          <div className="mt-3 flex flex-col gap-1.5 text-sm">
            <LinkRow label="Kalshi public site" onClick={open('https://kalshi.com')} />
            <LinkRow label="Kalshi demo dashboard" onClick={open('https://demo.kalshi.co')} />
            <LinkRow label="Kalshi API docs" onClick={open('https://trading-api.readme.io')} />
            <LinkRow label="Krypt Tools homepage" onClick={open(KRYPT_TOOLS)} />
          </div>
        </Card>
      </div>

      <Section title="Sign up to Kalshi · $25 free">
        <Card>
          <div className="flex flex-col items-start gap-4 md:flex-row md:items-center">
            <div className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-krypt-glow shadow-krypt-soft">
              <Gift className="h-5 w-5 text-white" />
            </div>
            <div className="flex-1">
              <div className="text-sm text-white">
                Don&apos;t have a Kalshi account yet?
              </div>
              <p className="mt-0.5 text-xs text-krypt-muted">
                Use our referral and Kalshi gives you <span className="text-white">$25 free</span> after
                your first deposit. Costs you nothing, supports Krypt&apos;s free tools.
              </p>
            </div>
            <button onClick={open(KALSHI_REFERRAL_URL)} className="krypt-btn-primary">
              <Gift className="h-4 w-4" /> Claim $25 on Kalshi <ExternalLink className="h-3 w-3" />
            </button>
          </div>
        </Card>
      </Section>

      <Section title="Risk &amp; disclosure">
        <Card>
          <p className="text-xs leading-relaxed text-krypt-muted">
            Krypt Trader is provided as-is, free of charge. Auto-trading event
            contracts is risky. Krypt makes no guarantee of profitability and accepts
            no liability for any losses incurred while using this tool. You are
            responsible for complying with Kalshi&apos;s terms of service and any
            applicable laws in your jurisdiction. Always test on the demo
            environment until you trust your config.
          </p>
        </Card>
      </Section>

      <Section title="Credits">
        <Card>
          <p className="text-xs text-krypt-muted">
            UI built with <span className="text-white">Electron · React · Tailwind · Recharts</span> ·
            backend in <span className="text-white">Python (httpx + cryptography)</span> ·
            packaged with <span className="text-white">PyInstaller + electron-builder</span>.
            Brand &amp; tooling by{' '}
            <a
              href="#"
              onClick={(e) => { e.preventDefault(); open(KRYPT_HOME)(); }}
              className="text-krypt-purple hover:underline"
            >
              Krypt
            </a>.
          </p>
        </Card>
      </Section>
    </Page>
  );
}

function LinkRow({ label, onClick }: { label: string; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center justify-between rounded-md border border-krypt-border bg-krypt-surface2 px-3 py-2 text-left text-xs hover:border-krypt-borderHi hover:bg-white/5"
    >
      <span>{label}</span>
      <ExternalLink className="h-3.5 w-3.5 text-krypt-muted" />
    </button>
  );
}
