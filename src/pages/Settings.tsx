import { useState } from 'react';
import {
  AlertTriangle, Banknote, Bitcoin, Cloud, Film, Globe2, RotateCcw, Save,
  Trophy, Vote,
} from 'lucide-react';
import type { TraderConfig } from '@shared/types';
import { useApp } from '../state/AppStateProvider';
import { useToast } from '../state/ToastProvider';
import { Card, NameDialog, NumberInput, Page, PercentInput, Section, Switch } from '../components/common';
import { cls } from '../utils/format';
import { computeTradeWarnings } from '../utils/warnings';

const KRYPT_CATEGORIES: { id: string; label: string; Icon: typeof Trophy }[] = [
  { id: 'sports', label: 'Sports', Icon: Trophy },
  { id: 'politics', label: 'Politics', Icon: Vote },
  { id: 'economics', label: 'Economics', Icon: Banknote },
  { id: 'crypto', label: 'Crypto', Icon: Bitcoin },
  { id: 'climate', label: 'Climate', Icon: Cloud },
  { id: 'entertainment', label: 'Entertainment', Icon: Film },
  { id: 'world', label: 'World', Icon: Globe2 },
];

export function SettingsPage() {
  const { config, account, credentialsAll, refresh, state } = useApp();
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const [saveOpen, setSaveOpen] = useState(false);

  if (!config) return <Page title="Settings"><div className="text-krypt-muted">Loading…</div></Page>;

  const update = async <K extends keyof TraderConfig>(key: K, value: TraderConfig[K]): Promise<void> => {
    try {
      await window.krypt.config.update({ [key]: value } as Partial<TraderConfig>);
      await refresh.state();
    } catch (e: any) {
      toast.error(`${e?.message || e}`);
    }
  };

  // Switching env is the #1 place users silently lock themselves out (wrong /
  // missing keys for the target env). Make it loud: switch, then verify + tell them.
  const switchEnv = async (e: 'demo' | 'production'): Promise<void> => {
    if (!config || e === config.kalshiEnv) return;
    await update('kalshiEnv', e);
    const label = e === 'production' ? 'Production (real money)' : 'Demo (play money)';
    const creds = e === 'production' ? credentialsAll?.production : credentialsAll?.demo;
    if (!creds?.hasApiKey || !creds?.hasRsaKey) {
      toast.warn(`Switched to ${label}, but no API keys are saved for it. Add them on the API Keys page or the bot can't connect or trade.`);
      return;
    }
    const r = await window.krypt.credentials.test(e);
    if (r.ok) {
      toast.success(`Connected to ${label}.`);
    } else {
      toast.error(`${label} keys were rejected by Kalshi — open the API Keys page and re-check the key for this environment. (${r.message ?? 'auth failed'})`);
    }
    await refresh.credentials();
  };

  const reset = async (): Promise<void> => {
    if (!window.confirm('Reset all trading settings to defaults?')) return;
    setBusy(true);
    try {
      await window.krypt.config.reset();
      await refresh.state();
      toast.success('Reset to defaults');
    } finally {
      setBusy(false);
    }
  };

  const saveAsProfile = async (name: string): Promise<void> => {
    setSaveOpen(false);
    const r = await window.krypt.profiles.save(name);
    if (r.ok) {
      toast.success(r.message || `Saved "${name}"`);
      await refresh.state();
    } else toast.error(r.message || 'Could not save profile');
  };

  const env = config.kalshiEnv;
  const warnings = computeTradeWarnings(config, account);

  return (
    <Page
      title="Settings"
      subtitle="Every knob the bot has. Changes are saved + applied immediately."
      actions={
        <>
          <button onClick={reset} disabled={busy} className="krypt-btn-default">
            <RotateCcw className="h-4 w-4" /> Reset
          </button>
          <button onClick={() => setSaveOpen(true)} className="krypt-btn-primary">
            <Save className="h-4 w-4" /> Save as Profile
          </button>
        </>
      }
    >
      {warnings.length > 0 && (
        <div className="mb-5 space-y-2">
          {warnings.map((w) => (
            <div
              key={w.id}
              className={cls(
                'flex items-start gap-2 rounded-lg border px-3 py-2 text-xs',
                w.severity === 'block'
                  ? 'border-krypt-loss/40 bg-krypt-loss/10 text-krypt-loss'
                  : 'border-krypt-warn/40 bg-krypt-warn/10 text-krypt-warn',
              )}
            >
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              <span>{w.message}</span>
            </div>
          ))}
        </div>
      )}

      <Section title="Environment">
        <Card>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="krypt-label">Kalshi environment</label>
              <div className="flex gap-2">
                {(['demo', 'production'] as const).map((e) => (
                  <button
                    key={e}
                    onClick={() => void switchEnv(e)}
                    className={cls(
                      'flex-1 rounded-md border px-3 py-2 text-sm capitalize transition-colors',
                      env === e
                        ? 'border-krypt-purple bg-krypt-purple/10 text-white'
                        : 'border-krypt-border bg-krypt-surface2 text-krypt-muted hover:border-krypt-borderHi',
                    )}
                  >
                    {e}
                  </button>
                ))}
              </div>
              <p className="krypt-help">
                Demo runs against demo-api.kalshi.co. Production trades real money.
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <Switch
                label="Auto-trading enabled"
                description="Master kill switch. When off, signals stream in but no orders are placed. To test risk-free, run on the Demo environment above."
                checked={config.enableTrading}
                onChange={(v) => void update('enableTrading', v)}
              />
            </div>
          </div>
        </Card>
      </Section>

      <Section
        title="Strategies"
        description="Toggle whole signal sources on/off. Off means the scanners still run but the trader ignores them."
      >
        <Card>
          <div className="grid gap-2 md:grid-cols-3">
            <Switch
              label="Trade whale signals"
              description="Follow $2.5k+ taker orders into the same side."
              checked={config.tradeWhales}
              onChange={(v) => void update('tradeWhales', v)}
            />
            <Switch
              label="Trade momentum signals"
              description="Fade clusters of trades against the underdog."
              checked={config.tradeMomentum}
              onChange={(v) => void update('tradeMomentum', v)}
            />
            <Switch
              label="Trade convergence (coming soon)"
              description="Will fire when 3+ whales agree on the same side within 2h. The convergence scanner is still in development."
              checked={false}
              disabled
              onChange={() => undefined}
            />
          </div>
        </Card>
      </Section>

      <Section
        title="Categories"
        description="Restrict which kinds of markets the bot is allowed to trade. Off = allow all (no filtering)."
      >
        <Card>
          <CategoryPicker
            value={config.allowedCategories}
            onChange={(v) => void update('allowedCategories', v)}
          />
        </Card>
      </Section>

      <Section
        title="Signal gates"
        description="Higher thresholds = fewer, higher-quality trades. Edge is confidence minus market-implied probability."
      >
        <Card>
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Min edge (whales)" hint="Pts of edge required for a whale signal to fire">
              <NumberInput value={config.minEdgePtsWhale} step={0.5} suffix="pts"
                onChange={(v) => void update('minEdgePtsWhale', v)} />
            </Field>
            <Field label="Min edge (momentum)">
              <NumberInput value={config.minEdgePtsMomentum} step={0.5} suffix="pts"
                onChange={(v) => void update('minEdgePtsMomentum', v)} />
            </Field>
            <Field label="Min confidence (whales)">
              <NumberInput value={config.minConfidenceWhale} step={1} suffix="%"
                onChange={(v) => void update('minConfidenceWhale', v)} />
            </Field>
            <Field label="Min confidence (momentum)">
              <NumberInput value={config.minConfidenceMomentum} step={1} suffix="%"
                onChange={(v) => void update('minConfidenceMomentum', v)} />
            </Field>
            <Field label="Min entry price">
              <NumberInput value={config.minEntryPriceCents} step={1} min={1} max={99} suffix="¢"
                onChange={(v) => void update('minEntryPriceCents', v)} />
            </Field>
            <Field label="Max entry price">
              <NumberInput value={config.maxEntryPriceCents} step={1} min={1} max={99} suffix="¢"
                onChange={(v) => void update('maxEntryPriceCents', v)} />
            </Field>
            <Field label="Max signal age" hint="Older signals are skipped">
              <NumberInput value={config.maxSignalAgeSec} step={10} suffix="s"
                onChange={(v) => void update('maxSignalAgeSec', v)} />
            </Field>
            <Field label="Contrarian only (momentum)">
              <Switch
                checked={config.contrarianOnly}
                label="Only fade markets where the cluster runs against current price"
                onChange={(v) => void update('contrarianOnly', v)}
              />
            </Field>
          </div>
        </Card>
      </Section>

      <Section
        title="Position sizing"
        description="Size each trade as a % of balance (edge-scaled) or a fixed dollar amount. Hard cap protects you on a single bad pick."
      >
        <Card>
          <div className="mb-4">
            <label className="krypt-label">Sizing mode</label>
            <div className="flex gap-2">
              {([['percent', '% of balance'], ['fixed', 'Fixed $ per trade']] as const).map(([m, lbl]) => (
                <button
                  key={m}
                  onClick={() => void update('sizingMode', m)}
                  className={cls(
                    'flex-1 rounded-md border px-3 py-2 text-sm transition-colors',
                    config.sizingMode === m
                      ? 'border-krypt-purple bg-krypt-purple/10 text-white'
                      : 'border-krypt-border bg-krypt-surface2 text-krypt-muted hover:border-krypt-borderHi',
                  )}
                >
                  {lbl}
                </button>
              ))}
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {config.sizingMode === 'fixed' ? (
              <Field label="Fixed trade size" hint="Every trade risks this exact dollar amount.">
                <NumberInput value={config.fixedTradeUsd} step={1} min={0} prefix="$"
                  onChange={(v) => void update('fixedTradeUsd', v)} />
              </Field>
            ) : (
              <>
                <Field label="Base size">
                  <PercentInput value={config.baseSizeFraction} step={0.5} min={0.1} max={100}
                    onChange={(v) => void update('baseSizeFraction', v)} />
                </Field>
                <Field label="Min size">
                  <PercentInput value={config.minSizeFraction} step={0.5} min={0.1} max={100}
                    onChange={(v) => void update('minSizeFraction', v)} />
                </Field>
                <Field label="Max size">
                  <PercentInput value={config.maxSizeFraction} step={0.5} min={0.1} max={100}
                    onChange={(v) => void update('maxSizeFraction', v)} />
                </Field>
                <Field label="Sizing base edge">
                  <NumberInput value={config.sizingBaseEdge} step={1} suffix="pts"
                    onChange={(v) => void update('sizingBaseEdge', v)} />
                </Field>
                <Field label="Sizing max edge">
                  <NumberInput value={config.sizingMaxEdge} step={1} suffix="pts"
                    onChange={(v) => void update('sizingMaxEdge', v)} />
                </Field>
              </>
            )}
            <Field label="Hard cap per trade">
              <NumberInput value={config.hardMaxPositionUsd} step={5} prefix="$"
                onChange={(v) => void update('hardMaxPositionUsd', v)} />
            </Field>
            <Field label="Min cash reserve">
              <PercentInput value={config.minCashReserveFraction} step={1} min={0} max={99}
                onChange={(v) => void update('minCashReserveFraction', v)} />
            </Field>
            <Field label="Max total exposure">
              <PercentInput value={config.maxTotalExposureFraction} step={5} min={0} max={100}
                onChange={(v) => void update('maxTotalExposureFraction', v)} />
            </Field>
            <Field label="Starting bankroll" hint="0 = auto-detect from your first observed balance">
              <NumberInput value={config.startBankrollUsd} step={50} min={0} prefix="$"
                onChange={(v) => void update('startBankrollUsd', v)} />
            </Field>
          </div>
        </Card>
      </Section>

      <Section
        title="Order placement"
        description="How the bot translates a signal into an actual Kalshi order."
      >
        <Card>
          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <label className="krypt-label">Order style</label>
              <div className="flex gap-1.5">
                {(['limit_cross', 'limit_mid', 'market'] as const).map((o) => (
                  <button
                    key={o}
                    onClick={() => void update('orderStyle', o)}
                    className={cls(
                      'flex-1 rounded-md border px-2 py-2 text-xs',
                      config.orderStyle === o
                        ? 'border-krypt-purple bg-krypt-purple/10 text-white'
                        : 'border-krypt-border bg-krypt-surface2 text-krypt-muted hover:border-krypt-borderHi',
                    )}
                  >
                    {o.replace('_', '-')}
                  </button>
                ))}
              </div>
              <p className="krypt-help">
                limit-cross hits the opposite side&apos;s best bid (highest fill rate).
              </p>
            </div>
            <Field label="Cross fallback offset">
              <NumberInput value={config.crossSpreadFallbackOffset} step={1} suffix="¢"
                onChange={(v) => void update('crossSpreadFallbackOffset', v)} />
            </Field>
            <Field label="Order expiration" hint="Auto-cancel if unfilled this long. 0 = never">
              <NumberInput value={config.orderExpirationSec ?? 0} step={10} suffix="s"
                onChange={(v) => void update('orderExpirationSec', v <= 0 ? null : v)} />
            </Field>
          </div>
        </Card>
      </Section>

      <Section
        title="Concurrency &amp; risk"
        description="Hard caps that prevent runaway exposure when many signals fire at once."
      >
        <Card>
          <div className="grid gap-4 md:grid-cols-3">
            <Field label="Max open positions">
              <NumberInput value={config.maxOpenPositions} step={1} min={1}
                onChange={(v) => void update('maxOpenPositions', v)} />
            </Field>
            <Field label="Max positions per event">
              <NumberInput value={config.maxPositionsPerEvent} step={1} min={1}
                onChange={(v) => void update('maxPositionsPerEvent', v)} />
            </Field>
            <Field label="Max new positions / day"
              hint={config.unlimitedDailyNewPositions
                ? 'Disabled — unlimited mode is on'
                : undefined}>
              <NumberInput
                value={config.maxDailyNewPositions}
                step={5}
                min={1}
                disabled={config.unlimitedDailyNewPositions}
                onChange={(v) => void update('maxDailyNewPositions', v)}
              />
            </Field>
            <Field label="Unlimited daily new positions"
              hint="Off = enforce the daily cap above. On = the only entry limit is Max open positions.">
              <div className="flex h-9 items-center">
                <Switch
                  checked={!!config.unlimitedDailyNewPositions}
                  onChange={(v) => void update('unlimitedDailyNewPositions', v)}
                />
              </div>
            </Field>
            <Field label="Daily stop-loss" hint="Halts new entries if today's P&L falls below">
              <NumberInput value={config.stopLossOnDay} step={5} prefix="$"
                onChange={(v) => void update('stopLossOnDay', v)} />
            </Field>
            <Field label="Daily take-profit" hint="Halts new entries when reached. 0 = disabled">
              <NumberInput value={config.takeProfitOnDay} step={5} prefix="$"
                onChange={(v) => void update('takeProfitOnDay', v)} />
            </Field>
          </div>
        </Card>
      </Section>

      <Section
        title="Trading hours"
        description="Optionally restrict the bot to only trade during certain hours and days. Polling, resolution, and signal scanning still run 24/7 — only new entries are gated."
      >
        <Card>
          <div className="mb-3 flex items-center justify-between">
            <div className="text-sm text-white">Restrict trading to a weekly window</div>
            <Switch
              checked={config.tradingHoursEnabled}
              onChange={(v) => void update('tradingHoursEnabled', v)}
            />
          </div>
          <div className={config.tradingHoursEnabled ? '' : 'pointer-events-none opacity-40'}>
            <div className="grid gap-4 md:grid-cols-3">
              <Field label="Start (HH:MM)" hint="Local time, 24h format">
                <input
                  type="time"
                  value={config.tradingHoursStart}
                  onChange={(e) => void update('tradingHoursStart', e.target.value)}
                  className="w-full rounded-md border border-krypt-border bg-krypt-surface2 px-3 py-1.5 font-mono text-sm text-white"
                />
              </Field>
              <Field label="End (HH:MM)" hint="Same day or next-morning (overnight ranges supported)">
                <input
                  type="time"
                  value={config.tradingHoursEnd}
                  onChange={(e) => void update('tradingHoursEnd', e.target.value)}
                  className="w-full rounded-md border border-krypt-border bg-krypt-surface2 px-3 py-1.5 font-mono text-sm text-white"
                />
              </Field>
              <Field label="UTC offset (minutes)" hint="0 = UTC · -300 = US Eastern (winter) · -240 = US Eastern (summer)">
                <NumberInput
                  value={config.tradingTimezoneOffsetMin}
                  step={30}
                  onChange={(v) => void update('tradingTimezoneOffsetMin', v)}
                />
              </Field>
            </div>
            <div className="mt-3">
              <div className="mb-2 text-xs uppercase tracking-wider text-krypt-muted">Active days</div>
              <DayPicker
                value={config.tradingDays}
                onChange={(v) => void update('tradingDays', v)}
              />
            </div>
            <div className="mt-3 rounded-md border border-krypt-border bg-krypt-surface2 p-3 text-[11px] text-krypt-muted">
              <span className="text-white">Tip:</span> sports markets settle on event clocks
              — restrict to evenings (19:00–23:30) if you only want trades around U.S.
              prime time. Late-night liquidity gets thin and the bot's edge can decay.
            </div>
          </div>
        </Card>
      </Section>

      <Section
        title="Loop cadence"
        description="How often each subsystem runs. Lower = more API calls; higher = laggier."
      >
        <Card>
          <div className="grid gap-4 md:grid-cols-3">
            <Field label="Trade scan interval">
              <NumberInput value={config.tradeScanInterval} step={5} suffix="s"
                onChange={(v) => void update('tradeScanInterval', v)} />
            </Field>
            <Field label="Position poll interval">
              <NumberInput value={config.positionPollInterval} step={5} suffix="s"
                onChange={(v) => void update('positionPollInterval', v)} />
            </Field>
            <Field label="Balance poll interval">
              <NumberInput value={config.balancePollInterval} step={5} suffix="s"
                onChange={(v) => void update('balancePollInterval', v)} />
            </Field>
            <Field label="Resolution check">
              <NumberInput value={config.resolutionCheckInterval} step={30} suffix="s"
                onChange={(v) => void update('resolutionCheckInterval', v)} />
            </Field>
            <Field label="Whale scan interval">
              <NumberInput value={config.whaleScanInterval} step={10} suffix="s"
                onChange={(v) => void update('whaleScanInterval', v)} />
            </Field>
            <Field label="Momentum scan interval">
              <NumberInput value={config.momentumScanInterval} step={10} suffix="s"
                onChange={(v) => void update('momentumScanInterval', v)} />
            </Field>
            <Field label="Market refresh interval">
              <NumberInput value={config.marketRefreshInterval} step={30} suffix="s"
                onChange={(v) => void update('marketRefreshInterval', v)} />
            </Field>
          </div>
        </Card>
      </Section>

      <Section
        title="Whale + momentum scanner thresholds"
        description="Lower thresholds = more raw signals (which the trade gates will further filter)."
      >
        <Card>
          <div className="grid gap-4 md:grid-cols-3">
            <Field label="Min whale $">
              <NumberInput value={config.minWhaleUsd} step={500} prefix="$"
                onChange={(v) => void update('minWhaleUsd', v)} />
            </Field>
            <Field label="Min whale confidence">
              <NumberInput value={config.minWhaleConfidence} step={1} suffix="%"
                onChange={(v) => void update('minWhaleConfidence', v)} />
            </Field>
            <Field label="Min entry price (whale)">
              <NumberInput value={config.minEntryPriceFrac} step={0.05} min={0} max={1}
                onChange={(v) => void update('minEntryPriceFrac', v)} />
            </Field>
          </div>
        </Card>
      </Section>

      <Section
        title="Discord webhooks (optional)"
        description="Drop your channel webhook URLs to mirror events to Discord."
      >
        <Card>
          <div className="grid gap-3 md:grid-cols-2">
            <UrlField label="Trade events" value={config.eventWebhookUrl}
              onChange={(v) => void update('eventWebhookUrl', v)} />
            <UrlField label="Stats" value={config.statsWebhookUrl}
              onChange={(v) => void update('statsWebhookUrl', v)} />
            <UrlField label="Whale alerts" value={config.whaleWebhookUrl}
              onChange={(v) => void update('whaleWebhookUrl', v)} />
            <UrlField label="Momentum alerts" value={config.momentumWebhookUrl}
              onChange={(v) => void update('momentumWebhookUrl', v)} />
          </div>
          <Switch
            label="Enable Discord webhooks"
            description="Master switch — turn off to mute all webhook posting without losing the URLs."
            checked={config.enableDiscord}
            onChange={(v) => void update('enableDiscord', v)}
          />
        </Card>
      </Section>

      <Section title="App preferences">
        <Card>
          <div className="grid gap-2 md:grid-cols-2">
            <Switch
              label="Start with Windows"
              description="Launch Krypt Trader at login (silent if Start Minimized is on)."
              checked={!!state?.startWithWindows}
              onChange={(v) => window.krypt.state.setStartWithWindows(v).then(refresh.state)}
            />
            <Switch
              label="Start minimized to tray"
              description="If autostarted, hide to tray on launch. Open from the tray icon."
              checked={!!state?.startMinimized}
              onChange={(v) => window.krypt.state.setStartMinimized(v).then(refresh.state)}
            />
          </div>
        </Card>
      </Section>

      <DangerZone busy={busy} setBusy={setBusy} />
      <NameDialog
        open={saveOpen}
        title="Save these settings as a profile"
        label="Saves a snapshot of every knob below. It'll appear under Your Strategies."
        placeholder="e.g. My small-balance sports config"
        confirmLabel="Save"
        onSubmit={(name) => void saveAsProfile(name)}
        onClose={() => setSaveOpen(false)}
      />
    </Page>
  );
}

