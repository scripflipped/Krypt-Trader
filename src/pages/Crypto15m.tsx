import { useEffect, useRef, useState } from 'react';
import { Bitcoin, RefreshCw, RotateCcw, SlidersHorizontal, Wallet, Zap } from 'lucide-react';
import type {
  Crypto15mAsset, Crypto15mPosition,
  Crypto15mSizing, Crypto15mSnapshot, Crypto15mStatus, TraderConfig,
} from '@shared/types';
import { useApp } from '../state/AppStateProvider';
import { Empty, Page, Switch } from '../components/common';
import { TickerLink } from '../components/KalshiTicker';
import { cls, fmtUsd } from '../utils/format';

const POLL_MS = 4000;

function fmtSpot(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  const dp = v >= 100 ? 2 : v >= 1 ? 4 : 6;
  return `$${v.toLocaleString(undefined, { maximumFractionDigits: dp })}`;
}

function fmtDelta(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  const dp = v >= 100 ? 2 : v >= 1 ? 3 : 5;
  return `$${v.toLocaleString(undefined, { maximumFractionDigits: dp })}`;
}

function fmtMins(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return `${v.toFixed(1)}m`;
}

function pct(v: number | null | undefined): string {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  return `${Math.round(v * 100)}%`;
}

export function Crypto15mPage() {
  const { config } = useApp();
  const [snap, setSnap] = useState<Crypto15mSnapshot | null>(null);
  const [status, setStatus] = useState<Crypto15mStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const timer = useRef<number | null>(null);

  async function load() {
    const api = window.krypt?.crypto15m;
    if (!api) {
      setErr('15m crypto API unavailable (restart the app after this update).');
      setLoading(false);
      return;
    }
    try {
      const [s, st] = await Promise.all([api.snapshot(), api.status()]);
      setSnap(s);
      setStatus(st);
      setErr(null);
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
    timer.current = window.setInterval(() => void load(), POLL_MS) as unknown as number;
    return () => {
      if (timer.current) window.clearInterval(timer.current);
    };
  }, []);

  async function patchAndReload(patch: Partial<TraderConfig>) {
    setBusy(true);
    try {
      await window.krypt.config.update(patch);
      await load();
    } catch (e: any) {
      setErr(e?.message || String(e));
    } finally {
      setBusy(false);
    }
  }

  const toggleEnabled = (next: boolean) => patchAndReload({ crypto15mEnabled: next });

  async function toggleLive(next: boolean) {
    if (next && !window.confirm(
      'Go LIVE? The 15-minute crypto executor will place REAL orders with your '
      + 'Kalshi balance — independently of the main bot\'s Start Trading switch.',
    )) return;
    await patchAndReload({ crypto15mLive: next });
  }

  const live = snap?.assets.filter((a) => a.signal).length ?? 0;
  const enabled = !!config?.crypto15mEnabled;
  const liveArmed = !!config?.crypto15mLive;
  const isLive = !!status?.live;
  const authed = !!status?.authed;
  const liveSupported = status?.liveSupported ?? true;
  const mode: 'OFF' | 'MONITOR' | 'LIVE' = !enabled ? 'OFF' : isLive ? 'LIVE' : 'MONITOR';
  const openPos = status?.open ?? [];
  const recentPos = (status?.recent ?? []).filter((p) => p.resolved);

  return (
    <Page
      title="15m Crypto"
      subtitle="Kalshi 15-minute crypto markets. Experimental — favorite-follow has no proven edge at any threshold (its return ≈ win-rate − price), so treat it as for-fun and test on Demo first. Tune the entry window, favorite threshold, delta filter, and stop-loss below."
      actions={
        <button
          onClick={() => void load()}
          className="inline-flex items-center gap-2 rounded-md border border-krypt-border bg-krypt-surface2 px-3 py-1.5 text-xs text-krypt-muted transition-colors hover:border-krypt-purple/40 hover:text-white"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      }
    >
      { }
      <div className="mb-4 rounded-xl border border-krypt-border bg-krypt-surface p-3">
        <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
          <div className="min-w-[260px] flex-1">
            <Switch
              checked={enabled}
              disabled={busy}
              onChange={(v) => void toggleEnabled(v)}
              label="Enable 15-minute crypto executor"
              description={
                mode === 'LIVE'
                  ? 'LIVE — placing real orders on your Kalshi account.'
                  : mode === 'MONITOR'
                    ? 'Monitor only — tracking signals but not placing orders (needs a live production account).'
                    : 'Off — monitor only.'
              }
            />
          </div>
          {enabled && (
            <div className="min-w-[220px]">
              <Switch
                checked={liveArmed}
                disabled={busy}
                onChange={(v) => void toggleLive(v)}
                label="Real orders (LIVE)"
                description="Runs on its own — the main bot's Start Trading switch is not required."
              />
            </div>
          )}
          <ModePill mode={mode} />
          <div className="flex items-center gap-4 text-xs">
            <KV label="Size" value={`${status?.orderSize ?? 1}c`} />
            <KV label="Max open" value={`${status?.maxConcurrent ?? 7}`} />
            <KV label="Open" value={`${status?.stats.openCount ?? 0}`} />
            <KV label="W / L" value={`${status?.stats.wins ?? 0} / ${status?.stats.losses ?? 0}`} />
            <KV
              label="Realized"
              value={fmtUsd(status?.stats.realizedPnlUsd ?? 0, { sign: true })}
              accent={(status?.stats.realizedPnlUsd ?? 0) >= 0 ? 'good' : 'bad'}
            />
          </div>
        </div>
        {enabled && !liveSupported && (
          <div className="mt-2 text-[11px] text-krypt-warn">
            Kalshi's <span className="text-krypt-muted">demo</span> exchange doesn't carry the 15-minute crypto
            markets, so orders can't be placed here — this just monitors. Switch to a
            <span className="text-krypt-muted"> Live</span> account in Settings to trade them for real.
          </div>
        )}
        {enabled && liveSupported && liveArmed && !authed && (
          <div className="mt-2 text-[11px] text-krypt-warn">
            Live is armed but Kalshi isn't connected — not trading until you connect your account in
            <span className="text-krypt-muted"> Settings → Credentials</span>.
          </div>
        )}
        {enabled && liveSupported && !liveArmed && (
          <div className="mt-2 text-[11px] text-krypt-dim">
            Monitor only. Flip <span className="text-krypt-muted">Real orders (LIVE)</span> to trade your Kalshi
            balance — no other settings needed.
          </div>
        )}
      </div>

      { }
      <StrategySettings
        config={config}
        liveSignals={live}
        spotSource={snap?.spotSource ?? 'cryptocompare'}
        spotOk={snap?.spotOk ?? true}
        hoursOk={snap?.hoursOk ?? true}
        sizing={status?.sizing ?? null}
      />

      {err && (
        <div className="mb-4 rounded-lg border border-krypt-loss/40 bg-krypt-loss/10 px-3 py-2 text-xs text-krypt-loss">
          {err}
        </div>
      )}

      {!snap && loading ? (
        <Empty title="Loading 15-minute crypto markets…" description="Fetching Kalshi markets and spot prices." />
      ) : snap && snap.assets.length === 0 ? (
        <Empty title="No data" description="Could not load any 15-minute crypto series." />
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {snap?.assets.map((a) => <AssetCard key={a.series} a={a} />)}
        </div>
      )}

      { }
      {(openPos.length > 0 || recentPos.length > 0) && (
        <div className="mt-6 space-y-4">
          {openPos.length > 0 && <PositionsTable title="Open positions" rows={openPos} />}
          {recentPos.length > 0 && <PositionsTable title="Recent (resolved)" rows={recentPos.slice(0, 20)} />}
        </div>
      )}
    </Page>
  );
}

