#!/usr/bin/env python3
"""
Audit POI Daily — citește monitoring_setups.json și reconciliază POI cu FVG-uri D1 live.

Usage (Linux/macOS):
    python scripts/audit_d1_poi_from_monitoring.py
    python scripts/audit_d1_poi_from_monitoring.py | tee audit_poi_$(date +%F).log

Usage (Windows PowerShell):
    python scripts/audit_d1_poi_from_monitoring.py --log-file audit_poi_2026-06-22.log
    python scripts/audit_d1_poi_from_monitoring.py *> audit_poi_$(Get-Date -Format 'yyyy-MM-dd').log
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Windows VPS (cp1252): emoji din smc_detector crăpau la print — aliniat cu daily_scanner.py
if sys.stdout.encoding is None or sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding is None or sys.stderr.encoding.lower() != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from smc_detector import SMCDetector, CHoCH, BOS

ACTIVE_STATUSES = frozenset({
    "MONITORING", "READY", "WAITING_D1_PULLBACK", "WAITING_4H_CHOCH",
    "WAITING_1H_CHOCH", "PARTIAL_OPEN", "TRADE_OPEN",
})

MONITORING_FILE = ROOT / "monitoring_setups.json"
CACHE_DIR = ROOT / "data" / "historical_cache"


def _normalize_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "time" not in df.columns:
        if "timestamp" in df.columns:
            df["time"] = pd.to_datetime(df["timestamp"])
        elif isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            df.rename(columns={df.columns[0]: "time"}, inplace=True)
        else:
            df["time"] = pd.to_datetime(df.iloc[:, 0])
    else:
        df["time"] = pd.to_datetime(df["time"])
    if hasattr(df["time"].dt, "tz") and df["time"].dt.tz is not None:
        df["time"] = df["time"].dt.tz_localize(None)
    for c in ("open", "high", "low", "close"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.sort_values("time").reset_index(drop=True)


def load_monitoring_setups(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        return data.get("setups") or []
    return data if isinstance(data, list) else []


def poi_from_setup(setup: dict) -> Tuple[Optional[float], Optional[float]]:
    top = setup.get("poi_top")
    if top is None:
        top = setup.get("fvg_top")
    bottom = setup.get("poi_bottom")
    if bottom is None:
        bottom = setup.get("fvg_bottom")
    try:
        t = float(top) if top is not None else None
        b = float(bottom) if bottom is not None else None
        return t, b
    except (TypeError, ValueError):
        return None, None


def required_direction(setup: dict) -> Optional[str]:
    d = (setup.get("direction") or setup.get("daily_bias") or "").lower()
    if d in ("buy", "long", "bullish"):
        return "bullish"
    if d in ("sell", "short", "bearish"):
        return "bearish"
    return None


def v427_poi_gate(price: float, poi_top: float, poi_bottom: float, direction: str) -> Tuple[bool, str]:
    if direction == "bullish":
        if price <= poi_top:
            if poi_bottom <= price <= poi_top:
                return True, "in POI zone"
            if price < poi_bottom:
                return True, "discount below POI"
            return True, "at POI edge"
        return False, f"Premium above POI top ({price:.5f} > {poi_top:.5f})"
    if direction == "bearish":
        if price >= poi_bottom:
            if poi_bottom <= price <= poi_top:
                return True, "in POI zone"
            if price > poi_top:
                return True, "premium above POI"
            return True, "at POI edge"
        return False, f"Discount below POI bottom ({price:.5f} < {poi_bottom:.5f})"
    return False, "unknown direction"


def zones_match(
    json_top: Optional[float],
    json_bottom: Optional[float],
    sel: Optional[dict],
    tol: float = 1e-4,
) -> bool:
    if json_top is None or json_bottom is None or sel is None:
        return False
    return (
        abs(float(json_top) - float(sel["top"])) <= tol
        and abs(float(json_bottom) - float(sel["bottom"])) <= tol
    )


def fetch_data(
    symbol: str,
    json_only: bool,
) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[float], str]:
    if not json_only:
        try:
            from ctrader_cbot_client import CTraderCBotClient

            client = CTraderCBotClient()
            if client.is_available(retries=1, wait=0.5):
                df_d1 = client.get_historical_data(symbol, "D1", 200)
                df_h4 = client.get_historical_data(symbol, "H4", 300)
                if df_d1 is not None and not df_d1.empty:
                    df_d1 = _normalize_ohlc(df_d1.reset_index() if "time" not in df_d1.columns else df_d1)
                    df_h4 = (
                        _normalize_ohlc(df_h4.reset_index() if df_h4 is not None and "time" not in df_h4.columns else df_h4)
                        if df_h4 is not None and not df_h4.empty
                        else None
                    )
                    price = float(df_d1["close"].iloc[-1])
                    return df_d1, df_h4, price, "ctrader:8010"
        except Exception as exc:
            pass  # fall through to cache

    matches = sorted(CACHE_DIR.glob(f"{symbol}_D1_*.csv"), reverse=True)
    h4_matches = sorted(CACHE_DIR.glob(f"{symbol}_H4_*.csv"), reverse=True)
    if matches:
        df_d1 = _normalize_ohlc(pd.read_csv(matches[0]))
        df_h4 = _normalize_ohlc(pd.read_csv(h4_matches[0])) if h4_matches else None
        price = float(df_d1["close"].iloc[-1])
        return df_d1, df_h4, price, f"cache:{matches[0].name}"

    return None, None, None, "no data"


def find_h4_choch(
    detector: SMCDetector,
    df_h4: pd.DataFrame,
    direction: str,
) -> Tuple[Optional[Any], Optional[int]]:
    if df_h4 is None or df_h4.empty:
        return None, None
    h4_chochs, _ = detector.detect_choch_and_bos(df_h4)
    recent = [c for c in h4_chochs if c.index >= len(df_h4) - 80 and c.direction == direction]
    if not recent:
        return None, None
    ch = recent[-1]
    age = len(df_h4) - 1 - ch.index
    return ch, age


def audit_setup(
    setup: dict,
    detector: SMCDetector,
    json_only: bool,
) -> Dict[str, Any]:
    symbol = setup.get("symbol", "?")
    direction = required_direction(setup) or "?"
    status = setup.get("status", "?")
    json_top, json_bottom = poi_from_setup(setup)

    result: Dict[str, Any] = {
        "symbol": symbol,
        "direction": direction,
        "status": status,
        "json_poi_top": json_top,
        "json_poi_bottom": json_bottom,
        "strategy_type": setup.get("strategy_type") or setup.get("setup_type"),
        "daily_bias_active": setup.get("daily_bias_active"),
        "execute_now": setup.get("EXECUTE_NOW"),
        "entry1_filled": setup.get("entry1_filled"),
        "flags": [],
    }

    df_d1, df_h4, price, data_src = fetch_data(symbol, json_only)
    result["data_source"] = data_src

    if df_d1 is None or price is None:
        result["verdict"] = "SKIP — no D1 data (use VPS 8010 or cache)"
        if json_top is not None and json_bottom is not None:
            result["json_poi_range"] = f"[{json_bottom:.5f} – {json_top:.5f}]"
        return result

    result["live_price"] = round(price, 5)

    swing_highs = detector.detect_swing_highs(df_d1)
    swing_lows = detector.detect_swing_lows(df_d1)
    daily_chochs, daily_bos = detector.detect_choch_and_bos(df_d1)
    range_state = detector.compute_structural_range(df_d1, swing_highs, swing_lows, symbol=symbol)
    daily_chochs, daily_bos, range_state = detector.filter_internal_range_signals(
        symbol, df_d1, daily_chochs, daily_bos, range_state
    )

    latest_signal, strategy_type, current_trend, leg_choch = detector._resolve_d1_leg(
        df_d1, daily_chochs, daily_bos, debug=False
    )
    if current_trend in ("bullish", "bearish"):
        direction = current_trend
        result["direction"] = direction
    result["strategy_type_live"] = strategy_type
    result["current_trend"] = current_trend

    if latest_signal is None:
        result["verdict"] = "NO D1 signal — leg unresolved"
        result["flags"].append("NO_D1_SIGNAL")
        return result

    sig_label = "CHoCH" if isinstance(latest_signal, CHoCH) else "BOS"
    result["d1_anchor"] = (
        f"{sig_label} {current_trend} @bar{latest_signal.index} "
        f"price={latest_signal.break_price:.5f}"
    )

    adr = detector.build_active_dealing_range(
        df_d1,
        swing_highs,
        swing_lows,
        latest_signal.index,
        current_trend,
        range_state=range_state,
        symbol=symbol,
    )
    structural_breach = SMCDetector.compute_structural_breach(price, current_trend, adr)
    result["structural_breach"] = structural_breach
    if adr is not None:
        result["adr_high"] = round(float(adr.current_swing_high), 5)
        result["adr_low"] = round(float(adr.current_swing_low), 5)
        result["adr_price_inside"] = adr.price_inside
    else:
        result["adr_high"] = None
        result["adr_low"] = None
        result["adr_price_inside"] = None

    audit_fvg: dict = {}
    poi_res = detector.resolve_d1_poi(
        df_d1,
        latest_signal,
        float(price),
        current_trend,
        strategy_type,
        adr,
        symbol=symbol,
        stored_poi_top=json_top,
        stored_poi_bottom=json_bottom,
        audit_out=audit_fvg,
    )
    result["fvg_audit"] = audit_fvg
    result["poi_source"] = poi_res.poi_source
    result["poi_preserve_stored"] = poi_res.preserve_stored_poi
    result["poi_zombie"] = poi_res.poi_zombie

    selected_fvg = poi_res.fvg
    if selected_fvg is None and direction in ("bullish", "bearish"):
        synthetic = detector._build_v246_synthetic_fvg(
            df_d1, latest_signal, current_trend, symbol=symbol, dealing_range=adr,
        )
        result["recalc_poi_top"] = round(float(synthetic.top), 5)
        result["recalc_poi_bottom"] = round(float(synthetic.bottom), 5)
        result["recalc_source"] = "V43 synthetic ADR clip"
    elif selected_fvg is not None:
        result["recalc_poi_top"] = round(float(selected_fvg.top), 5)
        result["recalc_poi_bottom"] = round(float(selected_fvg.bottom), 5)
        result["recalc_source"] = poi_res.poi_source or audit_fvg.get(
            "selection_reason", "resolve_d1_poi"
        )
    else:
        result["recalc_poi_top"] = None
        result["recalc_poi_bottom"] = None

    if (
        adr is not None
        and json_top is not None
        and json_bottom is not None
        and (strategy_type or "").lower() == "continuation"
        and SMCDetector.poi_conflicts_with_continuation(
            float(json_top), float(json_bottom), current_trend, adr,
        )
    ):
        result["flags"].append("V43_ADR_CONFLICT")
        result["v43_adr_conflict"] = True

    if json_top is not None and json_bottom is not None:
        sel = audit_fvg.get("selected")
        if result.get("recalc_source", "").startswith("V24.6"):
            sel_dict = {
                "top": result["recalc_poi_top"],
                "bottom": result["recalc_poi_bottom"],
            }
            match = zones_match(json_top, json_bottom, sel_dict)
        else:
            match = zones_match(json_top, json_bottom, sel)
        result["json_matches_recalc"] = match
        if not match:
            result["flags"].append("POI_DRIFT")

    gate_top = json_top if json_top is not None else result.get("recalc_poi_top")
    gate_bottom = json_bottom if json_bottom is not None else result.get("recalc_poi_bottom")
    if gate_top is not None and gate_bottom is not None and direction in ("bullish", "bearish"):
        poi_ok, poi_reason = v427_poi_gate(price, gate_top, gate_bottom, direction)
        result["v427_poi_ok"] = poi_ok
        result["v427_poi_reason"] = poi_reason
        result["v427_poi_source"] = "JSON" if json_top is not None else "recalc"
        if not poi_ok:
            result["flags"].append("V42.7_POI_BLOCK")

    h4_ch, h4_age = find_h4_choch(detector, df_h4, direction) if direction in ("bullish", "bearish") else (None, None)
    if h4_ch:
        result["h4_choch"] = f"{h4_ch.direction} @bar{h4_ch.index} price={h4_ch.break_price:.5f} age={h4_age}b"
        result["h4_aligned"] = True
    else:
        result["h4_choch"] = None
        result["h4_aligned"] = False
        result["flags"].append("WAIT_4H_CHOCH")

    # Verdict
    if "V43_ADR_CONFLICT" in result["flags"]:
        result["verdict"] = "JSON POI violates ADR — V43 rescan required"
    elif "POI_DRIFT" in result["flags"]:
        result["verdict"] = "POI JSON differs from live V16.1 recalc — review chart"
    elif not result.get("v427_poi_ok", True):
        result["verdict"] = "POI set OK — waiting Daily pullback (V42.7)"
    elif not result.get("h4_aligned"):
        result["verdict"] = "At POI or approaching — waiting 4H CHoCH alignment"
    elif status == "READY" or result.get("v427_poi_ok"):
        result["verdict"] = "POI + 4H aligned — ready for LTF EXECUTE (if radar triggers)"
    else:
        result["verdict"] = "Monitor — check flags"

    return result


def print_audit_report(results: List[dict]) -> None:
    print("\n" + "=" * 72)
    print("D1 POI AUDIT — monitoring_setups.json vs live FVG detection")
    print("=" * 72)

    for r in results:
        sym = r["symbol"]
        dir_u = (r.get("direction") or "?").upper()
        if dir_u == "BULLISH":
            dir_u = "LONG"
        elif dir_u == "BEARISH":
            dir_u = "SHORT"

        print(f"\n{'─' * 72}")
        print(f"{sym} | {dir_u} | status={r.get('status')}")
        if r.get("strategy_type"):
            print(f"  Strategy: {r.get('strategy_type')} | EXECUTE_NOW={r.get('execute_now')}")

        jt, jb = r.get("json_poi_top"), r.get("json_poi_bottom")
        if jt is not None and jb is not None:
            print(f"  JSON POI:     [{jb:.5f} – {jt:.5f}]")
        else:
            print("  JSON POI:     (not set — bias fallback or stale entry)")

        if r.get("live_price") is not None:
            print(f"  Live price:   {r['live_price']:.5f}  ({r.get('data_source')})")
            if "v427_poi_ok" in r:
                gate = "OPEN" if r["v427_poi_ok"] else "BLOCK"
                print(f"  V42.7 gate:   {gate} — {r.get('v427_poi_reason', '')}")

        if r.get("d1_anchor"):
            print(f"  D1 anchor:    {r['d1_anchor']}")

        ah, al = r.get("adr_high"), r.get("adr_low")
        if ah is not None and al is not None:
            print(f"  ADR High (LH): {ah:.5f}")
            print(f"  ADR Low (LL):  {al:.5f}")
            inside = r.get("adr_price_inside")
            if inside is not None:
                print(f"  ADR state:     {'INSIDE range' if inside else 'OUTSIDE range'}")
        else:
            print("  ADR:           (not computed — insufficient swings)")

        if r.get("structural_breach"):
            print(
                "  *** STRUCTURAL BREACH *** Daily close broke protected LH/LL — "
                "continuation setup structurally invalid (Etapa 2 will consume signal)"
            )

        if r.get("v43_adr_conflict") or "V43_ADR_CONFLICT" in (r.get("flags") or []):
            print(
                "[⚠️ V43_ADR_CONFLICT] Vechiul POI încalcă granițele ADR. "
                "Rescanare activată pentru zonă proaspătă."
            )

        fa = r.get("fvg_audit") or {}
        n_all = len(fa.get("all_fvgs") or [])
        n_mit = len(fa.get("after_mitigation") or [])
        n_pd = len(fa.get("pd_valid") or [])
        n_post = len(fa.get("post_choch") or [])
        print(
            f"  FVG D1:       {n_all} found → {n_mit} after mitigation → "
            f"{n_pd} P/D valid → {n_post} post-CHOCH"
        )
        if fa.get("equilibrium") is not None:
            print(f"  Equilibrium:  {fa['equilibrium']:.5f}")

        for label, key in (("P/D valid", "pd_valid"), ("Post-CHOCH", "post_choch")):
            items = fa.get(key) or []
            if items:
                print(f"  {label}:")
                for item in items[:5]:
                    print(
                        f"    • bar{item['index']} [{item['bottom']:.5f}–{item['top']:.5f}] "
                        f"gap={item['gap_size']:.5f}"
                    )
                if len(items) > 5:
                    print(f"    ... +{len(items) - 5} more")

        sel = fa.get("selected")
        if sel:
            print(
                f"  SELECTED:     [{sel['bottom']:.5f} – {sel['top']:.5f}] "
                f"@bar{sel['index']} ({fa.get('selection_reason', '')})"
            )
        elif r.get("recalc_source"):
            rt, rb = r.get("recalc_poi_top"), r.get("recalc_poi_bottom")
            if rt is not None and rb is not None:
                print(f"  RECALC POI:   [{rb:.5f} – {rt:.5f}] ({r['recalc_source']})")

        if r.get("json_matches_recalc") is False:
            rt, rb = r.get("recalc_poi_top"), r.get("recalc_poi_bottom")
            print(f"  POI DRIFT:    JSON ≠ recalc [{rb:.5f} – {rt:.5f}]")

        if r.get("h4_choch"):
            print(f"  4H CHoCH:     {r['h4_choch']} (aligned)")
        else:
            print("  4H CHoCH:     not aligned in last 80 bars")

        if r.get("flags"):
            print(f"  Flags:        {', '.join(r['flags'])}")

        print(f"  Verdict:      {r.get('verdict', '?')}")

    flagged = [r for r in results if r.get("flags")]
    print(f"\n{'=' * 72}")
    print(f"Summary: {len(results)} setup(s) audited, {len(flagged)} with flags")
    if flagged:
        print("Flagged symbols:", ", ".join(r["symbol"] for r in flagged))
    print("=" * 72)


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit Daily POI from monitoring_setups.json")
    parser.add_argument("--symbol", help="Audit single symbol only")
    parser.add_argument(
        "--symbols",
        help="Comma-separated symbols (skip JSON, audit from cache/live)",
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="Do not call cTrader — cache or JSON fields only",
    )
    parser.add_argument(
        "--no-json",
        action="store_true",
        help="Ignore monitoring_setups.json; use --symbols only",
    )
    parser.add_argument(
        "--monitoring-file",
        type=Path,
        default=MONITORING_FILE,
        help="Path to monitoring_setups.json",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        default=None,
        help="Write full report to file (recommended on Windows PowerShell)",
    )
    args = parser.parse_args()

    log_fp = None
    _console_out = sys.stdout
    if args.log_file:
        args.log_file.parent.mkdir(parents=True, exist_ok=True)
        log_fp = open(args.log_file, "w", encoding="utf-8")

    class _Tee:
        def __init__(self, *streams):
            self._streams = streams

        def write(self, data):
            for s in self._streams:
                if getattr(s, "closed", False):
                    continue
                s.write(data)

        def flush(self):
            for s in self._streams:
                if getattr(s, "closed", False):
                    continue
                s.flush()

        def isatty(self):
            return any(getattr(s, "isatty", lambda: False)() for s in self._streams)

    if log_fp:
        sys.stdout = _Tee(_console_out, log_fp)

    try:
        setups: List[dict] = []
        if not args.no_json:
            setups = load_monitoring_setups(args.monitoring_file)
            if setups:
                setups = [s for s in setups if s.get("status") in ACTIVE_STATUSES]
            elif not args.symbols and not args.symbol:
                print(f"Note: {args.monitoring_file} not found — use --symbols or run on VPS")

        if args.symbol:
            setups = [s for s in setups if s.get("symbol") == args.symbol.upper()]
            if not setups:
                setups = [{"symbol": args.symbol.upper(), "status": "SYMBOL_AUDIT"}]

        if args.symbols:
            for sym in args.symbols.split(","):
                sym = sym.strip().upper()
                if sym and not any(s.get("symbol") == sym for s in setups):
                    setups.append({"symbol": sym, "status": "CACHE_AUDIT"})

        if not setups:
            print("No setups to audit. Provide monitoring_setups.json or --symbols GBPNZD,BTCUSD")
            return 1

        detector = SMCDetector()
        results = [audit_setup(s, detector, json_only=args.json_only) for s in setups]
        print_audit_report(results)
        return 0
    finally:
        if log_fp:
            try:
                sys.stdout.flush()
            except Exception:
                pass
            sys.stdout = _console_out
            log_fp.close()
            print(f"Log saved: {args.log_file}")


if __name__ == "__main__":
    sys.exit(main())
