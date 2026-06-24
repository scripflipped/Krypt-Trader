import type { AccountSnapshot, TraderConfig } from '@shared/types';
import type { PageId } from '../App';
import { fmtPct, fmtUsd } from './format';

export interface TradeWarning {
  id: string;
  /** 'block' = this config/balance can NEVER place a trade. 'warn' = degraded but can still trade. */
  severity: 'block' | 'warn';
  message: string;
  page?: PageId;
  fixLabel?: string;
}

// Mirror of the two hard floors in the Python trader (trader.py):
//   - run_trade_cycle aborts the whole cycle when balance < $5
//   - execute_signal skips any order whose sized target is < $1
const MIN_ORDER_USD = 1;
const MIN_CYCLE_BALANCE_USD = 5;

const isEmptyArr = (a: unknown): boolean => Array.isArray(a) && a.length === 0;

/**
 * Catch configurations/balances that would silently never trade, so the UI can
 * warn the user instead of leaving them staring at a quiet bot. Conservative:
 * only flags states we're sure about (empty whitelists, inverted ranges, the
 * balance × sizing < $1 dead zone), never guesses.
 */
export function computeTradeWarnings(
  config: TraderConfig | null,
  account: AccountSnapshot | null,
): TradeWarning[] {
  if (!config) return [];
  const out: TradeWarning[] = [];
  const toSettings = { page: 'settings' as PageId, fixLabel: 'Open Settings' };

  // ── Signal sources / whitelists that can never pass ───────────────────────
  if (!config.tradeWhales && !config.tradeMomentum && !config.tradeConvergence) {
    out.push({ id: 'no-sources', severity: 'block', ...toSettings,
      message: 'No signal sources are on — turn on Whales or Momentum, or nothing can ever trade.' });
  }
  if (isEmptyArr(config.allowedCategories)) {
    out.push({ id: 'no-categories', severity: 'block', ...toSettings,
      message: 'No categories are enabled — every signal gets filtered out. Enable at least one category.' });
  }
  if (config.tradeWhales && isEmptyArr(config.allowedWhaleCategories)) {
    out.push({ id: 'no-whale-cats', severity: 'block', ...toSettings,
      message: 'Whale trading is on but its category list is empty — no whale signal can pass.' });
  }
  if (config.tradeMomentum && isEmptyArr(config.allowedMomentumCategories)) {
    out.push({ id: 'no-mom-cats', severity: 'block', ...toSettings,
      message: 'Momentum is on but its category list is empty — no momentum signal can pass.' });
  }
  if (config.tradeMomentum && isEmptyArr(config.allowedMomentumSignalTypes)) {
    out.push({ id: 'no-mom-types', severity: 'block', ...toSettings,
      message: 'Momentum is on but no signal types are allowed — momentum can never trade.' });
  }

  // ── Inverted ranges ───────────────────────────────────────────────────────
  if (config.minEntryPriceCents > config.maxEntryPriceCents) {
    out.push({ id: 'price-band', severity: 'block', ...toSettings,
      message: `Entry-price band is inverted (min ${config.minEntryPriceCents}¢ > max ${config.maxEntryPriceCents}¢) — no order can price inside it.` });
  }
  const c15thr = config.crypto15mEntryThreshold;
  const c15max = config.crypto15mEntryMax;
  if (config.crypto15mEnabled && c15thr != null && c15max != null && c15thr > c15max) {
    out.push({ id: 'c15-window', severity: 'block', page: 'crypto15m', fixLabel: 'Open 15m',
      message: `15m entry is impossible: the favorite must be ≥ ${Math.round(c15thr * 100)}¢ yet cost ≤ ${Math.round(c15max * 100)}¢. Raise "Entry max" to at least the threshold.` });
  }

  // ── Balance vs sizing dead zone (only when actually trading) ──────────────
  const isFixed = config.sizingMode === 'fixed';
  if (config.enableTrading) {
    // Fixed-$ sizing below the $1 floor can never place, regardless of balance.
    if (isFixed && config.fixedTradeUsd < MIN_ORDER_USD) {
      out.push({ id: 'fixed-too-small', severity: 'block', ...toSettings,
        message: `Fixed trade size ${fmtUsd(config.fixedTradeUsd)} is below the ${fmtUsd(MIN_ORDER_USD)} minimum order — nothing will place. Raise it to at least ${fmtUsd(MIN_ORDER_USD)}.` });
    }
    const bal = account?.cashUsd ?? null;
    if (bal != null) {
      if (bal < MIN_CYCLE_BALANCE_USD) {
        out.push({ id: 'bal-below-cycle', severity: 'block', ...toSettings,
          message: `Balance ${fmtUsd(bal)} is below the ${fmtUsd(MIN_CYCLE_BALANCE_USD)} minimum — the bot skips every cycle. Add funds to your Kalshi account.` });
      } else if (isFixed) {
        if (config.fixedTradeUsd > bal) {
          out.push({ id: 'fixed-over-balance', severity: 'warn', ...toSettings,
            message: `Fixed trade size ${fmtUsd(config.fixedTradeUsd)} is more than your ${fmtUsd(bal)} balance — most trades will be capped or skipped.` });
        }
      } else if (bal * config.maxSizeFraction < MIN_ORDER_USD) {
        const needPct = Math.ceil((MIN_ORDER_USD / bal) * 100);
        out.push({ id: 'sizing-never', severity: 'block', ...toSettings,
          message: `At your sizing (≤${fmtPct(config.maxSizeFraction * 100, 0)}), no trade on ${fmtUsd(bal)} reaches the ${fmtUsd(MIN_ORDER_USD)} minimum order — nothing will place. Raise sizing to ~${needPct}%+ or add funds.` });
      } else if (bal * config.minSizeFraction < MIN_ORDER_USD) {
        out.push({ id: 'sizing-weak', severity: 'warn', ...toSettings,
          message: `Low-edge trades won't place on ${fmtUsd(bal)} — they'd size under the ${fmtUsd(MIN_ORDER_USD)} minimum. Only stronger-edge signals will trade until you raise sizing or add funds.` });
      }
    }
  }

  return out;
}