function ModePill({ mode }: { mode: 'OFF' | 'MONITOR' | 'LIVE' }) {
  const sty =
    mode === 'LIVE'
      ? 'border-krypt-loss/50 bg-krypt-loss/15 text-krypt-loss'
      : mode === 'MONITOR'
        ? 'border-krypt-warn/50 bg-krypt-warn/15 text-krypt-warn'
        : 'border-krypt-border bg-krypt-surface2 text-krypt-muted';
  return (
    <span className={cls('rounded-full border px-3 py-1 text-[11px] font-bold uppercase tracking-wider', sty)}>
      {mode}
    </span>
  );
}

function KV({ label, value, accent }: { label: string; value: string; accent?: 'good' | 'bad' }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-krypt-dim">
      {label}
      <span className={cls('font-mono', accent === 'good' ? 'text-krypt-win' : accent === 'bad' ? 'text-krypt-loss' : 'text-white')}>
        {value}
      </span>
    </span>
  );
}


const C15_DEFAULTS = {
  directionMode: 'favorite' as 'favorite' | 'contrarian',
  timeDelayMin: 8,
  entryThreshold: 0.70,
  entryMax: 0.98,
  exitThreshold: 0.4,
  minDeltaPct: 0,
  entryDiff: 0.02,
  entryStyle: 'maker' as 'maker' | 'taker',
  makerCancelMin: 1,
  hoursStartUtc: 0,
  hoursEndUtc: 24,
  orderSize: 1,
  maxConcurrent: 7,
};

