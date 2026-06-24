import { app } from 'electron';
import { existsSync, mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';
import type { AppState, Profile, TraderConfig } from '../../shared/types';


const userDataDir = (): string => app.getPath('userData');

const settingsFile = (): string => join(userDataDir(), 'settings.json');

export const DEFAULT_CONFIG: TraderConfig = {
  kalshiEnv: 'demo',
  enableTrading: false,

  tradeWhales: true,
  tradeMomentum: true,
  tradeConvergence: false,

  minEdgePtsWhale: 5.0,
  minEdgePtsMomentum: 5.0,
  minConfidenceWhale: 55.0,
  minConfidenceMomentum: 55.0,
  minEntryPriceCents: 15,
  maxEntryPriceCents: 85,
  allowedMomentumSignalTypes: ['trade_cluster'],
  allowedCategories: null,
  allowedWhaleCategories: null,
  allowedMomentumCategories: null,
  contrarianOnly: true,

  gamblingMode: false,
  gamblingTradeProbability: 0.10,

  sizingMode: 'percent',
  fixedTradeUsd: 5,
  baseSizeFraction: 0.03,
  minSizeFraction: 0.02,
  maxSizeFraction: 0.06,
  sizingBaseEdge: 5.0,
  sizingMaxEdge: 20.0,
  hardMaxPositionUsd: 50.0,
  minCashReserveFraction: 0.05,

  orderStyle: 'limit_cross',
  crossSpreadFallbackOffset: 2,
  orderExpirationSec: 90,

  maxOpenPositions: 25,
  maxPositionsPerEvent: 1,
  maxDailyNewPositions: 40,
  unlimitedDailyNewPositions: false,
  maxTotalExposureFraction: 0.75,

  tradeScanInterval: 20,
  positionPollInterval: 30,
  balancePollInterval: 60,
  resolutionCheckInterval: 300,
  whaleScanInterval: 120,
  momentumScanInterval: 90,
  marketRefreshInterval: 300,

  maxSignalAgeSec: 120,

  startBankrollUsd: 0.0,
  stopLossOnDay: -50.0,
  takeProfitOnDay: 0.0,

  tradingHoursEnabled: false,
  tradingHoursStart: '00:00',
  tradingHoursEnd: '23:59',
  tradingDays: ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'],
  tradingTimezoneOffsetMin: 0,

  minWhaleUsd: 2500.0,
  minWhaleConfidence: 30.0,
  minWhaleEdge: 2.0,
  minMomentumConfidence: 0.0,
  minMomentumEdge: 5.0,
  minEntryPriceFrac: 0.5,

  eventWebhookUrl: '',
  statsWebhookUrl: '',
  whaleWebhookUrl: '',
  momentumWebhookUrl: '',
  statsPushInterval: 1800,
  statsChartWindowHours: 168,
  enableDiscord: true,

  crypto15mEnabled: false,
  crypto15mLive: false,
  crypto15mSizingMode: 'fixed',
  crypto15mOrderSize: 1,
  crypto15mBalancePct: 0.02,
  crypto15mMaxLossPct: 0,
  crypto15mMaxConcurrent: 7,
  crypto15mDirectionMode: 'favorite',
  crypto15mTimeDelayMin: 8,
  crypto15mEntryThreshold: 0.70,
  crypto15mEntryMax: 0.98,
  crypto15mExitThreshold: 0.4,
  crypto15mMinDeltaPct: 0,
  crypto15mEntryDiff: 0.02,
  crypto15mEntryStyle: 'maker',
  crypto15mMakerCancelMin: 1,
  crypto15mHoursStartUtc: 0,
  crypto15mHoursEndUtc: 24,
  crypto15mRecordSignals: true,
};

export const DEFAULT_STATE: AppState = {
  config: { ...DEFAULT_CONFIG },
  activeProfileId: null,
  customProfiles: [],
  startMinimized: false,
  startWithWindows: false,
  enableDiscordRpc: true,
  acceptedDisclaimer: false,
  windowBounds: null,
};

let cached: AppState | null = null;

function ensureDir(): void {
  const d = userDataDir();
  if (!existsSync(d)) mkdirSync(d, { recursive: true });
}

function mergeConfig(loaded: Partial<TraderConfig> | undefined): TraderConfig {
  return { ...DEFAULT_CONFIG, ...(loaded || {}) };
}

function mergeProfile(loaded: any): Profile | null {
  if (!loaded || typeof loaded !== 'object') return null;
  if (!loaded.id || !loaded.name || !loaded.config) return null;
  return {
    id: String(loaded.id),
    name: String(loaded.name),
    description: loaded.description ? String(loaded.description) : undefined,
    createdAt: loaded.createdAt || new Date().toISOString(),
    updatedAt: loaded.updatedAt || new Date().toISOString(),
    builtin: !!loaded.builtin,
    config: mergeConfig(loaded.config),
  };
}

function mergeState(loaded: any): AppState {
  if (!loaded || typeof loaded !== 'object') return { ...DEFAULT_STATE };
  const profiles: Profile[] = Array.isArray(loaded.customProfiles)
    ? loaded.customProfiles.map(mergeProfile).filter((p: Profile | null): p is Profile => p !== null)
    : [];
  return {
    config: mergeConfig(loaded.config),
    activeProfileId: loaded.activeProfileId || null,
    customProfiles: profiles,
    startMinimized: !!loaded.startMinimized,
    startWithWindows: !!loaded.startWithWindows,
    enableDiscordRpc:
      typeof loaded.enableDiscordRpc === 'boolean' ? loaded.enableDiscordRpc : true,
    acceptedDisclaimer: !!loaded.acceptedDisclaimer,
    windowBounds: loaded.windowBounds || null,
  };
}

export function load(): AppState {
  if (cached) return cached;
  ensureDir();
  const f = settingsFile();
  if (!existsSync(f)) {
    cached = { ...DEFAULT_STATE };
    save(cached);
    return cached;
  }
  try {
    const raw = readFileSync(f, 'utf-8');
    cached = mergeState(JSON.parse(raw));
  } catch (e) {
    console.error('settings parse failed, falling back to defaults:', e);
    cached = { ...DEFAULT_STATE };
  }
  return cached;
}

export function save(state: AppState): AppState {
  ensureDir();
  cached = state;
  const f = settingsFile();
  const tmp = `${f}.tmp`;
  writeFileSync(tmp, JSON.stringify(state, null, 2), 'utf-8');
  renameSync(tmp, f);
  return state;
}

export function get(): AppState {
  return cached ?? load();
}

export function patchConfig(patch: Partial<TraderConfig>): AppState {
  const cur = get();
  const next: AppState = { ...cur, config: { ...cur.config, ...patch } };
  return save(next);
}

export function replaceConfig(config: TraderConfig): AppState {
  const cur = get();
  const next: AppState = { ...cur, config: mergeConfig(config) };
  return save(next);
}

export function resetConfig(): AppState {
  const cur = get();
  const next: AppState = { ...cur, config: { ...DEFAULT_CONFIG }, activeProfileId: null };
  return save(next);
}
