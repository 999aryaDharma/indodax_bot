# Sprint index
Derived from manifest. Historical DONE does not imply fresh test execution.
| ID | Feature | Domain | Priority | Type | Dependencies | State | Path |
|---|---|---|---|---|---|---|---|
| AGENT-01 | Governed research curator | agent-governance | P0 | security | REPORT-01, JOB-03 | REVIEW | [Spec](agent-governance\AGENT-01-governed-research-curator.md) |
| BAR-01 | Causal time and event bars | bars | P0 | data | DATA-04, DATA-05 | DONE | [Spec](bars\BAR-01-causal-time-and-event-bars.md) |
| BASE-01 | Offline verification harness | baseline | P0 | quality | — | DONE | [Spec](baseline\BASE-01-offline-verification-harness.md) |
| BASE-02 | Reachable bullish risk reward | baseline | P0 | safety | BASE-01 | DONE | [Spec](baseline\BASE-02-reachable-bullish-risk-reward.md) |
| BASE-03 | Trade v2 ownership parsing | baseline | P0 | integration | BASE-01 | DONE | [Spec](baseline\BASE-03-trade-v2-ownership-parsing.md) |
| BASE-04 | Exact paper accounting migration | baseline | P0 | migration | BASE-01 | DONE | [Spec](baseline\BASE-04-exact-paper-accounting-migration.md) |
| BASE-05 | Unbiased signal observations | baseline | P0 | data | BASE-02, BASE-03, BASE-04 | DONE | [Spec](baseline\BASE-05-unbiased-signal-observations.md) |
| BASE-06 | Baseline trust checkpoint | baseline | P0 | quality | BASE-05 | DONE | [Spec](baseline\BASE-06-baseline-trust-checkpoint.md) |
| D01-01 | Tabular MLP baseline | deep-learning | P1 | research | DL-01 | REVIEW | [Spec](deep-learning\D01-01-tabular-mlp-baseline.md) |
| D02-01 | Causal TCN baseline | deep-learning | P2 | research | D01-01, DL-02 | REVIEW | [Spec](deep-learning\D02-01-causal-tcn-baseline.md) |
| D03-01 | ResNet LSTM challenger | deep-learning | P2 | research | D02-01, LABEL-02 | REVIEW | [Spec](deep-learning\D03-01-resnet-lstm-challenger.md) |
| D04-01 | Compact iTransformer challenger | deep-learning | P2 | research | D02-01 | REVIEW | [Spec](deep-learning\D04-01-compact-itransformer-challenger.md) |
| DL-01 | Isolated resumable neural training | deep-learning | P1 | feature | QA-01, JOB-02 | REVIEW | [Spec](deep-learning\DL-01-isolated-resumable-neural-training.md) |
| DL-02 | Causal sequence datasets | deep-learning | P1 | data | DL-01 | REVIEW | [Spec](deep-learning\DL-02-causal-sequence-datasets.md) |
| F01-01 | Foundation provenance gate | deep-learning | P2 | research | DL-01 | REVIEW | [Spec](deep-learning\F01-01-foundation-provenance-gate.md) |
| F01-02 | Staged foundation adaptation | deep-learning | P2 | research | F01-01, D01-01 | REVIEW | [Spec](deep-learning\F01-02-staged-foundation-adaptation.md) |
| G01-01 | Point-in-time graph challenger | deep-learning | P2 | research | D01-01, C04-01 | REVIEW | [Spec](deep-learning\G01-01-point-in-time-graph-challenger.md) |
| EVAL-01 | Immutable experiment registry | evaluation | P0 | data | SIM-04 | REVIEW | [Spec](evaluation\EVAL-01-immutable-experiment-registry.md) |
| EVAL-02 | Hard gates and selection diagnostics | evaluation | P0 | research | EVAL-01 | REVIEW | [Spec](evaluation\EVAL-02-hard-gates-and-selection-diagnostics.md) |
| EVAL-03 | Sealed candidate lifecycle | evaluation | P0 | safety | EVAL-02, SPLIT-01 | REVIEW | [Spec](evaluation\EVAL-03-sealed-candidate-lifecycle.md) |
| FEAT-01 | Versioned feature registry | features | P0 | data | DATA-06 | DONE | [Spec](features\FEAT-01-versioned-feature-registry.md) |
| FEAT-02 | Golden technical and liquidity transforms | features | P0 | data | FEAT-01 | DONE | [Spec](features\FEAT-02-golden-technical-and-liquidity-transforms.md) |
| FEAT-03 | As-of market context | features | P0 | data | FEAT-01 | DONE | [Spec](features\FEAT-03-as-of-market-context.md) |
| FEAT-04 | Immutable feature materialization | features | P0 | data | FEAT-02, FEAT-03 | DONE | [Spec](features\FEAT-04-immutable-feature-materialization.md) |
| LABEL-01 | Execution-aligned net return labels | labels | P0 | data | FEAT-04, SIM-01 | REVIEW | [Spec](labels\LABEL-01-execution-aligned-net-return-labels.md) |
| LABEL-02 | Triple barrier outcomes | labels | P0 | data | LABEL-01 | REVIEW | [Spec](labels\LABEL-02-triple-barrier-outcomes.md) |
| SPLIT-01 | Sealed purged chronological folds | labels | P0 | safety | LABEL-02 | REVIEW | [Spec](labels\SPLIT-01-sealed-purged-chronological-folds.md) |
| TRAIN-01 | Verified training dataset assembly | labels | P0 | data | SPLIT-01, FEAT-04 | REVIEW | [Spec](labels\TRAIN-01-verified-training-dataset-assembly.md) |
| DATA-01 | Canonical market contracts | market-data | P0 | data | BASE-01 | DONE | [Spec](market-data\DATA-01-canonical-market-contracts.md) |
| DATA-02 | Durable immutable publication | market-data | P0 | data | DATA-01 | DONE | [Spec](market-data\DATA-02-durable-immutable-publication.md) |
| DATA-03 | Auditable candle backfill | market-data | P0 | integration | DATA-02 | DONE | [Spec](market-data\DATA-03-auditable-candle-backfill.md) |
| DATA-04 | Snapshot quality decisions | market-data | P0 | data | DATA-03 | DONE | [Spec](market-data\DATA-04-snapshot-quality-decisions.md) |
| DATA-05 | Reliable forward market collection | market-data | P0 | integration | DATA-02 | DONE | [Spec](market-data\DATA-05-reliable-forward-market-collection.md) |
| DATA-06 | Provider-derived reproducible snapshot | market-data | P0 | quality | BASE-06, UNIV-01, BAR-01 | DONE | [Spec](market-data\DATA-06-provider-derived-reproducible-snapshot.md) |
| L01-01 | DeepLOB baseline | microstructure | P2 | research | LOB-01, D01-01 | REVIEW | [Spec](microstructure\L01-01-deeplob-baseline.md) |
| L02-01 | TLOB style challenger | microstructure | P2 | research | L01-01 | REVIEW | [Spec](microstructure\L02-01-tlob-style-challenger.md) |
| LOB-01 | Forward book dataset eligibility | microstructure | P2 | data | DATA-06, FEAT-04 | DONE | [Spec](microstructure\LOB-01-forward-book-dataset-eligibility.md) |
| M01-01 | Calibrated logistic baseline | models | P0 | research | ML-03 | REVIEW | [Spec](models\M01-01-calibrated-logistic-baseline.md) |
| M02-01 | XGBoost challenger | models | P0 | research | ML-03, M01-01 | REVIEW | [Spec](models\M02-01-xgboost-challenger.md) |
| M03-01 | Random forest regime gate | models | P1 | research | ML-04 | REVIEW | [Spec](models\M03-01-random-forest-regime-gate.md) |
| M04-01 | Quantile risk regression | models | P1 | research | ML-04 | REVIEW | [Spec](models\M04-01-quantile-risk-regression.md) |
| M05-01 | Meta-label signal filter | models | P1 | research | ML-04, C01-01 | REVIEW | [Spec](models\M05-01-meta-label-signal-filter.md) |
| M06-01 | Market anomaly risk gate | models | P1 | research | ML-04 | REVIEW | [Spec](models\M06-01-market-anomaly-risk-gate.md) |
| ML-01 | Train-only preprocessing | models | P0 | data | TRAIN-01 | REVIEW | [Spec](models\ML-01-train-only-preprocessing.md) |
| ML-02 | Held-out calibration and cost mapper | models | P0 | safety | ML-01, SIM-01 | REVIEW | [Spec](models\ML-02-held-out-calibration-and-cost-mapper.md) |
| ML-03 | Bounded trial search | models | P0 | research | ML-02, EVAL-01 | REVIEW | [Spec](models\ML-03-bounded-trial-search.md) |
| ML-04 | Portable model bundles and replay | models | P0 | integration | M01-01, M02-01, EVAL-03 | REVIEW | [Spec](models\ML-04-portable-model-bundles-and-replay.md) |
| R01-01 | Constrained allocation feasibility | models | P2 | spike | QA-01, SHADOW-02 | REVIEW | [Spec](models\R01-01-constrained-allocation-feasibility.md) |
| OPS-01 | Host profiles and service lifecycle | operations | P0 | release | JOB-02, SHADOW-02 | REVIEW | [Spec](operations\OPS-01-host-profiles-and-service-lifecycle.md) |
| OPS-02 | Snapshot transfer and restore | operations | P0 | safety | DATA-06, JOB-01 | REVIEW | [Spec](operations\OPS-02-snapshot-transfer-and-restore.md) |
| OPS-03 | Storage retention and integrity maintenance | operations | P0 | safety | OPS-02, EVAL-01 | REVIEW | [Spec](operations\OPS-03-storage-retention-and-integrity-maintenance.md) |
| JOB-01 | Durable leased jobs | orchestration | P0 | feature | EVAL-01 | REVIEW | [Spec](orchestration\JOB-01-durable-leased-jobs.md) |
| JOB-02 | Resource-aware idle admission | orchestration | P0 | safety | JOB-01 | REVIEW | [Spec](orchestration\JOB-02-resource-aware-idle-admission.md) |
| JOB-03 | Evaluator-controlled research DAG | orchestration | P0 | feature | JOB-02, EVAL-03, ML-04 | REVIEW | [Spec](orchestration\JOB-03-evaluator-controlled-research-dag.md) |
| REPORT-01 | Compact experiment reports | reporting | P0 | feature | EVAL-03, SIM-04 | REVIEW | [Spec](reporting\REPORT-01-compact-experiment-reports.md) |
| REPORT-02 | Read-only Telegram research status | reporting | P0 | integration | REPORT-01, SHADOW-02 | REVIEW | [Spec](reporting\REPORT-02-read-only-telegram-research-status.md) |
| SHADOW-01 | Auditable forward paper decisions | shadow | P0 | feature | EVAL-03, ML-04, DATA-05 | REVIEW | [Spec](shadow\SHADOW-01-auditable-forward-paper-decisions.md) |
| SHADOW-02 | Shared capital reconciliation | shadow | P0 | safety | SHADOW-01, SIM-02 | REVIEW | [Spec](shadow\SHADOW-02-shared-capital-reconciliation.md) |
| SHADOW-03 | Champion replacement gate | shadow | P0 | safety | SHADOW-02, EVAL-03 | REVIEW | [Spec](shadow\SHADOW-03-champion-replacement-gate.md) |
| COST-01 | Time-valid exchange cost schedules | simulation | P0 | data | DATA-01 | DONE | [Spec](simulation\COST-01-time-valid-exchange-cost-schedules.md) |
| LED-01 | Balanced research postings | simulation | P0 | safety | COST-01, BASE-04 | DONE | [Spec](simulation\LED-01-balanced-research-postings.md) |
| SIM-01 | Conservative execution simulator | simulation | P0 | feature | COST-01, BAR-01 | DONE | [Spec](simulation\SIM-01-conservative-execution-simulator.md) |
| SIM-02 | Portfolio risk and circuit breakers | simulation | P0 | safety | LED-01, SIM-01 | DONE | [Spec](simulation\SIM-02-portfolio-risk-and-circuit-breakers.md) |
| SIM-03 | Deterministic replay judge | simulation | P0 | integration | SIM-02, DATA-06 | REVIEW | [Spec](simulation\SIM-03-deterministic-replay-judge.md) |
| SIM-04 | Net-cost risk and capacity metrics | simulation | P0 | feature | SIM-03 | REVIEW | [Spec](simulation\SIM-04-net-cost-risk-and-capacity-metrics.md) |
| C01-01 | Donchian breakout | strategies | P0 | feature | STRAT-01 | REVIEW | [Spec](strategies\C01-01-donchian-breakout.md) |
| C02-01 | EMA pullback | strategies | P0 | feature | STRAT-01 | REVIEW | [Spec](strategies\C02-01-ema-pullback.md) |
| C03-01 | Time series momentum | strategies | P0 | feature | STRAT-01 | REVIEW | [Spec](strategies\C03-01-time-series-momentum.md) |
| C04-01 | Cross sectional momentum | strategies | P0 | feature | STRAT-01 | REVIEW | [Spec](strategies\C04-01-cross-sectional-momentum.md) |
| C05-01 | Volatility breakout | strategies | P1 | feature | STRAT-01 | PLANNED | [Spec](strategies\C05-01-volatility-breakout.md) |
| C06-01 | Directional trend strength | strategies | P1 | feature | STRAT-01 | PLANNED | [Spec](strategies\C06-01-directional-trend-strength.md) |
| C07-01 | Bollinger RSI reversion | strategies | P0 | feature | STRAT-01 | REVIEW | [Spec](strategies\C07-01-bollinger-rsi-reversion.md) |
| C08-01 | Multi timeframe confirmation | strategies | P1 | feature | STRAT-01 | PLANNED | [Spec](strategies\C08-01-multi-timeframe-confirmation.md) |
| C09-01 | VWAP deviation reversion | strategies | P1 | feature | STRAT-01 | PLANNED | [Spec](strategies\C09-01-vwap-deviation-reversion.md) |
| C10-01 | Regime ensemble | strategies | P0 | feature | C01-01, C07-01 | REVIEW | [Spec](strategies\C10-01-regime-ensemble.md) |
| C11-01 | Volatility allocation | strategies | P1 | feature | STRAT-01 | PLANNED | [Spec](strategies\C11-01-volatility-allocation.md) |
| C12-01 | Relative strength rotation | strategies | P1 | feature | C04-01 | PLANNED | [Spec](strategies\C12-01-relative-strength-rotation.md) |
| S01-01 | Liquidity screened breakout | strategies | P0 | feature | STRAT-01 | REVIEW | [Spec](strategies\S01-01-liquidity-screened-breakout.md) |
| S02-01 | Squeeze expansion | strategies | P0 | feature | STRAT-01 | REVIEW | [Spec](strategies\S02-01-squeeze-expansion.md) |
| S03-01 | Abnormal volume continuation | strategies | P1 | feature | STRAT-01 | PLANNED | [Spec](strategies\S03-01-abnormal-volume-continuation.md) |
| S04-01 | Order flow imbalance | strategies | P2 | feature | STRAT-01, LOB-01 | PLANNED | [Spec](strategies\S04-01-order-flow-imbalance.md) |
| S05-01 | Micro pullback | strategies | P1 | feature | STRAT-01 | PLANNED | [Spec](strategies\S05-01-micro-pullback.md) |
| S06-01 | Post listing maturation | strategies | P1 | feature | STRAT-01 | PLANNED | [Spec](strategies\S06-01-post-listing-maturation.md) |
| S07-01 | Small cap rotation | strategies | P1 | feature | C04-01, S01-01 | PLANNED | [Spec](strategies\S07-01-small-cap-rotation.md) |
| S08-01 | Passive mean reversion | strategies | P2 | feature | STRAT-01, LOB-01 | PLANNED | [Spec](strategies\S08-01-passive-mean-reversion.md) |
| S09-01 | Tail risk abstention | strategies | P1 | feature | STRAT-01 | PLANNED | [Spec](strategies\S09-01-tail-risk-abstention.md) |
| STRAT-01 | Declarative strategy protocol | strategies | P0 | feature | SIM-03, FEAT-04 | REVIEW | [Spec](strategies\STRAT-01-declarative-strategy-protocol.md) |
| UNIV-01 | Point-in-time investable universe | universe | P0 | data | DATA-04, DATA-05 | DONE | [Spec](universe\UNIV-01-point-in-time-investable-universe.md) |
| QA-01 | Wave 1 tournament checkpoint | verification | P0 | quality | JOB-03, SHADOW-02, C01-01, C02-01, C03-01, C04-01, C07-01, C10-01, S01-01, S02-01, ML-04 | REVIEW | [Spec](verification\QA-01-wave-1-tournament-checkpoint.md) |
| QA-02 | Boundary security verification | verification | P0 | security | REPORT-02, AGENT-01, OPS-02 | REVIEW | [Spec](verification\QA-02-boundary-security-verification.md) |
| QA-03 | Capacity and crash recovery qualification | verification | P0 | performance | OPS-01, OPS-03, QA-01 | REVIEW | [Spec](verification\QA-03-capacity-and-crash-recovery-qualification.md) |
| REL-01 | Paper research release candidate | verification | P0 | release | QA-02, QA-03, QA-01, REPORT-02 | REVIEW | [Spec](verification\REL-01-paper-research-release-candidate.md) |
| DOC-01 | Frozen architecture audit and delivery program | planning | P0 | planning | — | DONE | [Spec](planning\DOC-01-frozen-architecture-audit-and-delivery-program.md) |
| RP-01 | Shared SignalIntent ownership with compatibility | runtime-parity | P0 | integration | DOC-01, BASE-01 | DONE | [Spec](runtime-parity\RP-01-shared-signalintent-ownership-with-compatibility.md) |
| RW0-01 | Immutable Workbench domain manifests | research-workbench | P0 | integration | RP-01, DATA-01 | DONE | [Spec](research-workbench\RW0-01-immutable-workbench-domain-manifests.md) |
| RW1-01 | Reusable immutable dataset registry | research-workbench | P1 | integration | RW0-01, DATA-06 | DONE | [Spec](research-workbench\RW1-01-reusable-immutable-dataset-registry.md) |
| RW2-01 | Durable versioned strategy registry | research-workbench | P1 | integration | RW0-01, STRAT-01 | PLANNED | [Spec](research-workbench\RW2-01-durable-versioned-strategy-registry.md) |
| RW2-02 | Model registry and offline training services | research-workbench | P1 | integration | RW0-01, ML-04, JOB-01 | PLANNED | [Spec](research-workbench\RW2-02-model-registry-and-offline-training-services.md) |
| RW2-03 | Typed declarative pipeline composer | research-workbench | P1 | integration | RW2-01, RW2-02 | PLANNED | [Spec](research-workbench\RW2-03-typed-declarative-pipeline-composer.md) |
| RP-02 | Shared candidate feature and exit evaluation | runtime-parity | P0 | integration | RW2-03, FEAT-02 | PLANNED | [Spec](runtime-parity\RP-02-shared-candidate-feature-and-exit-evaluation.md) |
| RP-03 | Shared portfolio sizing and risk semantics | runtime-parity | P0 | integration | RW0-01, SIM-02 | DONE | [Spec](runtime-parity\RP-03-shared-portfolio-sizing-and-risk-semantics.md) |
| PM-01 | Authoritative fail-closed pre-write gate | production-main | P0 | integration | RW0-01 | DONE | [Spec](production-main\PM-01-authoritative-fail-closed-pre-write-gate.md) |
| PM-02 | Atomic financial execution state and recovery | production-main | P0 | integration | RW0-01, LED-01 | DONE | [Spec](production-main\PM-02-atomic-financial-execution-state-and-recovery.md) |
| PM-03 | Recovery mode and durable operator risk governance | production-main | P0 | integration | PM-01, PM-02 | DONE | [Spec](production-main\PM-03-recovery-mode-and-durable-operator-risk-governance.md) |
| PM-04 | Venue parser cancellation and supported order semantics | production-main | P0 | integration | PM-01, PM-02 | DONE | [Spec](production-main\PM-04-venue-parser-cancellation-and-supported-order-semantics.md) |
| RP-04 | Canonical feed and environment runtime adapters | runtime-parity | P0 | integration | RP-02, RP-03, PM-02 | PLANNED | [Spec](runtime-parity\RP-04-canonical-feed-and-environment-runtime-adapters.md) |
| RP-05 | Runtime parity qualification fixtures | runtime-parity | P0 | integration | RP-04, PM-04 | PLANNED | [Spec](runtime-parity\RP-05-runtime-parity-qualification-fixtures.md) |
| RW3-01 | Experiment lifecycle and backtest orchestration | research-workbench | P1 | integration | RW1-01, RW2-03, RP-04, EVAL-01, JOB-01, DATA-07 | PLANNED | [Spec](research-workbench\RW3-01-experiment-lifecycle-and-backtest-orchestration.md) |
| RW4-01 | Immutable candidate packaging and lifecycle | research-workbench | P1 | integration | RW3-01, ML-04 | PLANNED | [Spec](research-workbench\RW4-01-immutable-candidate-packaging-and-lifecycle.md) |
| RW5-01 | Isolated durable forward-shadow agents | research-workbench | P1 | integration | RW4-01, RP-05 | PLANNED | [Spec](research-workbench\RW5-01-isolated-durable-forward-shadow-agents.md) |
| RW5-02 | Tournament cohorts leaderboard and qualification | research-workbench | P1 | integration | RW5-01, SHADOW-03 | PLANNED | [Spec](research-workbench\RW5-02-tournament-cohorts-leaderboard-and-qualification.md) |
| RW6-01 | Separate shared-capital Portfolio Shadow | research-workbench | P1 | integration | RW5-01, RP-03, PM-08 | PLANNED | [Spec](research-workbench\RW6-01-separate-shared-capital-portfolio-shadow.md) |
| RW7-01 | Read-only QuantOps MCP boundary | research-workbench | P1 | integration | RW1-01, RW2-03, RW4-01, DATA-07 | PLANNED | [Spec](research-workbench\RW7-01-read-only-quantops-mcp-boundary.md) |
| RW7-02 | Audited QuantOps research mutations | research-workbench | P1 | integration | RW7-01, RW5-02, RW6-01, RW9-01 | PLANNED | [Spec](research-workbench\RW7-02-audited-quantops-research-mutations.md) |
| RW8-01 | Research read models and dashboard navigation | research-workbench | P1 | integration | RW5-02, RW6-01 | PLANNED | [Spec](research-workbench\RW8-01-research-read-models-and-dashboard-navigation.md) |
| RW8-02 | Workbench form and graph editors | research-workbench | P1 | integration | RW8-01, RW2-03, RW3-01 | PLANNED | [Spec](research-workbench\RW8-02-workbench-form-and-graph-editors.md) |
| PM-05 | Candidate-bound release provenance | production-main | P0 | integration | RW4-01, PM-03 | PLANNED | [Spec](production-main\PM-05-candidate-bound-release-provenance.md) |
| PM-06 | CI security and operational release evidence | production-main | P0 | integration | PM-05, RW5-01, PM-09, API-04, UI-03, RP-05, RW6-01, OPS-01, QA-03 | PLANNED | [Spec](production-main\PM-06-ci-security-and-operational-release-evidence.md) |
| RW9-01 | Promotion request and production export bridge | research-workbench | P1 | integration | RW4-01, RW5-02, PM-05 | PLANNED | [Spec](research-workbench\RW9-01-promotion-request-and-production-export-bridge.md) |
| API-00 | Shared API envelope, error, provenance and capability contracts | production-main | P0 | integration | — | DONE | [Spec](production-main\API-00-shared-api-envelope-error-provenance-and-capability-contracts.md) |
| API-01 | Production service-derived read models | production-main | P0 | integration | API-00, PM-01, PM-02, PM-03, PM-04 | DONE | [Spec](production-main\API-01-production-service-derived-read-models.md) |
| API-03 | Fail-closed read capability policy and audit context | production-main | P0 | integration | API-00 | DONE | [Spec](production-main\API-03-fail-closed-read-capability-policy-and-audit-context.md) |
| API-02 | Read-only Production API application and routes | production-main | P0 | integration | API-01, API-03 | DONE | [Spec](production-main\API-02-read-only-production-api-application-and-routes.md) |
| UI-00 | Kumo and Geist shell foundation with typed API client | production-main | P1 | integration | — | DONE | [Spec](production-main\UI-00-kumo-and-geist-shell-foundation-with-typed-api-client.md) |
| UI-01 | Production and Research context navigation with capability boundary | production-main | P1 | integration | UI-00, API-03 | DONE | [Spec](production-main\UI-01-production-and-research-context-navigation-with-capability-boundary.md) |
| UI-02 | Read-only Production operational pages | production-main | P1 | integration | UI-01, API-02 | DONE | [Spec](production-main\UI-02-read-only-production-operational-pages.md) |
| DATA-07 | Selectable public collection and coverage workflow | market-data | P1 | integration | DATA-03, DATA-05, RW1-01, JOB-01, JOB-02 | PLANNED | [Spec](market-data\DATA-07-selectable-public-collection-and-coverage-workflow.md) |
| PM-07 | Reviewed account portfolio adoption | production-main | P1 | integration | PM-02, PM-03, PM-04, PM-05 | PLANNED | [Spec](production-main\PM-07-reviewed-account-portfolio-adoption.md) |
| PM-08 | Shared capital allocation and stop risk sizing | production-main | P1 | integration | PM-07, PM-05, RP-03 | PLANNED | [Spec](production-main\PM-08-shared-capital-allocation-and-stop-risk-sizing.md) |
| PM-09 | Candidate exits and draining strategy replacement | production-main | P1 | integration | PM-08, RP-02, RP-04, PM-04 | PLANNED | [Spec](production-main\PM-09-candidate-exits-and-draining-strategy-replacement.md) |
| API-04 | Guarded Production portfolio and lifecycle commands | production-main | P1 | integration | PM-09, API-02, API-03, API-07 | PLANNED | [Spec](production-main\API-04-guarded-production-portfolio-and-lifecycle-commands.md) |
| UI-03 | Guarded portfolio and strategy operator workflows | production-main | P1 | integration | API-04, UI-02, API-07, UI-09 | PLANNED | [Spec](production-main\UI-03-guarded-portfolio-and-strategy-operator-workflows.md) |
| API-07 | Tailscale-authenticated Production read composition | production-main | P0 | security | API-02, API-03 | DONE | [Spec](production-main\API-07-tailscale-authenticated-production-read-composition.md) |
| UI-09 | Same-origin Production API access | production-main | P0 | integration | UI-02, API-02 | DONE | [Spec](production-main\UI-09-same-origin-production-api.md) |
