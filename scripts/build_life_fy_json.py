#!/usr/bin/env python3
"""
Build data/life/fy-{FY}.json from a manually filled CSV (IRDAI / public disclosure data).

The IRDAI website does not offer a single stable public API for all life metrics; operators
copy numbers from the Annual Report / Handbook / insurer PDFs into the CSV, then run
this script to produce versioned JSON for the app and sync to public/ via ingest_life_stats.py.

Usage:
  python scripts/build_life_fy_json.py --fy 2023-24 --csv data/life/source_templates/insurers_fy_template.csv

Optional:
  --note "Pasted from IRDAI AR 2023-24 table X"
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIFE_DIR = ROOT / "data" / "life"

REQUIRED_FLOAT = (
    "deathClaimSettlementRatio",
    "settledWithin30DaysPct",
    "thirteenthMonthPersistencyPct",
    "twentyFifthMonthPersistencyPct",
    "solvencyRatio",
)

# Optional IRDAI-style metrics — omit column or leave blank if unavailable.
OPTIONAL_FLOAT = ("grievancesPerLakhPolicies",)


def row_to_insurer(r: dict[str, str]) -> dict:
    out: dict = {
        "id": r["id"].strip(),
        "shortName": r["shortName"].strip(),
        "legalName": r["legalName"].strip(),
    }
    for k in REQUIRED_FLOAT + OPTIONAL_FLOAT:
        raw = (r.get(k) or "").strip()
        if raw == "":
            out[k] = None
        else:
            out[k] = float(raw)
    return out


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--fy", required=True, help='FY key, e.g. "2023-24"')
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--note", default="", help="QA note for sources[].note")
    args = p.parse_args()

    fy = args.fy
    csv_path = args.csv
    if not csv_path.is_file():
        print(f"CSV not found: {csv_path}", file=sys.stderr)
        return 1

    insurers: list[dict] = []
    with open(csv_path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("id", "").strip():
                continue
            insurers.append(row_to_insurer(row))

    bundle = {
        "fy": fy,
        "fyLabel": f"FY {fy.replace('-', '–')}",
        "schemaVersion": 1,
        "ingestedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "sources": [
            {
                "name": "Manual CSV ingest (IRDAI / insurer disclosures)",
                "url": "https://irdai.gov.in/annual-reports",
                "note": args.note
                or "Replace with exact table reference after QA (see docs/LIFE_STATS_QA_CHECKLIST.md).",
            }
        ],
        "insurers": insurers,
    }

    out_path = LIFE_DIR / f"fy-{fy}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"Wrote {out_path} ({len(insurers)} insurers). Next: update data/life/index.json if new FY, then:")
    print("  python scripts/ingest_life_stats.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
