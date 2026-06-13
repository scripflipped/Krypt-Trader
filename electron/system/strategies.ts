import type { StrategyPreset, TraderConfig } from '../../shared/types';
import { DEFAULT_CONFIG } from './settings-store';

const merge = (over: Partial<TraderConfig>): TraderConfig => ({
  ...DEFAULT_CONFIG,
  ...over,
});

export const BUILTIN_STRATEGIES: StrategyPreset[] = [
  {
    id: 'krypt-edge',
    name: 'Edge Stack',
    tagline: 'Both backtested edges at once — crypto whales + sports momentum.',
    description:
      "Our recommended pick — the best risk-adjusted edge. Runs the two signal sources that backtested net-POSITIVE after fees, each restricted to where it has an edge — whales in CRYPTO / EXOTICS / ENTERTAINMENT and contrarian momentum in SPORTS (confidence ≥ 40, since momentum scores run low) — with an 85¢ cap that drops the loss-making high-price favorites. Sports Momentum has a higher raw edge, but this diversifies across two independent sources, so it's the most reliable (highest-confidence positive result, less exposed to any one category's luck). In-sample +15.6¢/contract (t=3.2, n=81) vs the unfiltered default's net-NEGATIVE edge. EXPERIMENTAL / in-sample — paper-trade first to confirm it holds forward.",
    riskLabel: 'experimental',
    badge: 'recommended',
    backtest: { netCents: 15.6, t: 3.2, n: 81 },
    config: merge({
      tradeWhales: true,
      tradeMomentum: true,
      contrarianOnly: true,
      allowedCategories: null,
      allowedWhaleCategories: ['crypto', 'exotics', 'entertainment'],
      allowedMomentumCategories: ['sports'],
      allowedMomentumSignalTypes: ['trade_cluster'],
      minConfidenceWhale: 55.0,
      minEdgePtsWhale: 5.0,
      minConfidenceMomentum: 40.0,
      minEntryPriceCents: 15,
      maxEntryPriceCents: 85,
    }),
  },
  {
    id: 'krypt-sports-momentum',
    name: 'Sports Momentum',
    tagline: 'Contrarian trade-clusters, sports only.',
    description:
      "Highest raw edge, but noisier (single category, smaller sample). Contrarian momentum in SPORTS backtested strongly positive net-of-fee while news/world momentum lost. Fixed from the old preset: confidence ≥ 40 (the old 50 gate cut the edge to noise — momentum scores top out near 60) and a wider 15-70¢ band. In-sample +18.2¢/contract (t=2.2, n=37). EXPERIMENTAL / in-sample — paper-trade to confirm.",
    riskLabel: 'experimental',
    badge: 'new',
    backtest: { netCents: 18.2, t: 2.2, n: 37 },
    config: merge({
      tradeWhales: false,
      tradeMomentum: true,
      contrarianOnly: true,
      allowedCategories: ['sports'],
      allowedMomentumSignalTypes: ['trade_cluster'],
      minConfidenceMomentum: 40.0,
      minEntryPriceCents: 15,
      maxEntryPriceCents: 70,
    }),
  },
  {
    id: 'krypt-crypto-whale',
    name: 'Crypto Whale',
    tagline: 'Whale-following, crypto markets only.',
    description:
      "Most reliable edge (highest t-stat, 97% win). Whale signals in CRYPTO backtested strongly positive net-of-fee while sports whales lost. Fixed from the old preset: the entry cap is raised to 98¢ because crypto whales follow high-price favorites — the old 85¢ cap was throwing away most of its own edge. In-sample +9.3¢/contract (t=3.5, n=36). EXPERIMENTAL / in-sample on a small sample — paper-trade to confirm.",
    riskLabel: 'experimental',
    badge: 'new',
    backtest: { netCents: 9.3, t: 3.5, n: 36 },
    config: merge({
      tradeWhales: true,
      tradeMomentum: false,
      allowedCategories: ['crypto'],
      minConfidenceWhale: 55.0,
      minEdgePtsWhale: 5.0,
      minEntryPriceCents: 15,
      maxEntryPriceCents: 98,
    }),
  },
  {
    id: 'krypt-momentum-only',
    name: 'Crowd Contrarian',
    tagline: 'Mean-reversion on trade clusters. No whale signals.',
    description:
      'Fades clusters of trades against the underdog across ALL categories. Roughly break-even after fees in the data — the sports slice carries it while news/world drags. If you want the momentum edge, "Sports Momentum" isolates the winning part. Disables whale-following entirely.',
    riskLabel: 'balanced',
    backtest: { netCents: -0.1, t: 0.0, n: 40, approx: true },
    config: merge({
      tradeWhales: false,
      tradeMomentum: true,
      contrarianOnly: true,
      minEdgePtsMomentum: 7.0,
      minConfidenceMomentum: 50.0,
      allowedMomentumSignalTypes: ['trade_cluster'],
    }),
  },
  {
    id: 'krypt-conservative',
    name: 'Krypt Conservative',
    tagline: 'Tight sizing, high-edge only, capital-preservation mode.',
    description:
      'Only trades signals with edge ≥ 8pts and confidence ≥ 65%. Smaller sizing (1-3% of bankroll), $25 hard cap. Daily stop-loss at -$25. Trades every category, so net-negative after fees in the data despite the tight gates — capital-preservation, not edge.',
    riskLabel: 'safe',
    backtest: { netCents: -1.1, t: -0.8, n: 838, approx: true },
    config: merge({
      minEdgePtsWhale: 8.0,
      minEdgePtsMomentum: 8.0,
      minConfidenceWhale: 65.0,
      minConfidenceMomentum: 65.0,
      baseSizeFraction: 0.015,
      minSizeFraction: 0.01,
      maxSizeFraction: 0.03,
      hardMaxPositionUsd: 25.0,
      maxOpenPositions: 10,
      maxDailyNewPositions: 15,
      stopLossOnDay: -25.0,
      maxTotalExposureFraction: 0.5,
    }),
  },
  {
    id: 'krypt-aggressive',
    name: 'Krypt Aggressive',
    tagline: 'More signals, larger sizing, higher variance.',
    description:
      'Loosens edge gates to 3pts and confidence to 50%. Sizing scales 4-10% of bankroll, $100 cap. Higher max-open count. Trades every category — net-negative after fees in the data. Use only with a bankroll you can stand to drop 30% on a bad day.',
    riskLabel: 'aggressive',
    backtest: { netCents: -1.2, t: -1.0, n: 1330, approx: true },
    config: merge({
      minEdgePtsWhale: 3.0,
      minEdgePtsMomentum: 3.0,
      minConfidenceWhale: 50.0,
      minConfidenceMomentum: 50.0,
      baseSizeFraction: 0.06,
      minSizeFraction: 0.04,
      maxSizeFraction: 0.1,
      hardMaxPositionUsd: 100.0,
      maxOpenPositions: 40,
      maxDailyNewPositions: 80,
      maxTotalExposureFraction: 0.85,
      stopLossOnDay: -100.0,
    }),
  },
  {
    id: 'krypt-whale-only',
    name: 'Whale Hunter',
    tagline: 'Follows large taker orders. No momentum signals.',
    description:
      'Pure whale-following across ALL categories. Disables momentum and only trades when a $2.5k+ taker order hits a market with a scored edge ≥ 5pts. Net-negative after fees in the data (sports whales lose) — "Crypto Whale" isolates the winning slice.',
    riskLabel: 'balanced',
    backtest: { netCents: -1.4, t: -1.1, n: 1155, approx: true },
    config: merge({
      tradeWhales: true,
      tradeMomentum: false,
      minEdgePtsWhale: 5.0,
      minConfidenceWhale: 55.0,
    }),
  },
  {
    id: 'krypt-balanced',
    name: 'Krypt Balanced',
    tagline: 'Whales + momentum, both gates active.',
    description:
      'The original everyday config: both whale and trade-cluster momentum signals, edge ≥ 5pts, confidence ≥ 55%, every category, 2-6% sizing, $50 cap. Backtests net-NEGATIVE after fees on your data because it trades the losing categories too — kept as a neutral baseline. For a positive backtested edge use Edge Stack.',
    riskLabel: 'balanced',
    backtest: { netCents: -1.5, t: -1.1, n: 1171, approx: true },
    config: merge({}),
  },
  {
    id: 'krypt-paper',
    name: 'Paper Trade',
    tagline: 'Dry-run everything. Test signals without risk.',
    description:
      'Balanced signal gates with DRY-RUN on, so no real orders are placed. Use it to sanity-check ANY config for a few days before going live — apply a strategy, then switch dry-run on here. (Same gates as Balanced, so the same backtested edge.)',
    riskLabel: 'safe',
    backtest: { netCents: -1.5, t: -1.1, n: 1171, approx: true },
    config: merge({
      dryRun: true,
      enableTrading: true,
    }),
  },
  {
    id: 'krypt-edge-hunter',
    name: 'Edge Hunter',
    tagline: 'Top-decile edge only. Few but high-quality trades.',
    description:
      'Only fires on signals with edge ≥ 12pts, every category. Sizes more aggressively on high-edge picks. Long quiet periods between trades. Net-negative after fees in the data — a high edge-score does not survive the fee once you trade every category.',
    riskLabel: 'balanced',
    backtest: { netCents: -1.8, t: -1.3, n: 1026, approx: true },
    config: merge({
      minEdgePtsWhale: 12.0,
      minEdgePtsMomentum: 12.0,
      minConfidenceWhale: 60.0,
      minConfidenceMomentum: 55.0,
      baseSizeFraction: 0.04,
      minSizeFraction: 0.04,
      maxSizeFraction: 0.08,
      sizingBaseEdge: 12.0,
      sizingMaxEdge: 25.0,
      maxOpenPositions: 15,
    }),
  },
  {
    id: 'krypt-experimental',
    name: 'Convergence Hunter',
    tagline: 'Trades only when 3+ whales agree on the same side.',
    description:
      'Coming soon. Will trade when convergence is detected — 3+ whales taking the same side of the same market within 2 hours. The convergence scanner is still in development, so this preset cannot be applied yet (and has no backtest).',
    riskLabel: 'experimental',
    badge: 'soon',
    comingSoon: true,
    backtest: null,
    config: merge({
      tradeWhales: false,
      tradeMomentum: false,
      tradeConvergence: true,
      minEdgePtsWhale: 6.0,
      minConfidenceWhale: 60.0,
      maxOpenPositions: 12,
    }),
  },
];

export function listStrategies(): StrategyPreset[] {
  return BUILTIN_STRATEGIES;
}

export function findStrategy(id: string): StrategyPreset | undefined {
  return BUILTIN_STRATEGIES.find((s) => s.id === id);
}
