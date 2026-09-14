import asyncio
import importlib
import sqlite3
import sys
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest


def _load_observer_module():
    sys.modules.pop("signal_observer", None)
    return importlib.import_module("signal_observer")


def test_records_evaluated_candidate_without_manual_callback(tmp_path: Path) -> None:
    module = _load_observer_module()
    db_path = tmp_path / "observations.db"
    observer = module.SignalObserver(db_path=db_path, clock=lambda: 1_723_456_789.0)

    observation_id = observer.record_candidate(
        pair="btc_idr",
        strategy="SNIPER",
        strategy_version="signal_logic_v1",
        score=0.82,
        passed=False,
        reason="score below gate",
        dataset_version="live_ohlcv_v1",
        runtime_version="ibs_runtime_v1",
    )

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM signal_observations WHERE id = ?", (observation_id,)
        ).fetchone()
        callback_count = conn.execute(
            "SELECT COUNT(*) FROM signal_action_intents"
        ).fetchone()[0]

    stored = dict(row)
    assert len(stored.pop("decision_key")) == 64
    assert stored == {
        "id": observation_id,
        "decision_ts": 1_723_456_789.0,
        "decision_bar_id": 1_723_455_900,
        "first_eligible_bar_id": 1_723_456_800,
        "pair": "btc_idr",
        "strategy": "SNIPER",
        "strategy_version": "signal_logic_v1",
        "score": 0.82,
        "passed": 0,
        "reason": "score below gate",
        "planned_entry": None,
        "planned_stop_loss": None,
        "planned_take_profit": None,
        "planned_position_idr": None,
        "dataset_version": "live_ohlcv_v1",
        "runtime_version": "ibs_runtime_v1",
        "shadow_policy_version": "shadow_policy_v1",
        "shadow_status": "NOT_OPENED",
        "last_processed_bar_id": 1_723_455_900,
        "outcome": None,
        "outcome_price": None,
        "outcome_ts": None,
    }
    assert callback_count == 0


def test_replaying_same_decision_bar_returns_existing_observation(tmp_path: Path) -> None:
    module = _load_observer_module()
    db_path = tmp_path / "observations.db"
    observer = module.SignalObserver(db_path=db_path, clock=lambda: 1_001.0)
    values = dict(
        pair="btc_idr",
        strategy="SNIPER",
        strategy_version="signal_logic_v1",
        score=0.82,
        passed=False,
        reason="15m confirmation failed",
        dataset_version="live_ohlcv_v1",
        runtime_version="ibs_runtime_v1",
    )

    first = observer.record_candidate(**values)
    second = observer.record_candidate(**values)

    with sqlite3.connect(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM signal_observations").fetchone()[0]
        identity = conn.execute(
            "SELECT decision_bar_id, first_eligible_bar_id, decision_key "
            "FROM signal_observations WHERE id = ?",
            (first,),
        ).fetchone()
    assert second == first
    assert count == 1
    assert identity[0:2] == (900, 1800)
    assert identity[2]


def test_conflicting_decision_payload_fails_closed_without_reusing_stale_row(
    tmp_path: Path,
) -> None:
    module = _load_observer_module()
    db_path = tmp_path / "observations.db"
    observer = module.SignalObserver(db_path=db_path, clock=lambda: 1_001.0)
    common = dict(
        pair="btc_idr",
        strategy="SNIPER",
        strategy_version="signal_logic_v1",
        dataset_version="live_ohlcv_v1",
        runtime_version="ibs_runtime_v1",
    )
    rejected_id = observer.record_candidate(
        **common,
        score=0.79,
        passed=False,
        reason="15m confirmation failed",
    )

    with pytest.raises(ValueError, match="conflicting decision payload"):
        observer.record_candidate(
            **common,
            score=0.82,
            passed=True,
            reason="all gates passed",
            planned_entry=100,
            planned_stop_loss=90,
            planned_take_profit=110,
            planned_position_idr=50_000,
        )

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT id, passed, reason, planned_entry, shadow_status "
            "FROM signal_observations"
        ).fetchall()
    assert rows == [
        (rejected_id, 0, "15m confirmation failed", None, "NOT_OPENED")
    ]


