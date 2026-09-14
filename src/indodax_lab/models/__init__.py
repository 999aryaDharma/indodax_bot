"""Machine learning models, preprocessing, calibration, tuning, baseline and challenger models subsystem."""

from indodax_lab.models.calibration import (
    CalibrationSegmentError,
    FittedCalibratorArtifact,
    HeldOutCalibrator,
    InsufficientCalibrationDataError,
)
from indodax_lab.models.execution_mapper import (
    CostAwareExecutionMapper,
    CostBasis,
    DecisionAction,
    ExecutionDecision,
    ForecastKind,
    ForecastPayload,
    PayoffStructure,
)
from indodax_lab.models.m01_logistic import (
    ClassImbalanceError,
    InvalidSolverPenaltyError,
    M01Config,
    M01FittedBundle,
    M01LogisticTrainer,
    ModelUtilityComparison,
)
from indodax_lab.models.m02_xgboost import (
    M02Config,
    M02FittedBundle,
    M02MultiSeedAudit,
    M02SeedResult,
    M02XGBoostTrainer,
    SealedPartitionLeakageError,
)
from indodax_lab.models.preprocessing import (
    FeatureAlignmentError,
    FittedPreprocessorArtifact,
    NotFittedError,
    PreprocessorConfig,
    TabularPreprocessor,
)
from indodax_lab.models.tuning import (
    BoundedTrialSearch,
    ResumeConfigMismatchError,
    RevisionBudgetExhaustedError,
    SealedTestObjectiveForbiddenError,
    SearchSpace,
    TrialBudget,
    TrialBudgetExhaustedError,
    TrialOutcome,
    TrialStatus,
)
from indodax_lab.models.artifacts import (
    BundleChecksumMismatchError,
    BundleFeatureMismatchError,
    MissingCalibrationMetadataError,
    PortableBundle,
    PortableBundleLoader,
)
from indodax_lab.models.m03_rf_regime import (
    M03Config,
    M03FittedBundle,
    M03RFRegimeTrainer,
    RegimeAbstainError,
    RegimeLabel,
    RegimeUtilityReport,
)
from indodax_lab.models.m04_quantile_risk import (
    M04Config,
    M04FittedBundle,
    M04QuantileTrainer,
    QuantileCoverageReport,
    QuantileCrossingError,
    TailTargetLeakageError,
)
from indodax_lab.models.m05_meta_label import (
    M05Config,
    M05FittedBundle,
    M05MetaLabelTrainer,
    ManualLabelForbiddenError,
    MetaFilterComparisonReport,
    MetaTradeSample,
    purge_overlapping_trades,
)
from indodax_lab.models.m06_anomaly_gate import (
    AnomalyDecision,
    DirectionalClaimForbiddenError,
    M06AnomalyGate,
    M06Config,
    M06FittedBundle,
    MissingDataDistinctFromAnomalyError,
)

__all__ = [
    # ML-01 Preprocessing
    "FeatureAlignmentError",
    "FittedPreprocessorArtifact",
    "NotFittedError",
    "PreprocessorConfig",
    "TabularPreprocessor",
    # ML-02 Calibration & Execution Mapping
    "CalibrationSegmentError",
    "CostAwareExecutionMapper",
    "CostBasis",
    "DecisionAction",
    "ExecutionDecision",
    "FittedCalibratorArtifact",
    "ForecastKind",
    "ForecastPayload",
    "HeldOutCalibrator",
    "InsufficientCalibrationDataError",
    "PayoffStructure",
    # ML-03 Bounded Trial Search
    "BoundedTrialSearch",
    "ResumeConfigMismatchError",
    "RevisionBudgetExhaustedError",
    "SealedTestObjectiveForbiddenError",
    "SearchSpace",
    "TrialBudget",
    "TrialBudgetExhaustedError",
    "TrialOutcome",
    "TrialStatus",
    # M01-01 Calibrated Logistic Baseline
    "ClassImbalanceError",
    "InvalidSolverPenaltyError",
    "M01Config",
    "M01FittedBundle",
    "M01LogisticTrainer",
    "ModelUtilityComparison",
    # M02-01 XGBoost Challenger
    "M02Config",
    "M02FittedBundle",
    "M02MultiSeedAudit",
    "M02SeedResult",
    "M02XGBoostTrainer",
    "SealedPartitionLeakageError",
    # ML-04 Portable Model Bundles and Replay
    "BundleChecksumMismatchError",
    "BundleFeatureMismatchError",
    "MissingCalibrationMetadataError",
    "PortableBundle",
    "PortableBundleLoader",
    # M03-01 Random Forest Regime Gate
    "M03Config",
    "M03FittedBundle",
    "M03RFRegimeTrainer",
    "RegimeAbstainError",
    "RegimeLabel",
    "RegimeUtilityReport",
    # M04-01 Quantile Risk Regression
    "M04Config",
    "M04FittedBundle",
    "M04QuantileTrainer",
    "QuantileCoverageReport",
    "QuantileCrossingError",
    "TailTargetLeakageError",
    # M05-01 Meta-Label Signal Filter
    "M05Config",
    "M05FittedBundle",
    "M05MetaLabelTrainer",
    "ManualLabelForbiddenError",
    "MetaFilterComparisonReport",
    "MetaTradeSample",
    "purge_overlapping_trades",
    # M06-01 Market Anomaly Risk Gate
    "AnomalyDecision",
    "DirectionalClaimForbiddenError",
    "M06AnomalyGate",
    "M06Config",
    "M06FittedBundle",
    "MissingDataDistinctFromAnomalyError",
]
