
export type KalshiEnv = 'demo' | 'production';

export type OrderStyle = 'limit_cross' | 'limit_mid' | 'market';

export type SignalSource = 'whale' | 'momentum' | 'convergence' | 'external';


export interface TraderConfig {
  kalshiEnv: KalshiEnv;
  dryRun: boolean;
  enableTrading: boolean;

  tradeWhales: boolean;
  tradeMomentum: boolean;
  tradeConvergence: boolean;

  minEdgePtsWhale: number;
  minEdgePtsMomentum: number;
  minConfidenceWhale: number;
  minConfidenceMomentum: number;
  minEntryPriceCents: number;
  maxEntryPriceCents: number;
  allowedMomentumSignalTypes: string[];
  allowedCategories: string[] | null;
  allowedWhaleCategories: string[] | null;
  allowedMomentumCategories: string[] | null;
  contrarianOnly: boolean;

  baseSizeFraction: number;
  minSizeFraction: number;
  maxSizeFraction: number;
  sizingBaseEdge: number;
  sizingMaxEdge: number;
  hardMaxPositionUsd: number;
  minCashReserveFraction: number;

  orderStyle: OrderStyle;
  crossSpreadFallbackOffset: number;
  orderExpirationSec: number | null;

  maxOpenPositions: number;
  maxPositionsPerEvent: number;
  maxDailyNewPositions: number;
  unlimitedDailyNewPositions: boolean;
  maxTotalExposureFraction: number;

  tradeScanInterval: number;
  positionPollInterval: number;
  balancePollInterval: number;
  resolutionCheckInterval: number;
  whaleScanInterval: number;
  momentumScanInterval: number;
  marketRefreshInterval: number;

  maxSignalAgeSec: number;

  startBankrollUsd: number;
  stopLossOnDay: number;
  takeProfitOnDay: number;

  tradingHoursEnabled: boolean;
  tradingHoursStart: string;
  tradingHoursEnd: string;
  tradingDays: string[];
  tradingTimezoneOffsetMin: number;

  minWhaleUsd: number;
  minWhaleConfidence: number;
  minWhaleEdge: number;
  minMomentumConfidence: number;
  minMomentumEdge: number;
  minEntryPriceFrac: number;

  eventWebhookUrl: string;
  statsWebhookUrl: string;
  whaleWebhookUrl: string;
  momentumWebhookUrl: string;
  statsPushInterval: number;
  statsChartWindowHours: number;
  enableDiscord: boolean;

  crypto15mEnabled?: boolean;
  crypto15mLive?: boolean;
  crypto15mSizingMode?: 'fixed' | 'balance_pct';
  crypto15mOrderSize?: number;
  crypto15mBalancePct?: number;
  crypto15mMaxLossPct?: number;
  crypto15mMaxConcurrent?: number;
  crypto15mDirectionMode?: 'favorite' | 'contrarian';
  crypto15mTimeDelayMin?: number;
  crypto15mEntryThreshold?: number;
  crypto15mEntryMax?: number;
  crypto15mExitThreshold?: number;
  crypto15mMinDeltaPct?: number;
  crypto15mEntryDiff?: number;
  crypto15mEntryStyle?: 'maker' | 'taker';
  crypto15mMakerCancelMin?: number;
  crypto15mHoursStartUtc?: number;
  crypto15mHoursEndUtc?: number;
  crypto15mRecordSignals?: boolean;
}

export interface CredentialsState {
  env?: 'demo' | 'production';
  hasApiKey: boolean;
  hasRsaKey: boolean;
  apiKeyPreview: string;
  fingerprint: string;
}

export interface CredentialsStatusAll {
  current: 'demo' | 'production';
  demo: CredentialsState;
  production: CredentialsState;
}

export interface CredentialsInput {
  apiKey: string;
  rsaPem: string;
  env?: 'demo' | 'production';
}


export interface Profile {
  id: string;
  name: string;
  description?: string;
  createdAt: string;
  updatedAt: string;
  config: TraderConfig;
  builtin?: boolean;
}


export interface AppState {
  config: TraderConfig;
  activeProfileId: string | null;
  customProfiles: Profile[];
  startMinimized: boolean;
  startWithWindows: boolean;
  enableDiscordRpc: boolean;
  acceptedDisclaimer: boolean;
  windowBounds: { x: number; y: number; width: number; height: number } | null;
}


