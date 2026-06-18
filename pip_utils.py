"""Shared pip size utilities — V37.0 single source for RR/guard calculations."""

# V37.2: SL structural minim pe 4H — sub 30p = micro-stop (ex. AUDJPY 3.5p + lot 0.61)
MIN_SL_PIPS = 30
MAX_SL_PIPS = 100  # sniper cap — forex default (executor sentinel Guard#2)


def get_max_sl_pips(symbol: str) -> float:
    """
    V40.6: SL maxim permis per instrument — aliniat cu Radar structural + Fix #7.
    BTC/XAU au SL mult peste 100p; cap-ul forex-only bloca EXECUTE_NOW valide.
    """
    s = symbol.upper()
    if any(x in s for x in ['BTC', 'ETH', 'LTC', 'XRP', 'ADA', 'DOGE']):
        return 2000.0
    if any(x in s for x in ['XAU', 'XAG', 'GOLD', 'SILVER']):
        return 500.0
    if any(x in s for x in ['XTI', 'WTI', 'OIL', 'BRENT', 'USOIL']):
        return 300.0
    if 'JPY' in s:
        return 150.0
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
