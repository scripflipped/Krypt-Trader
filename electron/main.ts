import { app, BrowserWindow, screen, session, shell } from 'electron';
import { existsSync } from 'node:fs';
import { join } from 'node:path';
import { appendLog, broadcastState, registerIpc } from './ipc';
import { setStartWithWindows } from './system/autostart';
import { startDiscordRpc, stopDiscordRpc } from './system/discord';
import { pythonBackend } from './system/python-backend';
import * as store from './system/settings-store';
import { destroyTray, installTray, rebuild as rebuildTray } from './system/tray';

process.env.DIST_ELECTRON = __dirname;
process.env.DIST = join(__dirname, '..', 'dist');
process.env.VITE_PUBLIC = app.isPackaged
  ? process.env.DIST
  : join(__dirname, '..', 'public');

if (process.platform === 'win32') {
  app.setAppUserModelId('cc.krypt.trader');
}

let mainWindow: BrowserWindow | null = null;

function iconPath(): string {
  const candidates = [
    app.isPackaged
      ? join(process.resourcesPath, 'app.asar.unpacked', 'resources', 'krypt.ico')
      : join(process.cwd(), 'resources', 'krypt.ico'),
    app.isPackaged
      ? join(process.resourcesPath, 'krypt.ico')
      : join(process.cwd(), 'resources', 'krypt.ico'),
    join(__dirname, '..', 'resources', 'krypt.ico'),
  ];
  for (const c of candidates) {
    if (existsSync(c)) return c;
  }
  return candidates[0];
}