const C15_PRESETS: { id: string; name: string; hint: string; patch: Partial<TraderConfig> }[] = [
  {
    id: 'favorite', name: 'Deep Favorite',
    hint: 'Only the deepest favorites (95–98¢) — the one band that didn\'t lose in collected data (small sample).',
    patch: { crypto15mDirectionMode: 'favorite', crypto15mEntryThreshold: 0.95, crypto15mEntryMax: 0.98, crypto15mExitThreshold: 0.4, crypto15mEntryStyle: 'maker' },
  },
  {
    id: 'contrarian', name: 'Contrarian Fade',
    hint: 'Fade extreme favorites — buy the cheap side, hold to settle. Measured ≈ break-even.',
    patch: { crypto15mDirectionMode: 'contrarian', crypto15mEntryThreshold: 0.9, crypto15mEntryMax: 0.98, crypto15mExitThreshold: 0, crypto15mEntryStyle: 'maker' },
  },
];

function StrategySettings({
  config, liveSignals, spotSource, spotOk, hoursOk, sizing,
}: {
  config: TraderConfig | null;
  liveSignals: number;
  spotSource: string;
  spotOk: boolean;
  hoursOk: boolean;
  sizing: Crypto15mSizing | null;
}) {
  const sizingMode = config?.crypto15mSizingMode ?? 'fixed';
  const [savingPreset, setSavingPreset] = useState<string | null>(null);
  const update = async (patch: Partial<TraderConfig>) => {
    try { await window.krypt.config.update(patch); } catch {   }
  };
  const num = (k: keyof TraderConfig, d: number) => {
    const v = config?.[k] as number | undefined;
    return typeof v === 'number' && !Number.isNaN(v) ? v : d;
  };
  const dir = (config?.crypto15mDirectionMode ?? C15_DEFAULTS.directionMode);
  const entryStyle = (config?.crypto15mEntryStyle ?? C15_DEFAULTS.entryStyle);

  const applyPreset = async (p: typeof C15_PRESETS[number]) => {
    setSavingPreset(p.id);
    try { await window.krypt.config.update(p.patch); } finally { setSavingPreset(null); }
  };

  const resetDefaults = () => void update({
    crypto15mDirectionMode: C15_DEFAULTS.directionMode,
    crypto15mTimeDelayMin: C15_DEFAULTS.timeDelayMin,
    crypto15mEntryThreshold: C15_DEFAULTS.entryThreshold,
    crypto15mEntryMax: C15_DEFAULTS.entryMax,
    crypto15mExitThreshold: C15_DEFAULTS.exitThreshold,
    crypto15mMinDeltaPct: C15_DEFAULTS.minDeltaPct,
    crypto15mEntryDiff: C15_DEFAULTS.entryDiff,
    crypto15mEntryStyle: C15_DEFAULTS.entryStyle,
    crypto15mMakerCancelMin: C15_DEFAULTS.makerCancelMin,
    crypto15mHoursStartUtc: C15_DEFAULTS.hoursStartUtc,
    crypto15mHoursEndUtc: C15_DEFAULTS.hoursEndUtc,
  });

  return (
    <div className="mb-4 rounded-xl border border-krypt-border bg-krypt-surface p-4">
      <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-2">
        <span className="inline-flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-krypt-muted">
          <SlidersHorizontal className="h-3.5 w-3.5" /> Strategy settings
        </span>
        <span className="text-[11px] text-krypt-dim">changes apply live</span>
        <div className="ml-auto flex items-center gap-3">
          {liveSignals > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full bg-krypt-win/10 px-2 py-0.5 text-[11px] font-semibold text-krypt-win">
              <Zap className="h-3 w-3" /> {liveSignals} live signal{liveSignals === 1 ? '' : 's'}
            </span>
          )}
          {!hoursOk && (
            <span className="inline-flex items-center gap-1 rounded-full bg-krypt-warn/10 px-2 py-0.5 text-[11px] font-semibold text-krypt-warn">
              outside trading hours
            </span>
          )}
          <span className={cls('inline-flex items-center gap-1.5 text-[11px]', spotOk ? 'text-krypt-muted' : 'text-krypt-warn')}>
            <span className={cls('h-1.5 w-1.5 rounded-full', spotOk ? 'bg-krypt-win' : 'bg-krypt-warn')} />
            spot: {spotSource}{spotOk ? '' : ' (down)'}
          </span>
        </div>
      </div>

      { }
      <div className="mb-3 flex flex-wrap gap-2">
        {C15_PRESETS.map((p) => (
          <button
            key={p.id}
            onClick={() => void applyPreset(p)}
            disabled={savingPreset !== null}
            title={p.hint}
            className="rounded-md border border-krypt-border bg-krypt-surface2 px-2.5 py-1 text-[11px] text-krypt-muted transition-colors hover:border-krypt-purple/40 hover:text-white disabled:opacity-50"
          >
            {p.name}
          </button>
        ))}
        <button
          onClick={resetDefaults}
          className="ml-auto inline-flex items-center gap-1 rounded-md border border-krypt-border bg-krypt-surface2 px-2.5 py-1 text-[11px] text-krypt-dim transition-colors hover:border-krypt-warn/40 hover:text-krypt-warn"
        >
          <RotateCcw className="h-3 w-3" /> Reset
        </button>
      </div>

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        <SelectField
          label="Direction" value={dir}
          options={[['favorite', 'Favorite-follow'], ['contrarian', 'Contrarian fade']]}
          hint="Buy the favorite, or fade it and buy the cheap side."
          onCommit={(v) => void update({ crypto15mDirectionMode: v as 'favorite' | 'contrarian' })}
        />
        <NumField
          label="Entry window" suffix="min" min={1} max={15} step={1}
          value={num('crypto15mTimeDelayMin', C15_DEFAULTS.timeDelayMin)}
          hint="Only act inside the last N minutes of the 15-min quarter."
          onCommit={(v) => void update({ crypto15mTimeDelayMin: v })}
        />
        <NumField
          label="Favorite ≥" suffix="¢" min={1} max={99} step={1}
          value={Math.round(num('crypto15mEntryThreshold', C15_DEFAULTS.entryThreshold) * 100)}
          hint="The favorite side must be at least this likely to enter."
          onCommit={(v) => void update({ crypto15mEntryThreshold: v / 100 })}
        />
        <NumField
          label="Skip above" suffix="¢" min={1} max={99} step={1}
          value={Math.round(num('crypto15mEntryMax', C15_DEFAULTS.entryMax) * 100)}
          hint="Don't pay more than this — too little room left to profit."
          onCommit={(v) => void update({ crypto15mEntryMax: v / 100 })}
        />
        <NumField
          label="Min move Δ" suffix="%" min={0} max={50} step={0.05}
          value={+(num('crypto15mMinDeltaPct', C15_DEFAULTS.minDeltaPct) * 100).toFixed(2)}
          hint="Required underlying move from the 15-min open (CoinGecko spot). 0 = off."
          onCommit={(v) => void update({ crypto15mMinDeltaPct: v / 100 })}
        />
        <NumField
          label="Stop-loss" suffix="¢" min={0} max={99} step={1}
          value={Math.round(num('crypto15mExitThreshold', C15_DEFAULTS.exitThreshold) * 100)}
          hint="Executor sells if the held side falls to this price. 0 = hold to settlement."
          onCommit={(v) => void update({ crypto15mExitThreshold: v / 100 })}
        />
        <SelectField
          label="Entry style" value={entryStyle}
          options={[['maker', 'Rest at bid (maker)'], ['taker', 'Cross spread (taker)']]}
          hint="Maker rests a limit at the bid: no spread paid, ~zero Kalshi fee, but it may not fill. Taker crosses the ask: always fills, pays spread + the full taker fee."
          onCommit={(v) => void update({ crypto15mEntryStyle: v as 'maker' | 'taker' })}
        />
        {entryStyle === 'maker' ? (
          <NumField
            label="Cancel unfilled" suffix="min left" min={0} max={15} step={0.5}
            value={num('crypto15mMakerCancelMin', C15_DEFAULTS.makerCancelMin)}
            hint="Give up on a resting entry this many minutes before the market closes. 0 = keep it until close."
            onCommit={(v) => void update({ crypto15mMakerCancelMin: v })}
          />
        ) : (
          <NumField
            label="Entry markup" suffix="¢" min={0} max={20} step={1}
            value={Math.round(num('crypto15mEntryDiff', C15_DEFAULTS.entryDiff) * 100)}
            hint="How far through the spread the limit order crosses to get filled."
            onCommit={(v) => void update({ crypto15mEntryDiff: v / 100 })}
          />
        )}
        <NumField
          label="Trade from" suffix="UTC h" min={0} max={24} step={1}
          value={num('crypto15mHoursStartUtc', C15_DEFAULTS.hoursStartUtc)}
          hint="Only enter between these UTC hours (collected data leans positive 00–12 UTC, negative in the US session). Same start/end or 0–24 = always."
          onCommit={(v) => void update({ crypto15mHoursStartUtc: Math.round(v) })}
        />
        <NumField
          label="…until" suffix="UTC h" min={0} max={24} step={1}
          value={num('crypto15mHoursEndUtc', C15_DEFAULTS.hoursEndUtc)}
          hint="End of the UTC entry window. A start later than the end wraps overnight (e.g. 22 → 6)."
          onCommit={(v) => void update({ crypto15mHoursEndUtc: Math.round(v) })}
        />
        <SelectField
          label="Bet size by" value={sizingMode}
          options={[['fixed', 'Fixed contracts'], ['balance_pct', '% of balance']]}
          hint="Buy a fixed number of contracts, or spend a % of your balance each bet."
          onCommit={(v) => void update({ crypto15mSizingMode: v as 'fixed' | 'balance_pct' })}
        />
        {sizingMode === 'balance_pct' ? (
          <NumField
            label="Per bet" suffix="% bal" min={0.1} max={100} step={0.1}
            value={+(num('crypto15mBalancePct', 0.02) * 100).toFixed(2)}
            hint="Spend this % of your balance on each entry (contracts = budget ÷ price)."
            onCommit={(v) => void update({ crypto15mBalancePct: v / 100 })}
          />
        ) : (
          <NumField
            label="Order size" suffix="ct" min={1} max={1000} step={1}
            value={num('crypto15mOrderSize', C15_DEFAULTS.orderSize)}
            hint="Contracts per entry."
            onCommit={(v) => void update({ crypto15mOrderSize: Math.round(v) })}
          />
        )}
        <NumField
          label="Max loss / bet" suffix="% bal" min={0} max={100} step={0.5}
          value={+(num('crypto15mMaxLossPct', 0) * 100).toFixed(2)}
          hint="Never risk more than this % of balance on one bet (it's bought outright, so cost = max loss). 0 = off."
          onCommit={(v) => void update({ crypto15mMaxLossPct: v / 100 })}
        />
        <NumField
          label="Max concurrent" min={1} max={50} step={1}
          value={num('crypto15mMaxConcurrent', C15_DEFAULTS.maxConcurrent)}
          hint="Most open 15-min positions at once (across the 7 assets)."
          onCommit={(v) => void update({ crypto15mMaxConcurrent: Math.round(v) })}
        />
      </div>

      <SizingPreview sizing={sizing} mode={sizingMode} />
      {dir === 'contrarian' && (
        <p className="mt-2 text-[11px] text-krypt-warn/90">
          Contrarian: when a side is an extreme favorite (≥ threshold) the executor buys the CHEAP opposite side — a low-win, high-payoff longshot. Set stop-loss to 0 to hold to settlement.
        </p>
      )}
    </div>
  );
}

