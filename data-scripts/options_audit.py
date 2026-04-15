#!/usr/bin/env python3
"""
options_audit.py — VPS Readiness Audit for Weekly Index Options Data

Analyzes the data directory to determine if the environment is ready
for weekly index options strategy backtesting and live trading.

Usage:
    python data-scripts/options_audit.py
    python data-scripts/options_audit.py --data-root /path/to/data

Exit codes:
    0 = ready or partially_ready (can proceed with caution)
    1 = not_ready (requires data before proceeding)
"""

import argparse
import json
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd


DATA_ROOT = Path("data")
OPTION_TYPES = ["CE", "PE"]
INDICES = ["NIFTY", "BANKNIFTY", "FINNIFTY"]
INTERVALS = ["1min", "5min", "15min"]
OPT_TYPES = OPTION_TYPES  # Alias for convenience


def parse_args():
    p = argparse.ArgumentParser(description="Options Data Readiness Audit")
    p.add_argument(
        "--data-root",
        type=Path,
        default=DATA_ROOT,
        help="Root directory containing data/ (default: data/)",
    )
    p.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed findings"
    )
    return p.parse_args()


def scan_directory(base: Path) -> dict[str, Any]:
    """Recursively scan data directory and build a directory tree."""
    result = {"exists": base.exists(), "path": str(base)}
    if not base.exists():
        return result

    result["underlying"] = {}
    result["candles"] = {}

    for idx in INDICES:
        ud = base / "underlying" / idx
        result["underlying"][idx] = {
            "exists": ud.exists(),
            "files": {},
        }
        if ud.exists():
            for f in ud.glob("*.parquet"):
                result["underlying"][idx]["files"][f.stem] = str(f)

        for opt in OPT_TYPES:
            cd = base / "candles" / idx / opt
            result["candles"][idx] = result["candles"].get(idx, {})
            result["candles"][idx][opt] = {
                "exists": cd.exists(),
                "intervals": {},
            }
            if cd.exists():
                for iv in INTERVALS:
                    ivd = cd / iv
                    files = {}
                    if ivd.exists():
                        for f in ivd.glob("*.parquet"):
                            files[f.stem] = str(f)
                    result["candles"][idx][opt]["intervals"][iv] = {
                        "exists": ivd.exists(),
                        "files": files,
                        "count": len(files),
                    }

    return result


def analyze_timestamps(scan: dict) -> dict[str, Any]:
    """Analyze timestamp ranges in underlying and options files."""
    analysis = {
        "underlying": {},
        "options": {},
    }

    base = Path(scan["path"])

    for idx in INDICES:
        for fname, fpath in scan["underlying"][idx]["files"].items():
            try:
                df = pd.read_parquet(base / fpath, columns=["time"])
                if not df.empty:
                    times = pd.to_datetime(df["time"])
                    analysis["underlying"][f"{idx}/{fname}"] = {
                        "min": times.min().isoformat(),
                        "max": times.max().isoformat(),
                        "count": len(df),
                    }
            except Exception:
                pass

    for idx in INDICES:
        for opt in OPT_TYPES:
            for iv, iv_data in scan["candles"][idx][opt]["intervals"].items():
                for fname, fpath in iv_data.get("files", {}).items():
                    try:
                        df = pd.read_parquet(base / fpath, columns=["time"])
                        if not df.empty:
                            times = pd.to_datetime(df["time"])
                            key = f"{idx}/{opt}/{iv}/{fname}"
                            ec_match = (
                                fname.split("_")[1] if "_" in fname else "unknown"
                            )
                            analysis["options"][key] = {
                                "min": times.min().isoformat(),
                                "max": times.max().isoformat(),
                                "count": len(df),
                                "ec": ec_match,
                            }
                    except Exception:
                        pass

    return analysis


def count_expiry_families(scan: dict) -> dict[str, dict]:
    """Count expiry families (ec0, ec1, ec2, etc.) per index/option_type/interval."""
    families = {}

    base = Path(scan["path"])

    for idx in INDICES:
        families[idx] = {}
        for opt in OPT_TYPES:
            families[idx][opt] = {}
            for iv in INTERVALS:
                ec_counts = {"ec0": 0, "ec1": 0, "ec2+": 0}
                files = (
                    scan["candles"][idx][opt]["intervals"].get(iv, {}).get("files", {})
                )

                for fname in files.keys():
                    if "ec0" in fname and "ec0" == fname.split("_")[1]:
                        ec_counts["ec0"] += 1
                    elif "ec1" in fname and fname.split("_")[1] in ["ec1"]:
                        ec_counts["ec1"] += 1
                    elif "ec" in fname:
                        # Match ec2, ec3, ..., ec10, ec11, etc.
                        ec_counts["ec2+"] += 1

                families[idx][opt][iv] = ec_counts

    return families


def check_updater_wired() -> bool:
    """Check if the live updater is configured (ec0 should have recent data)."""
    return True  # For v1, assume updater can be run daily


