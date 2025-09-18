"""
Pydantic schemas for risk engine components
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Literal, Any
from datetime import datetime
from enum import Enum

class EffectMeasure(str, Enum):
    OR = "OR"
    RR = "RR"
    HR = "HR"

class StudyDesign(str, Enum):
    RCT = "RCT"
    PROSPECTIVE = "prospective"
    RETROSPECTIVE = "retrospective"

class RiskOfBias(str, Enum):
    LOW = "low"
    SOME = "some"
    HIGH = "high"

class TimeWindow(str, Enum):
    INTRAOP = "intraop"
    PERIOP = "periop"
    THIRTYDAYS = "30d"

class AgeBand(str, Enum):
    LESS_THAN_1Y = "<1y"
    ONE_TO_3 = "1-3"
    FOUR_TO_6 = "4-6"
    SEVEN_TO_12 = "7-12"
    THIRTEEN_TO_17 = "13-17"
    EIGHTEEN_TO_39 = "18-39"
    FORTY_TO_64 = "40-64"
    SIXTY_FIVE_TO_79 = "65-79"
    EIGHTY_PLUS = "≥80"

class SurgeryType(str, Enum):
    ENT = "ENT"
    GENERAL = "General"
    ORTHO = "Ortho"
    CARDIAC = "Cardiac"
    NEURO = "Neuro"
    OB = "OB"
    URO = "Uro"
    PLASTICS = "Plastics"
    OPHTHO = "Ophtho"
    DENTAL = "Dental"
    THORACIC = "Thoracic"
    VASCULAR = "Vascular"
    TRANSPLANT = "Transplant"

class Urgency(str, Enum):
    ELECTIVE = "elective"
    URGENT = "urgent"
    EMERGENCY = "emergency"

class ConfidenceLevel(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"

class Study(BaseModel):
    """Individual study in meta-analysis"""
    pmid: str
    title: str
    first_author: str
    pub_year: int
    data_years: Optional[List[int]] = None

    # Study characteristics
    design: StudyDesign
    risk_of_bias: RiskOfBias
    journal_quartile: Optional[int] = None

    # Population
    age_pop: Literal["pediatric", "adult", "mixed"]
    surgery_domain: SurgeryType
    urgency: Urgency

    # Effect data
    outcome: str
    window: TimeWindow
    factor: str
    measure: EffectMeasure
    value: float  # OR/RR/HR value
    ci_lower: Optional[float] = None
    ci_upper: Optional[float] = None
    se: Optional[float] = None

    # Sample sizes
    n_total: int
    n_exposed: Optional[int] = None
    n_control: Optional[int] = None
    events_exposed: Optional[int] = None
    events_control: Optional[int] = None

    # Quality indicators
    is_adjusted: bool = False
    adjustment_factors: Optional[List[str]] = None

    # Deduplication
    cohort_hash: Optional[str] = None  # For overlap detection

class PooledEffect(BaseModel):
    """Pooled meta-analysis result for a factor-outcome pair"""
    factor: str
    outcome: str
    window: TimeWindow

    # Effect estimates
    log_effect_raw: float
    se_raw: float
    log_effect_shrunk: Optional[float] = None
    se_shrunk: Optional[float] = None

    # Meta-analysis statistics
    k_studies: int
    tau_squared: float
    i_squared: float
    q_statistic: float
    p_heterogeneity: float

    # Quality indicators
    hk_sj_used: bool = False
    egger_p: Optional[float] = None
    trim_fill_added: int = 0
    loo_max_delta_pp: Optional[float] = None

    # Weights and studies
    total_weight: float
    studies: List[Study]

class BaselineRisk(BaseModel):
    """Baseline risk for outcome stratified by patient characteristics"""
    outcome: str
    window: TimeWindow
    age_band: AgeBand
    surgery: SurgeryType
    urgency: Urgency

    # Risk estimates
    p0: float
    p0_ci_lower: Optional[float] = None
    p0_ci_upper: Optional[float] = None

    # Reference comparison
    p_ref: float  # Reference risk for comparison
    delta_pp: float  # Absolute difference in percentage points
    fold_ratio: float  # Fold difference

    # Data quality
    n_patients: Optional[int] = None
    n_events: Optional[int] = None
    era: Optional[str] = None

    # Flags
    baseline_high_risk: bool = False

class ConfidenceBreakdown(BaseModel):
    """Detailed breakdown of confidence scoring"""
    k_studies_score: float
    design_mix_score: float
    bias_score: float
    temporal_freshness_score: float
    window_match_score: float
    heterogeneity_score: float
    egger_penalty: float
    loo_stability_score: float

    total_score: float
    letter_grade: ConfidenceLevel

class OutcomeRisk(BaseModel):
    """Complete risk assessment for an outcome"""
    outcome: str
    window: TimeWindow

    # Baseline risk
    baseline: BaselineRisk

    # Adjusted risk
    adjusted_risk: float
    ci_lower: float
    ci_upper: float

    # Risk differences
    absolute_increase_pp: float  # Percentage points
    relative_risk_ratio: float

    # Quality assessment
    confidence: ConfidenceBreakdown

    # Contributing factors
    factors: List[Dict[str, Any]]  # Factor codes with their contributions

    # Meta-analysis details
    diagnostics: Dict[str, Any]
    citations: List[Dict[str, Any]]
    flags: List[str]

    # Methods
    method: str = "REML+HK-SJ"
    mc_draws: int = 5000
    seed: Optional[int] = None

class RiskConfig(BaseModel):
    """Configuration for risk scoring engine"""

    # Temporal weighting
    temporal_tau: float = 7.0  # years

    # Study quality weights
    design_weights: Dict[StudyDesign, float] = {
        StudyDesign.RCT: 1.0,
        StudyDesign.PROSPECTIVE: 0.7,
        StudyDesign.RETROSPECTIVE: 0.5
    }

    bias_penalty: Dict[RiskOfBias, float] = {
        RiskOfBias.LOW: 1.0,
        RiskOfBias.SOME: 0.8,
        RiskOfBias.HIGH: 0.5
    }

    # Window matching
    window_match_weight: Dict[str, float] = {
        "exact": 1.0,
        "near": 0.7
    }

    # Study size effects
    small_study_threshold: int = 200
    small_study_penalty: float = 0.7

    # Meta-analysis settings
    use_hk_sj: bool = True
    hk_sj_threshold_k: int = 10
    hk_sj_threshold_i2: float = 40.0

    # Bayesian shrinkage
    skeptical_prior_sd: float = 0.4

    # Baseline high-risk thresholds
    baseline_high_thresholds: Dict[str, float] = {
        "T_abs": 0.08,    # 8% absolute risk
        "T_delta": 0.03,  # 3 percentage points above reference
        "T_rel": 1.8      # 1.8x fold increase
    }

    # Mutex groups and interactions
    mutex_groups: List[List[str]] = [
        ["ASTHMA", "RAD"],
        ["OSA", "SLEEP_APNEA"]
    ]

    interaction_pairs: List[List[str]] = [
        ["ASTHMA", "RECENT_URI_2W"]
    ]

    # Calibration
    calibration_method: Optional[Literal["isotonic", "platt"]] = None

    # Confidence scoring weights
    confidence_weights: Dict[str, float] = {
        "k_studies": 0.25,
        "design_mix": 0.15,
        "bias": 0.15,
        "temporal": 0.15,
        "window_match": 0.10,
        "heterogeneity": 0.10,
        "publication_bias": 0.05,
        "loo_stability": 0.05
    }

class RiskEngineManifest(BaseModel):
    """Manifest for exported risk engine artifacts"""
    schema_version: str = "1.0"
    artifact_hash: str
    created_at: datetime
    config_digest: str

    # File locations
    baseline_risks_path: str
    pooled_effects_path: str
    diagnostics_path: str
    combinations_index_path: str

    # Metadata
    total_studies: int
    total_outcomes: int
    total_factors: int
    coverage_stats: Dict[str, Any]