export type BackendStatus =
  | 'stopped'
  | 'starting'
  | 'running'
  | 'restarting'
  | 'crashed';

export interface BackendInfo {
  status: BackendStatus;
  pid: number | null;
  startedAt: string | null;
  lastError: string | null;
  pythonOk: boolean;
  authOk: boolean;
}

export interface AccountSnapshot {
  cashUsd: number;
  portfolioUsd: number;
  totalUsd: number;
  startBankrollUsd: number;
  bankrollSource?: 'user' | 'auto' | 'live';
  roiPct: number;
  realizedPnlUsd: number;
  todayPnlUsd?: number;
  alltimePnlUsd?: number;
  todayBaselineUsd?: number | null;
  alltimeBaselineUsd?: number | null;
  todayWins?: number;
  todayLosses?: number;
  unrealizedPnlUsd: number;
  openCostUsd: number;
  feesUsd: number;
  wins: number;
  losses: number;
  winRate: number;
  pendingCount: number;
  openCount: number;
  resolvedCount: number;
  totalOpened: number;
  byEnv: { demo: AccountByEnv; production: AccountByEnv };
  sessionPnlUsd?: number;
  sessionRoiPct?: number;
  sessionBaselineUsd?: number;
  sessionStartedAt?: string;
  sessionRunId?: number;
}

export interface BotRun {
  id: number;
  kalshiEnv: KalshiEnv;
  startedAt: string;
  endedAt: string | null;
  startCashUsd: number;
  startPortfolioUsd: number;
  startTotalUsd: number;
  endCashUsd: number | null;
  endPortfolioUsd: number | null;
  endTotalUsd: number | null;
  pnlUsd: number;
  tradesOpened: number;
  tradesWon: number;
  tradesLost: number;
  isActive: boolean;
}

export interface BotRunsResponse {
  runs: BotRun[];
  activeRunId: number;
  activeRun: BotRun | null;
}

export interface AccountByEnv {
  wins: number;
  losses: number;
  realizedPnl: number;
}

export interface PnlPoint {
  at: string;
  cashUsd: number;
  portfolioUsd: number;
  totalUsd: number;
  realizedPnlUsd: number;
  openPositions: number;
}

export interface BotPosition {
  id: number;
  signalSource: SignalSource;
  signalId: number;
  ticker: string;
  eventTicker: string;
  title: string;
  category: string;
  direction: 'yes' | 'no';
  action: 'buy' | 'sell';
  targetContracts: number;
  limitPriceCents: number;
  filledContracts: number;
  avgFillPriceCents: number | null;
  costUsd: number;
  feesUsd: number;
  clientOrderId: string;
  kalshiOrderId: string | null;
  status:
    | 'submitted'
    | 'partial'
    | 'filled'
    | 'canceled'
    | 'expired'
    | 'gone'
    | 'error'
    | 'dry_run';
  confidence: number;
  edgePts: number;
  signalPriceCents: number;
  resolved: boolean;
  outcomeCorrect: number | null;
  settlementUsd: number | null;
  pnlUsd: number | null;
  balanceBeforeUsd: number | null;
  kalshiEnv: KalshiEnv;
  createdAt: string;
  lastUpdated: string;
  resolvedAt: string | null;
  error: string | null;
}

export interface SignalRow {
  id: number;
  source: SignalSource;
  ticker: string;
  eventTicker: string;
  title: string;
  category: string;
  direction: 'yes' | 'no';
  priceCents: number;
  confidence: number;
  edgePts: number;
  signalType?: string;
  dollarValue?: number;
  createdAt: string;
  resolved: boolean;
  outcomeCorrect: number | null;
  pnlEstimate: number | null;
  traded: boolean;
}

export interface ScannerStats {
  whales: { total: number; sent: number; resolved: number; winRate: number };
  momentum: { total: number; sent: number; resolved: number; winRate: number };
  marketsTracked: number;
  lastWhaleScanAt: string | null;
  lastMomentumScanAt: string | null;
  lastTradeScanAt: string | null;
}

export interface LogEntry {
  ts: string;
  level: 'DEBUG' | 'INFO' | 'WARN' | 'ERROR' | 'CRITICAL';
  source: 'main' | 'backend' | 'trader' | 'whale' | 'momentum' | 'discord';
  msg: string;
}

