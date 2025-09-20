#!/usr/bin/env python3
"""
Risk Display Service - Patient-centric risk ranking and display logic
Implements priority scoring, filtering, and organization for the Risk Scores tab
"""

import yaml
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import os

logger = logging.getLogger(__name__)

@dataclass
class RiskOutcome:
    """Individual risk outcome with display metadata"""
    outcome: str
    outcome_label: str
    window: str
    organ_system: str
    p0: float  # baseline risk
    p_hat: float  # adjusted risk
    delta_pp: float  # percentage point increase
    confidence_score: int  # 0-100
    confidence_letter: str  # A-D
    has_mitigation: bool
    is_time_critical: bool
    is_applicable: bool
    is_calibrated: bool
    baseline_banner: bool

    # Computed fields
    priority: float = 0.0
    rank_phat: int = 0
    rank_delta: int = 0
    show_section: str = "hidden"  # "top", "organ", "hidden"
    why_shown: List[str] = field(default_factory=list)

@dataclass
class RiskDisplayConfig:
    """Configuration for risk display logic"""
    # Thresholds
    min_show_phat: float = 0.01
    min_show_delta_pp: float = 1.0
    hide_floor_phat: float = 0.005
    hide_floor_delta_pp: float = 0.5
    confidence_hide: str = "D"
    top_overall: int = 3
    top_per_organ: int = 2

    # Priority weights
    w_phat: float = 0.50
    w_delta: float = 0.25
    w_conf: float = 0.15
    w_mod: float = 0.05
    w_time: float = 0.03
    w_cal: float = 0.02

    # Configuration metadata
    variant: str = "B"
    last_updated: str = ""

