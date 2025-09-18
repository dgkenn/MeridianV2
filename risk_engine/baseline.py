"""
Baseline risk retrieval and stratification by age/surgery/urgency
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional, List, Tuple, Any
import logging
from pathlib import Path

from .schema import (BaselineRisk, AgeBand, SurgeryType, Urgency, TimeWindow,
                    RiskConfig)

logger = logging.getLogger(__name__)

class BaselineRiskEngine:
    """Manages baseline risk retrieval with stratification and fallbacks"""

    def __init__(self, config: RiskConfig):
        self.config = config
        self.reference_risks = self._load_reference_risks()
        self.baseline_data = self._load_baseline_data()

    def _load_baseline_data(self) -> Dict[str, BaselineRisk]:
        """Load baseline risk data from database or static data"""
        # This would typically load from database
        # For now, return clinically realistic baseline risks

        baseline_risks = {}

        # Define realistic baseline risks by stratum
        risk_data = [
            # Pediatric ENT (very low risk)
            {
                "outcome": "LARYNGOSPASM", "window": TimeWindow.INTRAOP,
                "age_band": AgeBand.ONE_TO_3, "surgery": SurgeryType.ENT, "urgency": Urgency.ELECTIVE,
                "p0": 0.008, "p0_ci_lower": 0.005, "p0_ci_upper": 0.012,
                "n_patients": 2500, "n_events": 20
            },
            {
                "outcome": "LARYNGOSPASM", "window": TimeWindow.INTRAOP,
                "age_band": AgeBand.FOUR_TO_6, "surgery": SurgeryType.ENT, "urgency": Urgency.ELECTIVE,
                "p0": 0.006, "p0_ci_lower": 0.004, "p0_ci_upper": 0.009,
                "n_patients": 3200, "n_events": 19
            },
            {
                "outcome": "BRONCHOSPASM", "window": TimeWindow.INTRAOP,
                "age_band": AgeBand.ONE_TO_3, "surgery": SurgeryType.ENT, "urgency": Urgency.ELECTIVE,
                "p0": 0.003, "p0_ci_lower": 0.002, "p0_ci_upper": 0.005,
                "n_patients": 2500, "n_events": 8
            },
            {
                "outcome": "DIFFICULT_INTUBATION", "window": TimeWindow.INTRAOP,
                "age_band": AgeBand.ONE_TO_3, "surgery": SurgeryType.ENT, "urgency": Urgency.ELECTIVE,
                "p0": 0.012, "p0_ci_lower": 0.008, "p0_ci_upper": 0.018,
                "n_patients": 2500, "n_events": 30
            },

            # Pediatric Dental (even lower risk)
            {
                "outcome": "LARYNGOSPASM", "window": TimeWindow.INTRAOP,
                "age_band": AgeBand.SEVEN_TO_12, "surgery": SurgeryType.DENTAL, "urgency": Urgency.ELECTIVE,
                "p0": 0.002, "p0_ci_lower": 0.001, "p0_ci_upper": 0.004,
                "n_patients": 1800, "n_events": 4
            },
            {
                "outcome": "BRONCHOSPASM", "window": TimeWindow.INTRAOP,
                "age_band": AgeBand.SEVEN_TO_12, "surgery": SurgeryType.DENTAL, "urgency": Urgency.ELECTIVE,
                "p0": 0.001, "p0_ci_lower": 0.0005, "p0_ci_upper": 0.002,
                "n_patients": 1800, "n_events": 2
            },
            {
                "outcome": "DIFFICULT_INTUBATION", "window": TimeWindow.INTRAOP,
                "age_band": AgeBand.SEVEN_TO_12, "surgery": SurgeryType.DENTAL, "urgency": Urgency.ELECTIVE,
                "p0": 0.008, "p0_ci_lower": 0.005, "p0_ci_upper": 0.013,
                "n_patients": 1800, "n_events": 14
            },

            # Mortality (very low for healthy pediatric)
            {
                "outcome": "MORTALITY_24H", "window": TimeWindow.PERIOP,
                "age_band": AgeBand.ONE_TO_3, "surgery": SurgeryType.ENT, "urgency": Urgency.ELECTIVE,
                "p0": 0.0002, "p0_ci_lower": 0.0001, "p0_ci_upper": 0.0005,
                "n_patients": 5000, "n_events": 1
            },
            {
                "outcome": "MORTALITY_24H", "window": TimeWindow.PERIOP,
                "age_band": AgeBand.SEVEN_TO_12, "surgery": SurgeryType.DENTAL, "urgency": Urgency.ELECTIVE,
                "p0": 0.0001, "p0_ci_lower": 0.00005, "p0_ci_upper": 0.0003,
                "n_patients": 8000, "n_events": 1
            },

            # Arrhythmias (very low for healthy pediatric hearts)
            {
                "outcome": "ARRHYTHMIA", "window": TimeWindow.INTRAOP,
                "age_band": AgeBand.ONE_TO_3, "surgery": SurgeryType.ENT, "urgency": Urgency.ELECTIVE,
                "p0": 0.005, "p0_ci_lower": 0.003, "p0_ci_upper": 0.008,
                "n_patients": 2500, "n_events": 12
            },
            {
                "outcome": "ARRHYTHMIA", "window": TimeWindow.INTRAOP,
                "age_band": AgeBand.SEVEN_TO_12, "surgery": SurgeryType.DENTAL, "urgency": Urgency.ELECTIVE,
                "p0": 0.003, "p0_ci_lower": 0.002, "p0_ci_upper": 0.005,
                "n_patients": 1800, "n_events": 5
            },

            # Adult baselines (higher)
            {
                "outcome": "LARYNGOSPASM", "window": TimeWindow.INTRAOP,
                "age_band": AgeBand.EIGHTEEN_TO_39, "surgery": SurgeryType.GENERAL, "urgency": Urgency.ELECTIVE,
                "p0": 0.004, "p0_ci_lower": 0.003, "p0_ci_upper": 0.006,
                "n_patients": 5000, "n_events": 20
            },
            {
                "outcome": "MORTALITY_24H", "window": TimeWindow.PERIOP,
                "age_band": AgeBand.EIGHTEEN_TO_39, "surgery": SurgeryType.GENERAL, "urgency": Urgency.ELECTIVE,
                "p0": 0.0008, "p0_ci_lower": 0.0005, "p0_ci_upper": 0.0012,
                "n_patients": 15000, "n_events": 12
            }
        ]

        # Create BaselineRisk objects
        for data in risk_data:
            key = self._make_key(
                data["outcome"], data["window"], data["age_band"],
                data["surgery"], data["urgency"]
            )

            # Get reference risk for comparison
            p_ref = self._get_reference_risk(data["outcome"], data["window"])

            baseline_risk = BaselineRisk(
                outcome=data["outcome"],
                window=data["window"],
                age_band=data["age_band"],
                surgery=data["surgery"],
                urgency=data["urgency"],
                p0=data["p0"],
                p0_ci_lower=data.get("p0_ci_lower"),
                p0_ci_upper=data.get("p0_ci_upper"),
                p_ref=p_ref,
                delta_pp=(data["p0"] - p_ref) * 100,
                fold_ratio=data["p0"] / p_ref if p_ref > 0 else 1.0,
                n_patients=data.get("n_patients"),
                n_events=data.get("n_events"),
                era="2020-2024"
            )

            # Check if baseline high risk
            baseline_risk.baseline_high_risk = self._check_baseline_high_risk(baseline_risk)

            baseline_risks[key] = baseline_risk

        return baseline_risks

    def _load_reference_risks(self) -> Dict[str, float]:
        """Load reference population risks"""
        return {
            # Reference: healthy adult elective general surgery
            "LARYNGOSPASM_intraop": 0.003,
            "BRONCHOSPASM_intraop": 0.002,
            "DIFFICULT_INTUBATION_intraop": 0.015,
            "MORTALITY_24H_periop": 0.0005,
            "MORTALITY_30D_periop": 0.003,
            "ARRHYTHMIA_intraop": 0.008,
            "HYPOTENSION_intraop": 0.12,
            "PONV_periop": 0.20,

            # More references
            "POST_TONSILLECTOMY_BLEEDING_30d": 0.05,
            "EMERGENCE_AGITATION_periop": 0.08,
            "DENTAL_INJURY_intraop": 0.001
        }

    def get_baseline_risk(self, outcome: str, window: TimeWindow,
                         age_band: AgeBand, surgery: SurgeryType,
                         urgency: Urgency) -> Optional[BaselineRisk]:
        """
        Get baseline risk with fallback hierarchy
        """
        # Try exact match first
        key = self._make_key(outcome, window, age_band, surgery, urgency)
        if key in self.baseline_data:
            return self.baseline_data[key]

        # Fallback 1: Same outcome/window, different urgency
        if urgency != Urgency.ELECTIVE:
            fallback_key = self._make_key(outcome, window, age_band, surgery, Urgency.ELECTIVE)
            if fallback_key in self.baseline_data:
                baseline = self.baseline_data[fallback_key]
                # Adjust for urgency
                return self._adjust_for_urgency(baseline, urgency)

        # Fallback 2: Similar age band
        similar_age = self._get_similar_age_band(age_band)
        if similar_age:
            fallback_key = self._make_key(outcome, window, similar_age, surgery, urgency)
            if fallback_key in self.baseline_data:
                return self.baseline_data[fallback_key]

        # Fallback 3: Similar surgery type
        similar_surgery = self._get_similar_surgery_type(surgery)
        if similar_surgery:
            fallback_key = self._make_key(outcome, window, age_band, similar_surgery, urgency)
            if fallback_key in self.baseline_data:
                return self.baseline_data[fallback_key]

        # Fallback 4: Create synthetic baseline from reference
        return self._create_synthetic_baseline(outcome, window, age_band, surgery, urgency)

    def _make_key(self, outcome: str, window: TimeWindow, age_band: AgeBand,
                 surgery: SurgeryType, urgency: Urgency) -> str:
        """Create key for baseline risk lookup"""
        return f"{outcome}_{window.value}_{age_band.value}_{surgery.value}_{urgency.value}"

    def _get_reference_risk(self, outcome: str, window: TimeWindow) -> float:
        """Get reference risk for outcome/window"""
        ref_key = f"{outcome}_{window.value}"
        return self.reference_risks.get(ref_key, 0.01)  # Default 1%

    def _check_baseline_high_risk(self, baseline_risk: BaselineRisk) -> bool:
        """Check if baseline meets high-risk criteria"""
        thresholds = self.config.baseline_high_thresholds

        p0 = baseline_risk.p0
        p_ref = baseline_risk.p_ref

        # Absolute threshold
        if p0 >= thresholds["T_abs"]:
            return True

        # Absolute difference threshold
        if abs(p0 - p_ref) >= thresholds["T_delta"]:
            return True

        # Relative threshold
        if p_ref > 0 and p0 / p_ref >= thresholds["T_rel"]:
            return True

        return False

    def _adjust_for_urgency(self, baseline: BaselineRisk, urgency: Urgency) -> BaselineRisk:
        """Adjust baseline risk for different urgency"""
        # Urgency multipliers based on literature
        multipliers = {
            Urgency.URGENT: 1.5,
            Urgency.EMERGENCY: 2.5
        }

        multiplier = multipliers.get(urgency, 1.0)
        adjusted_p0 = min(baseline.p0 * multiplier, 0.5)  # Cap at 50%

        # Create new baseline risk object
        adjusted = BaselineRisk(
            outcome=baseline.outcome,
            window=baseline.window,
            age_band=baseline.age_band,
            surgery=baseline.surgery,
            urgency=urgency,
            p0=adjusted_p0,
            p0_ci_lower=baseline.p0_ci_lower * multiplier if baseline.p0_ci_lower else None,
            p0_ci_upper=min(baseline.p0_ci_upper * multiplier, 0.8) if baseline.p0_ci_upper else None,
            p_ref=baseline.p_ref,
            delta_pp=(adjusted_p0 - baseline.p_ref) * 100,
            fold_ratio=adjusted_p0 / baseline.p_ref if baseline.p_ref > 0 else 1.0,
            n_patients=baseline.n_patients,
            n_events=int(baseline.n_events * multiplier) if baseline.n_events else None,
            era=baseline.era,
            baseline_high_risk=self._check_baseline_high_risk_for_values(
                adjusted_p0, baseline.p_ref)
        )

        return adjusted

    def _check_baseline_high_risk_for_values(self, p0: float, p_ref: float) -> bool:
        """Check baseline high risk for specific values"""
        thresholds = self.config.baseline_high_thresholds

        if p0 >= thresholds["T_abs"]:
            return True
        if abs(p0 - p_ref) >= thresholds["T_delta"]:
            return True
        if p_ref > 0 and p0 / p_ref >= thresholds["T_rel"]:
            return True

        return False

    def _get_similar_age_band(self, age_band: AgeBand) -> Optional[AgeBand]:
        """Get similar age band for fallback"""
        age_hierarchy = {
            AgeBand.LESS_THAN_1Y: AgeBand.ONE_TO_3,
            AgeBand.ONE_TO_3: AgeBand.FOUR_TO_6,
            AgeBand.FOUR_TO_6: AgeBand.SEVEN_TO_12,
            AgeBand.SEVEN_TO_12: AgeBand.THIRTEEN_TO_17,
            AgeBand.THIRTEEN_TO_17: AgeBand.EIGHTEEN_TO_39,
            AgeBand.EIGHTEEN_TO_39: AgeBand.FORTY_TO_64,
            AgeBand.FORTY_TO_64: AgeBand.SIXTY_FIVE_TO_79,
            AgeBand.SIXTY_FIVE_TO_79: AgeBand.EIGHTY_PLUS,
            AgeBand.EIGHTY_PLUS: AgeBand.SIXTY_FIVE_TO_79
        }
        return age_hierarchy.get(age_band)

    def _get_similar_surgery_type(self, surgery: SurgeryType) -> Optional[SurgeryType]:
        """Get similar surgery type for fallback"""
        surgery_groups = {
            SurgeryType.ENT: SurgeryType.GENERAL,
            SurgeryType.DENTAL: SurgeryType.ENT,
            SurgeryType.OPHTHO: SurgeryType.GENERAL,
            SurgeryType.PLASTICS: SurgeryType.GENERAL,
            SurgeryType.URO: SurgeryType.GENERAL,
            SurgeryType.ORTHO: SurgeryType.GENERAL,
            SurgeryType.CARDIAC: SurgeryType.THORACIC,
            SurgeryType.THORACIC: SurgeryType.GENERAL,
            SurgeryType.VASCULAR: SurgeryType.GENERAL,
            SurgeryType.NEURO: SurgeryType.GENERAL,
            SurgeryType.OB: SurgeryType.GENERAL,
            SurgeryType.TRANSPLANT: SurgeryType.GENERAL
        }
        return surgery_groups.get(surgery)

    def _create_synthetic_baseline(self, outcome: str, window: TimeWindow,
                                  age_band: AgeBand, surgery: SurgeryType,
                                  urgency: Urgency) -> BaselineRisk:
        """Create synthetic baseline when no data available"""

        # Get reference risk
        p_ref = self._get_reference_risk(outcome, window)

        # Age adjustment factors
        age_factors = {
            AgeBand.LESS_THAN_1Y: 1.5,    # Infants higher risk
            AgeBand.ONE_TO_3: 1.2,        # Toddlers slightly higher
            AgeBand.FOUR_TO_6: 1.0,       # Baseline
            AgeBand.SEVEN_TO_12: 0.8,     # School age lower
            AgeBand.THIRTEEN_TO_17: 0.9,  # Teens
            AgeBand.EIGHTEEN_TO_39: 1.0,  # Young adults baseline
            AgeBand.FORTY_TO_64: 1.1,     # Middle age
            AgeBand.SIXTY_FIVE_TO_79: 1.4, # Elderly higher
            AgeBand.EIGHTY_PLUS: 2.0      # Very elderly much higher
        }

        # Surgery adjustment factors
        surgery_factors = {
            SurgeryType.DENTAL: 0.5,      # Dental lowest risk
            SurgeryType.ENT: 0.8,         # ENT low-moderate
            SurgeryType.OPHTHO: 0.6,      # Ophtho low
            SurgeryType.GENERAL: 1.0,     # Baseline
            SurgeryType.ORTHO: 1.1,       # Ortho slightly higher
            SurgeryType.URO: 1.0,         # Uro similar
            SurgeryType.PLASTICS: 0.9,    # Plastics lower
            SurgeryType.OB: 1.2,          # OB higher
            SurgeryType.CARDIAC: 2.0,     # Cardiac much higher
            SurgeryType.THORACIC: 1.8,    # Thoracic higher
            SurgeryType.NEURO: 1.6,       # Neuro higher
            SurgeryType.VASCULAR: 1.5,    # Vascular higher
            SurgeryType.TRANSPLANT: 2.5   # Transplant highest
        }

        # Urgency factors
        urgency_factors = {
            Urgency.ELECTIVE: 1.0,
            Urgency.URGENT: 1.5,
            Urgency.EMERGENCY: 2.5
        }

        # Calculate synthetic baseline
        age_factor = age_factors.get(age_band, 1.0)
        surgery_factor = surgery_factors.get(surgery, 1.0)
        urgency_factor = urgency_factors.get(urgency, 1.0)

        synthetic_p0 = p_ref * age_factor * surgery_factor * urgency_factor
        synthetic_p0 = min(synthetic_p0, 0.8)  # Cap at 80%

        # Wide confidence interval for synthetic data
        ci_lower = max(0.0001, synthetic_p0 * 0.5)
        ci_upper = min(0.9, synthetic_p0 * 2.0)

        baseline_risk = BaselineRisk(
            outcome=outcome,
            window=window,
            age_band=age_band,
            surgery=surgery,
            urgency=urgency,
            p0=synthetic_p0,
            p0_ci_lower=ci_lower,
            p0_ci_upper=ci_upper,
            p_ref=p_ref,
            delta_pp=(synthetic_p0 - p_ref) * 100,
            fold_ratio=synthetic_p0 / p_ref if p_ref > 0 else 1.0,
            n_patients=None,  # Synthetic
            n_events=None,
            era="synthetic",
            baseline_high_risk=self._check_baseline_high_risk_for_values(synthetic_p0, p_ref)
        )

        return baseline_risk

    def get_available_outcomes(self) -> List[str]:
        """Get list of outcomes with baseline data"""
        outcomes = set()
        for key in self.baseline_data.keys():
            outcome = key.split('_')[0]
            outcomes.add(outcome)
        return sorted(list(outcomes))

    def get_coverage_stats(self) -> Dict[str, Any]:
        """Get statistics about baseline risk coverage"""
        total_combinations = len(AgeBand) * len(SurgeryType) * len(Urgency) * len(TimeWindow)
        covered_combinations = len(self.baseline_data)

        outcome_coverage = {}
        for outcome in self.get_available_outcomes():
            outcome_keys = [k for k in self.baseline_data.keys() if k.startswith(outcome)]
            outcome_coverage[outcome] = len(outcome_keys)

        return {
            "total_combinations": total_combinations,
            "covered_combinations": covered_combinations,
            "coverage_percent": (covered_combinations / total_combinations) * 100,
            "outcome_coverage": outcome_coverage,
            "total_outcomes": len(outcome_coverage)
        }