def test_plan_is_persisted_when_shadow_policy_is_disabled(tmp_path: Path) -> None:
    module = _load_observer_module()
    db_path = tmp_path / "observations.db"
    observer = module.SignalObserver(db_path=db_path, clock=lambda: 1_800.0)

    observation_id = observer.record_candidate(
        pair="eth_idr",
        strategy="BREAKOUT",
        strategy_version="signal_logic_v1",
        score=0.9,
        passed=True,
        reason="all gates passed",
        planned_entry=100,
        planned_stop_loss=90,
        planned_take_profit=110,
        planned_position_idr=50_000,
        dataset_version="live_ohlcv_v1",
        runtime_version="ibs_runtime_v1",
    )

    with sqlite3.connect(db_path) as conn:
        stored = conn.execute(
            "SELECT planned_entry, planned_stop_loss, planned_take_profit, "
            "planned_position_idr, shadow_status, first_eligible_bar_id, "
            "last_processed_bar_id, shadow_policy_version "
            "FROM signal_observations WHERE id = ?",
            (observation_id,),
        ).fetchone()
    assert stored == (
        100.0, 90.0, 110.0, 50_000.0, "NOT_OPENED", 1800, 900,
        "shadow_policy_v1",
    )


def test_observer_v1_schema_migrates_backup_first_and_idempotently(
    tmp_path: Path,
) -> None:
    module = _load_observer_module()
    db_path = tmp_path / "observations.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE signal_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_ts REAL NOT NULL, pair TEXT NOT NULL,
                strategy TEXT NOT NULL, strategy_version TEXT NOT NULL,
                score REAL NOT NULL, passed INTEGER NOT NULL,
                reason TEXT NOT NULL, planned_entry REAL,
                planned_stop_loss REAL, planned_take_profit REAL,
                dataset_version TEXT NOT NULL, runtime_version TEXT NOT NULL,
                shadow_status TEXT NOT NULL, last_processed_bar_id INTEGER,
                outcome TEXT, outcome_price REAL, outcome_ts REAL
            )
        """)
        conn.execute("""
            INSERT INTO signal_observations (
                decision_ts, pair, strategy, strategy_version, score, passed,
                reason, dataset_version, runtime_version, shadow_status
            ) VALUES (1001, 'btc_idr', 'SNIPER', 'v1', 0.8, 0, 'old',
                      'dataset-v1', 'runtime-v1', 'NOT_OPENED')
        """)

    module.SignalObserver(db_path=db_path)
    backup = db_path.with_name(f"{db_path.name}.pre-signal-observer-v2.bak")
    first_mtime = backup.stat().st_mtime_ns
    module.SignalObserver(db_path=db_path)

    assert backup.exists()
    assert backup.stat().st_mtime_ns == first_mtime
    with sqlite3.connect(db_path) as conn:
        migrated = conn.execute(
            "SELECT decision_bar_id, first_eligible_bar_id, decision_key, "
            "shadow_policy_version FROM signal_observations WHERE id=1"
        ).fetchone()
    with sqlite3.connect(backup) as conn:
        backup_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(signal_observations)")
        }
    assert migrated == (900, 1800, "legacy:1", "shadow_policy_v1")
    assert "decision_key" not in backup_columns


def test_observer_migration_enforces_action_intent_foreign_key(tmp_path: Path) -> None:
    module = _load_observer_module()
    db_path = tmp_path / "observations.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE signal_observations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                decision_ts REAL NOT NULL, pair TEXT NOT NULL,
                strategy TEXT NOT NULL, strategy_version TEXT NOT NULL,
                score REAL NOT NULL, passed INTEGER NOT NULL,
                reason TEXT NOT NULL, dataset_version TEXT NOT NULL,
                runtime_version TEXT NOT NULL, shadow_status TEXT NOT NULL
            )
        """)

    observer = module.SignalObserver(db_path=db_path)

    with observer._connect() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("""
                INSERT INTO signal_action_intents (
                    observation_id, action, action_ts, source
                ) VALUES (999, 'SKIP', 0, 'test')
            """)