class RiskDisplayService:
    """Service for computing risk priorities and organizing display"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "config/risk_display.yaml"
        self.config = self._load_config()
        self.confidence_scores = {"A": 100, "B": 75, "C": 50, "D": 25}
        self.time_critical_windows = {"intraop", "periop_24h"}
        self.organ_systems = self._load_organ_systems()

    def _load_config(self) -> RiskDisplayConfig:
        """Load configuration from YAML file"""
        try:
            config_file = Path(self.config_path)
            if config_file.exists():
                with open(config_file, 'r') as f:
                    config_data = yaml.safe_load(f)

                # Get current variant weights
                variant = config_data.get('runtime_config', {}).get('variant', 'B')
                variant_weights = config_data.get('ab_variants', {}).get(variant, {})

                # Merge thresholds and weights
                thresholds = config_data.get('display_thresholds', {})
                weights = variant_weights if variant_weights else config_data.get('priority_weights', {})

                return RiskDisplayConfig(
                    **thresholds,
                    **weights,
                    variant=variant,
                    last_updated=config_data.get('runtime_config', {}).get('last_updated', '')
                )
            else:
                logger.warning(f"Config file {self.config_path} not found, using defaults")
                return RiskDisplayConfig()

        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return RiskDisplayConfig()

    def _load_organ_systems(self) -> Dict[str, List[str]]:
        """Load organ system mappings"""
        try:
            with open(self.config_path, 'r') as f:
                config_data = yaml.safe_load(f)
            return config_data.get('organ_systems', {})
        except Exception as e:
            logger.error(f"Error loading organ systems: {e}")
            return {}

    def _get_organ_system(self, outcome: str) -> str:
        """Map outcome to organ system"""
        for organ, outcomes in self.organ_systems.items():
            if outcome in outcomes:
                return organ
        return "other"

    def compute_risk_priorities(self, risk_outcomes: List[Dict[str, Any]]) -> List[RiskOutcome]:
        """
        Compute priority scores for all risk outcomes

        Args:
            risk_outcomes: List of risk outcome dictionaries

        Returns:
            List of RiskOutcome objects with computed priorities
        """
        outcomes = []

        # Convert to RiskOutcome objects
        for outcome_data in risk_outcomes:
            outcome = RiskOutcome(
                outcome=outcome_data.get('outcome', ''),
                outcome_label=outcome_data.get('outcome_label', ''),
                window=outcome_data.get('window', 'periop'),
                organ_system=self._get_organ_system(outcome_data.get('outcome', '')),
                p0=outcome_data.get('baseline_risk', 0.0),
                p_hat=outcome_data.get('adjusted_risk', 0.0),
                delta_pp=outcome_data.get('risk_difference', 0.0) * 100,  # Convert to percentage points
                confidence_score=self.confidence_scores.get(
                    outcome_data.get('evidence_grade', 'D'), 25
                ),
                confidence_letter=outcome_data.get('evidence_grade', 'D'),
                has_mitigation=outcome_data.get('has_mitigation', False),
                is_time_critical=outcome_data.get('is_time_critical', False),
                is_applicable=outcome_data.get('is_applicable', True),
                is_calibrated=outcome_data.get('is_calibrated', False),
                baseline_banner=outcome_data.get('baseline_banner', False)
            )
            outcomes.append(outcome)

        if not outcomes:
            return []

        # Compute rank normalizations
        p_hats = [o.p_hat for o in outcomes]
        deltas = [o.delta_pp for o in outcomes]

        rank_phat = self._rank_normalize(p_hats)
        rank_delta = self._rank_normalize(deltas)

        # Compute priorities
        for i, outcome in enumerate(outcomes):
            outcome.rank_phat = rank_phat[i]
            outcome.rank_delta = rank_delta[i]
            outcome.priority = self._compute_priority(outcome, rank_phat[i], rank_delta[i])

        # Sort by priority (descending)
        outcomes.sort(key=lambda x: (x.priority, x.p_hat, x.confidence_score, x.has_mitigation),
                     reverse=True)

        return outcomes

    def _rank_normalize(self, values: List[float]) -> List[float]:
        """Convert values to rank-normalized scores (0-1)"""
        if not values or len(values) == 1:
            return [1.0] * len(values)

        # Convert to ranks (1 = highest)
        sorted_indices = np.argsort(values)[::-1]  # Descending order
        ranks = np.empty_like(sorted_indices)
        ranks[sorted_indices] = np.arange(len(values)) + 1

        # Normalize to 0-1 (1 = highest value)
        normalized = 1.0 - (ranks - 1) / (len(values) - 1)
        return normalized.tolist()

    def _compute_priority(self, outcome: RiskOutcome, rank_phat: float, rank_delta: float) -> float:
        """Compute priority score for an outcome"""
        priority = (
            self.config.w_phat * rank_phat +
            self.config.w_delta * rank_delta +
            self.config.w_conf * (outcome.confidence_score / 100) +
            self.config.w_mod * (1 if outcome.has_mitigation else 0) +
            self.config.w_time * (1 if outcome.window in self.time_critical_windows else 0) +
            self.config.w_cal * (1 if outcome.is_calibrated else 0)
        )

        return priority

    def organize_for_display(self, outcomes: List[RiskOutcome]) -> Dict[str, Any]:
        """
        Organize outcomes for display according to rules

        Returns:
            Dictionary with organized outcomes and metadata
        """
        # Filter applicable outcomes
        applicable_outcomes = [o for o in outcomes if o.is_applicable]

        # Determine show sections and reasons
        for outcome in applicable_outcomes:
            outcome.show_section, outcome.why_shown = self._determine_show_section(outcome)

        # Group outcomes
        top_strip = self._get_top_strip_outcomes(applicable_outcomes)
        organ_groups = self._group_by_organ(applicable_outcomes)
        hidden_outcomes = [o for o in applicable_outcomes if o.show_section == "hidden"]

        # Audit data
        priority_stats = self._compute_priority_stats(applicable_outcomes)

        return {
            "top_strip": top_strip,
            "organ_groups": organ_groups,
            "hidden_count": len(hidden_outcomes),
            "total_outcomes": len(applicable_outcomes),
            "priority_stats": priority_stats,
            "config_snapshot": {
                "variant": self.config.variant,
                "thresholds": {
                    "min_show_phat": self.config.min_show_phat,
                    "min_show_delta_pp": self.config.min_show_delta_pp,
                },
                "weights": {
                    "w_phat": self.config.w_phat,
                    "w_delta": self.config.w_delta,
                    "w_conf": self.config.w_conf,
                    "w_mod": self.config.w_mod,
                }
            }
        }

    def _determine_show_section(self, outcome: RiskOutcome) -> Tuple[str, List[str]]:
        """Determine which section to show outcome in and why"""
        why_shown = []

        # Check hide criteria first
        if self._should_hide_completely(outcome):
            return "hidden", ["Low relevance: below thresholds and no mitigation"]

        # Top strip criteria
        if (outcome.baseline_banner or
            (outcome.is_time_critical and outcome.has_mitigation)):
            why_shown.append("Baseline banner" if outcome.baseline_banner else "Time-critical with mitigation")
            return "top", why_shown

        # Check if meets organ tab thresholds
        if self._meets_organ_threshold(outcome):
            if outcome.p_hat >= self.config.min_show_phat:
                why_shown.append(f"High risk: {outcome.p_hat:.1%}")
            if outcome.delta_pp >= self.config.min_show_delta_pp:
                why_shown.append(f"High increase: +{outcome.delta_pp:.1f}pp")
            if outcome.confidence_letter in ["A", "B"] and outcome.has_mitigation:
                why_shown.append("High confidence with mitigation")

            return "organ", why_shown

        return "hidden", ["Below display thresholds"]

    def _should_hide_completely(self, outcome: RiskOutcome) -> bool:
        """Check if outcome should be hidden entirely"""
        return (
            outcome.confidence_letter == self.config.confidence_hide and
            outcome.p_hat < self.config.hide_floor_phat and
            outcome.delta_pp < self.config.hide_floor_delta_pp and
            not outcome.has_mitigation
        )

    def _meets_organ_threshold(self, outcome: RiskOutcome) -> bool:
        """Check if outcome meets thresholds for organ tabs"""
        return (
            outcome.p_hat >= self.config.min_show_phat or
            outcome.delta_pp >= self.config.min_show_delta_pp or
            (outcome.confidence_letter in ["A", "B"] and outcome.has_mitigation)
        )

    def _get_top_strip_outcomes(self, outcomes: List[RiskOutcome]) -> List[RiskOutcome]:
        """Get outcomes for top strip display"""
        # Top 3 by priority
        top_by_priority = outcomes[:self.config.top_overall]

        # Add baseline-bannered and time-critical mitigable
        special_outcomes = [
            o for o in outcomes
            if (o.baseline_banner or (o.is_time_critical and o.has_mitigation))
            and o not in top_by_priority
        ]

        # Combine and deduplicate
        top_strip = top_by_priority + special_outcomes

        # Mark as top strip
        for outcome in top_strip:
            if outcome.show_section != "top":
                outcome.show_section = "top"
                outcome.why_shown.append("Top priority")

        return top_strip

    def _group_by_organ(self, outcomes: List[RiskOutcome]) -> Dict[str, List[RiskOutcome]]:
        """Group outcomes by organ system for tabs"""
        organ_groups = {}

        # Group by organ system
        for outcome in outcomes:
            if outcome.show_section in ["organ", "top"]:
                organ = outcome.organ_system
                if organ not in organ_groups:
                    organ_groups[organ] = []
                organ_groups[organ].append(outcome)

        # Keep top N per organ for organ display
        for organ, organ_outcomes in organ_groups.items():
            # Sort by priority within organ
            organ_outcomes.sort(key=lambda x: x.priority, reverse=True)

            # Mark top N as organ display
            for i, outcome in enumerate(organ_outcomes):
                if outcome.show_section != "top" and i < self.config.top_per_organ:
                    outcome.show_section = "organ"
                    if "Top in organ" not in outcome.why_shown:
                        outcome.why_shown.append("Top in organ")

        return organ_groups

    def _compute_priority_stats(self, outcomes: List[RiskOutcome]) -> Dict[str, Any]:
        """Compute statistics for telemetry"""
        if not outcomes:
            return {}

        priorities = [o.priority for o in outcomes]
        p_hats = [o.p_hat for o in outcomes]
        deltas = [o.delta_pp for o in outcomes]

        return {
            "priority": {
                "mean": np.mean(priorities),
                "median": np.median(priorities),
                "std": np.std(priorities),
                "min": np.min(priorities),
                "max": np.max(priorities)
            },
            "p_hat": {
                "mean": np.mean(p_hats),
                "median": np.median(p_hats),
                "p95": np.percentile(p_hats, 95)
            },
            "delta_pp": {
                "mean": np.mean(deltas),
                "median": np.median(deltas),
                "p95": np.percentile(deltas, 95)
            },
            "counts": {
                "total": len(outcomes),
                "top": len([o for o in outcomes if o.show_section == "top"]),
                "organ": len([o for o in outcomes if o.show_section == "organ"]),
                "hidden": len([o for o in outcomes if o.show_section == "hidden"]),
                "with_mitigation": len([o for o in outcomes if o.has_mitigation]),
                "time_critical": len([o for o in outcomes if o.is_time_critical])
            }
        }

    def update_config(self, updates: Dict[str, Any]) -> bool:
        """Update configuration at runtime"""
        try:
            # Update current config
            for key, value in updates.items():
                if hasattr(self.config, key):
                    setattr(self.config, key, value)

            # Update timestamp
            self.config.last_updated = datetime.utcnow().isoformat()

            logger.info(f"Updated risk display config: {updates}")
            return True

        except Exception as e:
            logger.error(f"Error updating config: {e}")
            return False

    def get_hidden_outcomes(self, outcomes: List[RiskOutcome],
                           search_term: Optional[str] = None) -> List[RiskOutcome]:
        """Get hidden outcomes, optionally filtered by search term"""
        hidden = [o for o in outcomes if o.show_section == "hidden"]

        if search_term:
            search_lower = search_term.lower()
            hidden = [
                o for o in hidden
                if (search_lower in o.outcome.lower() or
                    search_lower in o.outcome_label.lower())
            ]

        return hidden

    def emit_telemetry_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Emit telemetry event for A/B testing and optimization"""
        event = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "variant": self.config.variant,
            "data": data
        }

        # In production, send to analytics service
        logger.info(f"Telemetry: {event_type}", extra=event)

    def validate_weights(self) -> bool:
        """Validate that priority weights sum to 1.0"""
        total = (self.config.w_phat + self.config.w_delta + self.config.w_conf +
                self.config.w_mod + self.config.w_time + self.config.w_cal)

        tolerance = 0.001
        is_valid = abs(total - 1.0) < tolerance

        if not is_valid:
            logger.warning(f"Priority weights sum to {total:.3f}, should be 1.0")

        return is_valid

# CLI interface for runtime config updates
def update_variant(variant: str, config_path: str = "config/risk_display.yaml") -> bool:
    """CLI function to update A/B test variant"""
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        if variant not in config.get('ab_variants', {}):
            print(f"Error: Variant '{variant}' not found in config")
            return False

        config['runtime_config']['variant'] = variant
        config['runtime_config']['last_updated'] = datetime.utcnow().isoformat()
        config['runtime_config']['updated_by'] = "cli"

        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)

        print(f"Updated variant to '{variant}'")
        return True

    except Exception as e:
        print(f"Error updating variant: {e}")
        return False

if __name__ == "__main__":
    import sys

    if len(sys.argv) >= 3 and sys.argv[1] == "set-variant":
        update_variant(sys.argv[2])
    else:
        print("Usage: python risk_display.py set-variant [A|B|C]")