function SizingPreview({ sizing, mode }: { sizing: Crypto15mSizing | null; mode: 'fixed' | 'balance_pct' }) {
  if (!sizing) return null;
  const { estContracts, estCostUsd, estPriceCents, balanceUsd, balancePct, maxLossPct, note } = sizing;
  const known = balanceUsd > 0;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-krypt-border bg-krypt-surface2 px-3 py-2 text-[11px]">
      <span className="inline-flex items-center gap-1.5 font-semibold uppercase tracking-wider text-krypt-dim">
        <Wallet className="h-3.5 w-3.5" /> Per bet
      </span>
      <span className="font-mono text-sm text-white">≈ {fmtUsd(estCostUsd)}</span>
      <span className="text-krypt-muted">
        {estContracts} contract{estContracts === 1 ? '' : 's'} @ ~{estPriceCents}¢
      </span>
      {mode === 'balance_pct' && (
        <span className="text-krypt-dim">
          {(balancePct * 100).toFixed(1)}% of {known ? fmtUsd(balanceUsd) : 'balance'}
        </span>
      )}
      {maxLossPct > 0 && (
        <span className="text-krypt-dim">
          max risk {(maxLossPct * 100).toFixed(1)}%{known ? ` · ${fmtUsd(balanceUsd * maxLossPct)}` : ''}
        </span>
      )}
      {known && <span className="ml-auto text-krypt-dim">balance {fmtUsd(balanceUsd)}</span>}
      {note && <span className="w-full text-krypt-warn">{note}</span>}
    </div>
  );
}

