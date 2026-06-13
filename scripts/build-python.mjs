import { existsSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { ensureVenv, run, VENV_PY, PY_DIR } from './python-utils.mjs';

ensureVenv();

console.log('>> Installing PyInstaller');
run(VENV_PY, ['-m', 'pip', 'install', 'pyinstaller==6.6.0', '--disable-pip-version-check']);

console.log('>> Cleaning previous build');
for (const d of ['build', 'dist']) {
  const p = join(PY_DIR, d);
  if (existsSync(p)) {
    rmSync(p, { recursive: true, force: true });
  }
}

console.log('>> Running PyInstaller (this takes ~60s)');
run(VENV_PY, [
  '-m', 'PyInstaller',
  '--noconfirm',
  '--name', 'krypt-trader-backend',
  '--console',
  '--hidden-import', 'db',
  '--hidden-import', 'scanner',
  '--hidden-import', 'trader',
  '--hidden-import', 'kalshi_api',
  '--hidden-import', 'kalshi_auth',
  '--hidden-import', 'categorize',
  '--hidden-import', 'config',
  '--hidden-import', 'webhook',
  '--hidden-import', 'crypto15m',
  '--hidden-import', 'crypto15m_trader',
  '--hidden-import', 'crypto15m_record',
  '--hidden-import', 'backtest',
  '--collect-submodules', 'cryptography',
  '--collect-submodules', 'httpx',
  'service.py',
]);

const out = join(PY_DIR, 'dist', 'krypt-trader-backend');
if (!existsSync(out)) {
  console.error('!! PyInstaller did not produce', out);
  process.exit(1);
}
console.log('>> OK \u2014 backend bundled at python/dist/krypt-trader-backend');