def test_manual_action_intent_is_separate_from_observation_creation(
    tmp_path: Path,
) -> None:
    module = _load_observer_module()
    db_path = tmp_path / "observations.db"
    observer = module.SignalObserver(db_path=db_path, clock=lambda: 1234.0)
    observation_id = observer.record_candidate(
        pair="eth_idr",
        strategy="BREAKOUT",
        strategy_version="signal_logic_v1",
        score=0.9,
        passed=True,
        reason="signal gate passed",
        dataset_version="live_ohlcv_v1",
        runtime_version="ibs_runtime_v1",
    )

    observer.record_action_intent(
        observation_id=observation_id,
        action="PAPER",
        source="telegram_callback",
    )

    with sqlite3.connect(db_path) as conn:
        observations = conn.execute(
            "SELECT COUNT(*) FROM signal_observations"
        ).fetchone()[0]
        intent = conn.execute(
            "SELECT observation_id, action, action_ts, source "
            "FROM signal_action_intents"
        ).fetchone()
    assert observations == 1
    assert intent == (observation_id, "PAPER", 1234.0, "telegram_callback")


def test_shadow_outcome_uses_closed_15m_bar_and_is_restart_idempotent(
    tmp_path: Path,
) -> None:
    module = _load_observer_module()
    db_path = tmp_path / "observations.db"
    now = [3_000.0]
    bars = [
        # Open before a mid-bar decision; its range is never eligible.
        SimpleNamespace(timestamp=2700, high=150.0, low=50.0),
        SimpleNamespace(timestamp=3600, high=112.0, low=88.0),
    ]
    fetch_calls: list[tuple[str, str]] = []

    def fetch_candles(pair: str, timeframe: str):
        fetch_calls.append((pair, timeframe))
        return bars

    observer = module.SignalObserver(
        db_path=db_path,
        clock=lambda: now[0],
        candle_fetcher=fetch_candles,
        shadow_enabled=True,
    )
    observation_id = observer.record_candidate(
        pair="btc_idr",
        strategy="SNIPER",
        strategy_version="signal_logic_v1",
        score=0.82,
        passed=True,
        reason="signal gate passed",
        planned_entry=100,
        planned_stop_loss=90,
        planned_take_profit=110,
        planned_position_idr=50_000,
        dataset_version="live_ohlcv_v1",
        runtime_version="ibs_runtime_v1",
    )

    # Eligible bar 3600 is not final until t=4500.
    assert observer.monitor_all() == []
    now[0] = 4_501.0
    events = observer.monitor_all()

    assert events == [{
        "observation_id": observation_id,
        "pair": "btc_idr",
        "reason": "SL",
        "price": 90,
        "bar_id": 3600,
    }]
    assert fetch_calls == [("btc_idr", "15m"), ("btc_idr", "15m")]
    with sqlite3.connect(db_path) as conn:
        outcome = conn.execute(
            "SELECT shadow_status, last_processed_bar_id, outcome, "
            "outcome_price, outcome_ts FROM signal_observations WHERE id = ?",
            (observation_id,),
        ).fetchone()
    assert outcome == ("CLOSED", 3600, "SL", 90.0, 4500.0)

    restarted = module.SignalObserver(
        db_path=db_path,
        clock=lambda: now[0],
        candle_fetcher=fetch_candles,
    )
    assert restarted.monitor_all() == []


