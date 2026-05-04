"""Pytest configuration for backend tests.

Adds the backend/ directory to sys.path so engine modules import as
`services.audit.*` exactly the way the production routers do (no
backend.-prefix). Keeps test imports identical to runtime imports.

Note: backend_test.py is the live-URL integration suite; it doesn't
import any backend module directly so it's unaffected by this conftest.
"""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))
