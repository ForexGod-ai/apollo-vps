"""Shared pip size utilities — V37.0 single source for RR/guard calculations."""

# V37.2: SL structural minim pe 4H — sub 30p = micro-stop (ex. AUDJPY 3.5p + lot 0.61)
MIN_SL_PIPS = 30
MAX_SL_PIPS = 100  # sniper cap (executor sentinel Guard#2)


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
