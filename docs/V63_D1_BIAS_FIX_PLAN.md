# V63 — D1 Bias Fix (Canonical SMC)

**Referință:** [`SMC_ALIGNMENT_AUDIT_GIM.md`](SMC_ALIGNMENT_AUDIT_GIM.md)  
**Status:** Implementat pe branch `cursor/v36-3-radar-live-sync`

## Reguli canonice (Pas 1)

| Context macro | Body-close | Semnal | strategy_type | direction |
|---------------|------------|--------|---------------|-----------|
| Bullish (HL majori) | peste high major | BOS bullish | continuation | buy |
| Bullish | sub low major (HL) | CHoCH bearish | reversal | sell |
| Bearish (LH majori) | sub low major | BOS bearish | continuation | sell |
| Bearish | peste high major (LH) | CHoCH bullish | reversal | buy |

**V42.6:** leg CHoCH macro-valid + ≥1 BOS post-leg same-dir → CONTINUITY; altfel → REVERSAL.

## Modificări V63

1. `detect_choch_and_bos` — pivoți majori; `prev_trend` din `macro_trend_from_swings`
2. `_find_leg_choch` — ultimul flip major confirmat (`_major_reversal_confirmed`)
3. `_resolve_d1_leg` — V42.6 pur; fără `_coerce_d1_bias_to_major_structure`
4. `compute_structural_range` — pivoți majori; `locked_bias` respectă macro_trend
5. Pipeline unic Scanner → JSON → Telegram

## Acceptance

| Symbol | direction | strategy_type |
|--------|-----------|---------------|
| EURJPY | sell | reversal* |
| AUDJPY | sell | reversal* |
| USDCHF | buy | continuation |

\* REVERSAL la momentul CHoCH; CONTINUATION după ≥1 BOS post-leg (V42.6).