function DangerZone({
  busy, setBusy,
}: { busy: boolean; setBusy: (b: boolean) => void }) {
  const toast = useToast();
  const [showModal, setShowModal] = useState(false);
  const [phrase, setPhrase] = useState('');

  const openModal = (): void => {
    setPhrase('');
    setShowModal(true);
  };

  const cancel = (): void => {
    setShowModal(false);
    setPhrase('');
  };

  const confirm = async (): Promise<void> => {
    if (phrase.trim() !== 'RESET') {
      toast.error('Type RESET (uppercase) to confirm.');
      return;
    }
    setShowModal(false);
    setBusy(true);
    try {
      const r = await window.krypt.app.factoryReset();
      if (r.ok) {
        const summary = (r.data as { deleted?: Record<string, number> })?.deleted || {};
        const detail = Object.entries(summary)
          .filter(([k, v]) => !k.startsWith('_') && (v as number) > 0)
          .map(([k, v]) => `${k}: ${v}`)
          .join(', ');
        toast.success(detail
          ? `Wiped — ${detail}`
          : (r.message || 'Local data cleared (nothing to delete)'));
      } else {
        toast.error(r.message || 'Reset failed');
      }
    } catch (e: any) {
      toast.error(`${e?.message || e}`);
    } finally {
      setBusy(false);
      setPhrase('');
    }
  };

  return (
    <>
      <Section title="Danger zone">
        <Card>
          <div className="space-y-3 rounded-xl border border-rose-500/40 bg-rose-500/5 p-4">
            <div>
              <div className="text-sm font-semibold text-rose-300">
                Full reset
              </div>
              <p className="text-xs text-krypt-muted mt-1">
                Wipes all locally stored trading history, P&amp;L snapshots,
                bot runs, and signals. API keys, profiles, and settings are
                preserved. Live Kalshi positions will be re-imported on the
                next reconcile cycle. Useful for clearing inconsistent state
                from old builds before live testing.
              </p>
            </div>
            <button
              onClick={openModal}
              disabled={busy}
              className="inline-flex items-center gap-2 rounded-lg border border-rose-500/60 bg-rose-500/15 px-4 py-2 text-sm font-semibold text-rose-200 hover:bg-rose-500/25 disabled:cursor-not-allowed disabled:opacity-50"
            >
              <RotateCcw className="h-4 w-4" />
              Full reset
            </button>
          </div>
        </Card>
      </Section>

      {showModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm"
          onClick={cancel}
        >
          <div
            className="w-full max-w-md rounded-2xl border border-rose-500/50 bg-krypt-panel p-6 shadow-2xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h3 className="text-lg font-semibold text-rose-300">
              Confirm full reset
            </h3>
            <div className="mt-3 space-y-2 text-sm text-krypt-muted">
              <p>This will permanently delete:</p>
              <ul className="ml-5 list-disc space-y-1">
                <li>all bot positions and trade history</li>
                <li>all bot runs (session P&amp;L)</li>
                <li>all P&amp;L snapshots</li>
                <li>all whale and momentum signals</li>
              </ul>
              <p className="pt-2">
                API keys, profiles, and settings are <strong>kept</strong>.
                Live Kalshi positions will be re-imported on the next
                reconcile cycle.
              </p>
            </div>
            <label className="mt-4 block text-xs font-semibold uppercase tracking-wider text-krypt-muted">
              Type <span className="text-rose-300">RESET</span> to confirm
            </label>
            <input
              autoFocus
              value={phrase}
              onChange={(e) => setPhrase(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') void confirm();
                if (e.key === 'Escape') cancel();
              }}
              className="mt-1 w-full rounded-lg border border-rose-500/40 bg-black/30 px-3 py-2 text-sm font-mono text-rose-100 placeholder-krypt-muted/50 outline-none focus:border-rose-400"
              placeholder="RESET"
            />
            <div className="mt-5 flex justify-end gap-2">
              <button
                onClick={cancel}
                className="rounded-lg border border-white/10 bg-white/5 px-4 py-2 text-sm font-semibold text-krypt-muted hover:bg-white/10"
              >
                Cancel
              </button>
              <button
                onClick={() => void confirm()}
                disabled={phrase.trim() !== 'RESET'}
                className="rounded-lg border border-rose-500/60 bg-rose-500/20 px-4 py-2 text-sm font-semibold text-rose-100 hover:bg-rose-500/30 disabled:cursor-not-allowed disabled:opacity-40"
              >
                Wipe everything
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Field({
  label, hint, children,
}: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="krypt-label">{label}</label>
      {children}
      {hint && <p className="krypt-help">{hint}</p>}
    </div>
  );
}

function CategoryPicker({
  value, onChange,
}: { value: string[] | null; onChange: (v: string[] | null) => void }) {
  const allEnabled = value === null;
  const selected = new Set(value ?? []);

  const toggleAll = (): void => {
    onChange(allEnabled ? [] : null);
  };

  const toggleOne = (id: string): void => {
    if (allEnabled) {
      onChange([id]);
      return;
    }
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    if (next.size === KRYPT_CATEGORIES.length) {
      onChange(null);
    } else {
      onChange(Array.from(next));
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <div className="text-xs text-krypt-muted">
          {allEnabled
            ? 'Trading all categories.'
            : selected.size === 0
              ? 'No categories selected — bot will skip all signals!'
              : `Trading ${selected.size} of ${KRYPT_CATEGORIES.length} categories.`}
        </div>
        <button onClick={toggleAll} className="krypt-btn-default text-xs">
          {allEnabled ? 'Pick specific' : 'Allow all'}
        </button>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        {KRYPT_CATEGORIES.map(({ id, label, Icon }) => {
          const active = allEnabled || selected.has(id);
          return (
            <button
              key={id}
              onClick={() => toggleOne(id)}
              className={cls(
                'flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition-colors',
                active
                  ? 'border-krypt-purple bg-krypt-purple/10 text-white'
                  : 'border-krypt-border bg-krypt-surface2 text-krypt-muted hover:border-krypt-borderHi',
              )}
            >
              <Icon className={cls('h-4 w-4', active ? 'text-krypt-purple' : 'text-krypt-dim')} />
              <span>{label}</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

function UrlField({
  label, value, onChange,
}: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <div>
      <label className="krypt-label">{label} webhook</label>
      <input
        type="text"
        className="krypt-input font-mono text-xs"
        value={value}
        placeholder="https://discord.com/api/webhooks/…"
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

const DAYS = [
  { id: 'mon', label: 'Mon' },
  { id: 'tue', label: 'Tue' },
  { id: 'wed', label: 'Wed' },
  { id: 'thu', label: 'Thu' },
  { id: 'fri', label: 'Fri' },
  { id: 'sat', label: 'Sat' },
  { id: 'sun', label: 'Sun' },
] as const;

function DayPicker({
  value, onChange,
}: { value: string[]; onChange: (v: string[]) => void }) {
  const set = new Set(value);
  const toggle = (id: string) => {
    const next = new Set(set);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    onChange(DAYS.filter((d) => next.has(d.id)).map((d) => d.id));
  };
  return (
    <div className="flex flex-wrap gap-1.5">
      {DAYS.map((d) => {
        const active = set.has(d.id);
        return (
          <button
            key={d.id}
            onClick={() => toggle(d.id)}
            className={cls(
              'rounded-md border px-3 py-1.5 text-xs font-medium uppercase tracking-wider transition-colors',
              active
                ? 'border-krypt-purple bg-krypt-purple/15 text-white'
                : 'border-krypt-border bg-krypt-surface2 text-krypt-muted hover:border-krypt-borderHi',
            )}
          >
            {d.label}
          </button>
        );
      })}
    </div>
  );
}
