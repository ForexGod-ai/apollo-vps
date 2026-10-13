#!/usr/bin/env python3
"""
Audit USDCAD D1 — raw vs major swings + structural labels (HH/HL/LH/LL).

Usage (macOS / Linux):
  python3 scripts/audit_swings_usdcad.py --bars 365

Usage (Windows VPS — nu folosi ``python3``; de obicei e doar ``python``):
  python scripts\\audit_swings_usdcad.py --bars 365
  scripts\\audit_swings_usdcad.bat --bars 365
  py -3 scripts\\audit_swings_usdcad.py --bars 365
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from smc_detector import SMCDetector  # noqa: E402
from smc_detector.models import SwingPoint  # noqa: E402


def _load_daily(bars: int, use_cache: bool) -> Tuple[pd.DataFrame, str]:
    cache_dir = ROOT / "data" / "historical_cache"
    matches = sorted(cache_dir.glob("USDCAD_D1_*.csv"), key=lambda p: p.stat().st_mtime)

    def from_cache() -> pd.DataFrame | None:
        if not matches:
            return None
        df = pd.read_csv(matches[-1])
        for col in ("time", "timestamp", "datetime"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col])
                df = df.set_index(col)
                break
        for c in ("open", "high", "low", "close"):
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df.dropna(subset=["close"])
        if bars and len(df) > bars:
            df = df.iloc[-bars:]
        return df

    if use_cache:
        df = from_cache()
        if df is not None and not df.empty:
            return df, f"cache:{matches[-1].name}"

    try:
        from daily_scanner import CTraderDataProvider

        dp = CTraderDataProvider()
        if dp.connect():
            df = dp.get_historical_data("USDCAD", "D1", bars)
            if df is not None and not df.empty:
                return df, "ctrader:live"
    except Exception as exc:
        print(f"⚠️  cTrader indisponibil: {exc}")

    df = from_cache()
    if df is None or df.empty:
        raise SystemExit("❌ Nu există date USDCAD D1 (cache sau cTrader).")
    return df, f"cache:{matches[-1].name}"


def _wick(df: pd.DataFrame, sp: SwingPoint) -> float:
    i = sp.index
    if sp.swing_type == "high":
        return float(df["high"].iloc[i])
    return float(df["low"].iloc[i])


def _body(df: pd.DataFrame, det: SMCDetector, sp: SwingPoint) -> float:
    if sp.swing_type == "high":
        return det._swing_body_high(df, sp.index)
    return det._swing_body_low(df, sp.index)


def _struct_label(
    sp: SwingPoint,
    prev_same: Optional[SwingPoint],
) -> str:
    if prev_same is None:
        return "—"
    if sp.swing_type == "high":
        return "HH" if sp.price > prev_same.price else "LH"
    return "HL" if sp.price > prev_same.price else "LL"


def _print_table(
    title: str,
    rows: List[dict],
    tail: int | None = None,
) -> None:
    print(f"\n{'=' * 88}")
    print(title)
    print("=" * 88)
    if not rows:
        print("(gol)")
        return
    show = rows[-tail:] if tail else rows
    hdr = (
        f"{'idx':>4}  {'date':<20}  {'type':<4}  {'wick':>10}  {'body':>10}  "
        f"{'struct':<6}  {'SwingPoint.price':>10}"
    )
    print(hdr)
    print("-" * len(hdr))
    for r in show:
        print(
            f"{r['idx']:>4}  {str(r['date'])[:20]:<20}  {r['type']:<4}  "
            f"{r['wick']:>10.5f}  {r['body']:>10.5f}  {r['struct']:<6}  "
            f"{r['sp_price']:>10.5f}"
        )
    if tail and len(rows) > tail:
        print(f"... ({len(rows) - tail} rânduri mai vechi omise)")


def _rows_from_swings(
    df: pd.DataFrame,
    det: SMCDetector,
    swings: List[SwingPoint],
) -> List[dict]:
    rows: List[dict] = []
    prev_high: Optional[SwingPoint] = None
    prev_low: Optional[SwingPoint] = None
    for sp in sorted(swings, key=lambda x: x.index):
        prev = prev_high if sp.swing_type == "high" else prev_low
        rows.append(
            {
                "idx": sp.index,
                "date": sp.candle_time,
                "type": sp.swing_type.upper()[:4],
                "wick": _wick(df, sp),
                "body": _body(df, det, sp),
                "struct": _struct_label(sp, prev),
                "sp_price": sp.price,
            }
        )
        if sp.swing_type == "high":
            prev_high = sp
        else:
            prev_low = sp
    return rows


def _major_combined(
    major_highs: List[SwingPoint],
    major_lows: List[SwingPoint],
) -> List[SwingPoint]:
    tagged = [(sp, "HIGH") for sp in major_highs] + [(sp, "LOW") for sp in major_lows]
    tagged.sort(key=lambda x: x[0].index)
    return [t[0] for t in tagged]


def main() -> None:
    ap = argparse.ArgumentParser(description="USDCAD D1 swing audit")
    ap.add_argument("--bars", type=int, default=365)
    ap.add_argument("--cache", action="store_true", help="Force cache only")
    ap.add_argument("--tail-raw", type=int, default=25, help="Last N raw swings per side")
    ap.add_argument("--tail-major", type=int, default=15, help="Last N major pivots combined")
    args = ap.parse_args()

    df_full, src = _load_daily(args.bars, use_cache=args.cache)
    det = SMCDetector()
    df = det.d1_closed_structure_df(df_full)
    if df is None or df.empty:
        raise SystemExit("❌ DataFrame structural gol.")

    print(f"USDCAD D1 | sursă: {src} | bare structural: {len(df)} | "
          f"ultim close: {float(df['close'].iloc[-1]):.5f} | "
          f"ultimă dată: {df.index[-1]}")

    sh = det.detect_swing_highs(df)
    sl = det.detect_swing_lows(df)
    mh, ml = det.filter_major_swings(df, sh, sl)

    _print_table(
        f"SWING HIGH brute (ultimele {args.tail_raw})",
        _rows_from_swings(df, det, sh),
        tail=args.tail_raw,
    )
    _print_table(
        f"SWING LOW brute (ultimele {args.tail_raw})",
        _rows_from_swings(df, det, sl),
        tail=args.tail_raw,
    )

    major_rows: List[dict] = []
    prev_high: Optional[SwingPoint] = None
    prev_low: Optional[SwingPoint] = None
    for sp in _major_combined(mh, ml):
        kind = "HIGH" if sp in mh else "LOW"
        prev = prev_high if kind == "HIGH" else prev_low
        struct = _struct_label(sp, prev)
        major_rows.append(
            {
                "idx": sp.index,
                "date": sp.candle_time,
                "type": kind,
                "wick": _wick(df, sp),
                "body": _body(df, det, sp),
                "struct": struct,
                "sp_price": sp.price,
            }
        )
        if kind == "HIGH":
            prev_high = sp
        else:
            prev_low = sp

    _print_table("MAJOR SWINGS (cronologic)", major_rows, tail=args.tail_major)

    print(f"\n{'=' * 88}")
    print("ULTIMELE 10 PIVOȚI MAJORI DAILY (USDCAD)")
    print("=" * 88)
    if not major_rows:
        print("(gol)")
    else:
        hdr = (
            f"{'idx':>4}  {'date':<20}  {'type':<4}  {'wick':>10}  {'body':>10}  "
            f"{'struct':<6}  {'SwingPoint.price':>10}"
        )
        print(hdr)
        print("-" * len(hdr))
        for r in major_rows[-10:]:
            print(
                f"{r['idx']:>4}  {str(r['date'])[:20]:<20}  {r['type']:<4}  "
                f"{r['wick']:>10.5f}  {r['body']:>10.5f}  {r['struct']:<6}  "
                f"{r['sp_price']:>10.5f}"
            )

    chochs, _ = det.detect_choch_and_bos(df)
    flips = det._true_choch_flips(chochs)
    if flips:
        active = flips[-1]
        print(f"\nUltim CHoCH flip: {active.direction.upper()} @ bar {active.index} "
              f"({active.candle_time}) break={active.break_price:.5f}")
        if active.direction == "bullish":
            prot = det._protected_hl_impulse_origin(df, active)
            print(f"Protected HL (V72 origin major low): {prot:.5f}" if prot else "Protected HL: n/a")
        else:
            prot = det._protected_ceiling_bearish_leg_at(df, active, len(df) - 1)
            print(f"Protected LH (V72): {prot:.5f}" if prot else "Protected LH: n/a")

    print(f"\nTotal: raw H={len(sh)} L={len(sl)} | major H={len(mh)} L={len(ml)}")


if __name__ == "__main__":
    main()
