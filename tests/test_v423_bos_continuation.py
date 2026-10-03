"""V42.3 executor: BOS allowed on CONTINUATION setups."""
from setup_executor_monitor import SetupExecutorMonitor


def test_v423_accepts_bos_on_continuation():
    setup = {
        "direction": "buy",
        "strategy_type": "CONTINUATION",
        "radar_4h_bos_detected": True,
        "radar_4h_bos_direction": "bullish",
        "radar_4h_choch_detected": False,
    }
    ok, detail = SetupExecutorMonitor._v423_structural_sync_ok(setup)
    assert ok is True
    assert detail == ""


def test_v423_still_requires_choch_on_reversal():
    setup = {
        "direction": "buy",
        "strategy_type": "REVERSAL",
        "radar_4h_bos_detected": True,
        "radar_4h_bos_direction": "bullish",
        "radar_4h_choch_detected": False,
    }
    ok, detail = SetupExecutorMonitor._v423_structural_sync_ok(setup)
    assert ok is False
    assert detail == "missing"