function NumField({
  label, value, onCommit, suffix, min, max, step, hint,
}: {
  label: string;
  value: number;
  onCommit: (v: number) => void;
  suffix?: string;
  min: number;
  max: number;
  step: number;
  hint?: string;
}) {
  const [text, setText] = useState(String(value));
  useEffect(() => { setText(String(value)); }, [value]);

  const commit = () => {
    const parsed = Number(text);
    if (Number.isNaN(parsed)) { setText(String(value)); return; }
    const clamped = Math.min(max, Math.max(min, parsed));
    setText(String(clamped));
    if (clamped !== value) onCommit(clamped);
  };

  return (
    <label className="block rounded-lg border border-krypt-border bg-krypt-surface2 px-2.5 py-1.5" title={hint}>
      <div className="flex items-center justify-between text-[9px] uppercase tracking-wider text-krypt-dim">
        <span>{label}</span>
        {suffix && <span className="text-krypt-dim/70">{suffix}</span>}
      </div>
      <input
        type="number"
        inputMode="decimal"
        value={text}
        min={min}
        max={max}
        step={step}
        onChange={(e) => setText(e.target.value)}
        onBlur={commit}
        onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur(); }}
        className="mt-0.5 w-full bg-transparent font-mono text-sm text-white outline-none [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
      />
    </label>
  );
}