def determine_readiness(
    scan: dict, timestamps: dict, families: dict, updater_wired: bool
) -> tuple[str, list[str]]:
    """Determine overall readiness based on analysis."""
    issues = []
    warnings = []

    has_underlying = all(
        scan["underlying"][idx]["exists"] and scan["underlying"][idx]["files"]
        for idx in INDICES
    )
    if not has_underlying:
        issues.append("Missing underlying data for one or more indices")

    has_ce_pe = all(
        scan["candles"][idx][opt]["exists"] for idx in INDICES for opt in OPT_TYPES
    )
    if not has_ce_pe:
        issues.append("Missing CE or PE directories")

    expired_counts = []
    for idx in INDICES:
        for opt in OPT_TYPES:
            for iv in INTERVALS:
                opt_data = families[idx].get(opt, {})
                iv_data = opt_data.get(iv, {})
                ec1 = iv_data.get("ec1", 0)
                ec2 = iv_data.get("ec2+", 0)
                expired_counts.append(ec1 + ec2)

    has_expired_history = sum(expired_counts) >= 2
    if not has_expired_history:
        issues.append("No expired weekly options history (need ec1+)")

    has_ec0 = any(
        families[idx].get(opt, {}).get(iv, {}).get("ec0", 0) > 0
        for idx in INDICES
        for opt in OPT_TYPES
        for iv in INTERVALS
    )
    if not has_ec0:
        warnings.append("No current-week (ec0) data found")
    else:
        warnings.append(
            "ec0 (live current-week) unproven: Dhan API returns DH-905 for expiry_code=0; "
            "requires active option instruments redesign"
        )

    has_overlap = False
    if timestamps["underlying"] and timestamps["options"]:
        ul_keys = list(timestamps["underlying"].keys())
        opt_keys = list(timestamps["options"].keys())
        if ul_keys and opt_keys:
            ul_key = ul_keys[0]
            opt_key = opt_keys[0]
            ul_min = pd.Timestamp(timestamps["underlying"][ul_key]["min"])
            ul_max = pd.Timestamp(timestamps["underlying"][ul_key]["max"])
            opt_min = pd.Timestamp(timestamps["options"][opt_key]["min"])
            opt_max = pd.Timestamp(timestamps["options"][opt_key]["max"])
            ranges_overlap = (ul_min <= opt_max) and (opt_min <= ul_max)
            has_overlap = ranges_overlap

    if not has_overlap and timestamps["options"]:
        warnings.append(
            "Could not verify timestamp overlap between underlying and options"
        )

    if issues:
        return "not_ready", issues
    elif warnings or not has_expired_history:
        return "partially_ready", warnings
    else:
        return "ready", []


def print_report(scan: dict, timestamps: dict, families: dict, verbose: bool):
    """Print the audit report."""
    print("\n" + "=" * 60)
    print("  OPTIONS DATA READINESS AUDIT")
    print("=" * 60)
    print(f"  Data root: {scan['path']}")
    print()

    print("─ 1. Underlying Data")
    print("─" * 40)
    for idx in INDICES:
        info = scan["underlying"][idx]
        status = "✓" if info["exists"] and info["files"] else "✗"
        files = list(info["files"].keys())
        print(f"  {status} {idx}: {len(files)} intervals")
        if verbose and files:
            for f in files:
                ts_info = timestamps["underlying"].get(f"{idx}/{f}")
                if ts_info:
                    print(
                        f"      {f}: {ts_info['min'][:10]} → {ts_info['max'][:10]} ({ts_info['count']} rows)"
                    )

    print()
    print("─ 2. Options Data (CE/PE)")
    print("─" * 40)
    for idx in INDICES:
        for opt in OPT_TYPES:
            for iv in INTERVALS:
                counts = families[idx][opt][iv]
                total = sum(counts.values())
                status = "✓" if total > 0 else "✗"
                print(
                    f"  {status} {idx}/{opt}/{iv}: {total} strikes (ec0={counts.get('ec0', 0)}, ec1={counts.get('ec1', 0)}, ec2+={counts.get('ec2+', 0)})"
                )

    print()
    print("─ 3. Expiry Family Summary")
    print("─" * 40)
    for idx in INDICES:
        print(f"  {idx}:")
        for opt in OPT_TYPES:
            total_ec0 = sum(families[idx][opt][iv].get("ec0", 0) for iv in INTERVALS)
            total_ec1 = sum(families[idx][opt][iv].get("ec1", 0) for iv in INTERVALS)
            total_ec2 = sum(families[idx][opt][iv].get("ec2+", 0) for iv in INTERVALS)
            print(f"    {opt}: ec0={total_ec0}, ec1={total_ec1}, ec2+={total_ec2}")

    print()
    print("─ 4. Sample Timestamps")
    print("─" * 40)
    if timestamps["underlying"]:
        sample = next(iter(timestamps["underlying"].values()))
        print(f"  Underlying: {sample['min'][:19]} → {sample['max'][:19]}")
    if timestamps["options"]:
        sample = next(iter(timestamps["options"].values()))
        print(f"  Options:   {sample['min'][:19]} → {sample['max'][:19]}")


def main():
    args = parse_args()
    base = args.data_root.resolve()

    print(f"Scanning {base}...")

    scan = scan_directory(base)
    timestamps = analyze_timestamps(scan)
    families = count_expiry_families(scan)
    updater_wired = check_updater_wired()

    verdict, findings = determine_readiness(scan, timestamps, families, updater_wired)

    print_report(scan, timestamps, families, args.verbose)

    print()
    print("=" * 60)
    print(f"  VERDICT: {verdict.upper()}")
    print("=" * 60)

    if findings:
        print("  Findings:")
        for f in findings:
            print(f"    ⚠ {f}")

    if verdict == "ready":
        print("\n  Environment is ready for weekly index options strategy.")
        print("  Proceed with backtesting and live trading setup.")
        return 0
    elif verdict == "partially_ready":
        print("\n  Environment is partially ready.")
        print("  Some data is missing - proceed with caution.")
        return 0
    else:
        print("\n  Environment is NOT ready.")
        print("  Please backfill missing data before proceeding.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
