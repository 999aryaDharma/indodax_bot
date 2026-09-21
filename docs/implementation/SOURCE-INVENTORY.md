# Audited source inventory

FACT: tracked baseline `fc0b4eb4bd57ae9fd5d9edac4237645fba72aed4`. Every entry is file existence and symbol inspection, not runtime correctness or test execution. Product models were not loaded. No ignored local dataset/runtime DB is included.

| Path | Top-level symbols / format | SHA-256 prefix |
|---|---|---|
| `.github/workflows/ci.yml` | yml | `bf64e1182bc7a8c3` |
| `.github/workflows/deploy.yml` | yml | `d0a7ae27b6b80a5b` |
| `.github/workflows/test-ssh.yml` | yml | `d0fe9eabdde7a698` |
| `configs/bars/event_v1.yaml` | yaml | `2a88d0891d24a7d8` |
| `configs/bars/time_v1.yaml` | yaml | `8e39b4b4eaf8d419` |
| `configs/costs/indodax_idr_v1.yaml` | yaml | `91d1522c78db9978` |
| `configs/features/tabular_bar_5m_v1.yaml` | yaml | `85b832508e89d53a` |
| `configs/features/tabular_bar_v1.yaml` | yaml | `e370e62bba32f324` |
| `configs/labels/net_return_v1.yaml` | yaml | `80a8ca674f39220d` |
| `configs/labels/triple_barrier_v1.yaml` | yaml | `a0a364cc17b1d1b5` |
| `configs/models/M01_logistic_v1.yaml` | yaml | `0b4e0a00cf136de9` |
| `configs/models/M02_xgboost_v1.yaml` | yaml | `ff55edc2a5320ba1` |
| `configs/schedules/host_profiles.yaml` | yaml | `1b7fc25fd894bfb0` |
| `configs/splits/annual_v1.yaml` | yaml | `298c0fd681e40a33` |
| `configs/strategies/C01_MTF_v1.yaml` | yaml | `2b35c31c594fcb1f` |
| `configs/strategies/C01_v1.yaml` | yaml | `3f52e2e634f1bbcb` |
| `configs/strategies/C02_v1.yaml` | yaml | `097458baff284958` |
| `configs/strategies/C03_v1.yaml` | yaml | `c4d784326e725453` |
| `configs/strategies/C04_v1.yaml` | yaml | `5fda717664041d49` |
| `configs/strategies/C07_v1.yaml` | yaml | `3584ac0bcec4f4f3` |
| `configs/strategies/C10_v1.yaml` | yaml | `f76f4be7f86f8c0b` |
| `configs/strategies/S01_v1.yaml` | yaml | `c5875e4376e57f72` |
| `configs/strategies/S02_v1.yaml` | yaml | `93f67ad0f8211bbe` |
| `configs/universe/default_v1.yaml` | yaml | `909f875d18560e8c` |
| `configs/universe/phase1_materialization_v1.yaml` | yaml | `8acd49956d618b75` |
| `dashboard.pen` | pen | `8b7ef150153a1129` |
| `deploy/backup-lab.sh` | sh | `11c810bb4da75e03` |
| `deploy/ibs.service` | service | `d8a83706802d4362` |
| `deploy/lab-collector.service` | service | `ef21304b2b3d535c` |
| `deploy/lab-shadow.service` | service | `0cc2dbcea458f7e2` |
| `deploy/lab-worker.service` | service | `ebc19810f3525780` |
| `deploy/logrotate.conf` | conf | `38bff84b82a6bfa0` |
| `deploy/release-lab.sh` | sh | `b651cefbd29cd666` |
| `deploy/restore-lab.sh` | sh | `eb7129aa34650e8b` |
| `deploy/setup.sh` | sh | `2e0c88be2e6cbd48` |
| `models/artifacts/d01_mlp_btc_1h_v1.json` | json | `8c6d984bd58457cb` |
| `models/artifacts/d01_mlp_btc_1h_v1.pt` | pt | `69ab1b1872d0545f` |
| `models/artifacts/d01_mlp_btc_1h_v2_tuned.pt` | pt | `7c7d983ba25d80df` |
| `models/artifacts/d02_tcn_btc_1h_v1.json` | json | `5c2b1ea7866f9b25` |
| `models/artifacts/d02_tcn_btc_1h_v1.pt` | pt | `8e2334bc0d42baa1` |
| `models/artifacts/d02_tcn_btc_1h_v2_tuned.pt` | pt | `e4b215a03f6dfe9b` |
| `models/artifacts/d03_resnet_lstm_btc_1h_v1.json` | json | `034a7cf5d5209e97` |
| `models/artifacts/d03_resnet_lstm_btc_1h_v1.pt` | pt | `a7fee1d481210c3e` |
| `models/artifacts/d03_resnet_lstm_btc_1h_v2_tuned.pt` | pt | `e61f37ebe85afec6` |
| `models/artifacts/d03_resnet_lstm_btc_idr_v2.pt` | pt | `75fef09b9ad89655` |
| `models/artifacts/d03_resnet_lstm_eth_idr_v2.pt` | pt | `996b057fbef33e2e` |
| `models/artifacts/d03_resnet_lstm_sol_idr_v2.pt` | pt | `5b3da45cb0764443` |
| `models/artifacts/d04_itransformer_btc_1h_v1.json` | json | `d206296955f050ef` |
| `models/artifacts/d04_itransformer_btc_1h_v1.pt` | pt | `6a327fc2d2ec40e1` |
| `models/artifacts/d04_itransformer_btc_1h_v2_tuned.pt` | pt | `2a412cb1ac294532` |
| `models/artifacts/d04_itransformer_btc_idr_v2.pt` | pt | `9fb23cf91d955eb5` |
| `models/artifacts/d04_itransformer_eth_idr_v2.pt` | pt | `9043c06fb95d996c` |
| `models/artifacts/d04_itransformer_sol_idr_v2.pt` | pt | `112fb77f39e77ff0` |
| `models/artifacts/m01_logistic_btc_1h_v1.json` | json | `b9bf7520749da454` |
| `models/artifacts/m01_logistic_btc_1h_v2_tuned.json` | json | `336442ae0156b554` |
| `models/artifacts/m02_xgboost_btc_1h_v1.json` | json | `36d2ab0c7f47361a` |
| `models/artifacts/m02_xgboost_btc_1h_v1.ubj` | ubj | `6968b01f9da18d6c` |
| `models/artifacts/m02_xgboost_btc_1h_v2_tuned.json` | json | `405177f51cc68d4c` |
| `models/artifacts/m02_xgboost_btc_1h_v2_tuned.ubj` | ubj | `ccde22aa32bcf956` |
| `models/artifacts/m02_xgboost_btc_idr_v2.json` | json | `eb56d9b13c197818` |
| `models/artifacts/m02_xgboost_btc_idr_v2.ubj` | ubj | `ccde22aa32bcf956` |
| `models/artifacts/m02_xgboost_eth_idr_v2.json` | json | `e91f4bb12bc8aac7` |
| `models/artifacts/m02_xgboost_eth_idr_v2.ubj` | ubj | `6414c95997d89719` |
| `models/artifacts/m02_xgboost_omni_cross_asset_v2.json` | json | `711a51bed0dda461` |
| `models/artifacts/m02_xgboost_omni_cross_asset_v2.ubj` | ubj | `0fe04442de94abd7` |
| `models/artifacts/m02_xgboost_sol_idr_v2.json` | json | `088b962f2d097386` |
| `models/artifacts/m02_xgboost_sol_idr_v2.ubj` | ubj | `eb26fe1126ca71ab` |
| `pyproject.toml` | toml | `4c333e0ec6ffcbb4` |
| `requirements-dev.txt` | txt | `6412d2240add9ccf` |
| `requirements-dl.txt` | txt | `5169ddbcb3c9b08e` |
| `requirements-research.txt` | txt | `fa4d661046a61dc7` |
| `requirements.txt` | txt | `930dc72f51ac1555` |
| `results/1h_swing_500k/c01_1h_500k.json` | json | `c62b3d56fa052b1a` |
| `results/1h_swing_500k/c02_1h_500k.json` | json | `13a6cd0856eb7aa4` |
| `results/1h_swing_500k/c03_1h_500k.json` | json | `046e4ceb56672b84` |
| `results/1h_swing_500k/c07_1h_500k.json` | json | `b53bfa9b13b9b9d2` |
| `results/1h_swing_500k/c10_1h_500k.json` | json | `2c61fc0531c70c24` |
| `results/1h_swing_500k/comparison_summary.json` | json | `83e7ff5692f75693` |
| `results/1h_swing_500k/s01_1h_500k.json` | json | `6929ca10e0050ebc` |
| `results/1h_swing_500k/s02_1h_500k.json` | json | `b54e6303d76932a8` |
| `results/1h_swing_500k_tuned/c01_1h_tuned_500k.json` | json | `13ba47f3ea3cc256` |
| `results/1h_swing_500k_tuned/c02_1h_tuned_500k.json` | json | `5cdab8db2bf852c5` |
| `results/1h_swing_500k_tuned/c03_1h_tuned_500k.json` | json | `7afe1fa2846a1f32` |
| `results/1h_swing_500k_tuned/c07_1h_tuned_500k.json` | json | `e785215f811cd62f` |
| `results/1h_swing_500k_tuned/c10_1h_tuned_500k.json` | json | `5449f6fa17b9a31f` |
| `results/1h_swing_500k_tuned/s01_1h_tuned_500k.json` | json | `76e8b99dc296a100` |
| `results/1h_swing_500k_tuned/s02_1h_tuned_500k.json` | json | `2a33ac864f14d206` |
| `results/1h_swing_500k_tuned/tuned_comparison_summary.json` | json | `0b035d8e7fab4ec4` |
| `results/2year_swing_500k/2year_exploration_summary.json` | json | `ee30f18819ac9d8b` |
| `results/2year_swing_500k/c01_2y_maker.json` | json | `accbde05f786f423` |
| `results/2year_swing_500k/c01_2y_runner.json` | json | `2d55bbaa21d64c1f` |
| `results/2year_swing_500k/c02_2y_runner.json` | json | `c2ae3f744da28911` |
| `results/2year_swing_500k/c03_2y_runner.json` | json | `9a87a3f86be774ea` |
| `results/2year_swing_500k/c07_2y_reversion.json` | json | `27e7be8d006d313f` |
| `results/2year_swing_500k/s02_2y_squeeze.json` | json | `41e15838ed4aec2a` |
| `results/README.md` | md | `74aebdbbdf7a4976` |
| `results/all_models_tournament/summary.json` | json | `ae4a702679e35bdb` |
| `results/all_models_tournament/tuned_v2_summary.json` | json | `f8881838c0333c90` |
| `results/altcoin_momentum_breakout/altcoin_breakout_ai_summary.json` | json | `5afb5509bc27cd92` |
| `results/c01_mtf_btc_2021-01-04_3d.json` | json | `489531bc2a6101ab` |
| `results/c01_mtf_btc_2021-01-04_7d.json` | json | `dc625c7fb6b3910d` |
| `results/c01_mtf_btc_2021-01-04_7d_500k.json` | json | `b171cac1816bb3f3` |
| `results/c07_dual_ml_all_pairs/summary.json` | json | `44a818e5f595e766` |
| `results/continual_learning_simulation/continual_learning_simulation_results.json` | json | `f787bc2a868f3013` |
| `results/ml_meta_filter_2024_2025/summary.json` | json | `92001e68ee023564` |
| `results/multi_asset_eth_sol/eth_c01_full.json` | json | `c5b99bb163a36c73` |
| `results/multi_asset_eth_sol/eth_c02_full.json` | json | `6d8b1c47f27bb0fc` |
| `results/multi_asset_eth_sol/eth_c03_full.json` | json | `9cba820af88fb940` |
| `results/multi_asset_eth_sol/eth_c07_full.json` | json | `37397b008cce26ea` |
| `results/multi_asset_eth_sol/eth_s02_full.json` | json | `02d0146fb035653d` |
| `results/multi_asset_eth_sol/multi_asset_benchmark_summary.json` | json | `b84d330fc6e2bfec` |
| `results/multi_asset_eth_sol/sol_c01_full.json` | json | `68dc5416c4cf5776` |
| `results/multi_asset_eth_sol/sol_c02_full.json` | json | `f03cbecd34fe92a7` |
| `results/multi_asset_eth_sol/sol_c03_full.json` | json | `dc59cc98e2a9abf0` |
| `results/multi_asset_eth_sol/sol_c07_full.json` | json | `a8dd7c0520afd92b` |
| `results/multi_asset_eth_sol/sol_s02_full.json` | json | `cf87759174745f1e` |
| `results/overnight_alpha_breakthrough/overnight_master_summary.json` | json | `11f3abb388029843` |
| `results/overnight_alpha_breakthrough/overnight_report.md` | md | `fe5bb156ba779b19` |
| `results/unified_portfolio_simulation/summary.json` | json | `c11c1a6511aa2048` |
| `run_shadow_bot.py` | run_single_scan, run_continuous_watch, main | `20987dfeae502107` |
| `src/__init__.py` | module declarations | `09008d84dd8aec46` |
| `src/config.py` | _require_env, Credentials, IndodaxConfig, TAConfig, RiskConfig, BearBounceConfig, BreakoutConfig, TrailingConfig, PaperConfig, ScoringConfig, ContextConfig, AppConfig | `a3a10b5d645a2cfa` |
| `src/indodax_api.py` | OHLCVCandle, WalletBalance, TradeRecord, MarketContext, _build_session, _sign_payload, _get_timestamp_ms, fetch_ohlcv, fetch_ticker, fetch_wallet_balance, _parse_my_trades_v2, fetch_recent_trades, is_pair_already_held, fetch_market_context, _fetch_fear_greed, _fetch_btc_dominance, _classify_fear_greed | `8b638d5402ffcae1` |
| `src/indodax_lab/__init__.py` | module declarations | `30354621cc71b6c9` |
| `src/indodax_lab/backtest/__init__.py` | module declarations | `0d4063501608af9b` |
| `src/indodax_lab/backtest/costs.py` | OrderSide, OrderRole, UnknownCostScheduleError, _ensure_utc, CostScheduleInterval, CostScheduleTable, CostScheduleResolution, load_cost_schedule_table, lookup_cost | `8325712101cc5797` |
| `src/indodax_lab/backtest/engine.py` | ReplayBacktestEngine | `ddebd09c25522045` |
| `src/indodax_lab/backtest/events.py` | _ensure_utc, ExecutionStatus, MarketBar, SignalIntent, ExecutionResult | `5421720655f45a78` |
| `src/indodax_lab/backtest/execution.py` | ConservativeExecutionSimulator | `ed373ad70eb223a2` |
| `src/indodax_lab/backtest/feature_replay.py` | _ensure_utc, _check_naive_timestamps, validate_no_future_leakage, FeatureReplayConfig, FeatureReplayAdapter, load_bars_from_parquet, load_bars_from_parquet_dir | `f0ef9ea7bd9efd30` |
| `src/indodax_lab/backtest/ledger.py` | _ensure_utc, AccountType, DuplicateFillError, InsufficientQuantityError, Posting, Position, LedgerTransaction, ResearchLedger | `7fd110b84043a00f` |
| `src/indodax_lab/backtest/metrics.py` | ProfitFactorResult, CostStressMetrics, PerformanceMetrics, calculate_equity, compute_performance_metrics | `637397da6512bc29` |
| `src/indodax_lab/backtest/orders.py` | _ensure_utc, Fill | `bdf60c632b39df36` |
| `src/indodax_lab/backtest/result.py` | BacktestResult | `431f583df544265e` |
| `src/indodax_lab/backtest/risk.py` | _ensure_utc, RiskPolicy, RiskAssessmentResult, PortfolioRiskManager | `c37384dfe376918c` |
| `src/indodax_lab/cli/__init__.py` | module declarations | `a4c0e1a8e7d920d0` |
| `src/indodax_lab/cli/approval.py` | _argument_parser, main | `fa53e894a13861db` |
| `src/indodax_lab/cli/backfill_candles.py` | BackfillWindow, BackfillSummary, BackfillStorageError, UrllibTransport, plan_windows, run_backfill, _build_checkpoint, _checkpoint_path, _checkpoint_checksum, _read_checkpoint, _validate_wire_metadata, _safe_relative_path, _publish_checkpoint, _fsync_directory, _parse_utc, _require_utc, _argument_parser, main | `e91e9290cf4a1617` |
| `src/indodax_lab/cli/build_bars.py` | _Parser, _arguments, main, _build_time_payload, _build_event_payload, _publish, _source_quality_row, _read_trades, _read_trade_batch, _read_bars, _read_continuity, _validate_official_sequence, _json_decimal, _utc_datetime, _optional_utc_iso, _bar_key | `c1fe6de3ac08fe19` |
| `src/indodax_lab/cli/build_features.py` | parse_args, _load_table, _sha256_file, main | `9ac6d548aaa2c3a2` |
| `src/indodax_lab/cli/build_training_dataset.py` | parse_args, _load_df, main | `90b4b8f6a4c31e46` |
| `src/indodax_lab/cli/build_universe.py` | _Parser, _parse_date, _argument_parser, main | `9452adee2aedb40d` |
| `src/indodax_lab/cli/collect_market_stream.py` | _WebsocketsTransport, _connect, _parser, main, _run | `da740a5d5cb42bad` |
| `src/indodax_lab/cli/dataset_inventory.py` | _sha256, inventory, main | `211e99d416aa6233` |
| `src/indodax_lab/cli/dataset_quality.py` | _sha256_file, validate_manifest, main | `e35f6b57f3df4f87` |
| `src/indodax_lab/cli/dataset_registry.py` | _canonical, build_registry, publish_no_clobber, main | `a51ec10720ddc823` |
| `src/indodax_lab/cli/kill_switch.py` | _argument_parser, main | `942ac8a55fee5fff` |
| `src/indodax_lab/cli/reconcile.py` | _argument_parser, _FakeReadOnlyClient, main | `f662e73a24bc74df` |
| `src/indodax_lab/cli/run_backtest.py` | _build_strategy_fn, _build_report, main | `7543287804dcc396` |
| `src/indodax_lab/cli/strategy_catalog.py` | load_catalog, main | `61a8270ccc8a25d0` |
| `src/indodax_lab/cli/validate_snapshot.py` | _parse_utc, _Parser, _argument_parser, main, _write | `4be08cbe1876db29` |
| `src/indodax_lab/contracts/__init__.py` | module declarations | `4dc733de3244caa4` |
| `src/indodax_lab/contracts/common.py` | _require_utc, QualityStatus, AggressorSide, CanonicalPair | `c7296f7325d9717d` |
| `src/indodax_lab/contracts/market.py` | _require_decimal, CandleRecord, TradeEvent | `f69bd4fd4fe43c18` |
| `src/indodax_lab/control/__init__.py` | module declarations | `03637b6bf2881acb` |
| `src/indodax_lab/control/approval.py` | generate_approval_token, verify_approval_token, ProposalStatus, PendingProposal, ManualApprovalStore | `ecf4358236cc72e8` |
| `src/indodax_lab/control/mode.py` | ExecutionMode, InvalidModeTransitionError, validate_mode_transition, DurableModeStore, AutonomousLimits | `6891d696a4ec00d3` |
| `src/indodax_lab/control/pipeline.py` | PipelineStepReport, TradingPipeline | `b846d4e2cbc609f4` |
| `src/indodax_lab/data/__init__.py` | module declarations | `c809625c97c64443` |
| `src/indodax_lab/data/bars.py` | BarType, SourceSelection, TimeBarConfig, LoadedTimeBarConfig, SilverBar, BarGap, TimeBarBuildResult, BarMismatch, SourceComparison, ReconciliationPolicy, load_time_bar_config, aggregate_time_bars, build_time_bars, resample_time_bars, compare_time_bar_sources, _validate_window, _validate_and_order_trades, _validate_trade_runtime, _bar_from_trades, _make_bar, _floor_utc, _bucket_starts, _require_utc, _sum_optional, _timedelta_microseconds, _optional_utc_iso, _validate_reconciliation_source | `a671bd53543fb794` |
| `src/indodax_lab/data/book_recovery.py` | QuarantinedGap, OutstandingRecovery, BookRecoveryCoordinator | `6278ad13a45f20f9` |
| `src/indodax_lab/data/checksums.py` | sha256_bytes, sha256_file | `66e2812e8cbbca08` |
| `src/indodax_lab/data/event_bars.py` | _exact_positive_decimal, ThresholdArtifact, EventThresholdConfig, EventBarConfig, LoadedEventBarConfig, EventBarRemainder, EventBarBuildResult, TradeContinuity, load_event_bar_config, build_event_bars, _ClosedBucket, _ContinuitySegment, _event_buckets, _validate_event_trades, _remainder, _continuity_segments | `85e96f6568f7b112` |
| `src/indodax_lab/data/indodax_candles.py` | InvalidCandlePayload, CandleHttpError, CandleReject, ParsedCandle, ParseBatch, HttpResponse, HttpTransport, CandleFetch, IndodaxCandleAdapter, parse_pascal_rows, parse_columnar, IndodaxCandleClient, _columnar_rows, _parse_rows, _parse_row, _constrain_to_window, _decimal, _source_event_id, _row_metadata, _venue_symbol, _interval_seconds, _require_utc | `7c527f5b2d96aded` |
| `src/indodax_lab/data/indodax_stream.py` | _publish_immutable, StreamTransportClosed, AppendOnlyStreamWriter, _atomic_replace, CollectorConfig, PublicTransport, PublicMarketCollector, _utc_now, _payload_channel, _abandonment_reason | `3fbc490b96de7c3e` |
| `src/indodax_lab/data/manifest.py` | ImmutableContentConflictError, canonical_json_bytes, canonical_manifest_bytes_without_id, dataset_snapshot_id, build_dataset_manifest, validate_manifest, read_manifest, content_id_path_component, snapshot_manifest_path | `0f617e08e13e8e48` |
| `src/indodax_lab/data/parquet_store.py` | WriteStatus, StorageValidationError, PartitionAudit, WriteResult, ParquetStore, _fsync_directory, _ensure_directory_tree, _remove_entry, _best_effort_remove_entry, _rollback_or_raise_indeterminate, _read_storage_manifest | `ff4cc18b21b5dadd` |
| `src/indodax_lab/data/publication.py` | IndeterminatePublicationError, fsync_directory, ensure_directory_tree, remove_entry, best_effort_remove_entry, rollback_or_raise_indeterminate, publish_existing_partial, publish_immutable_bytes | `075a2ee76d3d2f62` |
| `src/indodax_lab/data/quality.py` | InvalidValidationWindowError, QualityFinding, QualityReport, interval_duration, validate_candles, failure_report, _as_mapping, _pair, _timestamps, _check_invariants, _check_source_status, _check_monotonic, _check_duplicates, _check_gaps, _coalesce_missing, _check_staleness, _append, _finding, _decimal, _is_utc, _validate_requested_window, _require_utc, _safe_timestamp, _timestamp, _timedelta_microseconds, _finding_key | `943385e55995782b` |
| `src/indodax_lab/data/sentry.py` | _StrictFinding, _Coverage, _GapRange, _StrictQualityReport, SnapshotValidationResult, SnapshotPathUnresolvableError, ApprovedSnapshotDecision, validate_snapshot, require_approved_snapshot_decision, _safe_partition_path, validate_snapshot_id, _contained_path, _combine_failures, _finalize, _unpublished_result, _unrecorded_failure | `05324a0af5cd7ddd` |
| `src/indodax_lab/data/stream_protocol.py` | InvalidPublicStreamMessage, ConflictingSequenceError, SequenceRegressionError, StreamState, BookSide, BookEvent, ParsedPublicMessage, ProtocolResult, _mapping, _sequence, _decimal, _require_utc, parse_public_message, _parse_trades, _parse_book, BookSessionProtocol | `efc54b9a4f1dbfd3` |
| `src/indodax_lab/data/trade_sentry.py` | TradeBatchDecision, _Batch, _CanonicalDecision, validate_trade_batches, _canonical_trade_decision, require_existing_approved_trade_decision, _load_batch, _load_current_batches, _strictly_contiguous | `722ef938ce5285cb` |
| `src/indodax_lab/data/trade_wire.py` | TradeWireArtifactLink, VerifiedTradeWireArtifact, persist_trade_wire_artifact, load_trade_wire_artifact, _mapping, _contained, _parse_utc, _require_utc | `965624279975e018` |
| `src/indodax_lab/data/wire_store.py` | WireRequest, WireArtifact, WireStore, _publish_immutable, _fsync_directory, _rollback_or_raise_indeterminate | `1944cc9b8d68beb0` |
| `src/indodax_lab/evaluation/__init__.py` | module declarations | `a4dfdf653ced6e5d` |
| `src/indodax_lab/evaluation/gates.py` | EvaluationOutcome, EvaluationPolicy, EvaluationResult, MultiSeedEvaluationResult, evaluate_run, evaluate_multi_seed_runs | `2e1091b10f4848e1` |
| `src/indodax_lab/evaluation/lifecycle.py` | _ensure_utc, CandidateStage, InvalidTransitionError, CandidateFrozenError, GateAlreadyOpenedError, CandidateNotFoundError, CandidateRecord, TransitionRecord, ExposureAuditRecord, LeaderboardEntry, CandidateLifecycleManager | `6141967e33163b6d` |
| `src/indodax_lab/evaluation/registry.py` | _ensure_utc, ExperimentRunStatus, ExperimentRunRecord, ExperimentRegistry | `195567e6c8e811a6` |
| `src/indodax_lab/evaluation/statistics.py` | compute_deflated_sharpe_ratio, compute_pbo | `d637e6f47ceead17` |
| `src/indodax_lab/evaluation/tournament.py` | LiveProfitabilityClaimForbiddenError, TournamentCandidate, TournamentFollowUp, TournamentReport, run_wave1_tournament | `6f1db4a9333d334f` |
| `src/indodax_lab/execution/__init__.py` | module declarations | `4b851c30b8c0d018` |
| `src/indodax_lab/execution/fake_venue.py` | DeterministicFakeVenue | `555b76c6c5280da7` |
| `src/indodax_lab/execution/fill_ingestion.py` | FillIngestionStatus, OverfillInvariantError, FillIngestionResult, VenueFillIngester | `75f91c2469d386c3` |
| `src/indodax_lab/execution/fill_normalizer.py` | VenueFillNormalizationError, normalize_venue_fill | `ac209e37cb5bc802` |
| `src/indodax_lab/execution/indodax_readonly.py` | VenueReadError, VenueAuthenticationError, VenueProtocolError, VenueBalance, VenueAccountSnapshot, VenueOrder, VenueFill, _decimal, _utc_from_epoch, _pair, _symbol, _side, _required_text, _legacy_order_quantities, _validate_time_window, IndodaxReadOnlyClient | `44fd4f56c250b75e` |
| `src/indodax_lab/execution/indodax_trading.py` | IndodaxTradingVenue | `8577ae8fbed29d7b` |
| `src/indodax_lab/execution/ledger_store.py` | LedgerIntegrityError, ProductionLedgerStore | `defa6bb6c51223fe` |
| `src/indodax_lab/execution/oms.py` | _ensure_utc, OmsOrderState, OmsOrder, OmsTransitionError, OmsStateMachine | `d2a93dec902cbb4b` |
| `src/indodax_lab/execution/oms_store.py` | OmsStateCorruptionError, OmsConcurrencyError, OmsStore | `17659211790f34b0` |
| `src/indodax_lab/execution/order_router.py` | UnresolvedOrderStateError, OrderRouter | `b470c052efa2456e` |
| `src/indodax_lab/execution/read_only_reconciler.py` | PrivateReadOnlyReconciliationService | `b05803573865f3c4` |
| `src/indodax_lab/execution/read_only_smoke.py` | run_read_only_smoke, _parser, main | `b4fd482e924320a9` |
| `src/indodax_lab/execution/reconciliation.py` | ReconciliationStatus, ReconciliationPolicy, ReconciliationIssue, ReconciliationReport, ReconciliationEngine | `ec7d32de10ddfaff` |
| `src/indodax_lab/execution/reconciliation_coordinator.py` | ReconciliationCycleResult, DurableReconciliationCoordinator | `ac41a788e5e0cf5d` |
| `src/indodax_lab/execution/reconciliation_store.py` | ReconciliationCursorError, ReconciliationCursorCorruptionError, ReconciliationCursorConcurrencyError, ReconciliationCursor, ReconciliationCursorStore | `5782b5293cc79f4d` |
| `src/indodax_lab/execution/venue.py` | VenueError, VenueRejectError, UncertainVenueSubmissionError, TradingVenue | `b00352a29708bbb4` |
| `src/indodax_lab/features/__init__.py` | module declarations | `187d22c613c1bfa3` |
| `src/indodax_lab/features/builder.py` | _compute_sample_id, _is_forbidden, build_feature_frame | `54ebf21e2ccaf4f9` |
| `src/indodax_lab/features/context.py` | _utc_column, _closed_source, asof_join_features, point_in_time_market_context, hour_sin, hour_cos, dow_sin, dow_cos, log_listing_age, bar_completeness, btc_log_return, beta_btc, tier_momentum_rank, market_breadth_positive, market_rv_median | `c80d93256b32cffb` |
| `src/indodax_lab/features/liquidity.py` | quote_turnover, zero_volume_ratio, amihud | `b4f57e3eb8d644b0` |
| `src/indodax_lab/features/lob.py` | extract_lob_tensor, compute_depth_imbalance, compute_spread, compute_microprice | `525dcb31fc232dec` |
| `src/indodax_lab/features/registry.py` | FeatureAvailability, MissingPolicy, FeatureDefinition, FeatureRegistry, LoadedFeatureRegistry, load_feature_registry, _semver_tuple, _integer_param, _minimum_lookback | `2587855907b39823` |
| `src/indodax_lab/features/technical.py` | _float_series, _divide, true_range, wilder_average, atr, ema_ratio, ema_slope_atr, rsi, rsi_centered, stochrsi, stochrsi_component, macd_hist_atr, adx_di, adx_di_component, bollinger_features, bollinger_component, atr_pct, donchian_position, volume_zscore, vwap_deviation, log_return, rolling_distance, realized_volatility, downside_volatility, parkinson_volatility | `21f4dc3bf58f3375` |
| `src/indodax_lab/labels/__init__.py` | module declarations | `6b995aba1cc323e8` |
| `src/indodax_lab/labels/materializer.py` | _ensure_utc, DuplicateSampleError, TargetLeakageError, ArtifactIntegrityError, AvailabilityMismatchError, _content_digest, _validated_times, TrainingDatasetManifest, TrainingDatasetArtifact, materialize_training_dataset | `244deffa55e0a945` |
| `src/indodax_lab/labels/returns.py` | NetReturnConfig, NetReturnLabel, _get_val, _require_utc, build_net_return_label, build_net_return_labels_frame | `bd261703142f9ec9` |
| `src/indodax_lab/labels/splits.py` | _ensure_utc, SampleRole, ExposedPeriodViolationError, FoldWindow, SplitPolicy, SampleRecord, FoldAssignment, SplitManifest, assign_folds | `687671eff9efcbdd` |
| `src/indodax_lab/labels/triple_barrier.py` | BarrierTouch, TripleBarrierConfig, TripleBarrierLabel, _get_val, build_triple_barrier_label, compute_concurrency_weights | `78f48c7eaceb91c0` |
| `src/indodax_lab/market/__init__.py` | module declarations | `fa53ae6b9b544646` |
| `src/indodax_lab/market/clock.py` | ClockRegressionError, ClockReport, ClockGuard | `c51651566bc0b37a` |
| `src/indodax_lab/market/gateway.py` | MarketSnapshot, MarketGateway | `e32f30a6e551e78b` |
| `src/indodax_lab/market/health.py` | MarketHealthState, MarketHealthReport | `a28e90bb277638bb` |
| `src/indodax_lab/market/quality.py` | TickerSnapshot, QualityValidationResult, DataQualityGuard | `4190c1c285761daa` |
| `src/indodax_lab/models/__init__.py` | module declarations | `2d5c75a52816d770` |
| `src/indodax_lab/models/artifacts.py` | BundleChecksumMismatchError, MissingCalibrationMetadataError, BundleFeatureMismatchError, _canonical_json_bytes, _bundle_content_hash, _assert_finite_json, PortableBundle, PortableBundleLoader | `22055eb47d15d7e6` |
| `src/indodax_lab/models/calibration.py` | CalibrationSegmentError, InsufficientCalibrationDataError, NotFittedError, FittedCalibratorArtifact, HeldOutCalibrator | `86083069b1cd3623` |
| `src/indodax_lab/models/dl/__init__.py` | module declarations | `3bf537f983da6b18` |
| `src/indodax_lab/models/dl/checkpoint.py` | TorchNotAvailableError, ResumeInputMismatchError, check_torch_availability, require_torch, NeuralTrainingCheckpoint, save_checkpoint, load_checkpoint | `c792f91adf6f8316` |
| `src/indodax_lab/models/dl/d01_mlp.py` | SearchBudgetExceededError, SampleComparatorMismatchError, D01MLPConfig, D01MLPFittedBundle, SameSampleComparisonResult, D01FinalistEvaluation, _build_mlp_module, D01MLPTrainer, SameSampleComparator, D01MultiSeedEvaluator | `85ef3906d879d232` |
| `src/indodax_lab/models/dl/d02_tcn.py` | TCNComputeBudgetSummary, CausalTCNConfig, CausalTCNTrainedBundle, CausalConv1dBlock, CausalTCNModel, CausalTCNTrainer | `45a43e318d565bcc` |
| `src/indodax_lab/models/dl/d03_resnet_lstm.py` | BidirectionalLeakageError, ResNetLSTMConfig, ResNetLSTMUtilityComparison, ResNetLSTMTrainedBundle, ResidualTemporalBlock, ResNetLSTMModel, ResNetLSTMTrainer | `599d66dbc387b581` |
| `src/indodax_lab/models/dl/d04_itransformer.py` | InvertedDimensionError, FutureUniverseError, ITransformerComputeBudgetSummary, CompactITransformerConfig, PointInTimePanelSnapshot, PointInTimeUniverseGate, ITransformerOutput, _build_itransformer_classes, CompactITransformer | `2374bd549d537b66` |
| `src/indodax_lab/models/dl/dataset.py` | TargetLeakageForbiddenError, SessionGapBrokenWindowError, CausalSequenceConfig, CausalSequenceBatch, CausalSequenceBuilder | `aa8ed3a9532ed788` |
| `src/indodax_lab/models/dl/training.py` | NeuralTrainingConfig, EarlyStoppingTracker, NeuralTrainer | `e1e1f16589025f7c` |
| `src/indodax_lab/models/execution_mapper.py` | _ensure_utc, ForecastKind, DecisionAction, PayoffStructure, CostBasis, ForecastPayload, ExecutionDecision, CostAwareExecutionMapper | `50662e3288905518` |
| `src/indodax_lab/models/foundation/__init__.py` | module declarations | `2cd497bdaa9c01a7` |
| `src/indodax_lab/models/foundation/f01_kronos.py` | AdaptationStage, StagePreconditionNotMetError, FullFineTuneForbiddenError, ContaminatedDatesClaimError, FoundationAdaptationConfig, StageEvaluationResult, StagedFoundationAdapter | `c1fe5d02e66c14f4` |
| `src/indodax_lab/models/foundation/provenance.py` | FoundationArtifactStatus, ChecksumVerificationFailedError, IncompatibleLicenseError, UnknownCutoffBlockedError, FoundationModelProvenance, VerificationResult, FoundationProvenanceGate, FakeFoundationModelAdapter | `d724689133ca0f7b` |
| `src/indodax_lab/models/graph/__init__.py` | module declarations | `57ce415194267f33` |
| `src/indodax_lab/models/graph/g01_cross_asset.py` | FullSampleAdjacencyLeakageError, PrematureNodeInclusionError, GraphBudgetExceededError, PointInTimeGraphConfig, GraphSnapshot, RankedAsset, GraphBaselineComparison, PointInTimeGraphBuilder, CrossAssetGNNRanker, GraphBaselineComparator | `60cb69694c68a5fe` |
| `src/indodax_lab/models/lob/__init__.py` | module declarations | `928021f2038e06d6` |
| `src/indodax_lab/models/lob/dataset.py` | CandleSubstitutionForbiddenError, SessionGapBrokenWindowError, InsufficientCoverageGateError, SessionStatus, BookLevel, BookSnapshot, LOBSessionMetadata, LOBEligibilityReport, LOBDatasetEligibilityGate | `2e0598a94abcaf4a` |
| `src/indodax_lab/models/lob/l01_deeplob.py` | GappedBookBlockedError, SampleComparatorMismatchError, DeepLOBSampleComparisonResult, DeepLOBSampleComparator, SpreadAwareAssessment, SpreadAwareEdgeEvaluator, DeepLOBConfig, _build_deeplob_classes, DeepLOBModel, DeepLOBTrainer | `f7c582d48af46d56` |
| `src/indodax_lab/models/lob/l02_tlob.py` | PerfectQueueFillForbiddenError, TLOBSearchBudgetExceededError, QueueFillModel, TLOBComputeSummary, TLOBConfig, ArchivedChallengerResult, TLOBTournamentArchiver, _build_tlob_classes, TLOBModel | `917507aadc93b2c5` |
| `src/indodax_lab/models/m01_logistic.py` | InvalidSolverPenaltyError, ClassImbalanceError, M01Config, M01FittedBundle, ModelUtilityComparison, M01LogisticTrainer | `c002e9e146d3bf1c` |
| `src/indodax_lab/models/m02_xgboost.py` | SealedPartitionLeakageError, M02Config, M02FittedBundle, M02SeedResult, M02MultiSeedAudit, M02XGBoostTrainer | `72a1ba52a2886e43` |
| `src/indodax_lab/models/m03_rf_regime.py` | RegimeAbstainError, RegimeLabel, M03Config, M03FittedBundle, RegimeUtilityReport, M03RFRegimeTrainer | `ae6926e737ea9b06` |
| `src/indodax_lab/models/m04_quantile_risk.py` | QuantileCrossingError, TailTargetLeakageError, M04Config, M04FittedBundle, QuantileCoverageReport, M04QuantileTrainer | `d7e007f5770997eb` |
| `src/indodax_lab/models/m05_meta_label.py` | ManualLabelForbiddenError, MetaTradeSample, M05Config, M05FittedBundle, MetaFilterComparisonReport, purge_overlapping_trades, M05MetaLabelTrainer | `f38ce85ea1292dd6` |
| `src/indodax_lab/models/m06_anomaly_gate.py` | MissingDataDistinctFromAnomalyError, DirectionalClaimForbiddenError, M06Config, M06FittedBundle, AnomalyDecision, M06AnomalyGate | `edf51bb3e6c91f6f` |
| `src/indodax_lab/models/preprocessing.py` | _ensure_utc, FeatureAlignmentError, NotFittedError, PreprocessorConfig, FittedPreprocessorArtifact, TabularPreprocessor | `8ddd95dff43e4d69` |
| `src/indodax_lab/models/r01_rl_allocator.py` | LiveExecutionForbiddenError, CostAwareRewardFunction, AllocationBaselineComparator, RLAllocationEnvironment, RLFeasibilityReport, evaluate_rl_allocation_feasibility | `7b42e28be7a1bd61` |
| `src/indodax_lab/models/tuning.py` | SealedTestObjectiveForbiddenError, TrialBudgetExhaustedError, RevisionBudgetExhaustedError, ResumeConfigMismatchError, TrialStatus, SearchSpace, TrialBudget, TrialOutcome, BoundedTrialSearch | `719d3a09179b9af8` |
| `src/indodax_lab/observability/__init__.py` | module declarations | `b4dfd9a152892dd4` |
| `src/indodax_lab/observability/logging.py` | RedactingJsonFormatter | `eca2ee8cfa476c69` |
| `src/indodax_lab/observability/metrics.py` | MetricsCollector | `69b5a81850ad400b` |
| `src/indodax_lab/operations/__init__.py` | module declarations | `382fd6b1b6d71f6f` |
| `src/indodax_lab/operations/backup.py` | _ensure_utc, compute_sha256, _safe_relative_member, _assert_no_symlink_ancestors, _assert_no_symlink_path, _copy_file_durable, _fsync_directory, is_sqlite_database, backup_sqlite_db, create_backup_bundle | `d32a8d46b56f90af` |
| `src/indodax_lab/operations/recovery.py` | DiskFullError, CapacityCeilingExceededError, DiskGuardWriter, IdempotentMetricLedger, EmpiricalHostCapacityValidator, HostWorkloadQualificationReport, qualify_host_workload_and_recovery | `e4a95112125ddfb5` |
| `src/indodax_lab/operations/restore.py` | RestoreResult, restore_snapshot_bundle | `da81534ae3f7f54a` |
| `src/indodax_lab/operations/service_lifecycle.py` | ConcurrentWriterLockError, MissingSecretError, LifecycleOperationError, HostServiceProfile, SingleWriterLock, ManagedService, ServiceManager | `96fbc7b98830754d` |
| `src/indodax_lab/operations/staging.py` | _ensure_utc, ChecksumMismatchError, CorruptTransferError, TransferManifest, StagingResult, _canonical_json_bytes, _manifest_hash, _canonical_member, _normalized_manifest_members, _reject_symlink_ancestors, _safe_bundle_file, _copy_file_durable, _fsync_directory, _fsync_tree, load_transfer_manifest, verify_bundle, stage_and_publish_transfer | `4e834b93fdeb7776` |
| `src/indodax_lab/orchestration/__init__.py` | module declarations | `337cdf2aefa8125b` |
| `src/indodax_lab/orchestration/curator_policy.py` | HardFailTuningForbiddenError, SelfApprovalForbiddenError, ProposalStatus, ChangeRequestProposal, ChangeRequestRecord, sanitize_curator_input, CuratorEngine | `b7aeb1fec265c752` |
| `src/indodax_lab/orchestration/dag.py` | HardFailCannotBeReopenedError, InvalidRunRetryLimitExceededError, NearMissMustHaveNewVersionError, ExperimentRecipe, RepeatPolicy, RepeatOutcome, RepeatDecision, InvalidRunRetryConfig, ResearchDAGJob, DAGScheduler | `b43239704b6ebdc6` |
| `src/indodax_lab/orchestration/jobs.py` | _ensure_utc, JobStatus, LeaseFencingError, PartialArtifactError, JobDefinition, JobRecord | `d5a390732e11a87e` |
| `src/indodax_lab/orchestration/maintenance.py` | _ensure_utc, SymlinkEscapeError, RetentionPolicy, CleanupReport, StorageCleaner | `4b7cf306431776bc` |
| `src/indodax_lab/orchestration/queue.py` | _ensure_utc, _parse_utc_iso, SqliteJobQueue | `ff1a8adedd0caf80` |
| `src/indodax_lab/orchestration/resources.py` | _ensure_utc, HostProfile, ResourceClass, AsusProfileTrainingProhibitedError, SystemResourceReading, ResourceProbe, StaticResourceProbe, ResourceThresholds, AdmissionPolicy, AdmissionDecision, resolve_resource_class, is_training_job, guard_asus_training_import, evaluate_admission | `2904cfb72df460f2` |
| `src/indodax_lab/orchestration/worker.py` | WorkerConfig, ExecutionResult, ResearchWorker | `094bafc4aff3fb98` |
| `src/indodax_lab/paper/__init__.py` | module declarations | `94e35a451c7b76d3` |
| `src/indodax_lab/paper/contracts.py` | StaleDataError, ModelMismatchError, DuplicateDecisionError, ForwardDecisionStatus, ForwardDecision, ForwardDecisionRecord, ManualIntentRecord, PaperDecisionStore | `7ad9714f45de777a` |
| `src/indodax_lab/paper/live_shadow_engine.py` | ShadowPosition, ClosedTrade, LiveShadowEngine | `c0c726879c979ad8` |
| `src/indodax_lab/paper/portfolio.py` | MaxPositionsExceededError, InsufficientCashError, PaperOrderIntent, PaperPosition, IntentProcessingResult, SharedLedgerCheckpoint, SharedCapitalLedger | `ff25dcc86263c77d` |
| `src/indodax_lab/paper/promotion.py` | InsufficientForwardDurationError, InsufficientForwardTradesError, UnsealedCandidatePromotionError, PolicyBreachPromotionError, ChallengerEvidence, PromotionDecision, ChampionRegistry | `bdc7fd0ba68dbb27` |
| `src/indodax_lab/paper/shadow_store.py` | ShadowStateCorruptionError, ShadowStateStore | `ba810109c2e834b9` |
| `src/indodax_lab/paths.py` | LabPaths | `12228818d9124067` |
| `src/indodax_lab/portfolio/__init__.py` | module declarations | `f0380800455b585b` |
| `src/indodax_lab/portfolio/constructor.py` | _ensure_utc, TargetExposure, PortfolioConstructor | `d46814c80d9c6caa` |
| `src/indodax_lab/reporting/__init__.py` | module declarations | `c4f5ea940fff4deb` |
| `src/indodax_lab/reporting/summary.py` | _format_metric_display, ExperimentSummaryReport, generate_experiment_report_md, generate_experiment_report_json, generate_multi_run_comparison_md | `9717550c30bcebf8` |
| `src/indodax_lab/reporting/telegram.py` | UnauthorizedChatError, escape_telegram_markdown, redact_secrets, ResearchQueueStatus, ChampionStatus, SystemHealthStatus, ResearchHoldingsStatus, TelegramDeliveryResult, format_research_status, ReadOnlyTelegramReporter | `98886b00befadfad` |
| `src/indodax_lab/risk/__init__.py` | module declarations | `01557bdc7cb8c4c1` |
| `src/indodax_lab/risk/engine.py` | KillSwitchTriggeredError, RiskEngine | `7bec412bb3427a44` |
| `src/indodax_lab/security/__init__.py` | module declarations | `9961ef30f6df203c` |
| `src/indodax_lab/security/boundary.py` | PathTraversalError, SecurityViolationError, safe_resolve_artifact_path, verify_artifact_bytes_safe, audit_no_trade_withdraw_keys, SecurityAuditReport, SecurityAuditRunner | `0a7bda666e4c47d3` |
| `src/indodax_lab/security/redaction.py` | redact_text | `36b73e2c58613ef2` |
| `src/indodax_lab/strategies/__init__.py` | module declarations | `2f6665ba95a48aec` |
| `src/indodax_lab/strategies/base.py` | _ensure_utc, _compute_logic_hash, StrategySpecification, DecisionFrame, create_decision_frame, RegisteredStrategy | `300bc07308a42085` |
| `src/indodax_lab/strategies/c01.py` | load_c01_specification, c01_decide | `248468021dbb065a` |
| `src/indodax_lab/strategies/c02.py` | load_c02_specification, c02_decide | `ae1095a9176da198` |
| `src/indodax_lab/strategies/c03.py` | load_c03_specification, c03_decide | `d88ae38ae2fbaf55` |
| `src/indodax_lab/strategies/c04.py` | load_c04_specification, c04_decide | `bb697bb3fe52aee8` |
| `src/indodax_lab/strategies/c07.py` | load_c07_specification, c07_decide | `34eb9a8e6d1ed854` |
| `src/indodax_lab/strategies/c10.py` | load_c10_specification, c10_decide | `2fd30eff9b04b9b0` |
| `src/indodax_lab/strategies/multitimeframe.py` | align_closed_context | `f5c5894b4a8d15c6` |
| `src/indodax_lab/strategies/registry.py` | StrategyRegistry | `8f092bbafab42cc2` |
| `src/indodax_lab/strategies/s01.py` | load_s01_specification, s01_decide | `f614fcb43002ca56` |
| `src/indodax_lab/strategies/s02.py` | load_s02_specification, s02_decide | `322f30b400fa8e8e` |
| `src/indodax_lab/universe/__init__.py` | module declarations | `f60fe57ce2931361` |
| `src/indodax_lab/universe/coingecko_adapter.py` | HttpResponse, HttpTransport, ProviderUnavailableCode, ProviderUnavailable, CapObservation, CapWireArtifact, CapBatch, CoinGeckoAdapter, reconstruct_coingecko_batch, _reconstruct_current_wire, _cap_batch_from_response, _reconstruct_historical_audit, _parse_json, _source_timestamps, _observation, _unavailable_batch, _parse_utc, _require_utc | `25b967353dfa95f2` |
| `src/indodax_lab/universe/contracts.py` | UniverseTier, ReasonCode, _decimal, TierPolicy, UniversePolicy, LoadedUniversePolicy, UniverseMetrics, UniverseDecision, load_universe_policy | `d2bfa1c932a01ff0` |
| `src/indodax_lab/universe/eligibility.py` | classify_pair, _cap_is_valid, _liquidity_reasons | `455d03f973609cf3` |
| `src/indodax_lab/universe/lineage.py` | ListingEvidence, CapEvidence, MaterializationProfile, _Reference, CandleWireArtifactRef, BronzeSnapshotArtifactRef, CandleQualityArtifactRef, TradeWireArtifactRef, TradeBatchArtifactRef, GlobalTradeQualityArtifactRef, BarArtifactRef, BookArtifactRef, ListingArtifactRef, CapProviderResponseArtifactRef, ProfileArtifactRef, UniversePolicyArtifactRef, LoadedListingArtifact, LoadedCapProviderArtifact, LoadedMaterializationProfile, LoadedUniversePolicyArtifact, LoadedTradeArtifacts, LoadedBarArtifact, LoadedBookArtifact, PipelineLineageInputs, require_reference_type, load_listing_artifact, load_materialization_profile, load_universe_policy_artifact, load_candle_wire_artifact, load_bronze_snapshot_artifact, load_candle_quality_artifact, load_trade_artifacts, load_bar_artifact, load_book_artifact, load_cap_provider_artifact, _require_ref_tuple, _contained, _bytes_id, _mapping_id, _utc, _book_event, _silver_bar, _expected_bar_id | `2f89fe821bf934b1` |
| `src/indodax_lab/universe/materializer.py` | materialize_universe_metrics, _daily_quote_volume, _book_metrics, _depth, _median, _require_utc_before_cutoff, _require_utc | `5b6dd8aff14b6edd` |
| `src/indodax_lab/universe/snapshot.py` | PreparedUniverseSnapshot, UniverseSnapshotArtifact, prepare_daily_snapshot, build_daily_snapshot | `3e2d9ef2a1c9d643` |
| `src/indodax_lab/verification/__init__.py` | module declarations | `e7107bbdc565c6bb` |
| `src/indodax_lab/verification/release.py` | ExperimentalPromotionForbiddenError, RollbackIntegrityError, ReleaseCandidatePackage, ReleaseCandidateManager | `7c92f64672a0db56` |
| `src/indodax_lab/verification/release_bundle.py` | ReleaseBundleIntegrityError, ReleaseBundle, compute_sha256, create_release_bundle, verify_release_bundle | `4551e13d50c42962` |
| `src/main.py` | _get_signal_observer, scan_market, _process_pair, _monitor_active_positions, _try_close_position, fetch_context, _send_weekly_report, health_check, _startup_check, _handle_shutdown, main | `b18ca976cd851c8d` |
| `src/paper_accounting.py` | BuyFill, SellFill, _require_positive_finite, _require_fee_rate, account_buy, account_sell, realized_pnl | `4e309370f964c2a9` |
| `src/paper_trader.py` | Candle, PaperTrade, _get_conn, _migration_backup_path, _create_migration_backup, _migrate_accounting_columns, _quote_identifier, _rebuild_column_declaration, _sqlite_sequence_state, _restore_paper_trades_sequence, _rebuild_accounting_table, _create_paper_trades_table, _create_bar_state_table, _init_db, _positive_decimal, _decimal_storage, PaperTrader | `f523f95b3cf4d8d2` |
| `src/position_tracker.py` | ActivePosition, _init_db, _save_position, _load_open_positions, PositionTracker | `9ab35e6005825a54` |
| `src/risk_manager.py` | TradingPlan, _get_risk_params, calculate_trading_plan | `d0c83c41325a25ea` |
| `src/signal_cache.py` | set_entry, get_entry, clear_entry, clear_all | `59449896bbee53da` |
| `src/signal_logic.py` | MarketMode, SignalStrategy, LayerResult, SignalDecision, CooldownManager, _v, _threshold, _bb_gap, _vol_ratio, _log_ta_snapshot, classify_daily_mode, _classify_daily_reason, _calculate_sniper_score, _calculate_breakout_score, _calculate_bear_bounce_score, _log_sniper_breakdown, _log_breakout_breakdown, _log_bear_breakdown, _apply_context_adjustment, _build_sniper_layers, _build_breakout_layers, _build_bear_bounce_layers, _try_sniper, _try_breakout, _try_bear_bounce, _make_rejection, evaluate_signal, confirm_entry_15m, confirm_signal_sent, get_cooldown_status | `ada94702ebd160bb` |
| `src/signal_observer.py` | Candle, ConflictingCandleError, ConflictingDecisionError, canonicalize_bars, BarrierResolution, resolve_barriers, SignalObserver, set_runtime_observer, get_runtime_observer | `75a16d1a0d7c44d6` |
| `src/ta_processor.py` | TAResult, calculate, _candles_to_dataframe, _compute_indicators, _extract_last_values | `d3d1eab18b984546` |
| `src/telegram_bot.py` | _is_chat_authorized, _escape_md2, _score_bar, _get_strategy_label, format_signal_message, _build_signal_keyboard, send_signal, escape_md_v2, send_text, _add_to_history, cmd_start, cmd_status, cmd_saldo, cmd_history, _record_callback_intent, callback_exec, callback_skip, callback_noop, callback_paper, cmd_posisi, cmd_raport, cmd_gate, format_trailing_activated, format_trailing_updated, build_application | `cfc20adac5e740ce` |
| `tests/architecture/test_canonical_runtime_boundary.py` | _import_roots, test_canonical_runtime_does_not_import_legacy_flat_modules | `e991b547b5817b45` |
| `tests/conftest.py` | module declarations | `116146fe79b4e462` |
| `tests/fixtures/features/golden_ohlcv.csv` | csv | `52684f7d38a2de9f` |
| `tests/fixtures/indodax/history_v2_columns.json` | json | `2a65d7e668db08e5` |
| `tests/fixtures/indodax/history_v2_pascal.json` | json | `feb183b59908576f` |
| `tests/fixtures/indodax/my_trades_v2.json` | json | `105949ac0dbce951` |
| `tests/fixtures/indodax/phase1/cap.json` | json | `f7193adb4b32ff8b` |
| `tests/fixtures/indodax/phase1/listing.json` | json | `569b1efec0546e5c` |
| `tests/fixtures/indodax/stream/book_snapshot.json` | json | `1479cbc6af93c859` |
| `tests/fixtures/indodax/stream/book_update.json` | json | `3c2a1ca15abc9525` |
| `tests/fixtures/indodax/stream/duplicate_sequence.json` | json | `3c2a1ca15abc9525` |
| `tests/fixtures/indodax/stream/gap_sequence.json` | json | `f04d33706f4bd75a` |
| `tests/fixtures/indodax/stream/heartbeat.json` | json | `1d07ff42d56599f5` |
| `tests/fixtures/indodax/stream/public_trade.json` | json | `d411888daa388ce3` |
| `tests/fixtures/indodax/stream/reconnect.json` | json | `b5dbefa974f8726a` |
| `tests/integration/lab/test_backtest_golden.py` | test_schedule_table, test_risk_policy, _sample_bars, _simple_strategy, test_sim_03_valid_contract, test_sim_03_contract_1, test_sim_03_contract_2, test_sim_03_contract_3, test_replay_exact_cost_once_arithmetic | `f42a3843311c70dc` |
| `tests/integration/lab/test_backup_restore.py` | _setup_source_environment, test_ops_02_valid_contract, test_ops_02_contract_1, test_ops_02_contract_2, test_ops_02_contract_3, _write_manifest, test_transfer_rejects_unsafe_manifest_member_before_writing, test_transfer_rejects_duplicate_normalized_targets, test_transfer_rejects_symlink_escape, test_backup_rejects_source_traversal, _simple_bundle, test_second_publish_failure_keeps_entire_old_active_view, test_successful_transfer_retry_is_idempotent | `b3aefd4fa4147ff5` |
| `tests/integration/lab/test_candle_backfill.py` | FixtureTransport, test_dry_run_reports_windows_without_clock_transport_or_filesystem, test_fake_transport_backfill_is_wire_first_bronze_published_and_resumable, test_backfill_rate_limits_between_actual_requests_only, test_backfill_rejects_rows_outside_end_exclusive_window, test_semantically_inconsistent_completion_marker_fails_closed_before_http, test_resume_fails_closed_when_wire_metadata_is_corrupt, test_checkpoint_namespace_fsync_failure_rolls_back_visible_marker | `8f88559bb55cafa2` |
| `tests/integration/lab/test_d01_training_smoke.py` | _generate_synthetic_tabular_data, test_d01_01_valid_contract, test_d01_01_contract_1, test_d01_01_contract_2, test_d01_01_contract_3 | `e2975e28f623fd7f` |
| `tests/integration/lab/test_deeplob_smoke.py` | _generate_synthetic_lob_series, test_l01_01_valid_contract, test_l01_01_contract_1, test_l01_01_contract_2, test_l01_01_contract_3 | `46e6f2756cf98efa` |
| `tests/integration/lab/test_disaster_drills.py` | test_drill_1_crash_after_submit_recovers_across_restart, test_drill_2_http_500_server_error_and_kill_switch_halt, test_drill_3_cancel_fill_race_under_partial_fill, test_drill_4_backward_clock_jump_fails_closed | `06cd3aa49aed040c` |
| `tests/integration/lab/test_feature_materialization.py` | _create_registry_yaml, _make_bars, test_feat_04_valid_contract, test_feat_04_contract_1, test_feat_04_contract_2, test_feat_04_contract_3, test_canonical_wave1_feature_materialization, _small_registry, test_feature_rejects_unusable_temporal_history, test_btc_feature_uses_available_benchmark_not_asset, test_builder_recomputes_cross_section_eligibility_after_context, test_optional_infinite_source_does_not_become_eligible | `95374693c3f5625c` |
| `tests/integration/lab/test_operational_recovery.py` | test_qa_03_valid_contract, test_synthetic_smoke_checks_cannot_default_to_qualified, test_qa_03_contract_1, test_qa_03_contract_2, test_qa_03_contract_3 | `946d59fe1bbe0a35` |
| `tests/integration/lab/test_raw_to_silver_pipeline.py` | FixtureTransport, test_golden_raw_to_silver_replay_is_immutable_and_content_addressed, test_24_hour_trade_batch_resource_smoke_records_child_vm_hwm_without_hardware_gate, test_quarantined_trade_batch_cannot_publish_bars, _run_golden_pipeline, _build_bars, _write_public_trade_batch, _materialize_metrics | `ca3ef786b9bdaade` |
| `tests/integration/lab/test_retention.py` | _setup_storage_environment, test_ops_03_valid_contract, test_ops_03_contract_1, test_ops_03_contract_2, test_ops_03_contract_3 | `ce0233ec98e3a0a7` |
| `tests/integration/lab/test_service_lifecycle.py` | test_ops_01_valid_contract, test_ops_01_contract_1, test_ops_01_contract_2, test_ops_01_contract_3, test_managed_service_without_hooks_fails_closed, test_failed_flush_does_not_release_lease_or_claim_success, _hold_process_lock, test_os_lock_is_released_when_owner_process_dies | `043905158a8b8420` |
| `tests/integration/lab/test_snapshot_validation.py` | _candle, test_checksum_mismatch_quarantines_without_mutating_bronze_or_raw, test_cli_emits_structured_failure_and_exit_three_for_corrupt_snapshot, test_cli_returns_four_for_invalid_invocation_without_traceback, test_cli_returns_zero_for_pass_and_two_for_unapproved_warning, test_valid_cli_corrupt_content_returns_structured_fail_not_invalid_invocation, test_full_shaped_inconsistent_pass_cannot_authorize_silver, test_unsafe_snapshot_id_is_an_invalid_invocation_before_any_path_write, test_interval_invalid_requested_window_is_invalid_invocation, test_symlink_loop_in_snapshot_path_is_structured_content_failure, test_quality_record_publication_failures_are_structured_and_not_claimed_written, _write_schema_valid_snapshot | `90cac0b171fb92ef` |
| `tests/integration/lab/test_telegram_status.py` | test_report_02_valid_contract, test_report_02_contract_1, test_report_02_contract_2, test_report_02_contract_3 | `12288665db3b08f2` |
| `tests/integration/lab/test_tlob_smoke.py` | _generate_synthetic_lob_series, test_l02_01_valid_contract, test_l02_01_contract_1, test_l02_01_contract_2, test_l02_01_contract_3 | `8551e65fdb4315b8` |
| `tests/integration/lab/test_training_materialization.py` | _build_test_data, test_train_01_valid_contract, test_train_01_contract_1, test_train_01_contract_2, test_train_01_contract_3, _temporal_inputs, _assemble_temporal, test_training_preserves_label_availability, test_training_rejects_label_received_after_declared_cutoff, test_training_rejects_missing_feature_temporal_evidence, test_training_rejects_missing_label_availability, test_training_rejects_identity_disagreement, test_training_cannot_accept_unknown_fold_cutoff, test_generated_fold_cutoffs_exclude_delayed_labels_from_training, test_training_identity_binds_logical_content, test_training_identity_deterministic_for_reordered_rows_and_has_digests, test_legacy_split_without_policy_evidence_requires_rebuild, test_training_rejects_invalid_identity_or_inference_contract | `cb8efb07c5348d26` |
| `tests/integration/lab/test_universe_snapshot.py` | _sha, _metrics, FakeTransport, test_fake_provider_persists_raw_lineage_and_preserves_decimal_integer_types, test_current_only_provider_never_queries_current_markets_for_a_historical_date, test_provider_rejects_source_timestamp_after_response_availability, test_safe_header_variation_produces_distinct_immutable_response_identity, test_rate_quota_and_provider_errors_are_explicit_unavailable_never_zero, test_snapshot_retains_delisted_and_new_pairs_and_is_content_addressed, test_current_or_late_cap_never_labels_past_and_raw_input_changes_snapshot_id, test_cli_dry_run_is_offline_and_creates_no_output_root | `a7f908c959106f4a` |
| `tests/integration/test_paper_db_migration.py` | _create_legacy_db, _create_v1_real_accounting_db, _point_module_at_db, _open_and_close_exact_trade, paper_trader_module, test_migration_adds_nullable_accounting_columns_without_rewriting_legacy_row, test_migration_creates_one_deterministic_legacy_backup_before_schema_change, test_backup_failure_aborts_migration_without_mutating_original, test_migration_failure_rolls_back_original_and_keeps_recovery_backup, test_v1_real_accounting_schema_rebuilds_to_text_and_preserves_owned_objects, test_bar_state_migration_preserves_later_checkpoint, test_real_accounting_rebuild_preserves_existing_bar_state_foreign_key, test_v1_real_schema_rebuild_failure_rolls_back_and_keeps_backup, test_new_trade_persists_exact_cost_basis_fees_and_net_proceeds, test_authoritative_decimal_fields_round_trip_as_canonical_text_without_float_loss, test_open_trade_rejects_invalid_inputs_without_inserting, test_close_trade_rejects_invalid_price_and_leaves_trade_open, test_weekly_report_marks_legacy_accounting_as_estimated, test_weekly_stats_marks_all_exact_accounting, test_weekly_stats_distinguishes_mixed_accounting_from_all_legacy, test_empty_weekly_stats_include_accounting_status_and_zero_counts, _CoordinatedCursor, _CoordinatedConnection, test_two_connections_cannot_both_successfully_close_the_same_trade | `ba9a2156375b2e53` |
| `tests/integration/test_signal_observation.py` | _load_observer_module, test_records_evaluated_candidate_without_manual_callback, test_replaying_same_decision_bar_returns_existing_observation, test_conflicting_decision_payload_fails_closed_without_reusing_stale_row, test_plan_is_persisted_when_shadow_policy_is_disabled, test_observer_v1_schema_migrates_backup_first_and_idempotently, test_observer_migration_enforces_action_intent_foreign_key, test_manual_action_intent_is_separate_from_observation_creation, test_shadow_outcome_uses_closed_15m_bar_and_is_restart_idempotent, test_shadow_decision_at_boundary_accepts_the_newly_closed_bar, test_conflicting_duplicate_bar_fails_closed_without_checkpoint, test_identical_out_of_order_duplicates_are_processed_once_in_bar_order, test_shadow_policy_can_keep_passing_candidate_closed, test_paper_trader_uses_closed_bar_range_and_persists_bar_identity, test_paper_bar_is_retried_when_close_does_not_commit, test_paper_close_and_bar_checkpoint_roll_back_together, test_paper_connection_enforces_bar_state_foreign_key, test_paper_conflicting_duplicate_does_not_advance_state, test_process_pair_opens_observation_before_telegram_callback, test_process_pair_persists_later_gate_failure_as_one_final_row, _FakeQuery, _FakeBot, test_actual_telegram_callbacks_persist_intent_before_downstream_action, test_legacy_callback_without_observation_id_is_rejected_explicitly, test_shadow_config_defaults_disabled_and_callback_payloads_fit_limit | `8ce6ef75afc83590` |
| `tests/property/lab/test_ledger_invariants.py` | test_transaction_balance_invariant, test_unit_separation_and_equity_invariant, test_cost_schedule_integration | `b6818123ee974430` |
| `tests/regression/test_phase0_invariants.py` | _bullish_decision, test_phase0_public_invariants_are_reconciled_and_offline | `fc5ba64a5e8b36cf` |
| `tests/regression/test_phase1_snapshot.py` | test_phase1_gate_quarantines_checksum_mismatch_before_silver_eligibility, test_phase1_gate_refuses_to_publish_bars_without_an_approved_source_decision, test_phase1_gate_rejects_gaps_and_upstream_quarantine_before_silver, _candle | `2a49dd4c638b5eb8` |
| `tests/regression/test_release_candidate.py` | test_rel_01_valid_contract, test_rel_01_contract_1, test_rel_01_contract_2, test_rel_01_contract_3 | `17ad1853c3017e50` |
| `tests/regression/test_wave1_tournament.py` | test_qa_01_valid_contract, test_qa_01_contract_1, test_qa_01_contract_2, test_qa_01_contract_3 | `beb19da4d6b1eaba` |
| `tests/research/test_rl_reward_contract.py` | test_r01_01_valid_contract, test_r01_01_contract_1, test_r01_01_contract_2, test_r01_01_contract_3 | `2df15e9fabf70ffe` |
| `tests/security/test_lab_boundaries.py` | test_qa_02_valid_contract, test_qa_02_contract_1, test_qa_02_contract_2, test_qa_02_contract_3 | `601518a3789d7d36` |
| `tests/unit/lab/__init__.py` | module declarations | `49d34321965aa349` |
| `tests/unit/lab/backtest/__init__.py` | module declarations | `7f10cd64e2e1d84e` |
| `tests/unit/lab/backtest/test_accounting_failure_atomicity.py` | test_invalid_paper_allocation_never_changes_cash, make_fill, test_paper_position_failure_keeps_event_retryable, test_paper_rejects_naive_decision_time, test_fee_inclusive_overdraft_rejected_without_postings, test_failed_balance_check_does_not_consume_fill, test_risk_cap_counts_existing_position | `57d8bf7fb259aad2` |
| `tests/unit/lab/backtest/test_cost_schedule.py` | _sample_schedule_yaml, test_cost_01_valid_contract, test_cost_01_contract_1, test_cost_01_contract_2, test_cost_01_contract_3, test_cost_schedule_rejects_negative_rate_and_naive_datetime | `e07d8bb62a7dde42` |
| `tests/unit/lab/backtest/test_execution.py` | sample_cost_table, test_sim_01_valid_contract, test_sim_01_contract_1, test_sim_01_contract_2, test_sim_01_contract_3 | `7a426d0e972b8c3b` |
| `tests/unit/lab/backtest/test_feature_replay.py` | _make_5m_feature_row, _make_1h_feature_row, _make_signal_df, _make_context_df, test_fr01_config_requires_pair, test_fr02_future_leakage_detected, test_fr03_no_leakage_when_ready_at_eq_decision, test_fr04_ineligible_rows_excluded, test_fr05_as_of_future_rows_excluded, test_fr06_future_context_fails_closed, test_fr07_valid_context_attached, test_fr08_missing_context_no_bfill, test_fr09_pair_mismatch_context_rejected, test_fr10_naive_timestamp_rejected, test_fr11_load_bars_from_parquet_returns_market_bars, test_fr12_bars_sorted_ascending, test_fr13_signal_decision_ts_is_bar_available_at, test_fr14_naive_as_of_rejected, test_fr15_warmup_rows_produce_no_eligible_pairs, test_fr16_context_strictly_backward_only, test_fr17_config_immutable, test_fr18_missing_row_ready_at_column_rejected | `700b5d4cb78e8741` |
| `tests/unit/lab/backtest/test_indodax_cost_boundaries.py` | _cost, test_cfx_activation_boundary, test_2025_tax_boundary, test_2026_cfx_reduction_boundary, test_observed_current_pro_minimum_boundary | `d24de893c291f215` |
| `tests/unit/lab/backtest/test_judge_remediation.py` | offline, costs, policy, bar, intent, test_invalid_risk_policy_fails_closed, test_invalid_initial_cash, test_halted_manager_allows_safe_sell, test_invalid_mark_does_not_change_halt_state, test_pending_buys_share_reserved_cash_and_release, test_gap_up_rechecks_actual_fee_inclusive_cash, test_exit_is_independent_and_never_backdated, test_open_fill_ignores_outcome_volume_and_extrema, test_maker_bar_evidence_is_not_backdated, test_missing_open_liquidity_is_rejected, test_same_engine_replay_resets_all_state, test_shared_allocations_are_serialized, test_ledger_revalidates_forged_fee_without_mutation, test_execution_identity_discloses_proxy_and_binds_event_time, test_reservations_cancel_idempotently_and_protect_other_orders, test_bar_rejects_partial_and_noncausal_evidence, test_stale_open_liquidity_is_rejected, test_quantity_precision_never_rounds_minimum_up, test_delayed_observation_cannot_supply_open_liquidity, test_open_pair_never_uses_future_other_pair_close, test_rejected_and_end_of_run_pending_orders_release_cash, test_maker_without_limit_rejects_without_crashing, test_risk_position_cap_includes_rounded_fee_equity_loss, test_peak_and_drawdown_are_observed_without_strategy_intents, test_actual_fill_rechecks_new_cost_schedule, test_research_ledger_serializes_competing_fills | `348c054884fc2439` |
| `tests/unit/lab/backtest/test_ledger.py` | test_led_01_valid_contract, test_led_01_contract_1, test_led_01_contract_2, test_led_01_contract_3, test_ledger_state_roundtrip_preserves_balanced_history, test_ledger_state_tamper_fails_closed | `26fee923752d0501` |
| `tests/unit/lab/backtest/test_metrics.py` | _populate_sample_ledger, test_sim_04_valid_contract, test_sim_04_contract_1, test_sim_04_contract_2, test_sim_04_contract_3 | `7e3d695177923541` |
| `tests/unit/lab/backtest/test_risk.py` | default_policy, test_sim_02_valid_contract, test_sim_02_contract_1, test_sim_02_contract_2, test_sim_02_contract_3 | `b795f465e86eb13b` |
| `tests/unit/lab/cli/test_operator_clis.py` | test_kill_switch_cli_lifecycle, test_kill_switch_cli_clear_governance, test_approval_cli_lifecycle, test_approval_cli_reject_and_clean, test_reconcile_cli_missing_credentials, test_reconcile_cli_fake_drill, test_reconcile_cli_with_authoritative_stores_and_output | `5847b3f309b0402a` |
| `tests/unit/lab/control/test_control_pipeline.py` | pipeline_fixture, test_pipeline_disabled_mode_skips, test_pipeline_read_only_mode_does_not_write_or_persist, test_pipeline_shadow_mode_routes_to_venue, test_pipeline_manual_approval_queues_proposal, test_pipeline_autonomous_limited_success_and_breach, test_pipeline_autonomous_limited_uncertain_submit_trips_kill_switch, test_pipeline_autonomous_daily_loss_limit_trips_kill_switch, test_pipeline_reconciliation_pre_write_gate, test_pipeline_recover_and_promote, test_pipeline_execute_approved_proposal_with_hmac_and_risk_recheck | `49fc5995fff1bc8c` |
| `tests/unit/lab/control/test_manual_approval_execution.py` | test_manual_approval_hmac_token_verification, test_trading_pipeline_execute_approved_proposal | `fda716ed506ae2e8` |
| `tests/unit/lab/control/test_mode_durability_and_shadow_isolation.py` | test_durable_mode_store_persistence_and_transitions, test_shadow_mode_structurally_forbids_live_venue | `952d3f205d062ba8` |
| `tests/unit/lab/data/test_book_recovery.py` | _fixture, test_gap_recovers_from_official_offset_without_crossing_an_unreliable_window, test_recovery_response_must_match_outstanding_request_session_and_pair, test_recovering_demultiplexes_heartbeat_trade_book_and_stale_control, test_batch_is_durable_before_checkpoint_and_failed_flush_remains_retryable, test_heartbeat_timeout_reconnects_with_injected_backoff_then_shutdown_flushes, test_failed_recovery_quarantines_exact_gap_and_rotates_session, test_quarantine_publish_failure_preserves_gap_for_retry_without_duplicate, test_transport_abandonment_durably_quarantines_pending_gap, test_offset_regression_is_quarantined_before_new_session_sync, test_backoff_resets_after_a_subscribed_connection_receives_a_valid_frame, test_trade_and_control_traffic_do_not_refresh_heartbeat_deadline, test_recognized_heartbeat_refreshes_deadline_and_requests_next_ping, test_cli_retains_and_awaits_signal_shutdown_task, test_shutdown_flush_failure_still_closes_transport, test_sigterm_quarantine_failure_closes_transport_and_keeps_gap_retryable, test_cli_dry_run_exposes_only_public_channels_and_never_the_static_token, test_websocket_library_close_is_normalized_at_lazy_transport_boundary, test_lazy_connector_uses_supported_websockets_exception_module, test_websocket_handshake_failure_is_normalized_for_reconnect, _collector_for, _FakeTransport | `698defd93b4446f8` |
| `tests/unit/lab/data/test_dataset_quality_cli.py` | _ts, _make_row, _write_parquet_and_manifest, test_validate_manifest_passes_clean_rows, test_validate_manifest_detects_duplicate_pair_open_time, test_validate_manifest_detects_gap_in_interval, test_validate_manifest_detects_non_chronological, test_validate_manifest_detects_ohlc_invalid_high_below_close, test_validate_manifest_detects_ohlc_invalid_low_above_open, test_validate_manifest_detects_availability_before_close, test_validate_manifest_detects_listing_cutoff_violation, test_validate_manifest_passes_rows_after_listing_cutoff, test_validate_manifest_detects_checksum_mismatch, test_validate_manifest_blocked_status_on_any_failure | `dfa34349164fc033` |
| `tests/unit/lab/data/test_event_bars.py` | _approved_source, _batch_args, _wire_trade, _trade, _build, test_cusum_closes_on_positive_and_negative_boundaries_then_resets, test_range_boundary_includes_crossing_trade_and_resets_range, test_cumulative_volume_and_dollar_boundaries_are_exact, test_partial_final_bar_is_excluded_with_auditable_remainder, test_input_order_does_not_change_event_boundaries_or_ids, test_fit_threshold_must_exist_by_as_of_and_end_before_as_of, test_valid_fit_artifact_is_lineage_and_never_refit_from_events, test_threshold_must_be_positive_exact_decimal, test_wrong_pair_unreliable_or_future_trade_fails_closed, test_event_config_loader_is_strict_and_content_addressed, test_event_threshold_config_rejects_cusum_time_bar_and_duplicate_ids, _continuity, test_fitted_threshold_must_predate_first_event_and_be_available_by_first_input, test_fitted_threshold_lineage_and_availability_reach_result_bar_and_cli_payload, test_event_bar_identity_changes_for_every_material_construction_input, test_stream_event_bars_require_continuity_and_never_bridge_gap_or_session, test_bar_builders_always_reject_even_identical_duplicate_event_ids, test_fitted_artifact_yaml_accepts_exact_string_or_integer, test_fitted_artifact_rejects_bool_and_float_thresholds, test_event_cli_publishes_fitted_threshold_id_version_and_policy_lineage, test_fixed_threshold_has_explicit_null_artifact_provenance, test_event_config_rejects_removed_duplicate_policy | `64fd2e4d8b979e1e` |
| `tests/unit/lab/data/test_indodax_candles.py` | _wire_request, test_named_shape_parsers_are_offline_boundary_functions, test_parser_canonicalizes_supported_shapes_without_zero_filling, test_source_event_ids_ignore_ingestion_time_and_input_order, test_conflicting_duplicate_identity_is_rejected_without_order_dependent_winner, test_epoch_overflow_is_an_explicit_row_reject_and_does_not_abort_batch, test_unsupported_top_level_shapes_fail_closed, test_wire_store_persists_raw_response_and_safe_audit_metadata_immutably, test_wire_metadata_publish_failure_rolls_back_new_body, test_wire_publish_durably_records_parent_creation_and_idempotent_reuse, test_wire_partial_cleanup_failure_rolls_back_visible_body, test_wire_failed_rollback_reports_indeterminate_publication, test_client_writes_wire_before_unsupported_json_shape_is_parsed | `7e153da19228fd85` |
| `tests/unit/lab/data/test_manifest.py` | test_manifest_id_is_stable_for_equivalent_partition_ordering, test_manifest_id_changes_when_a_partition_checksum_changes | `cde21c99c72b37e8` |
| `tests/unit/lab/data/test_parquet_store.py` | _candle, test_store_writes_sorted_zstd_utc_partitions_and_content_addressed_manifest, test_candle_schema_uses_documented_decimals_and_utc_timestamps, test_store_reuses_identical_content_and_changes_snapshot_when_source_changes, test_store_never_overwrites_a_tampered_content_addressed_partition, test_store_returns_retryable_failure_and_never_publishes_manifest_after_write_error, test_store_returns_retryable_failure_when_manifest_publish_link_fails, test_partial_cleanup_failure_rolls_back_new_partition_and_never_reports_success, test_failed_partition_rollback_reports_indeterminate_publication, test_successful_new_and_idempotent_writes_fsync_partition_and_manifest_namespaces, test_corrupt_parquet_validation_maps_to_retryable_failure_without_manifest, test_corrupt_existing_manifest_maps_to_retryable_failure | `501026eaa85e862b` |
| `tests/unit/lab/data/test_quality.py` | _row, test_dataset_contract_failures_are_structured, test_stale_final_bar_is_a_fail_with_injected_as_of, test_report_preserves_subsecond_staleness_policy_exactly, test_report_has_stable_content_and_exact_coverage_facts, test_upstream_warning_requires_explicit_approval_but_is_not_a_contract_failure, test_non_approved_source_statuses_fail_closed, test_gap_findings_are_clipped_coalesced_and_count_missing_intervals | `762546f4625a2d37` |
| `tests/unit/lab/data/test_stream_parser.py` | _fixture, test_public_trade_parser_preserves_official_identity_decimal_and_utc_contracts, test_book_protocol_reaches_reliable_only_after_a_valid_snapshot, test_identical_duplicate_offset_is_idempotent_and_emits_no_book_rows, test_conflicting_duplicate_offset_fails_closed, test_heartbeat_is_recognized_without_becoming_market_data, test_unrelated_bare_control_id_is_not_a_recognized_heartbeat, test_public_authentication_ack_is_control_data_not_a_protocol_failure, test_configured_book_pair_mismatch_fails_before_state_mutation, test_offset_regression_is_structured_without_an_inverted_missing_window, test_reconnect_cannot_clear_an_unquarantined_pending_gap | `d408c729f484f559` |
| `tests/unit/lab/data/test_time_bars.py` | _approved_source, _batch_args, _wire_trade, _trade, test_one_minute_bar_is_exact_end_exclusive_and_availability_safe, test_ids_and_values_ignore_input_order_and_ingestion_order, test_bar_preserves_one_trade_source_and_rejects_cross_provider_mixing, test_empty_bucket_is_an_explicit_gap_not_a_fabricated_candle, test_non_pass_trade_fails_the_whole_requested_window, test_conflicting_duplicate_trade_identity_fails_closed, test_resampling_requires_every_contiguous_smaller_bar, test_resampling_uses_smallest_reliable_source_and_exact_ohlcv, test_official_mismatch_is_reported_and_source_is_selected_without_merging, test_time_config_loader_rejects_unknown_fields_and_has_content_identity, test_cli_dry_run_is_offline_non_writing_and_identity_is_replay_stable, test_cli_publishes_content_addressed_time_bars_without_network, test_time_bar_identity_changes_with_lag_provider_session_and_policy, test_resample_rejects_mixed_pair_provider_snapshot_or_session, test_reconciliation_reports_union_missing_keys_and_blocks_incomplete_official_selection, test_reconciliation_applies_explicit_tolerance_and_validates_full_lineage, test_reconciliation_compares_availability_interval_and_bar_type, test_cli_requires_independent_official_provider_and_snapshot_anchors, test_cli_validates_every_official_row_before_interval_grouping, test_duplicate_policy_is_not_accepted_by_strict_bar_configs | `50b3703b1f6a6dfb` |
| `tests/unit/lab/data/test_trade_sentry.py` | test_global_validator_rejects_garbage_wire_with_supplied_valid_event, test_global_validator_rejects_batch_event_different_from_parsed_wire, test_loader_rejects_content_addressed_forged_pass_for_mixed_pairs, test_global_validator_rejects_mixed_presence_duplicates_and_gaps, test_global_validator_detects_omitted_middle_batch_and_ignores_cli_order, _trade, _batch, _official_payload, _wire_link, _raw_batch, _forge_pass | `3d7e99a810f005db` |
| `tests/unit/lab/evaluation/__init__.py` | module declarations | `e486a6a2e1b0cb4e` |
| `tests/unit/lab/evaluation/test_gates.py` | _build_test_run, test_eval_02_valid_contract, test_eval_02_contract_1, test_eval_02_contract_2, test_eval_02_contract_3 | `d252edae03210b21` |
| `tests/unit/lab/evaluation/test_lifecycle.py` | _build_test_candidate, test_eval_03_valid_contract, test_eval_03_contract_1, test_eval_03_contract_2, test_eval_03_contract_3 | `f75067eb9fdc69af` |
| `tests/unit/lab/evaluation/test_registry.py` | _make_run, test_eval_01_valid_contract, test_eval_01_contract_1, test_eval_01_contract_2, test_eval_01_contract_3 | `9d2f1b8a9259e51d` |
| `tests/unit/lab/execution/test_fill_ingestion.py` | make_venue_fill, temp_env, test_fill_ingestion_single_buy_updates_ledger_and_oms, test_fill_ingestion_completes_order_to_filled, test_fill_ingestion_duplicate_fill_skipped_idempotently, test_fill_ingestion_non_quote_commission_fails_closed, test_fill_ingestion_quote_notional_mismatch_fails_closed, FakeClient, FakeService, test_durable_reconciliation_coordinator_auto_ingests_and_advances | `35a4360e3bfb417b` |
| `tests/unit/lab/execution/test_fill_ingestion_overfill_and_repair.py` | test_fill_ingestion_overfill_raises_invariant_error, test_fill_ingestion_duplicate_replay_repairs_stale_oms_order | `4fc07596967eb9f7` |
| `tests/unit/lab/execution/test_fill_normalizer.py` | _fill, test_real_venue_commission_becomes_ledger_fee_without_recalculation, test_non_quote_commission_fails_closed_until_explicit_valuation_exists, test_inconsistent_venue_quote_notional_fails_closed | `dfb1ce35854e6234` |
| `tests/unit/lab/execution/test_indodax_readonly.py` | FakeResponse, FakeSession, test_get_info_signing_and_balance_normalization, test_v2_trade_history_uses_current_endpoint_and_normalizes_fill, test_client_exposes_no_order_write_or_withdraw_methods, test_open_buy_order_with_idr_amount_normalizes_to_base_quantity, test_get_order_by_client_id_handles_legacy_rp_buy_amount | `7317b3e8f00c972a` |
| `tests/unit/lab/execution/test_ledger_store.py` | test_ledger_store_initialization, test_ledger_store_durability_across_restart, test_ledger_store_tamper_detection, test_ledger_store_snapshot_tamper_detection | `41f6f58cc235123d` |
| `tests/unit/lab/execution/test_oms.py` | _new_order, test_unknown_state_requires_reconciliation, test_oms_store_persists_unknown_state_across_restart, test_unknown_can_only_resolve_from_venue_evidence, test_illegal_direct_new_to_filled_is_rejected, test_partial_fill_invariants_are_enforced, test_transition_revalidates_nonfinite_values, test_stale_writer_cannot_overwrite_newer_order_state, test_tampered_oms_payload_fails_closed, test_model_boundary_rejects_acknowledged_without_venue_id, test_client_order_id_contract_matches_indodax_limit | `8f138d9035165d12` |
| `tests/unit/lab/execution/test_oms_limit_price.py` | test_oms_order_limit_price_validation, test_indodax_trading_client_rejects_missing_or_invalid_limit_price | `34ddcc2b288baef0` |
| `tests/unit/lab/execution/test_order_router.py` | temp_router, test_order_router_normal_submit_acknowledged, test_order_router_definite_reject, test_order_router_uncertain_submit_transitions_to_unknown, test_order_router_cancel_fill_race_partial_fill, test_order_router_cancel_fill_race_full_fill, test_indodax_trading_venue_security_boundary_no_withdrawals | `24cb26fc00a1a9f4` |
| `tests/unit/lab/execution/test_read_only_reconciler.py` | FakeReadOnlyClient, _account, test_service_fetches_private_truth_and_returns_healthy, test_saturated_fill_window_halts_instead_of_silently_truncating, test_service_rejects_implicit_or_too_wide_fill_window, test_ledger_fill_absent_from_venue_history_halts | `b55ddd248a246166` |
| `tests/unit/lab/execution/test_read_only_smoke.py` | FakeSmokeClient, test_smoke_result_contains_only_structural_health_not_private_amounts, test_smoke_main_reports_blocked_external_when_credentials_missing | `b8522deb1419dce4` |
| `tests/unit/lab/execution/test_readonly_retry_resigning.py` | FakeResponse, FakeSession, test_legacy_view_call_regenerates_timestamp_and_signature_on_retry, test_v2_get_regenerates_timestamp_and_signature_on_retry | `0a6447397ddadae6` |
| `tests/unit/lab/execution/test_reconciliation.py` | _account, _ledger_with_btc, test_matching_balances_orders_and_fills_are_healthy, test_quote_balance_mismatch_halts_new_orders, test_unexpected_venue_order_halts_new_orders, test_venue_fill_missing_from_ledger_halts_new_orders | `bfe2d2021182154f` |
| `tests/unit/lab/execution/test_reconciliation_coordinator.py` | FakeService, _report, test_healthy_cycle_advances_durable_cursor, test_unhealthy_cycle_does_not_advance_cursor | `7a9cdc803705cce6` |
| `tests/unit/lab/execution/test_reconciliation_store.py` | test_cursor_initializes_and_advances_with_overlap, test_stale_cursor_writer_is_rejected, test_cursor_tampering_fails_closed | `4e7a58e409178bed` |
| `tests/unit/lab/execution/test_unknown_resolution_inconclusive.py` | test_resolve_unknown_order_inconclusive_leaves_unknown, test_resolve_unknown_order_definitive_fill_transitions_to_filled | `e3b408303fd27de5` |
| `tests/unit/lab/features/__init__.py` | module declarations | `5a47518672adc371` |
| `tests/unit/lab/features/test_availability.py` | test_context_preserves_feature_and_universe_eligibility, test_context_requires_feature_evidence, test_asof_rejects_missing_closed_evidence, _minimal_config, _bars, test_asof_join_uses_only_available_complete_4h_and_daily_bars, test_point_in_time_rank_and_breadth_ignore_ineligible_and_future_universe_rows, test_feat_03_valid_contract, test_feat_03_contract_1, test_feat_03_contract_2, test_feat_03_contract_3, test_warmup_rows_stay_null_with_reason_and_never_backfill, test_build_features_cli_dry_run_is_offline_and_non_mutating, test_build_features_cli_persists_parquet_and_companion_manifest | `238e13d8f6d4b850` |
| `tests/unit/lab/features/test_registry.py` | _registry_yaml, _ema_feature, test_canonical_registry_contains_exact_wave1_names_and_metadata, test_registry_rejects_duplicate_names_bfill_and_insufficient_lookback, test_registry_rejects_timeframe_without_asof_policy, test_registry_requires_version_bump_when_content_changes, test_feat_01_valid_contract, test_feat_01_contract_1, test_feat_01_contract_2, test_feat_01_contract_3, test_5m_registry_loads_with_correct_interval_and_feature_count, test_5m_registry_context_features_use_asof_policy, test_5m_suffix_in_1h_registry_requires_asof_policy | `8f4fa078c0207e57` |
| `tests/unit/lab/features/test_technical.py` | _ohlcv, test_normalized_indicators_match_explicit_golden_values, test_price_rescaling_does_not_change_cross_asset_normalized_indicators, test_feat_02_valid_contract, test_feat_02_contract_1, test_feat_02_contract_2, test_feat_02_contract_3 | `e8d96e27e9cab418` |
| `tests/unit/lab/labels/__init__.py` | module declarations | `338c46cebdf0d684` |
| `tests/unit/lab/labels/test_returns.py` | test_open_price_proxy_cannot_claim_verified_simulator_fills, test_delayed_entry_observation_delays_label_availability, test_other_pair_cannot_supply_label_prices, test_unclosed_outcome_source_excludes_label, test_gap_inside_outcome_horizon_excludes_label, test_non_utc_outcome_availability_is_rejected, test_duplicate_outcome_bar_cannot_choose_arbitrary_price, test_closed_outcome_cannot_be_available_before_close, test_partial_bar_with_early_availability_remains_auditable, test_generated_label_frame_flows_through_split_and_training, _make_schedule_table, _make_market_bars, test_label_01_valid_contract, test_label_01_contract_1, test_label_01_contract_2, test_label_01_contract_3, test_label_changes_when_cost_changes, test_delayed_label_excluded_from_training_cutoff, test_no_future_input_affects_earlier_labels, test_proxy_cannot_be_promoted | `b65faa6900ca6f31` |
| `tests/unit/lab/labels/test_splits.py` | _build_test_policy, test_split_identity_binds_policy_and_preserves_row_order_equivalence, test_split_rejects_duplicate_sample_identity, test_split_rejects_overlapping_folds, test_split_01_valid_contract, test_split_01_contract_1, test_split_01_contract_2, test_split_01_contract_3, test_unknown_label_availability_is_not_trainable, test_delayed_label_is_purged_at_training_cutoff, test_adjacent_folds_use_half_open_decision_boundaries, test_adjacent_exposure_does_not_overlap_sealed_fold | `46e612cd02dc2ce8` |
| `tests/unit/lab/labels/test_triple_barrier.py` | _make_bar, test_label_02_valid_contract, test_label_02_contract_1, test_label_02_contract_2, test_label_02_contract_3, test_label_02_concurrency_weights | `3cf3204ac2d4ce30` |
| `tests/unit/lab/market/test_gap_detection_and_invalid_price.py` | _make_bar, test_quality_guard_detects_forward_interval_gap, test_market_health_report_is_clean_rejects_invalid_and_crossed_prices, test_market_gateway_snapshot_with_zero_price_is_unsafe | `a280c0d1f3ab7bb3` |
| `tests/unit/lab/market/test_market_gateway.py` | test_clock_guard_rejects_naive_timestamp, test_clock_guard_detects_backwards_regression, test_clock_guard_detects_offset_exceeding_threshold, test_data_quality_guard_rejects_non_positive_and_crossed_ticker, test_data_quality_guard_detects_stale_ticker, test_data_quality_guard_enforces_closed_bar_semantics, test_data_quality_guard_detects_duplicate_and_out_of_order_bars, test_market_gateway_produces_healthy_snapshot, test_market_gateway_fails_closed_on_clock_unsafe, test_market_gateway_fails_closed_on_stale_data | `2c4da12c47c239b2` |
| `tests/unit/lab/models/dl/test_early_stopping.py` | test_dl_01_valid_contract, test_dl_01_contract_1, test_dl_01_contract_2, test_dl_01_contract_3 | `ab3dfe05fe2848ee` |
| `tests/unit/lab/models/dl/test_sequence_dataset.py` | _generate_synthetic_bar_df, test_sequence_never_crosses_repeated_role_boundaries, test_sequence_rejects_unsafe_inputs, test_sequence_arrays_are_immutable, test_sequence_torch_conversion_does_not_alias_immutable_numpy, test_sequence_revalidates_mutated_allowlist_and_identity, test_sequence_rejects_null_sample_identity, test_dl_02_valid_contract, test_dl_02_contract_1, test_dl_02_contract_2, test_dl_02_contract_3 | `baab27432f295b33` |
| `tests/unit/lab/models/lob/test_lob_data_gate.py` | test_lob_01_valid_contract, test_lob_01_contract_1, test_lob_01_contract_2, test_lob_01_contract_3 | `3fb3121b8a69263c` |
| `tests/unit/lab/models/test_d02_01.py` | _generate_synthetic_sequences, test_d02_01_valid_contract, test_d02_01_contract_1, test_d02_01_contract_2, test_d02_01_contract_3 | `5a5f46ac828d3be6` |
| `tests/unit/lab/models/test_d03_01.py` | _generate_synthetic_sequences, test_d03_01_valid_contract, test_d03_01_contract_1, test_d03_01_contract_2, test_d03_01_contract_3 | `4d7245be2f681a33` |
| `tests/unit/lab/models/test_d04_01.py` | test_d04_01_valid_contract, test_d04_01_contract_1, test_d04_01_contract_2, test_d04_01_contract_3 | `ae5b42bd466ac4a1` |
| `tests/unit/lab/models/test_execution_mapper.py` | test_ml_02_valid_contract, test_ml_02_contract_1, test_ml_02_contract_2, test_ml_02_contract_3, test_ml_02_edge_cases_and_guards | `73c0ec0a68faa0b2` |
| `tests/unit/lab/models/test_f01_01.py` | test_f01_01_valid_contract, test_f01_01_contract_1, test_f01_01_contract_2, test_f01_01_contract_3 | `b7e8578b133f9b32` |
| `tests/unit/lab/models/test_f01_02.py` | _generate_synthetic_foundation_features, test_f01_02_valid_contract, test_f01_02_contract_1, test_f01_02_contract_2, test_f01_02_contract_3 | `96687375762ff0ed` |
| `tests/unit/lab/models/test_g01_01.py` | _generate_synthetic_panel_data, test_g01_01_valid_contract, test_g01_01_contract_1, test_g01_01_contract_2, test_g01_01_contract_3 | `a725585b718e63f4` |
| `tests/unit/lab/models/test_m01_logistic.py` | _generate_synthetic_classification_data, test_m01_01_valid_contract, test_m01_01_contract_1, test_m01_01_contract_2, test_m01_01_contract_3, test_m01_01_config_yaml_and_unfitted_guards | `6240284d68bac3c1` |
| `tests/unit/lab/models/test_m02_xgboost.py` | _generate_tabular_dataset, test_m02_01_valid_contract, test_m02_01_contract_1, test_m02_01_contract_2, test_m02_01_contract_3, test_m02_01_config_yaml_and_unfitted_guards | `1e8f1238d7fbc90d` |
| `tests/unit/lab/models/test_m03_rf_regime.py` | _make_feature_df, _make_regime_labels, _build_trainer_and_bundle, test_m03_01_valid_contract, test_m03_01_contract_1, test_m03_01_contract_2, test_m03_01_contract_3, test_m03_01_not_fitted_error | `7c3a2038845f0856` |
| `tests/unit/lab/models/test_m04_quantile_risk.py` | _make_returns, _make_features, test_m04_01_valid_contract, test_m04_01_contract_1, test_m04_01_contract_2, test_m04_01_contract_3, test_m04_01_not_fitted_error | `e7162ea219339049` |
| `tests/unit/lab/models/test_m05_meta_label.py` | _make_base_trades, test_m05_01_valid_contract, test_m05_01_contract_1, test_m05_01_contract_2, test_m05_01_contract_3 | `2e60baaee722b716` |
| `tests/unit/lab/models/test_m06_anomaly_gate.py` | _make_liquidity_df, test_m06_01_valid_contract, test_m06_01_contract_1, test_m06_01_contract_2, test_m06_01_contract_3 | `e7ab81e29cd5a6b0` |
| `tests/unit/lab/models/test_ml04_bundle_loader.py` | _make_feature_df, _make_labels, _build_portable_bundle, test_ml_04_valid_contract, test_ml_04_contract_1, test_ml_04_contract_2, test_ml_04_contract_3, test_ml_04_bundle_hash_includes_feature_names, _canonical_payload_hash, test_loader_rejects_any_tampered_inference_metadata, test_bundle_schema_carries_preprocessing_and_provenance, test_loader_rejects_tampered_schema_preprocessing_or_provenance, test_unverified_legacy_bundle_is_not_promoted_to_validated_schema, test_nonfinite_parameters_are_rejected_even_with_matching_full_hash | `0424ac3bf8dac0dc` |
| `tests/unit/lab/models/test_preprocessing.py` | _build_sample_dfs, test_ml_01_valid_contract, test_ml_01_contract_1, test_ml_01_contract_2, test_ml_01_contract_3 | `d9614a1f0cac96b2` |
| `tests/unit/lab/models/test_tuning_budget.py` | test_ml_03_valid_contract, test_ml_03_contract_1, test_ml_03_contract_2, test_ml_03_contract_3, test_ml_03_edge_cases_and_winning_recipe | `ac213d362b8d9af8` |
| `tests/unit/lab/observability/test_observability.py` | test_redacting_json_formatter_formats_and_redacts, test_metrics_collector_counters_and_gauges | `7c614641f38aada0` |
| `tests/unit/lab/orchestration/__init__.py` | module declarations | `b9bbef5b2c16cb94` |
| `tests/unit/lab/orchestration/test_curator_policy.py` | _make_proposal, test_agent_01_valid_contract, test_agent_01_contract_1, test_agent_01_contract_2, test_agent_01_contract_3 | `8183078874a0dfb5` |
| `tests/unit/lab/orchestration/test_queue.py` | _build_test_job, test_job_01_valid_contract, test_job_01_contract_1, test_job_01_contract_2, test_job_01_contract_3, test_expired_running_job_cannot_exceed_attempt_budget, test_attempt_budget_cannot_be_reset_by_state_or_worker_change, test_worker_is_fenced_immediately_at_lease_expiry, test_concurrent_claims_on_separate_connections_have_one_winner, test_failed_claim_transaction_rolls_back_attempt_increment, test_every_queue_connection_enables_foreign_keys | `91ea21923a5a7f8d` |
| `tests/unit/lab/orchestration/test_repeat_policy.py` | _make_recipe, _make_policy, test_job_03_valid_contract, test_job_03_contract_1, test_job_03_contract_2, test_job_03_contract_3, test_job_03_idempotent_same_window | `e8c07394180dc5bc` |
| `tests/unit/lab/orchestration/test_resources.py` | _build_test_job, test_job_02_valid_contract, test_job_02_contract_1, test_job_02_contract_2, test_job_02_contract_3, test_job_02_lenovo_concurrency_limit | `10458ebb97ac084f` |
| `tests/unit/lab/paper/test_forward_decisions.py` | _make_decision, test_shadow_01_valid_contract, test_shadow_01_contract_1, test_shadow_01_contract_2, test_shadow_01_contract_3, test_shadow_01_idempotent_guard | `61d67a218264f88f` |
| `tests/unit/lab/paper/test_live_shadow_engine.py` | _seed_open_position, temp_engine, test_initial_ledger_state, test_state_persistence_and_recovery, test_take_profit_exit_and_fee_accounting, test_stop_loss_exit_and_capital_protection, test_trailing_stop_advancement, test_missing_model_fails_closed, test_bars_held_advances_only_on_new_closed_bar, _market_frame, test_model_metadata_schema_mismatch_fails_closed, test_missing_live_ticker_rejects_entry_before_model, test_stale_closed_bar_rejects_entry_before_model, test_legacy_json_checkpoint_requires_explicit_migration | `82e349b177050da9` |
| `tests/unit/lab/paper/test_promotion.py` | _make_evidence, test_shadow_03_valid_contract, test_shadow_03_contract_1, test_shadow_03_contract_2, test_shadow_03_contract_3 | `f5c480830d5aef99` |
| `tests/unit/lab/paper/test_shadow_store.py` | test_shadow_store_roundtrip_and_wal, test_shadow_store_corruption_fails_closed | `bee5a469a160c601` |
| `tests/unit/lab/paper/test_shared_reconciliation.py` | _make_intent, test_shadow_02_valid_contract, test_shadow_02_contract_1, test_shadow_02_contract_2, test_shadow_02_contract_3 | `a98a3f204d9ceccf` |
| `tests/unit/lab/portfolio/test_portfolio_constructor.py` | test_construct_exposures_incremental_buy, test_construct_exposures_sell_reduction, test_generate_rebalance_intents_filters_dust, test_missing_mark_price_fails_closed | `2eb27c047e5e218a` |
| `tests/unit/lab/reporting/test_summary.py` | _build_test_run, test_report_01_valid_contract, test_report_01_contract_1, test_report_01_contract_2, test_report_01_contract_3, test_report_01_statistical_selection_and_errors | `2641cc70a6b91195` |
| `tests/unit/lab/risk/test_risk_engine.py` | sample_risk_engine, test_risk_engine_normal_approval_creates_oms_order, test_risk_engine_programmatic_kill_switch, test_risk_engine_file_kill_switch, test_risk_engine_unsafe_market_health_blocks_buys, test_risk_engine_rate_limit_throttle | `d904297a56189ebb` |
| `tests/unit/lab/risk/test_risk_engine_governance.py` | risk_policy, test_risk_engine_reset_requires_healthy_reconciliation_and_zero_unknown, test_risk_engine_reset_confirmation_token_verification, test_risk_engine_throttle_history_persistence | `ad91c4052701c7a1` |
| `tests/unit/lab/security/test_redaction.py` | test_redact_api_key_and_secret, test_redact_custom_secret, test_redact_empty_or_clean_text | `c1498bf2c918f93e` |
| `tests/unit/lab/strategies/__init__.py` | module declarations | `a14a246b48092f47` |
| `tests/unit/lab/strategies/test_c01.py` | _build_test_bars, test_c01_01_valid_contract, test_c01_01_contract_1, test_c01_01_contract_2, test_c01_01_contract_3 | `821c1220558ac646` |
| `tests/unit/lab/strategies/test_c02.py` | _build_c02_bars, test_c02_01_valid_contract, test_c02_01_contract_1, test_c02_01_contract_2, test_c02_01_contract_3 | `045c5ebf06d606b7` |
| `tests/unit/lab/strategies/test_c03.py` | _build_c03_bars, test_c03_01_valid_contract, test_c03_01_contract_1, test_c03_01_contract_2, test_c03_01_contract_3 | `0bf9f722d3c5cd6a` |
| `tests/unit/lab/strategies/test_c04.py` | _build_c04_pair_bars, test_c04_01_valid_contract, test_c04_01_contract_1, test_c04_01_contract_2, test_c04_01_contract_3 | `6e1780db2b5243c6` |
| `tests/unit/lab/strategies/test_c07.py` | _build_c07_features, test_c07_01_valid_contract, test_c07_01_contract_1, test_c07_01_contract_2, test_c07_01_contract_3 | `c6431541d3d4aa75` |
| `tests/unit/lab/strategies/test_c10.py` | _build_c10_bars, test_c10_01_valid_contract, test_c10_01_contract_1, test_c10_01_contract_2, test_c10_01_contract_3 | `f0d3844bb9f45fb7` |
| `tests/unit/lab/strategies/test_multitimeframe.py` | test_context_must_be_available_at_signal_time, test_uses_latest_closed_context_without_forward_fill | `f873f50a9e40c868` |
| `tests/unit/lab/strategies/test_registry.py` | _make_sample_features, test_strat_01_valid_contract, test_strat_01_contract_1, test_strat_01_contract_2, test_strat_01_contract_3 | `62de8ccdc2922ebf` |
| `tests/unit/lab/strategies/test_s01.py` | _build_s01_bars, test_s01_01_valid_contract, test_s01_01_contract_1, test_s01_01_contract_2, test_s01_01_contract_3 | `2e2702ba11bfb778` |
| `tests/unit/lab/strategies/test_s02.py` | _build_s02_bars, test_s02_01_valid_contract, test_s02_01_contract_1, test_s02_01_contract_2, test_s02_01_contract_3 | `d7115241187025b4` |
| `tests/unit/lab/test_contracts.py` | test_canonical_pair_rejects_venue_symbol_in_core_validation, test_adapter_constructor_normalizes_venue_symbol_to_canonical_pair, test_candle_record_rejects_timezone_naive_datetime, test_candle_record_keeps_decimal_prices_without_float_conversion, test_trade_event_keeps_venue_symbol_as_separate_source_identity, test_trade_event_keeps_explicit_aggressor_side, test_trade_event_requires_clock_anomaly_flag_for_pre_event_ingestion, test_candle_record_requires_explicit_schema_version, test_trade_event_requires_explicit_schema_version, test_candle_record_rejects_non_contract_intervals | `b5d50b2fb709517f` |
| `tests/unit/lab/test_paths.py` | test_from_env_uses_explicit_project_root_defaults, test_from_env_uses_environment_output_overrides | `e75e7a18cd5c1b1b` |
| `tests/unit/lab/universe/test_artifact_lineage.py` | _Transport, test_cap_loader_rejects_forged_observation_over_genuine_provider_body, test_listing_loader_rejects_pair_component_and_provider_mapping_mismatch, test_listing_and_profile_refs_are_loaded_from_exact_schema_valid_bytes, test_pipeline_lineage_rejects_one_verified_artifact_type_in_another_field, test_reference_constructor_rejects_arbitrary_sha_strings | `34674958af9c0a63` |
| `tests/unit/lab/universe/test_eligibility.py` | _sha, _policy, _metrics, test_point_in_time_rank_boundary_selects_big_or_small_liquidity_policy, test_each_fail_closed_gate_emits_a_stable_reason_code, test_missing_historical_cap_falls_back_without_becoming_small_cap, test_future_or_late_current_cap_never_backfills_a_past_snapshot, test_stale_cap_is_audited_and_only_liquidity_can_classify_the_pair, test_cap_expiry_boundary_is_inclusive_and_derived_from_availability, test_causally_impossible_cap_source_timestamp_is_not_classified, test_newly_listed_pair_stays_in_decisions_but_is_ineligible, test_default_yaml_enforces_documented_boundary_behavior, test_unknown_fields_and_invalid_thresholds_fail_closed | `e44d054ea87deb42` |
| `tests/unit/lab/universe/test_materializer_causality.py` | _inputs, _materialize, test_materializer_rejects_wrong_pair_inputs, test_materializer_rejects_future_or_impossible_availability, test_materializer_enforces_stable_causal_failure_codes, _lineage, _ref | `b80302d1ef511b13` |
| `tests/unit/lab/verification/test_release_bundle.py` | test_release_bundle_creation_and_verification_success, test_release_bundle_verification_fails_on_tampered_config, test_release_bundle_verification_fails_on_git_sha_mismatch, test_release_bundle_with_all_provenance_hashes | `7fec9b4399655fea` |
| `tests/unit/test_barrier_resolution.py` | test_same_bar_stop_and_target_is_stop_first, test_single_barrier_touch_resolves_at_the_barrier, test_no_barrier_touch_has_no_resolution | `2659fbd3f586d695` |
| `tests/unit/test_indodax_trade_v2.py` | _load_payload, test_parse_my_trades_v2_preserves_official_trade_contract, test_parse_my_trades_v2_skips_string_boolean_flags, test_parse_my_trades_v2_returns_empty_for_non_mapping_payloads, test_is_pair_already_held_uses_newest_buy_by_millisecond_timestamp, test_is_pair_already_held_uses_newest_sell_by_millisecond_timestamp | `56184f422990d25a` |
| `tests/unit/test_paper_accounting.py` | test_round_trip_uses_gross_cash_debit_as_cost_basis, test_accounting_rejects_invalid_or_non_finite_inputs | `a75145f33786c6dc` |
| `tests/unit/test_repository_smoke.py` | test_baseline_modules_import | `db7478e6e8841264` |
| `tests/unit/test_risk_config.py` | test_default_bull_rr_can_pass_gate | `025c5792235b073b` |
| `tests/unit/test_risk_manager.py` | _bullish_decision, test_bullish_plan_meets_rr_gate_without_exceeding_risk_limit | `7976bb071b0831b9` |