function SelectField({
  label, value, options, onCommit, hint,
}: {
  label: string;
  value: string;
  options: [string, string][];
  onCommit: (v: string) => void;
  hint?: string;
}) {
  return (
    <label className="block rounded-lg border border-krypt-border bg-krypt-surface2 px-2.5 py-1.5" title={hint}>
      <div className="text-[9px] uppercase tracking-wider text-krypt-dim">{label}</div>
      <select
        value={value}
        onChange={(e) => onCommit(e.target.value)}
        className="mt-0.5 w-full cursor-pointer bg-transparent font-mono text-sm text-white outline-none"
      >
        {options.map(([v, lbl]) => (
          <option key={v} value={v} className="bg-krypt-surface text-white">{lbl}</option>
        ))}
      </select>
    </label>
  );
}

type CardState = 'signal' | 'window' | 'watching' | 'idle';

function cardState(a: Crypto15mAsset): CardState {
  if (a.signal) return 'signal';
  if (a.inWindow) return 'window';
  if (a.hasMarket) return 'watching';
  return 'idle';
}

function AssetCard({ a }: { a: Crypto15mAsset }) {
  const state = cardState(a);
  const ring =
    state === 'signal'
      ? 'border-krypt-win/60 shadow-[0_0_22px_rgba(34,197,94,0.18)]'
      : state === 'window'
        ? 'border-krypt-warn/50'
        : 'border-krypt-border';

  const upFav = a.favorite === 'up';
  const downFav = a.favorite === 'down';

  return (
    <div className={cls('krypt-card flex flex-col gap-3 border', ring)}>
      <div className="flex items-center gap-2">
        <div className="grid h-8 w-8 place-items-center rounded-lg bg-krypt-surface2 text-krypt-purple">
          <Bitcoin className="h-4 w-4" />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold text-white">{a.asset}</div>
          <div className="font-mono text-[10px] text-krypt-dim">{a.series}</div>
        </div>
        <div className="ml-auto">
          <StatePill state={state} />
        </div>
      </div>

      {a.error ? (
        <div className="rounded-md border border-krypt-loss/30 bg-krypt-loss/5 px-2 py-1.5 text-[11px] text-krypt-loss">
          {a.error}
        </div>
      ) : !a.hasMarket ? (
        <div className="py-2 text-center text-xs text-krypt-dim">No open contract right now.</div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2">
            <SideBox label="UP" prob={a.upProb} fav={upFav} good />
            <SideBox label="DOWN" prob={a.downProb} fav={downFav} />
          </div>
          <div className="flex items-center justify-between text-xs">
            <span className="text-krypt-muted">
              closes in <span className="font-mono text-white">{fmtMins(a.minsLeft)}</span>
            </span>
            <span className="text-krypt-muted">
              entry <span className="font-mono text-white">{pct(a.entryCost)}</span>
            </span>
          </div>
        </>
      )}

      <div className="-mx-5 -mb-5 mt-1 grid grid-cols-3 gap-px border-t border-krypt-border bg-krypt-border/40 text-center text-[11px]">
        <Foot label="Spot" value={fmtSpot(a.spotUsd)} />
        <Foot label="Open" value={fmtSpot(a.open15mUsd)} />
        <Foot label="Δ move" value={fmtDelta(a.deltaUsd)} />
      </div>
    </div>
  );
}

