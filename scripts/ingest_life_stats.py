#!/usr/bin/env python3
"""
Sync IRDAI-style life insurer stat packs from data/life/ to frontend/public/data/life/.

Source of truth: repo-root data/life/index.json + data/life/fy-*.json
Run after editing FY JSON or adding a new fy-YYYY-YY.json referenced from index.json.

Usage:
  python scripts/ingest_life_stats.py
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "data" / "life"
DST_DIR = ROOT / "frontend" / "public" / "data" / "life"


def main() -> int:
    if not SRC_DIR.is_dir():
        print(f"Missing {SRC_DIR}", file=sys.stderr)
        return 1
    index_path = SRC_DIR / "index.json"
    if not index_path.is_file():
        print(f"Missing {index_path}", file=sys.stderr)
        return 1

    with open(index_path, encoding="utf-8") as f:
        index = json.load(f)

    DST_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(index_path, DST_DIR / "index.json")

    data_files = index.get("dataFiles") or {}
    for fy, fname in data_files.items():
        src = SRC_DIR / fname
        if not src.is_file():
            print(f"Skip missing FY file for {fy}: {src}", file=sys.stderr)
            continue
        shutil.copy2(src, DST_DIR / fname)
        print(f"Synced {fy} -> frontend/public/data/life/{fname}")

    print("Done. Commit data/life/* and frontend/public/data/life/* together.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
