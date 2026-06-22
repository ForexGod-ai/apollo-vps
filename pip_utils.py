"""Shared pip size utilities — V37.0 single source for RR/guard calculations."""

from typing import Optional, Union

# V37.2: SL structural minim pe 4H — sub 30p = micro-stop
MIN_SL_PIPS = 30
# V42.6: cap sniper forex — entry SL tipic 30–40p (ultimul pivot 4H)
MAX_SL_PIPS = 40
MAX_SL_PIPS_XAU = 30  # aur: max 30p structural sniper
MAX_SL_PIPS_ENERGY = 40


def get_max_sl_pips(symbol: str) -> float:
    """
    V42.6: SL maxim per instrument — sniper 4H structural (30–40p FX/XTI, 30p XAU).
    TP = pivot D1 (executor V40.8). BTC = excepție structurală largă.
    """
    s = symbol.upper()
    if any(x in s for x in ['BTC', 'ETH', 'LTC', 'XRP', 'ADA', 'DOGE']):
        return 2000.0
    if any(x in s for x in ['XAU', 'XAG', 'GOLD', 'SILVER']):
        return float(MAX_SL_PIPS_XAU)
    if any(x in s for x in ['XTI', 'WTI', 'OIL', 'BRENT', 'USOIL']):
        return float(MAX_SL_PIPS_ENERGY)
    if 'JPY' in s:
        return float(MAX_SL_PIPS)
    return float(MAX_SL_PIPS)


def get_pip_size(symbol: str) -> float:
    """Pip size per instrument — aliniat cu multi_tf_radar V36.3 / smc_detector."""
    s = symbol.upper()
    if any(x in s for x in ['XTI', 'WTI', 'OIL', 'BRENT', 'USOIL']):
        return 0.01
    if any(x in s for x in ['XAU', 'XAG', 'GOLD', 'SILVER']):
        return 0.10
    if any(x in s for x in ['BTC', 'ETH', 'XRP', 'LTC', 'ADA', 'DOGE']):
        return 1.0
    if 'JPY' in s:
        return 0.01
    return 0.0001


def get_asset_class(symbol: str) -> str:
    """Asset class for Telegram price formatting — aligned with smc_detector._get_asset_class."""
    s = (symbol or '').upper()
    if any(x in s for x in ['BTC', 'ETH', 'XRP', 'LTC', 'ADA', 'DOGE']):
        return 'crypto'
    if any(x in s for x in ['XAU', 'XAG', 'GOLD', 'SILVER']):
        return 'metals'
    if any(x in s for x in ['XTI', 'WTI', 'OIL', 'BRENT', 'USOIL']):
        return 'energy'
    if 'JPY' in s:
        return 'jpy_pairs'
    return 'forex'


def format_telegram_price(symbol: str, price: Union[float, int, str, None]) -> str:
    """
    V43.6 — Telegram display precision per asset class.
    crypto: int | metals: 1dp | energy: 2dp | jpy_pairs: 3dp | forex: 5dp
    """
    if price is None:
        return 'N/A'
    try:
        p = float(price)
    except (TypeError, ValueError):
        return str(price)

    cls = get_asset_class(symbol)
    if cls == 'crypto':
        return str(int(round(p)))
    if cls == 'forex':
        return f"{p:.5f}"
    if cls == 'jpy_pairs':
        return f"{p:.3f}"
    if cls == 'metals':
        return f"{p:.1f}"
    if cls == 'energy':
        return f"{p:.2f}"
    return f"{p:.5f}"


def format_telegram_fvg_range(
    symbol: str,
    bottom: Union[float, int, None],
    top: Union[float, int, None],
) -> str:
    """Formatted FVG/POI range for Telegram HTML."""
    return (
        f"{format_telegram_price(symbol, bottom)} – "
        f"{format_telegram_price(symbol, top)}"
    )


def format_swap_line(
    swap_val: Optional[Union[float, int]],
    *,
    triple_day: Optional[str] = 'Wed',
    prefix: str = '\n',
) -> str:
    """
    V43.6 — Swap row for Telegram alerts.
    Zero swap → neutral; non-zero → CREDIT/DEBIT.
    """
    if swap_val is None:
        return ''
    try:
        sv = float(swap_val)
    except (TypeError, ValueError):
        return ''
    triple_suffix = f" (3x {triple_day})" if triple_day else ''
    if abs(sv) < 1e-9:
        return f"{prefix}💱 SWAP: ⚪ NEUTRAL | 0.00 pips/day{triple_suffix}"
    swap_status = '✅ CREDIT' if sv > 0 else '⚠️ DEBIT'
    return f"{prefix}💱 SWAP: {swap_status} | {sv:+.2f} pips/day{triple_suffix}"


def sl_pips_between(symbol: str, entry: float, stop_loss: float) -> float:
    """Distance entry → SL in pips (always positive)."""
    if not entry or not stop_loss:
        return 0.0
    pip = get_pip_size(symbol)
    return abs(entry - stop_loss) / pip if pip > 0 else 0.0


def liquidity_already_swept(
    df,
    level: float,
    side: str,
    *,
    lookback: int = 15,
    tolerance: float = 0.0,
) -> bool:
    """
    V37.7: Lichiditate deja atinsa recent — nu o folosim ca TP.
    side 'low'  = swing low  (TP pentru SELL)
    side 'high' = swing high (TP pentru BUY)
    """
    if df is None or len(df) < 2 or level is None:
        return False
    window = df.iloc[-lookback:]
    lvl = float(level)
    if side == 'low':
        return float(window['low'].min()) <= lvl + tolerance
    return float(window['high'].max()) >= lvl - tolerance


def prices_direction_valid(
    direction: str,
    entry: float,
    stop_loss: float,
    take_profit: float = None,
) -> bool:
    """V37.8: SL/TP trebuie sa fie in directia corecta fata de entry."""
    if not entry or not stop_loss:
        return False
    try:
        entry_f = float(entry)
        sl_f = float(stop_loss)
    except (TypeError, ValueError):
        return False
    d = str(direction).lower()
    if d in ('sell', 'short'):
        if sl_f <= entry_f:
            return False
        if take_profit is not None and float(take_profit) >= entry_f:
            return False
    else:
        if sl_f >= entry_f:
            return False
        if take_profit is not None and float(take_profit) <= entry_f:
            return False
    return True


def sl_entry_magnitude_sane(symbol: str, entry: float, stop_loss: float) -> bool:
    """V37.8: Respinge SL corupt din JSON (ex. GBPNZD SL 1.38 la entry 2.30)."""
    if not entry or not stop_loss:
        return False
    try:
        entry_f = abs(float(entry))
        sl_f = abs(float(stop_loss))
    except (TypeError, ValueError):
        return False
    if entry_f <= 0:
        return False
    ratio = sl_f / entry_f
    s = symbol.upper()
    if any(x in s for x in ['BTC', 'ETH', 'XRP', 'LTC']):
        return 0.85 < ratio < 1.15
    if any(x in s for x in ['XAU', 'XAG', 'GOLD', 'SILVER']):
        return 0.90 < ratio < 1.10
    # FX / JPY — SL structural de obicei within ~8% of entry
    return 0.92 < ratio < 1.08