def test_shadow_decision_at_boundary_accepts_the_newly_closed_bar(
    tmp_path: Path,
) -> None:
    module = _load_observer_module()
    now = [1_800.0]
    observer = module.SignalObserver(
        db_path=tmp_path / "observations.db",
        clock=lambda: now[0],
        candle_fetcher=lambda _pair, _tf: [
            SimpleNamespace(timestamp=1_800, high=111.0, low=95.0)
        ],
        shadow_enabled=True,
    )
    observation_id = observer.record_candidate(
        pair="btc_idr",
        strategy="SNIPER",
        strategy_version="signal_logic_v1",
        score=0.82,
        passed=True,
        reason="all gates passed",
        planned_entry=100,
        planned_stop_loss=90,
        planned_take_profit=110,
        planned_position_idr=50_000,
        dataset_version="live_ohlcv_v1",
        runtime_version="ibs_runtime_v1",
    )
    now[0] = 2_700.0

    assert observer.monitor_all() == [{
        "observation_id": observation_id,
        "pair": "btc_idr",
        "reason": "TP",
        "price": 110,
        "bar_id": 1_800,
    }]


def test_conflicting_duplicate_bar_fails_closed_without_checkpoint(
    tmp_path: Path,
) -> None:
    module = _load_observer_module()
    db_path = tmp_path / "observations.db"
    bars = [
        SimpleNamespace(timestamp=1800, open=100, high=109, low=91, close=100, volume=1),
        SimpleNamespace(timestamp=1800, open=100, high=112, low=88, close=100, volume=1),
    ]
    now = [1_800.0]
    observer = module.SignalObserver(
        db_path=db_path,
        clock=lambda: now[0],
        candle_fetcher=lambda _pair, _tf: bars,
        shadow_enabled=True,
    )
    observation_id = observer.record_candidate(
        pair="btc_idr", strategy="SNIPER", strategy_version="signal_logic_v1",
        score=0.82, passed=True, reason="all gates passed",
        planned_entry=100, planned_stop_loss=90, planned_take_profit=110,
        planned_position_idr=50_000, dataset_version="live_ohlcv_v1",
        runtime_version="ibs_runtime_v1",
    )
    now[0] = 2_701.0

    assert observer.monitor_all() == []
    with sqlite3.connect(db_path) as conn:
        state = conn.execute(
            "SELECT shadow_status, last_processed_bar_id "
            "FROM signal_observations WHERE id=?", (observation_id,)
        ).fetchone()
    assert state == ("OPEN", 900)


def test_identical_out_of_order_duplicates_are_processed_once_in_bar_order(
    tmp_path: Path,
) -> None:
    module = _load_observer_module()
    now = [1_800.0]
    no_touch = SimpleNamespace(
        timestamp=1800, open=100, high=109, low=91, close=100, volume=1
    )
    bars = [
        SimpleNamespace(
            timestamp=2700, open=100, high=112, low=95, close=110, volume=2
        ),
        no_touch,
        no_touch,
    ]
    observer = module.SignalObserver(
        db_path=tmp_path / "observations.db",
        clock=lambda: now[0], candle_fetcher=lambda _pair, _tf: bars,
        shadow_enabled=True,
    )
    observation_id = observer.record_candidate(
        pair="btc_idr", strategy="SNIPER", strategy_version="v1", score=0.8,
        passed=True, reason="all gates passed", planned_entry=100,
        planned_stop_loss=90, planned_take_profit=110,
        planned_position_idr=50_000, dataset_version="dataset-v1",
        runtime_version="runtime-v1",
    )
    now[0] = 3_601.0

    events = observer.monitor_all()

    assert events[0]["reason"] == "TP"
    assert events[0]["bar_id"] == 2700
    with sqlite3.connect(tmp_path / "observations.db") as conn:
        assert conn.execute(
            "SELECT last_processed_bar_id FROM signal_observations WHERE id=?",
            (observation_id,),
        ).fetchone() == (2700,)


