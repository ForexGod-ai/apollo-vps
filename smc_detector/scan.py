from __future__ import annotations

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from smc_detector.models import (
    ActiveDealingRange,
    BOS,
    CHoCH,
    D1AuthContext,
    FVG,
    OrderBlock,
    POIResolution,
    StructuralRangeState,
    SwingPoint,
    TradeSetup,
    CRYPTO_MACRO_CEILING_LOOKBACK,
    CRYPTO_MACRO_CEILING_MIN_BARS,
)



class ScanOrchestratorMixin:
    """V67 C: scan_for_setup entry."""

    def scan_for_setup(
        self, 
        symbol: str,
        df_daily: pd.DataFrame, 
        df_4h: pd.DataFrame,
        priority: int,
        require_4h_choch: bool = True,  # V3.0: Strict entry, V2.1: False for original logic
        skip_fvg_quality: bool = False,  # For backtesting: skip quality check to find more trades
        debug: bool = False,  # ✅ V10.4 FIX CRASH: param explicit — era UnboundLocalError!
        stored_poi_top: Optional[float] = None,  # V43.0: passive preserve signal (JSON in Etapa 2)
        stored_poi_bottom: Optional[float] = None,
        d1_ctx: Optional[D1AuthContext] = None,  # V67: cached D1 authority from scanner
    ) -> Optional[TradeSetup]:
        """
        Main scanner: Check if "Glitch in Matrix" setup exists
        
        FINAL LOGIC (V3.0 - CHoCH + BOS CORRECT USAGE):
        
        TWO SETUP TYPES:
        1. REVERSAL: Daily CHoCH (trend changes) + FVG + 4H CHoCH from pullback
        2. CONTINUITY: Daily BOS (trend continues) + FVG + 4H CHoCH from pullback
        
        V37.0 strategy_type: determinat EXCLUSIV de V25.0 UNIVERSAL BIAS (index CHoCH vs BOS).
        Nu există motor paralel — detect_strategy_type() a fost eliminat ca dead code.
        
        WHY 4H CHoCH FOR BOTH?
        - Confirms pullback finished
        - Confirms momentum returns to Daily direction
        - Safer entry (prevents SL hit during extended pullbacks)
        
        V3.0 GBP ADAPTIVE FILTERING:
        - Stricter FVG quality (≥70 vs ≥60)
        - Body dominance ≥70%
        
        Steps:
        1. Detect Daily CHoCH (REVERSAL) or Daily BOS (CONTINUITY)
        2. Find FVG after signal
        3. Check if price is retesting FVG
        4. Check 4H for CHoCH confirmation (pullback finished)
        5. Return complete setup
        """
        return self._scan_through_poi_validation(            symbol, df_daily, df_4h, priority, require_4h_choch,            skip_fvg_quality, debug, stored_poi_top, stored_poi_bottom, d1_ctx,        )
