"""Pytest bootstrap for the Krypt Trader backend.

The backend modules use top-level imports (`import db`, `import trader`,
…) and expect to run with the `python/` directory on `sys.path`. This
conftest lives in `python/` so pytest puts that directory on the path
for us, and it redirects all on-disk state (the SQLite DB, the rotating
log files, credential files) into a throwaway temp directory so the
suite never touches the user's real `<userData>` tree.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_SCRATCH = tempfile.mkdtemp(prefix="krypt-test-")
os.environ.setdefault("KRYPT_TRADER_USERDATA", _SCRATCH)