def test_shadow_policy_can_keep_passing_candidate_closed(tmp_path: Path) -> None:
    module = _load_observer_module()
    observer = module.SignalObserver(
        db_path=tmp_path / "observations.db",
        clock=lambda: 1_000.0,
        shadow_enabled=False,
    )
    observation_id = observer.record_candidate(
        pair="sol_idr",
        strategy="SNIPER",
        strategy_version="signal_logic_v1",
        score=0.75,
        passed=True,
        reason="signal gate passed",
        dataset_version="live_ohlcv_v1",
        runtime_version="ibs_runtime_v1",
    )

    opened = observer.open_shadow(
        observation_id=observation_id,
        entry_price=100,
        stop_loss=90,
        take_profit=110,
        last_closed_bar_id=0,
    )

    assert opened is False


def test_paper_trader_uses_closed_bar_range_and_persists_bar_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import config

    db_path = tmp_path / "paper.db"
    monkeypatch.setattr(
        config,
        "PAPER_CONFIG",
        replace(config.PAPER_CONFIG, db_path=str(db_path)),
    )
    sys.modules.pop("paper_trader", None)
    module = importlib.import_module("paper_trader")
    now = [3_000.0]
    bars = [
        SimpleNamespace(timestamp=2_700, high=150.0, low=50.0),
        SimpleNamespace(timestamp=3_600, high=112.0, low=88.0),
    ]
    calls: list[tuple[str, str]] = []

    def fetch_candles(pair: str, timeframe: str):
        calls.append((pair, timeframe))
        return bars

    trader = module.PaperTrader(
        clock=lambda: now[0],
        candle_fetcher=fetch_candles,
    )
    trade_id = trader.open_trade(
        pair="btc_idr",
        entry_price=100,
        stop_loss=90,
        take_profit=110,
        position_idr=100_000,
        score_pct=82,
    )

    # The partially elapsed 2700 bar is permanently ineligible.
    assert trader.monitor_all() == []
    now[0] = 4_501.0
    events = trader.monitor_all()

    assert len(events) == 1
    assert events[0]["type"] == "PAPER_SL"
    assert events[0]["price"] == 90
    with sqlite3.connect(db_path) as conn:
        trade = conn.execute(
            "SELECT closed, close_reason, close_price FROM paper_trades WHERE id = ?",
            (trade_id,),
        ).fetchone()
        state = conn.execute(
            "SELECT last_processed_bar_id FROM paper_trade_bar_state "
            "WHERE trade_id = ?",
            (trade_id,),
        ).fetchone()
    assert trade == (1, "SL", 90.0)
    assert state == (3600,)
    assert calls == [("btc_idr", "15m"), ("btc_idr", "15m")]

    restarted = module.PaperTrader(
        clock=lambda: now[0],
        candle_fetcher=fetch_candles,
    )
    assert restarted.monitor_all() == []
    sys.modules.pop("paper_trader", None)


def test_paper_bar_is_retried_when_close_does_not_commit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import config

    db_path = tmp_path / "paper-close-retry.db"
    monkeypatch.setattr(
        config,
        "PAPER_CONFIG",
        replace(config.PAPER_CONFIG, db_path=str(db_path)),
    )
    sys.modules.pop("paper_trader", None)
    module = importlib.import_module("paper_trader")
    now = [3_000.0]
    trader = module.PaperTrader(
        clock=lambda: now[0],
        candle_fetcher=lambda _pair, _tf: [
            SimpleNamespace(timestamp=3_600, high=112.0, low=88.0)
        ],
    )
    trade_id = trader.open_trade(
        pair="btc_idr",
        entry_price=100,
        stop_loss=90,
        take_profit=110,
        position_idr=100_000,
        score_pct=82,
    )
    now[0] = 4_501.0
    original_close = trader.close_trade
    monkeypatch.setattr(trader, "close_trade", lambda *_args: None)

    assert trader.monitor_all() == []
    with sqlite3.connect(db_path) as conn:
        state_after_failure = conn.execute(
            "SELECT last_processed_bar_id FROM paper_trade_bar_state "
            "WHERE trade_id = ?",
            (trade_id,),
        ).fetchone()
    assert state_after_failure == (2_700,)

    monkeypatch.setattr(trader, "close_trade", original_close)
    events = trader.monitor_all()
    assert len(events) == 1
    assert events[0]["type"] == "PAPER_SL"
    sys.modules.pop("paper_trader", None)