function createMainWindow(): BrowserWindow {
  if (mainWindow && !mainWindow.isDestroyed()) {
    if (mainWindow.isMinimized()) mainWindow.restore();
    mainWindow.show();
    mainWindow.focus();
    return mainWindow;
  }
  const state = store.get();
  const bounds = state.windowBounds;
  const primary = screen.getPrimaryDisplay();
  const width = bounds?.width ?? Math.min(1380, primary.workArea.width - 40);
  const height = bounds?.height ?? Math.min(900, primary.workArea.height - 40);
  const x = bounds?.x;
  const y = bounds?.y;

  mainWindow = new BrowserWindow({
    width,
    height,
    minWidth: 1100,
    minHeight: 720,
    x,
    y,
    backgroundColor: '#0A0A0F',
    show: false,
    frame: false,
    titleBarStyle: 'hidden',
    icon: iconPath(),
    webPreferences: {
      preload: join(__dirname, 'preload.js'),
      contextIsolation: true,
      sandbox: true,
      nodeIntegration: false,
      backgroundThrottling: false,
    },
  });

  mainWindow.webContents.setWindowOpenHandler(({ url: target }) => {
    if (/^https?:\/\//i.test(target)) void shell.openExternal(target);
    return { action: 'deny' };
  });
  mainWindow.webContents.on('will-navigate', (e, target) => {
    const dev = process.env['VITE_DEV_SERVER_URL'];
    if ((dev && target.startsWith(dev)) || target.startsWith('file://')) return;
    e.preventDefault();
    if (/^https?:\/\//i.test(target)) void shell.openExternal(target);
  });

  const url = process.env['VITE_DEV_SERVER_URL'];
  if (url) {
    void mainWindow.loadURL(url);
  } else {
    void mainWindow.loadFile(join(process.env.DIST!, 'index.html'));
  }

  mainWindow.once('ready-to-show', () => {
    if (state.startMinimized && process.argv.includes('--autostart')) {
    } else {
      mainWindow?.show();
    }
  });

  const persistBounds = (): void => {
    if (!mainWindow || mainWindow.isDestroyed()) return;
    if (mainWindow.isMaximized() || mainWindow.isMinimized()) return;
    const b = mainWindow.getBounds();
    const cur = store.get();
    store.save({ ...cur, windowBounds: b });
  };
  mainWindow.on('move', persistBounds);
  mainWindow.on('resize', persistBounds);
  mainWindow.on('maximize', () => mainWindow?.webContents.send('window:maximizeChange', true));
  mainWindow.on('unmaximize', () => mainWindow?.webContents.send('window:maximizeChange', false));

  mainWindow.on('close', (e) => {
    if (!quitting) {
      e.preventDefault();
      mainWindow?.hide();
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  return mainWindow;
}

let quitting = false;

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) {
  app.quit();
} else {
  app.on('second-instance', () => {
    const w = createMainWindow();
    if (w.isMinimized()) w.restore();
    w.show();
    w.focus();
  });

  app.whenReady().then(bootstrap);
}

function installCsp(): void {
  if (!app.isPackaged) return;
  session.defaultSession.webRequest.onHeadersReceived((details, cb) => {
    cb({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [
          "default-src 'self'; script-src 'self'; " +
          "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; " +
          "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; " +
          "connect-src 'self'",
        ],
      },
    });
  });
}

async function bootstrap(): Promise<void> {
  registerIpc();
  installCsp();

  const state = store.load();

  pythonBackend.onStatusChange((info) => {
    for (const w of BrowserWindow.getAllWindows()) {
      if (!w.isDestroyed()) {
        w.webContents.send('backend:info', info);
      }
    }
    rebuildTray({
      openWindow: () => createMainWindow(),
      toggleTrading: toggleTradingFromTray,
      isTrading: () => store.get().config.enableTrading,
      quit: () => {
        quitting = true;
        app.quit();
      },
    });
  });

  pythonBackend.onEvent((name, data) => {
    if (name === 'backend:ready') {
      const state = store.get();
      void pythonBackend
        .request('setConfig', { config: state.config })
        .catch(() => {
        });
    }
    for (const w of BrowserWindow.getAllWindows()) {
      if (w.isDestroyed()) continue;
      if (name === 'account:update') {
        w.webContents.send('data:account', data);
      } else if (name === 'position:new' || name === 'position:update') {
        w.webContents.send('data:position', data);
      } else if (name === 'signal:new') {
        w.webContents.send('data:signal', data);
      } else if (name === 'credentials:changed') {
        w.webContents.send('credentials:changed', data);
      } else if (name === 'data:reset') {
        w.webContents.send('data:reset', data);
      } else if (name === 'backend:authChanged' || name === 'backend:reconciled' || name === 'backend:ready' || name === 'backend:shutdown') {
      }
    }
  });

  pythonBackend.onLog((entry) => {
    appendLog(entry);
    for (const w of BrowserWindow.getAllWindows()) {
      if (!w.isDestroyed()) {
        w.webContents.send('logs:append', entry);
      }
    }
  });

  void pythonBackend.start().then(async () => {
    const start = Date.now();
    while (!pythonBackend.isRunning() && Date.now() - start < 8000) {
      await new Promise((r) => setTimeout(r, 200));
    }
    try {
      await pythonBackend.request('setConfig', { config: state.config });
    } catch {
    }
  });

  void startDiscordRpc();

  installTray({
    openWindow: () => createMainWindow(),
    toggleTrading: toggleTradingFromTray,
    isTrading: () => store.get().config.enableTrading,
    quit: () => {
      quitting = true;
      app.quit();
    },
  });

  if (app.isPackaged) {
    setStartWithWindows(state.startWithWindows);
  }

  const launchedAtLogin =
    (() => {
      try {
        return app.getLoginItemSettings().wasOpenedAtLogin === true;
      } catch {
        return false;
      }
    })() ||
    process.argv.some((a) => a === '--autostart' || a === '--hidden');

  if (!(state.startMinimized && launchedAtLogin)) {
    createMainWindow();
  }
}

async function toggleTradingFromTray(): Promise<void> {
  const cur = store.get();
  const next = store.patchConfig({ enableTrading: !cur.config.enableTrading });
  broadcastState(next);
  if (pythonBackend.isRunning()) {
    try {
      await pythonBackend.request('setConfig', { config: next.config });
    } catch {
    }
  }
  rebuildTray({
    openWindow: () => createMainWindow(),
    toggleTrading: toggleTradingFromTray,
    isTrading: () => store.get().config.enableTrading,
    quit: () => {
      quitting = true;
      app.quit();
    },
  });
}

app.on('window-all-closed', (e: Electron.Event) => {
  e.preventDefault();
});

app.on('before-quit', async () => {
  quitting = true;
  stopDiscordRpc();
  destroyTray();
  await pythonBackend.stop();
});
