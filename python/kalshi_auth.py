"""RSA-PSS request signing for the Kalshi trading API.

Krypt-Trader stores credentials at:

    <userData>/credentials/apikey.txt    UTF-8, single line
    <userData>/credentials/rsakey.pem    PEM-encoded RSA private key

The path to <userData> is provided via the KRYPT_TRADER_USERDATA env var
(set by the Electron main process on backend spawn). In dev / standalone
mode it falls back to `./credentials/` next to this file.

Kalshi authenticates writes with three headers:
    KALSHI-ACCESS-KEY         : the API key (UUID)
    KALSHI-ACCESS-TIMESTAMP   : current time in ms since epoch
    KALSHI-ACCESS-SIGNATURE   : base64(RSA-PSS-SHA256(timestamp + method + path))
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import sys
import time
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Optional

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa


logger = logging.getLogger(__name__)



_DPAPI_MARKER = b"#KRYPT-DPAPI-v1\n"
_warned_plaintext = False


def _dpapi_available() -> bool:
    return sys.platform == "win32"


if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_char))]

    def _to_blob(data: bytes) -> "_DATA_BLOB":
        buf = ctypes.create_string_buffer(bytes(data), len(data))
        return _DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_char)))

    def _from_blob(blob: "_DATA_BLOB") -> bytes:
        try:
            return ctypes.string_at(blob.pbData, blob.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(blob.pbData)

    def _dpapi_encrypt(data: bytes) -> bytes:
        out = _DATA_BLOB()
        blob_in = _to_blob(data)
        if not ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(out)
        ):
            raise OSError("CryptProtectData failed")
        return _from_blob(out)

    def _dpapi_decrypt(data: bytes) -> bytes:
        out = _DATA_BLOB()
        blob_in = _to_blob(data)
        if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(out)
        ):
            raise OSError("CryptUnprotectData failed")
        return _from_blob(out)
else:  # pragma: no cover - non-Windows fallback
    def _dpapi_encrypt(data: bytes) -> bytes:
        raise OSError("DPAPI not available")

    def _dpapi_decrypt(data: bytes) -> bytes:
        raise OSError("DPAPI not available")


def _write_secret_bytes(path: Path, data: bytes) -> None:
    """Atomically write `data`, DPAPI-encrypted when possible."""
    global _warned_plaintext
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    if _dpapi_available():
        try:
            tmp.write_bytes(_DPAPI_MARKER + base64.b64encode(_dpapi_encrypt(data)))
            tmp.replace(path)
            return
        except Exception as e:
            logger.warning(f"DPAPI encrypt failed, storing plaintext: {e}")
    if not _warned_plaintext:
        logger.warning("Credentials stored UNENCRYPTED (DPAPI unavailable on this platform).")
        _warned_plaintext = True
    tmp.write_bytes(data)
    tmp.replace(path)


def _read_secret_bytes(path: Path, upgrade: bool = True) -> bytes:
    """Read a credential file, decrypting DPAPI-wrapped content. Legacy
    plaintext is returned as-is and (when possible) re-encrypted in place."""
    raw = path.read_bytes()
    if raw.startswith(_DPAPI_MARKER):
        return _dpapi_decrypt(base64.b64decode(raw[len(_DPAPI_MARKER):]))
    if upgrade and _dpapi_available():
        try:
            _write_secret_bytes(path, raw)
        except Exception:
            pass
    return raw


def _credentials_dir() -> Path:
    base = os.environ.get("KRYPT_TRADER_USERDATA")
    if base:
        return Path(base) / "credentials"
    return Path(__file__).resolve().parent / "credentials"




def _env_api_key_file(env: str) -> Path:
    return _credentials_dir() / f"apikey.{env}.txt"


def _env_rsa_key_file(env: str) -> Path:
    return _credentials_dir() / f"rsakey.{env}.pem"


def _maybe_migrate_legacy(env: str) -> None:
    """One-time: if the legacy single-set files exist AND the env-specific
    files for `env` do not, copy the legacy files into the env-specific
    paths and then delete the legacy files. After this, both envs are
    fully isolated (saving keys for one never spills into the other).

    We migrate into whichever env is the *first* one that asks for keys
    after the upgrade — usually the active env on first launch.
    """
    d = _credentials_dir()
    legacy_api = d / "apikey.txt"
    legacy_pem = d / "rsakey.pem"
    if not (legacy_api.exists() or legacy_pem.exists()):
        return
    target_api = _env_api_key_file(env)
    target_pem = _env_rsa_key_file(env)
    if target_api.exists() or target_pem.exists():
        return
    try:
        if legacy_api.exists():
            _write_secret_bytes(target_api, _read_secret_bytes(legacy_api, upgrade=False))
            legacy_api.unlink()
        if legacy_pem.exists():
            _write_secret_bytes(target_pem, _read_secret_bytes(legacy_pem, upgrade=False))
            legacy_pem.unlink()
        for nm in ("apikey.env", "rsakey.env"):
            p = d / nm
            if p.exists():
                try: p.unlink()
                except Exception: pass
    except Exception:
        pass


def _api_key_file(env: Optional[str] = None) -> Path:
    """Return the API key file for `env` (defaults to active env).

    Critically: this is STRICTLY env-isolated. If `env`'s file doesn't
    exist, we return the canonical env-specific path (which won't exist
    yet) — we never silently fall back to the *other* env's keys, which
    is what caused the demo key to appear under the Live slot.
    """
    e = env or _current_env
    _maybe_migrate_legacy(e)
    return _env_api_key_file(e)


def _rsa_key_file(env: Optional[str] = None) -> Path:
    e = env or _current_env
    _maybe_migrate_legacy(e)
    return _env_rsa_key_file(e)


_SERVER_BASES = {
    "demo": "https://demo-api.kalshi.co",
    "production": "https://api.elections.kalshi.com",
}

_cached_api_key: Optional[str] = None
_cached_private_key: Optional[rsa.RSAPrivateKey] = None
_server_offset_ms: int = 0
_last_sync: float = 0.0
_RESYNC_INTERVAL_SEC = 300

_current_env: str = "production"


def set_env(env: str) -> None:
    global _current_env, _last_sync
    if env not in _SERVER_BASES:
        raise ValueError(f"unknown env: {env}")
    if env != _current_env:
        _current_env = env
        _last_sync = 0.0


def get_env() -> str:
    return _current_env


def _server_time_url() -> str:
    return f"{_SERVER_BASES[_current_env]}/trade-api/v2/exchange/status"


def reset_credential_cache() -> None:
    """Drop cached API + RSA key. Call after the user saves new keys."""
    global _cached_api_key, _cached_private_key
    _cached_api_key = None
    _cached_private_key = None


def _load_api_key() -> str:
    global _cached_api_key
    if _cached_api_key is not None:
        return _cached_api_key
    f = _api_key_file()
    if not f.exists():
        raise FileNotFoundError(f"Kalshi API key not configured ({f})")
    text = _read_secret_bytes(f).decode("utf-8", "replace")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line and not line.startswith("---"):
            _, _, val = line.partition("=")
            val = val.strip().strip('"').strip("'")
            if val:
                _cached_api_key = val
                return val
        else:
            _cached_api_key = line
            return line
    raise ValueError(f"No API key parsed from {f}")


def _load_private_key() -> rsa.RSAPrivateKey:
    global _cached_private_key
    if _cached_private_key is not None:
        return _cached_private_key
    f = _rsa_key_file()
    if not f.exists():
        raise FileNotFoundError(f"Kalshi RSA private key not configured ({f})")
    pem_bytes = _read_secret_bytes(f)
    key = serialization.load_pem_private_key(pem_bytes, password=None)
    if not isinstance(key, rsa.RSAPrivateKey):
        raise TypeError("RSA key file does not contain an RSA private key")
    _cached_private_key = key
    return key


def credentials_present(env: Optional[str] = None) -> bool:
    return _api_key_file(env).exists() and _rsa_key_file(env).exists()


def credentials_status(env: Optional[str] = None) -> dict:
    """Diagnostic info for the UI — never returns the secret material.

    Pass `env` to inspect a specific env's credentials. Default is the
    currently-active env (`get_env()`).
    """
    e = env or _current_env
    apk = _api_key_file(e)
    rkf = _rsa_key_file(e)
    info = {
        "env": e,
        "hasApiKey": apk.exists(),
        "hasRsaKey": rkf.exists(),
        "apiKeyPreview": "",
        "fingerprint": "",
    }
    if apk.exists():
        try:
            text = _read_secret_bytes(apk).decode("utf-8", "replace").strip().splitlines()[0]
            if "=" in text and not text.startswith("-"):
                _, _, text = text.partition("=")
            text = text.strip().strip('"').strip("'")
            if len(text) >= 4:
                info["apiKeyPreview"] = text[-4:]
        except Exception:
            pass
    if rkf.exists():
        try:
            key = serialization.load_pem_private_key(
                _read_secret_bytes(rkf), password=None
            )
            if isinstance(key, rsa.RSAPrivateKey):
                pub = key.public_key().public_numbers().n
                fp = hashlib.sha256(str(pub).encode()).hexdigest()[:8].upper()
                info["fingerprint"] = fp
        except Exception:
            pass
    return info


def credentials_status_all() -> dict:
    """Per-env credential status for both Kalshi envs."""
    return {
        "current": _current_env,
        "demo": credentials_status("demo"),
        "production": credentials_status("production"),
    }


def save_credentials(api_key: str, rsa_pem: str, env: Optional[str] = None) -> None:
    """Atomically write a credential pair to disk for `env` (defaults to
    the currently-active env). Writing for one env never touches the
    other env's saved keys."""
    e = env or _current_env
    d = _credentials_dir()
    d.mkdir(parents=True, exist_ok=True)
    api_key = api_key.strip()
    if not api_key:
        raise ValueError("API key is empty")
    try:
        key = serialization.load_pem_private_key(
            rsa_pem.encode("utf-8"), password=None
        )
    except Exception as ex:
        raise ValueError(f"RSA key did not parse: {ex}") from ex
    if not isinstance(key, rsa.RSAPrivateKey):
        raise ValueError("RSA key file is not an RSA private key")
    api_path = _env_api_key_file(e)
    pem_path = _env_rsa_key_file(e)
    _write_secret_bytes(api_path, (api_key + "\n").encode("utf-8"))
    _write_secret_bytes(pem_path, (rsa_pem.strip() + "\n").encode("utf-8"))
    if e == _current_env:
        reset_credential_cache()