export interface ActionResult<T = void> {
  ok: boolean;
  message?: string;
  data?: T;
}


export interface StrategyPreset {
  id: string;
  name: string;
  tagline: string;
  description: string;
  riskLabel: 'safe' | 'balanced' | 'aggressive' | 'experimental';
  badge?: 'recommended' | 'new' | 'soon' | null;
  comingSoon?: boolean;
  backtest?: {
    netCents: number;
    t: number;
    n: number;
    approx?: boolean;
  } | null;
  config: TraderConfig;
}


export interface Crypto15mConstants {
  timeDelayMin: number;
  entryThreshold: number;
  exitThreshold: number;
  entryMax: number;
  minDeltaPct?: number;
  entryDiff: number;
  directionMode?: 'favorite' | 'contrarian';
  entryStyle?: 'maker' | 'taker';
  hoursStartUtc?: number;
  hoursEndUtc?: number;
}

export interface Crypto15mAsset {
  asset: string;
  series: string;
  spotUsd: number | null;
  open15mUsd: number | null;
  deltaUsd: number | null;
  deltaPct?: number | null;
  hasMarket: boolean;
  ticker: string | null;
  closeTime: string | null;
  minsLeft: number | null;
  upProb: number | null;
  downProb: number | null;
  favorite: 'up' | 'down' | null;
  favoritePrice: number | null;
  entryCost: number | null;
  yesBid?: number | null;
  yesAsk?: number | null;
  inWindow: boolean;
  signal: boolean;
  openMarketCount: number;
  error: string | null;
}

export interface Crypto15mSnapshot {
  fetchedAt: string;
  spotOk: boolean;
  spotSource: string;
  hoursOk?: boolean;
  constants: Crypto15mConstants;
  assets: Crypto15mAsset[];
}

export type Crypto15mStatusName =
  | 'dry_run' | 'submitted' | 'filled' | 'exiting'
  | 'exited' | 'settled' | 'canceled' | 'error';

export interface Crypto15mPosition {
  id: number;
  asset: string;
  series: string;
  ticker: string;
  side: 'up' | 'down' | '';
  direction: 'yes' | 'no' | '';
  targetContracts: number;
  filledContracts: number;
  entryLimitCents: number;
  avgEntryCents: number | null;
  costUsd: number;
  status: Crypto15mStatusName | string;
  exitReason: string | null;
  exitLimitCents: number | null;
  proceedsUsd: number | null;
  confidence: number;
  entryDeltaUsd: number | null;
  outcomeCorrect: number | null;
  settlementUsd: number | null;
  pnlUsd: number | null;
  resolved: boolean;
  dryRun: boolean;
  closeTime: string;
  kalshiEnv: KalshiEnv;
  createdAt: string;
  resolvedAt: string | null;
  error: string | null;
}

export interface Crypto15mStats {
  openCount: number;
  wins: number;
  losses: number;
  realizedPnlUsd: number;
  total: number;
}

export interface Crypto15mSizing {
  mode: 'fixed' | 'balance_pct';
  balancePct: number;
  maxLossPct: number;
  balanceUsd: number;
  estPriceCents: number;
  estContracts: number;
  estCostUsd: number;
  note: string;
}

export interface Crypto15mStatus {
  enabled: boolean;
  live: boolean;
  liveArmed: boolean;
  liveSupported: boolean;
  authed: boolean;
  orderSize: number;
  maxConcurrent: number;
  sizing: Crypto15mSizing;
  env: KalshiEnv;
  stats: Crypto15mStats;
  open: Crypto15mPosition[];
  recent: Crypto15mPosition[];
}


