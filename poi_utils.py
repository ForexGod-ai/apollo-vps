"""Shared POI box helpers — daily_scanner lifecycle + multi_tf_radar gate (V45 wick)."""
from typing import Optional


def price_in_poi_box(
    price: float,
    poi_bottom: Optional[float],
    poi_top: Optional[float],
) -> bool:
    """Preț live strict în caseta POI [poi_bottom, poi_top]."""
    if poi_bottom is None or poi_top is None:
        return False
    lo = min(float(poi_bottom), float(poi_top))
    hi = max(float(poi_bottom), float(poi_top))
    return lo <= float(price) <= hi


def poi_box_intersects_wick(
    candle_high: Optional[float],
    candle_low: Optional[float],
    poi_bottom: Optional[float],
    poi_top: Optional[float],
) -> bool:
    """Wick Daily intersectează POI — trigger pândă radar / lifecycle MONITORING."""
    if poi_bottom is None or poi_top is None:
        return False
    if candle_high is None or candle_low is None:
        return False
    lo = min(float(poi_bottom), float(poi_top))
    hi = max(float(poi_bottom), float(poi_top))
    return float(candle_low) <= hi and float(candle_high) >= lo


def poi_touch_active(
    price: Optional[float],
    poi_bottom: Optional[float],
    poi_top: Optional[float],
    d1_wick_high: Optional[float] = None,
    d1_wick_low: Optional[float] = None,
) -> bool:
    """V45: wick Daily ∩ POI sau preț în POI."""
    if poi_touch_via_wick(poi_bottom, poi_top, d1_wick_high, d1_wick_low):
        return True
    if price is not None and price_in_poi_box(price, poi_bottom, poi_top):
        return True
    return False


def poi_touch_via_wick(
    poi_bottom: Optional[float],
    poi_top: Optional[float],
    d1_wick_high: Optional[float],
    d1_wick_low: Optional[float],
) -> bool:
    return poi_box_intersects_wick(d1_wick_high, d1_wick_low, poi_bottom, poi_top)


def poi_bounds_from_stored(stored: dict) -> tuple[Optional[float], Optional[float]]:
    """POI top/bottom din JSON (poi_* sau fvg_* legacy)."""
    top = stored.get('poi_top') if stored.get('poi_top') is not None else stored.get('fvg_top')
    bottom = (
        stored.get('poi_bottom')
        if stored.get('poi_bottom') is not None
        else stored.get('fvg_bottom')
    )
    if top is None or bottom is None:
        return None, None
    return float(bottom), float(top)
