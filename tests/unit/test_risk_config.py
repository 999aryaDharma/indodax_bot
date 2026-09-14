from config import RISK_CONFIG


def test_default_bull_rr_can_pass_gate() -> None:
    configured_rr = RISK_CONFIG.tp_atr_multiplier / RISK_CONFIG.sl_atr_multiplier
    assert configured_rr >= RISK_CONFIG.min_rr_ratio
