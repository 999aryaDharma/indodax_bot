def test_baseline_modules_import() -> None:
    import config
    import indodax_api
    import risk_manager
    import signal_logic

    assert config.APP_CONFIG.app_name == "IndoBot Signal (IBS)"
    assert callable(indodax_api.fetch_ohlcv)
    assert callable(risk_manager.calculate_trading_plan)
    assert callable(signal_logic.evaluate_signal)