function StatePill({ state }: { state: CardState }) {
  if (state === 'signal') {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-krypt-win/15 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-krypt-win">
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-krypt-win shadow-[0_0_8px_currentColor]" />
        Signal
      </span>
    );
  }
  if (state === 'window') {
    return (
      <span className="rounded-full bg-krypt-warn/15 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-krypt-warn">
        In window
      </span>
    );
  }
  if (state === 'watching') {
    return (
      <span className="rounded-full bg-white/5 px-2 py-0.5 text-[10px] uppercase tracking-wider text-krypt-muted">
        watching
      </span>
    );
  }
  return <span className="text-[10px] uppercase tracking-wider text-krypt-dim">idle</span>;
}

function SideBox({
  label, prob, fav, good,
}: { label: string; prob: number | null; fav: boolean; good?: boolean }) {
  return (
    <div
      className={cls(
        'rounded-lg border px-2 py-1.5 text-center',
        fav
          ? good
            ? 'border-krypt-win/40 bg-krypt-win/10'
            : 'border-krypt-loss/40 bg-krypt-loss/10'
          : 'border-krypt-border bg-krypt-surface2',
      )}
    >
      <div className={cls('text-[10px] uppercase tracking-wider', fav ? (good ? 'text-krypt-win' : 'text-krypt-loss') : 'text-krypt-dim')}>
        {label}{fav ? ' ★' : ''}
      </div>
      <div className="font-mono text-lg text-white">{pct(prob)}</div>
    </div>
  );
}

