"""Shared pip size utilities — V37.0 single source for RR/guard calculations."""


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
