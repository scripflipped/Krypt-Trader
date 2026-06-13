import { useState } from 'react';
import { Check, ChevronRight, Sparkles } from 'lucide-react';
import { useApp } from '../state/AppStateProvider';
import { useToast } from '../state/ToastProvider';
import { Page } from '../components/common';
import { cls, fmtPct, fmtUsd } from '../utils/format';
import type { StrategyPreset } from '@shared/types';

function rankScore(b?: StrategyPreset['backtest'] | null): number {
  if (!b) return -Infinity;
  if (b.t <= 0) return b.netCents - Math.abs(b.netCents);
  return b.netCents - Math.abs(b.netCents) / b.t;
}

export function StrategiesPage() {
  const { strategies, state, refresh } = useApp();
  const toast = useToast();
  const [busyId, setBusyId] = useState<string | null>(null);

  const apply = async (s: StrategyPreset): Promise<void> => {
    if (s.comingSoon) return;
    setBusyId(s.id);
    try {
      await window.krypt.config.applyStrategy(s.id);
      await refresh.state();
      toast.success(`Applied "${s.name}"`);
    } catch (e: any) {
      toast.error(`Could not apply: ${e?.message || e}`);
    } finally {
      setBusyId(null);
    }
  };

  const activeId = state?.activeProfileId ?? null;

  const ranked = [...strategies].sort((a, b) => rankScore(b.backtest) - rankScore(a.backtest));

  return (
    <Page
      title="Strategies"
      subtitle="Ranked by risk-adjusted, in-sample backtest of your own resolved signals. These are experimental heuristics — none has a proven forward edge, so paper-trade the top pick first. Apply one, then tweak in Settings or save as a profile."
    >
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {ranked.map((s, i) => {
          const active = activeId === s.id;
          const comingSoon = !!s.comingSoon;
          const rank = s.backtest ? i + 1 : null;
          return (
            <div
              key={s.id}
              className={cls(
                'group relative flex flex-col overflow-hidden rounded-xl border bg-krypt-surface p-5 transition-colors',
                comingSoon
                  ? 'border-krypt-border opacity-60'
                  : active
                    ? 'border-krypt-purple shadow-krypt-soft'
                    : 'border-krypt-border hover:border-krypt-borderHi',
              )}
            >
              {s.badge && (
                <span className={cls(
                  'absolute right-3 top-3 rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wider',
                  s.badge === 'recommended' && 'bg-krypt-glow text-white shadow-krypt-soft',
                  s.badge === 'new' && 'border border-krypt-pink/40 bg-krypt-pink/10 text-krypt-pink',
                  s.badge === 'soon' && 'border border-krypt-border bg-krypt-surface2 text-krypt-muted',
                )}>
                  {s.badge}
                </span>
              )}
              <div className="flex items-center gap-3">
                <div className={cls(
                  'grid h-9 w-9 place-items-center rounded-lg',
                  s.riskLabel === 'safe' && 'bg-krypt-win/10 text-krypt-win',
                  s.riskLabel === 'balanced' && 'bg-krypt-purple/15 text-krypt-purple',
                  s.riskLabel === 'aggressive' && 'bg-krypt-loss/10 text-krypt-loss',
                  s.riskLabel === 'experimental' && 'bg-krypt-warn/10 text-krypt-warn',
                )}>
                  <Sparkles className="h-4 w-4" />
                </div>
                <div>
                  <div className="text-sm font-semibold text-white">{s.name}</div>
                  <div className="text-[11px] uppercase tracking-wider text-krypt-muted">
                    {s.riskLabel}
                  </div>
                </div>
              </div>

              <p className="mt-3 text-xs italic text-krypt-purple/80">{s.tagline}</p>
              <p className="mt-2 flex-1 text-xs leading-relaxed text-krypt-muted">
                {s.description}
              </p>

              {s.backtest && (
                <div className={cls(
                  'mt-3 flex items-center gap-3 rounded-lg border px-3 py-2',
                  s.backtest.netCents > 0.05
                    ? 'border-krypt-win/30 bg-krypt-win/10'
                    : s.backtest.netCents < -0.05
                      ? 'border-krypt-loss/25 bg-krypt-loss/5'
                      : 'border-krypt-border bg-krypt-surface2',
                )}>
                  <span className={cls(
                    'grid h-6 w-6 shrink-0 place-items-center rounded-full text-[11px] font-bold',
                    rank === 1
                      ? 'bg-krypt-glow text-white shadow-krypt-soft'
                      : 'bg-krypt-surface2 text-krypt-muted',
                  )}>
                    {rank}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="text-[9px] uppercase tracking-wider text-krypt-dim">
                      Backtested edge
                    </div>
                    <div className="flex items-baseline gap-2">
                      <span className={cls(
                        'font-mono text-sm font-semibold',
                        s.backtest.netCents > 0.05
                          ? 'text-krypt-win'
                          : s.backtest.netCents < -0.05
                            ? 'text-krypt-loss'
                            : 'text-krypt-muted',
                      )}>
                        {s.backtest.netCents >= 0 ? '+' : ''}{s.backtest.netCents.toFixed(1)}¢/contract
                      </span>
                      <span className="truncate text-[10px] text-krypt-dim">
                        t&nbsp;{s.backtest.t >= 0 ? '+' : ''}{s.backtest.t.toFixed(1)} · n&nbsp;{s.backtest.n}
                        {Math.abs(s.backtest.t) >= 2 && s.backtest.n >= 30 ? ' · sig' : ''}
                        {s.backtest.approx ? ' · ≈' : ''}
                      </span>
                    </div>
                  </div>
                </div>
              )}

              <div className="mt-3 grid grid-cols-3 gap-2 text-[11px]">
                <Stat label="Edge ≥" value={`${s.config.minEdgePtsWhale}pt`} />
                <Stat label="Conf ≥" value={`${s.config.minConfidenceWhale.toFixed(0)}%`} />
                <Stat label="Cap" value={fmtUsd(s.config.hardMaxPositionUsd)} />
                <Stat label="Sizing" value={`${fmtPct(s.config.minSizeFraction * 100, 0)}–${fmtPct(s.config.maxSizeFraction * 100, 0)}`} />
                <Stat label="Max open" value={`${s.config.maxOpenPositions}`} />
                <Stat label="Daily" value={`${s.config.maxDailyNewPositions}`} />
              </div>

              <button
                onClick={() => apply(s)}
                disabled={busyId === s.id || comingSoon}
                title={comingSoon ? 'This strategy is not available yet' : undefined}
                className={cls(
                  active ? 'krypt-btn-default' : 'krypt-btn-primary',
                  'mt-4 w-full',
                  comingSoon && 'cursor-not-allowed',
                )}
              >
                {comingSoon ? (
                  'Coming soon'
                ) : active ? (
                  <>
                    <Check className="h-4 w-4" /> Active
                  </>
                ) : (
                  <>
                    Apply <ChevronRight className="h-4 w-4" />
                  </>
                )}
              </button>
            </div>
          );
        })}
      </div>

      <p className="mt-5 max-w-3xl text-[11px] leading-relaxed text-krypt-dim">
        <span className="font-semibold text-krypt-muted">How the ranking works:</span>{' '}
        each preset's gates (source, confidence, category, entry-price) are
        replayed against your own resolved signals and scored net of an
        estimated Kalshi fee. The chip shows mean net{' '}
        <span className="font-mono">¢/contract</span>, the t-stat{' '}
        <span className="font-mono">t</span> (≥&nbsp;2 ≈ a real edge, not
        noise), and sample size <span className="font-mono">n</span>. Cards are
        ordered by the <em>best risk-adjusted in-sample result</em> — a
        risk-adjusted edge (net minus one standard error), <strong>not</strong>{' '}
        the biggest raw number — so a steadier edge can outrank a larger but
        noisier one (Edge Stack ranks above Sports Momentum even though Sports
        has a higher ¢, because its smaller n / lower t make it less reliable).{' '}
        <span className="font-mono">≈</span> marks presets whose edge-point gate
        can't be replayed, so their number ignores it. All figures are{' '}
        <em>in-sample</em> on a small history — run the top pick under{' '}
        <span className="font-semibold">Paper Trade</span> before risking real
        money.
      </p>
    </Page>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border border-krypt-border bg-krypt-surface2 px-2 py-1">
      <div className="text-[9px] uppercase tracking-wider text-krypt-dim">{label}</div>
      <div className="font-mono text-[11px] text-white">{value}</div>
    </div>
  );
}