function Foot({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-krypt-surface px-2 py-2">
      <div className="text-[9px] uppercase tracking-wider text-krypt-dim">{label}</div>
      <div className="mt-0.5 font-mono text-white">{value}</div>
    </div>
  );
}

function PositionsTable({ title, rows }: { title: string; rows: Crypto15mPosition[] }) {
  return (
    <div>
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-[0.16em] text-krypt-muted">{title}</h3>
      <div className="overflow-hidden rounded-xl border border-krypt-border">
        <table className="krypt-table">
          <thead>
            <tr>
              <th>Asset</th>
              <th>Side</th>
              <th>Status</th>
              <th>Contracts</th>
              <th>Entry</th>
              <th>Cost</th>
              <th>P&amp;L</th>
              <th>Mode</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => <PositionRow key={p.id} p={p} />)}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function PositionRow({ p }: { p: Crypto15mPosition }) {
  const entryC = p.avgEntryCents ?? p.entryLimitCents;
  return (
    <tr>
      <td><TickerLink ticker={p.ticker} env={p.kalshiEnv} label={p.asset} /></td>
      <td>
        <span className={cls(
          'rounded-md px-1.5 py-0.5 text-[10px] font-semibold uppercase',
          p.side === 'up' ? 'bg-krypt-win/10 text-krypt-win' : 'bg-krypt-loss/10 text-krypt-loss',
        )}>
          {p.side || p.direction}
        </span>
      </td>
      <td className="text-xs text-krypt-muted">
        {p.status}{p.exitReason === 'stop_loss' ? ' · stop' : ''}
      </td>
      <td className="font-mono text-xs">{p.filledContracts}/{p.targetContracts}</td>
      <td className="font-mono text-xs">{entryC ? `${Math.round(entryC)}¢` : '—'}</td>
      <td className="font-mono text-xs text-krypt-muted">{fmtUsd(p.costUsd)}</td>
      <td className={cls(
        'font-mono text-xs',
        p.pnlUsd === null ? 'text-krypt-dim' : p.pnlUsd >= 0 ? 'text-krypt-win' : 'text-krypt-loss',
      )}>
        {p.pnlUsd === null ? '—' : fmtUsd(p.pnlUsd, { sign: true })}
      </td>
      <td>
        {p.dryRun
          ? <span className="rounded-md bg-krypt-warn/10 px-1.5 py-0.5 text-[10px] uppercase text-krypt-warn">paper</span>
          : <span className="rounded-md bg-krypt-loss/10 px-1.5 py-0.5 text-[10px] uppercase text-krypt-loss">live</span>}
      </td>
    </tr>
  );
}