export interface KryptApi {
  app: {
    version: () => Promise<string>;
    openExternal: (url: string) => Promise<void>;
    showItemInFolder: (filePath: string) => Promise<void>;
    getUserDataPath: () => Promise<string>;
    factoryReset: () => Promise<ActionResult<{ deleted: Record<string, number> }>>;
    onDataReset: (cb: (payload: unknown) => void) => () => void;
  };
  state: {
    get: () => Promise<AppState>;
    onChange: (cb: (state: AppState) => void) => () => void;
    setStartMinimized: (v: boolean) => Promise<ActionResult>;
    setStartWithWindows: (v: boolean) => Promise<ActionResult>;
    setEnableDiscordRpc: (v: boolean) => Promise<ActionResult>;
    acceptDisclaimer: () => Promise<ActionResult>;
  };
  config: {
    get: () => Promise<TraderConfig>;
    update: (patch: Partial<TraderConfig>) => Promise<TraderConfig>;
    replace: (config: TraderConfig) => Promise<TraderConfig>;
    reset: () => Promise<TraderConfig>;
    listStrategies: () => Promise<StrategyPreset[]>;
    applyStrategy: (id: string) => Promise<TraderConfig>;
  };
  profiles: {
    list: () => Promise<Profile[]>;
    save: (name: string, description?: string) => Promise<ActionResult<Profile>>;
    apply: (id: string) => Promise<ActionResult<TraderConfig>>;
    rename: (id: string, name: string) => Promise<ActionResult>;
    delete: (id: string) => Promise<ActionResult>;
    duplicate: (id: string) => Promise<ActionResult<Profile>>;
    export: (id: string) => Promise<ActionResult<string>>;
    import: (json: string) => Promise<ActionResult<Profile>>;
  };
  credentials: {
    status: () => Promise<CredentialsState>;
    statusAll: () => Promise<CredentialsStatusAll>;
    save: (input: CredentialsInput) => Promise<ActionResult>;
    test: (env?: KalshiEnv) => Promise<ActionResult<{ env: KalshiEnv; balanceUsd: number }>>;
    clear: (env?: KalshiEnv) => Promise<ActionResult>;
    onChanged: (cb: (payload: unknown) => void) => () => void;
  };
  backend: {
    info: () => Promise<BackendInfo>;
    start: () => Promise<ActionResult>;
    stop: () => Promise<ActionResult>;
    restart: () => Promise<ActionResult>;
    onInfo: (cb: (info: BackendInfo) => void) => () => void;
    runOnce: (
      action:
        | 'syncMarkets'
        | 'pollOrders'
        | 'resolveAll'
        | 'reconcilePositions'
        | 'recomputePnl'
        | 'reconcileFills'
        | 'auditPnl'
    ) => Promise<ActionResult<{ summary: string }>>;
  };
  trading: {
    setEnabled: (enabled: boolean) => Promise<ActionResult>;
    setDryRun: (dry: boolean) => Promise<ActionResult>;
    cancelAllOpen: () => Promise<ActionResult<{ canceled: number }>>;
    flatten: () => Promise<ActionResult<{ closed: number }>>;
  };
  data: {
    account: () => Promise<AccountSnapshot>;
    pnlSeries: (sinceHours?: number) => Promise<PnlPoint[]>;
    positions: (filter?: PositionFilter) => Promise<BotPosition[]>;
    signals: (filter?: SignalFilter) => Promise<SignalRow[]>;
    scannerStats: () => Promise<ScannerStats>;
    botRuns: (env?: KalshiEnv | null, limit?: number) => Promise<BotRunsResponse>;
    onAccount: (cb: (snap: AccountSnapshot) => void) => () => void;
    onPosition: (cb: (pos: BotPosition) => void) => () => void;
    onSignal: (cb: (sig: SignalRow) => void) => () => void;
  };
  crypto15m: {
    snapshot: () => Promise<Crypto15mSnapshot>;
    status: () => Promise<Crypto15mStatus>;
  };
  kalshi: {
    marketUrl: (args: { eventTicker?: string; ticker?: string; env?: string }) =>
      Promise<{ url: string }>;
  };
  logs: {
    tail: (limit?: number) => Promise<LogEntry[]>;
    onAppend: (cb: (entry: LogEntry) => void) => () => void;
    clear: () => Promise<ActionResult>;
    openFolder: () => Promise<void>;
  };
  window: {
    minimize: () => void;
    maximize: () => void;
    close: () => void;
    isMaximized: () => Promise<boolean>;
    onMaximizeChange: (cb: (max: boolean) => void) => () => void;
  };
}

export interface PositionFilter {
  status?: BotPosition['status'][];
  resolved?: boolean | null;
  signalSource?: SignalSource | null;
  limit?: number;
}

export interface SignalFilter {
  source?: SignalSource | null;
  minConfidence?: number;
  minEdge?: number;
  resolved?: boolean | null;
  limit?: number;
}

declare global {
  interface Window {
    krypt: KryptApi;
  }
}
