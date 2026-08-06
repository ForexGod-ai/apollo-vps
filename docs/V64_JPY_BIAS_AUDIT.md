# V64 — JPY D1 Bias Audit (HH/HL/LH/LL · BOS · CHoCH)

**Data audit:** 2026-08-06 · cache D1 ultim: ~2025-12-11 (stale vs live Aug 2026)

## Simptom

Toate perechile JPY arată **LONG** pe Telegram/JSON deși structura D1 s-a schimbat (CHoCH bearish sub HL major).

## Root cause #1 — CHoCH complet absent pe JPY (CRITICAL)

`detect_choch_and_bos()` aplica `filter_major_swings()` **înainte** de iterarea HH/HL/LH/LL.

Pe JPY în uptrend, `filter_major_swings()` marchează aproape **zero swing highs recente** ca majori (condiția: body-close sub prior low după high). Rezultat EURJPY:

| Set | Major Highs | CHoCH detectate |
|-----|-------------|-----------------|
| V63 (bug) | 3 highs @ bar 5,19,63 (~163) | **0 CHoCH** |
| V64 (fix) | iterate geometric swings | **9 CHoCH** |

Fără CHoCH, pipeline-ul cădea pe **ultimul BOS** sau leg vechi → bias incorect / blocat pe LONG.

**Fix V64:** iterare pe **toate** swing-urile geometrice; pivoții majori rămân pentru `_find_leg_choch`, `_major_reversal_confirmed`, `compute_structural_range`.

## Root cause #2 — `daily_choch.direction` vs `d1_bias_direction`

`TradeSetup.daily_choch` = ultimul semnal (BOS sau CHoCH), **nu** bias-ul canonic D1.
`daily_scanner.py` folosea `setup.daily_choch.direction` pentru Telegram drift, swap, gates → drift LONG/SHORT greșit.

**Fix V64:** helper `_setup_d1_trend()` / `_setup_trade_direction()` peste tot.

## Root cause #3 — identity lock bloca flip-ul

`setup_identity_lock` putea păstra direcția LONG din JSON chiar când `resolve_authoritative_d1_bias()` zicea SHORT.

**Fix V64:** la contradicție, **auth D1 canonic** câștigă întotdeauna (`[V64 AUTH FLIP]`).

## Root cause #4 — cache stale

Cache local EURJPY se termină **2025-12-11** (close 182.92). Ultimul CHoCH valid pe cache = **bullish @218** → LONG corect *pentru acele bare*.

Pe chart live Aug 2026, după rally, un **CHoCH bearish nou** (sub HL major) nu există în cache → VPS trebuie **rescan live** cu cTrader pornit.

## Verificare post-fix (cache)

```
EURJPY: 9 CHoCH | ultim flip bullish@218 | auth=buy (continuation)
AUDJPY: 12 CHoCH | ultim flip bullish@235 | auth=buy
GBPJPY: 9 CHoCH | ultim flip bullish@254 | auth=buy
USDJPY: 0 CHoCH filtrate V40 | auth=sell (ultim BOS bearish)
```

CHoCH bearish @173/@211 există în serie — la momentul acelui bar → **REVERSAL SELL** (V42.6 fără BOS post-leg).

## Acțiuni VPS

1. Deploy branch `cursor/v36-3-radar-live-sync` + commit V64
2. Pornește DATA-Market cBot (port 8010)
3. Rulează scan zilnic / `daily_scanner.py` — rehydrate + V64 AUTH FLIP actualizează JSON
4. Verifică: `python scripts/audit_structural_classification.py --symbol EURJPY AUDJPY GBPJPY`

## Fișiere modificate V64

- `smc_detector.py` — detect_choch_and_bos, macro_trend_from_swings fallback
- `daily_scanner.py` — _setup_d1_trend, V64 AUTH FLIP
- `tests/test_v63_jpy_chf_bias.py` — CHoCH detection + reversal moment tests