def test_paper_close_and_bar_checkpoint_roll_back_together(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import config

    db_path = tmp_path / "paper-atomic-checkpoint.db"
    monkeypatch.setattr(
        config, "PAPER_CONFIG", replace(config.PAPER_CONFIG, db_path=str(db_path))
    )
    sys.modules.pop("paper_trader", None)
    module = importlib.import_module("paper_trader")
    now = [3_000.0]
    trader = module.PaperTrader(
        clock=lambda: now[0],
        candle_fetcher=lambda _pair, _tf: [
            SimpleNamespace(timestamp=3_600, high=112.0, low=88.0)
        ],
    )
    trade_id = trader.open_trade(
        "btc_idr", 100, 90, 110, 100_000, 82
    )
    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TRIGGER fail_bar_checkpoint
            BEFORE UPDATE ON paper_trade_bar_state
            WHEN NEW.last_processed_bar_id = 3600
            BEGIN
                SELECT RAISE(ABORT, 'checkpoint failed');
            END
        """)
    now[0] = 4_501.0

    assert trader.monitor_all() == []
    with sqlite3.connect(db_path) as conn:
        trade = conn.execute(
            "SELECT closed FROM paper_trades WHERE id=?", (trade_id,)
        ).fetchone()
        state = conn.execute(
            "SELECT last_processed_bar_id FROM paper_trade_bar_state WHERE trade_id=?",
            (trade_id,),
        ).fetchone()
        conn.execute("DROP TRIGGER fail_bar_checkpoint")
    assert trade == (0,)
    assert state == (2700,)

    assert len(trader.monitor_all()) == 1


def test_paper_connection_enforces_bar_state_foreign_key(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import config

    db_path = tmp_path / "paper-fk.db"
    monkeypatch.setattr(
        config, "PAPER_CONFIG", replace(config.PAPER_CONFIG, db_path=str(db_path))
    )
    sys.modules.pop("paper_trader", None)
    module = importlib.import_module("paper_trader")

    with module._get_conn() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO paper_trade_bar_state "
                "(trade_id, first_eligible_bar_id, last_processed_bar_id) "
                "VALUES (999, 0, -900)"
            )


def test_paper_conflicting_duplicate_does_not_advance_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import config

    db_path = tmp_path / "paper-conflict.db"
    monkeypatch.setattr(
        config, "PAPER_CONFIG", replace(config.PAPER_CONFIG, db_path=str(db_path))
    )
    sys.modules.pop("paper_trader", None)
    module = importlib.import_module("paper_trader")
    now = [1_800.0]
    bars = [
        SimpleNamespace(timestamp=1800, open=100, high=109, low=91, close=100, volume=1),
        SimpleNamespace(timestamp=1800, open=100, high=112, low=88, close=100, volume=1),
    ]
    trader = module.PaperTrader(
        clock=lambda: now[0], candle_fetcher=lambda _pair, _tf: bars
    )
    trade_id = trader.open_trade("btc_idr", 100, 90, 110, 100_000, 82)
    now[0] = 2_701.0

    assert trader.monitor_all() == []
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT last_processed_bar_id FROM paper_trade_bar_state WHERE trade_id=?",
            (trade_id,),
        ).fetchone() == (900,)


def test_process_pair_opens_observation_before_telegram_callback(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_observer_module()
    db_path = tmp_path / "observations.db"
    observer = module.SignalObserver(
        db_path=db_path,
        clock=lambda: 10_000.0,
        shadow_enabled=True,
    )
    sys.modules.pop("main", None)
    main = importlib.import_module("main")

    strategy = SimpleNamespace(value="SNIPER")
    market_mode = SimpleNamespace(value="BULL_TREND")
    decision = SimpleNamespace(
        pair="btc_idr",
        should_signal=True,
        rejection_reason="",
        strategy=strategy,
        market_mode=market_mode,
        score=0.82,
        score_pct=82,
    )
    plan = SimpleNamespace(
        entry_price=100.0,
        stop_loss=90.0,
        take_profit=110.0,
        sl_pct=-10.0,
        tp_pct=10.0,
        risk_reward_ratio=1.0,
        position_idr=100_000.0,
        position_pct=20.0,
        estimated_coin=1_000.0,
        max_risk_idr=10_000.0,
        atr_value=10.0,
    )
    balance = SimpleNamespace(idr_available=500_000.0, idr_total=500_000.0)
    tracker = SimpleNamespace(has_open_position=lambda _pair: False)

    monkeypatch.setattr(main, "fetch_ohlcv", lambda _pair, _tf: [object()] * 60)
    monkeypatch.setattr(main, "calculate", lambda *_args: object())
    monkeypatch.setattr(main, "evaluate_signal", lambda **_kwargs: decision)
    monkeypatch.setattr(main, "confirm_entry_15m", lambda _ta: True)
    monkeypatch.setattr(main, "is_pair_already_held", lambda _pair: False)
    monkeypatch.setattr(main, "fetch_wallet_balance", lambda: balance)
    monkeypatch.setattr(main, "calculate_trading_plan", lambda *_args: plan)

    callback_observation_ids = []

    async def telegram_failure(_decision, _plan, *, observation_id):
        callback_observation_ids.append(observation_id)
        return None

    monkeypatch.setattr(main, "send_signal", telegram_failure)

    asyncio.run(
        main._process_pair(
            "btc_idr",
            observer=observer,
            tracker_instance=tracker,
        )
    )

    with sqlite3.connect(db_path) as conn:
        row = conn.execute("""
            SELECT pair, strategy, strategy_version, score, passed, reason,
                   planned_entry, planned_stop_loss, planned_take_profit,
                   dataset_version, runtime_version, shadow_status
            FROM signal_observations
        """).fetchone()
    assert row == (
        "btc_idr",
        "SNIPER",
        "signal_logic_v1",
        0.82,
        1,
        "all gates passed",
        100.0,
        90.0,
        110.0,
        "live_ohlcv_v1",
        "ibs_runtime_v1",
        "OPEN",
    )
    assert callback_observation_ids == [1]


def test_process_pair_persists_later_gate_failure_as_one_final_row(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_observer_module()
    db_path = tmp_path / "observations.db"
    observer = module.SignalObserver(
        db_path=db_path,
        clock=lambda: 10_001.0,
        shadow_enabled=True,
    )
    sys.modules.pop("main", None)
    main = importlib.import_module("main")
    decision = SimpleNamespace(
        pair="btc_idr",
        should_signal=True,
        rejection_reason="",
        strategy=SimpleNamespace(value="SNIPER"),
        market_mode=SimpleNamespace(value="BULL_TREND"),
        score=0.82,
        score_pct=82,
    )
    tracker = SimpleNamespace(has_open_position=lambda _pair: False)
    monkeypatch.setattr(main, "fetch_ohlcv", lambda _pair, _tf: [object()] * 60)
    monkeypatch.setattr(main, "calculate", lambda *_args: object())
    monkeypatch.setattr(main, "evaluate_signal", lambda **_kwargs: decision)
    monkeypatch.setattr(main, "confirm_entry_15m", lambda _ta: False)

    asyncio.run(main._process_pair(
        "btc_idr", observer=observer, tracker_instance=tracker
    ))

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT passed, reason, planned_entry, shadow_status "
            "FROM signal_observations"
        ).fetchall()
    assert rows == [(0, "15m confirmation failed", None, "NOT_OPENED")]


class _FakeQuery:
    def __init__(self, data: str) -> None:
        self.data = data
        self.message = SimpleNamespace(message_id=7, chat_id=123, text="signal")
        self.answers: list[tuple[str | None, bool]] = []

    async def answer(self, text=None, show_alert=False) -> None:
        self.answers.append((text, show_alert))

    async def edit_message_reply_markup(self, **_kwargs) -> None:
        return None

    async def edit_message_text(self, **_kwargs) -> None:
        return None


class _FakeBot:
    async def send_message(self, **_kwargs) -> None:
        return None


def test_actual_telegram_callbacks_persist_intent_before_downstream_action(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observer_module = _load_observer_module()
    now = [900.0]
    observer = observer_module.SignalObserver(
        db_path=tmp_path / "observations.db", clock=lambda: now[0]
    )
    ids = []
    for pair in ("btc_idr", "eth_idr", "sol_idr"):
        ids.append(observer.record_candidate(
            pair=pair, strategy="SNIPER", strategy_version="signal_logic_v1",
            score=0.8, passed=True, reason="all gates passed",
            planned_entry=100, planned_stop_loss=90, planned_take_profit=110,
            planned_position_idr=50_000, dataset_version="live_ohlcv_v1",
            runtime_version="ibs_runtime_v1",
        ))
        now[0] += 900
    observer_module.set_runtime_observer(observer)
    telegram = importlib.import_module("telegram_bot")

    tracker_module = ModuleType("position_tracker")
    tracker_module.tracker = SimpleNamespace(open_position=lambda *_args: None)
    monkeypatch.setitem(sys.modules, "position_tracker", tracker_module)
    paper_module = ModuleType("paper_trader")
    paper_module.paper_trader = SimpleNamespace(open_trade=lambda *_args: 42)
    monkeypatch.setitem(sys.modules, "paper_trader", paper_module)
    context = SimpleNamespace(bot=_FakeBot())

    asyncio.run(telegram.callback_exec(
        SimpleNamespace(callback_query=_FakeQuery(f"exec:{ids[0]}")), context
    ))
    asyncio.run(telegram.callback_paper(
        SimpleNamespace(callback_query=_FakeQuery(f"paper:{ids[1]}")), context
    ))
    asyncio.run(telegram.callback_skip(
        SimpleNamespace(callback_query=_FakeQuery(f"skip:{ids[2]}")), context
    ))

    with sqlite3.connect(tmp_path / "observations.db") as conn:
        intents = conn.execute(
            "SELECT observation_id, action, source FROM signal_action_intents "
            "ORDER BY id"
        ).fetchall()
    assert intents == [
        (ids[0], "EXECUTE", "telegram_callback"),
        (ids[1], "PAPER", "telegram_callback"),
        (ids[2], "SKIP", "telegram_callback"),
    ]


def test_legacy_callback_without_observation_id_is_rejected_explicitly(
    tmp_path: Path,
) -> None:
    observer_module = _load_observer_module()
    observer = observer_module.SignalObserver(db_path=tmp_path / "observations.db")
    observer_module.set_runtime_observer(observer)
    telegram = importlib.import_module("telegram_bot")
    query = _FakeQuery("skip_btc_idr")

    asyncio.run(telegram.callback_skip(
        SimpleNamespace(callback_query=query), SimpleNamespace(bot=_FakeBot())
    ))

    assert query.answers[-1][1] is True
    with sqlite3.connect(tmp_path / "observations.db") as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM signal_action_intents"
        ).fetchone()[0] == 0


def test_shadow_config_defaults_disabled_and_callback_payloads_fit_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import config

    monkeypatch.delenv("PAPER_SHADOW_ENABLED", raising=False)
    policy = config.PaperConfig()
    assert policy.shadow_observations_enabled is False
    assert policy.shadow_policy_version == "shadow_policy_v1"

    telegram = importlib.import_module("telegram_bot")
    plan = SimpleNamespace()
    keyboard = telegram._build_signal_keyboard(plan, 10**30)
    payloads = [row[0].callback_data for row in keyboard.inline_keyboard]
    assert payloads == [f"exec:{10**30}", f"paper:{10**30}", f"skip:{10**30}"]
    assert all(len(payload.encode("utf-8")) <= 64 for payload in payloads)