def clear_credentials(env: Optional[str] = None) -> None:
    """Delete a single env's credentials. Always also wipes the legacy
    shared files (`apikey.txt`, `rsakey.pem`, `*.env`) so they cannot
    silently re-appear in the next read via the migration helper."""
    d = _credentials_dir()
    e = env or _current_env
    for p in (_env_api_key_file(e), _env_rsa_key_file(e)):
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
    for name in ("apikey.txt", "apikey.env", "rsakey.pem", "rsakey.env"):
        p = d / name
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass
    if e == _current_env:
        reset_credential_cache()


def migrate_legacy_credentials(target_env: str) -> bool:
    """Public entry-point to force-migrate the legacy single-set key files
    into a target env. Returns True if anything was moved."""
    before = _env_api_key_file(target_env).exists()
    _maybe_migrate_legacy(target_env)
    after = _env_api_key_file(target_env).exists()
    return after and not before


def sync_server_time(force: bool = False) -> int:
    global _server_offset_ms, _last_sync
    now_local = time.time()
    if (not force) and (now_local - _last_sync) < _RESYNC_INTERVAL_SEC:
        return _server_offset_ms
    try:
        with httpx.Client(timeout=5.0) as c:
            resp = c.head(_server_time_url())
            date_hdr = resp.headers.get("Date") or resp.headers.get("date")
        if date_hdr:
            server_dt = parsedate_to_datetime(date_hdr).timestamp()
            new_offset = int((server_dt - now_local) * 1000) - 750
            _server_offset_ms = new_offset
            _last_sync = now_local
            logger.debug(f"Kalshi clock sync: offset = {new_offset} ms")
    except Exception as e:
        logger.warning(f"Kalshi clock sync failed ({e})")
    return _server_offset_ms


def now_ms() -> int:
    if (time.time() - _last_sync) >= _RESYNC_INTERVAL_SEC:
        sync_server_time(force=False)
    return int(time.time() * 1000) + _server_offset_ms


def _sign(message: bytes) -> str:
    private_key = _load_private_key()
    signature = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=hashes.SHA256().digest_size,
        ),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("ascii")


def sign_headers(method: str, path: str) -> dict[str, str]:
    ts = str(now_ms())
    message = (ts + method.upper() + path).encode("utf-8")
    return {
        "KALSHI-ACCESS-KEY": _load_api_key(),
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "KALSHI-ACCESS-SIGNATURE": _sign(message),
    }


def prime_credentials(sync_time: bool = True) -> bool:
    _load_api_key()
    _load_private_key()
    if sync_time:
        sync_server_time(force=True)
    return True
