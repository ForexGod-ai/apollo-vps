"""Glitch in Matrix SMC detector — V67 C modular package."""

from smc_detector.models import (
    ActiveDealingRange,
    BOS,
    CHoCH,
    CRYPTO_MACRO_CEILING_LOOKBACK,
    CRYPTO_MACRO_CEILING_MIN_BARS,
    D1AuthContext,
    FVG,
    OrderBlock,
    POIResolution,
    StructuralRangeState,
    SwingPoint,
    TradeSetup,
)
from smc_detector.core_swings import CoreSwingsMixin
from smc_detector.core_structure import CoreStructureMixin
from smc_detector.d1_leg import D1LegMixin
from smc_detector.d1_authority import D1AuthorityMixin
from smc_detector.fvg import FvgMixin
from smc_detector.poi import PoiMixin
from smc_detector.w1 import W1Mixin
from smc_detector.scan_entry import ScanEntryMixin
from smc_detector.scan_setup import ScanSetupMixin
from smc_detector.scan_finalize import ScanFinalizeMixin
from smc_detector.scan import ScanOrchestratorMixin


class SMCDetector(
    W1Mixin,
    D1LegMixin,
    D1AuthorityMixin,
    PoiMixin,
    FvgMixin,
    CoreStructureMixin,
    CoreSwingsMixin,
    ScanFinalizeMixin,
    ScanSetupMixin,
    ScanOrchestratorMixin,
    ScanEntryMixin,
):
    """SMC detector facade — same public API as legacy monolith."""

    def __init__(self, swing_lookback: int = 10, atr_multiplier: float = 0.3):
        # ── V9.0 LOOKBACK ADAPTIV: base_lookback e ancora, lookback real calculat dinamic ──
        # V17.5: default=10 (restaurat) — inainte FW era hardcodat la 10 pentru Daily/4H/1H.
        # W1 detector este creat explicit cu SMCDetector(swing_lookback=3) in calculate_w1_bias.
        self.base_lookback = swing_lookback          # ancora (10 candle default)
        self.swing_lookback = swing_lookback         # runtime — folosit ca FRACTAL_WINDOW in detect_swing_*
        self.atr_multiplier = atr_multiplier         # ✅ V10.6: ATR ultra-relaxat (1.2→0.3) — Body Close Rule
        # Track FVG zones with trade count for ALL pairs (UNIVERSAL anti-overtrading)
        # Format: {symbol: [(top, bottom, date, trade_count), ...]}
        self.fvg_zones_tracker = {}  # UNIVERSAL for all pairs
        
        # 🎯 V3.4 ORDER BLOCKS PREPARATION: Store last 2 FVG zones per timeframe as "price magnets"
        # Format: {symbol: {'4H': [FVG, FVG]}}
        self.fvg_magnets = {}  # Zonele de întoarcere pentru preț

        # ⚡ V13.1 PERFORMANCE CACHE: Evită re-calcularea swing-urilor pentru același df
        # Key = (id(df), len(df)) — același obiect df, aceleași date → returnam cached
        # Clear la fiecare scan_for_setup() nou pentru a evita date stale
        self._swing_highs_cache: dict = {}  # {(id, len): List[SwingPoint]}
        self._swing_lows_cache:  dict = {}  # {(id, len): List[SwingPoint]}
        # V67 D: V11.9 unconfirmed CHoCH heuristic off in production (debug/audit may enable)
        self.enable_unconfirmed_guard = False

