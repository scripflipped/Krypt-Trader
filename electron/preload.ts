import { contextBridge, ipcRenderer } from 'electron';
import type {
  AccountSnapshot, ActionResult, AppState, BackendInfo, BotPosition, CredentialsInput,
  CredentialsState, KryptApi, LogEntry, PnlPoint, PositionFilter, Profile,
  ScannerStats, SignalFilter, SignalRow, StrategyPreset, TraderConfig,
} from '../shared/types';

const sub = <T>(channel: string, cb: (val: T) => void): (() => void) => {
  const handler = (_e: unknown, val: T) => cb(val);
  ipcRenderer.on(channel, handler);
  return () => ipcRenderer.removeListener(channel, handler);
};

const api: KryptApi = {
  app: {
    version: () => ipcRenderer.invoke('app:version'),
    openExternal: (url) => ipcRenderer.invoke('app:openExternal', url),
    showItemInFolder: (p) => ipcRenderer.invoke('app:showItemInFolder', p),
    getUserDataPath: () => ipcRenderer.invoke('app:getUserDataPath'),
    factoryReset: () => ipcRenderer.invoke('app:factoryReset'),
    onDataReset: (cb) => sub<unknown>('data:reset', cb),
  },
  state: {
    get: (): Promise<AppState> => ipcRenderer.invoke('state:get'),
    onChange: (cb) => sub<AppState>('state:changed', cb),
    setStartMinimized: (v) => ipcRenderer.invoke('state:setStartMinimized', v),
    setStartWithWindows: (v) => ipcRenderer.invoke('state:setStartWithWindows', v),
    setEnableDiscordRpc: (v) => ipcRenderer.invoke('state:setEnableDiscordRpc', v),
    acceptDisclaimer: () => ipcRenderer.invoke('state:acceptDisclaimer'),
  },
  config: {
    get: (): Promise<TraderConfig> => ipcRenderer.invoke('config:get'),
    update: (patch) => ipcRenderer.invoke('config:update', patch),
    replace: (cfg) => ipcRenderer.invoke('config:replace', cfg),
    reset: () => ipcRenderer.invoke('config:reset'),
    listStrategies: (): Promise<StrategyPreset[]> =>
      ipcRenderer.invoke('config:listStrategies'),
    applyStrategy: (id) => ipcRenderer.invoke('config:applyStrategy', id),
  },
  profiles: {
    list: (): Promise<Profile[]> => ipcRenderer.invoke('profiles:list'),
    save: (name, description) => ipcRenderer.invoke('profiles:save', name, description),
    apply: (id) => ipcRenderer.invoke('profiles:apply', id),
    rename: (id, name) => ipcRenderer.invoke('profiles:rename', id, name),
    delete: (id) => ipcRenderer.invoke('profiles:delete', id),
    duplicate: (id) => ipcRenderer.invoke('profiles:duplicate', id),
    export: (id) => ipcRenderer.invoke('profiles:export', id),
    import: (json) => ipcRenderer.invoke('profiles:import', json),
  },
  credentials: {
    status: (): Promise<CredentialsState> => ipcRenderer.invoke('credentials:status'),
    statusAll: () => ipcRenderer.invoke('credentials:statusAll'),
    save: (input: CredentialsInput) => ipcRenderer.invoke('credentials:save', input),
    test: (env?: string) => ipcRenderer.invoke('credentials:test', env),
    clear: (env?: string) => ipcRenderer.invoke('credentials:clear', env),
    onChanged: (cb) => sub<unknown>('credentials:changed', cb),
  },
  backend: {
    info: (): Promise<BackendInfo> => ipcRenderer.invoke('backend:info'),
    start: () => ipcRenderer.invoke('backend:start'),
    stop: () => ipcRenderer.invoke('backend:stop'),
    restart: () => ipcRenderer.invoke('backend:restart'),
    onInfo: (cb) => sub<BackendInfo>('backend:info', cb),
    runOnce: (action) => ipcRenderer.invoke('backend:runOnce', action),
  },
  trading: {
    setEnabled: (v: boolean): Promise<ActionResult> =>
      ipcRenderer.invoke('trading:setEnabled', v),
    setDryRun: (v) => ipcRenderer.invoke('trading:setDryRun', v),
    cancelAllOpen: () => ipcRenderer.invoke('trading:cancelAllOpen'),
    flatten: () => ipcRenderer.invoke('trading:flatten'),
  },
  data: {
    account: (): Promise<AccountSnapshot> => ipcRenderer.invoke('data:account'),
    pnlSeries: (sinceHours?: number): Promise<PnlPoint[]> =>
      ipcRenderer.invoke('data:pnlSeries', sinceHours),
    positions: (filter?: PositionFilter): Promise<BotPosition[]> =>
      ipcRenderer.invoke('data:positions', filter),
    signals: (filter?: SignalFilter): Promise<SignalRow[]> =>
      ipcRenderer.invoke('data:signals', filter),
    scannerStats: (): Promise<ScannerStats> => ipcRenderer.invoke('data:scannerStats'),
    botRuns: (env, limit) =>
      ipcRenderer.invoke('data:botRuns', env ?? null, limit),
    onAccount: (cb) => sub<AccountSnapshot>('data:account', cb),
    onPosition: (cb) => sub<BotPosition>('data:position', cb),
    onSignal: (cb) => sub<SignalRow>('data:signal', cb),
  },
  crypto15m: {
    snapshot: () => ipcRenderer.invoke('crypto15m:snapshot'),
    status: () => ipcRenderer.invoke('crypto15m:status'),
  },
  kalshi: {
    marketUrl: (args) => ipcRenderer.invoke('kalshi:marketUrl', args),
  },
  logs: {
    tail: (limit?: number): Promise<LogEntry[]> => ipcRenderer.invoke('logs:tail', limit),
    onAppend: (cb) => sub<LogEntry>('logs:append', cb),
    clear: () => ipcRenderer.invoke('logs:clear'),
    openFolder: () => ipcRenderer.invoke('logs:openFolder'),
  },
  window: {
    minimize: () => ipcRenderer.send('window:minimize'),
    maximize: () => ipcRenderer.send('window:maximize'),
    close: () => ipcRenderer.send('window:close'),
    isMaximized: () => ipcRenderer.invoke('window:isMaximized'),
    onMaximizeChange: (cb) => sub<boolean>('window:maximizeChange', cb),
  },
};

contextBridge.exposeInMainWorld('krypt', api);
