#!/usr/bin/env python3
"""
Unit tests for risk display service
"""

import pytest
import yaml
import tempfile
from pathlib import Path
import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.risk_display import RiskDisplayService, RiskOutcome, RiskDisplayConfig

class TestRiskDisplayService:
    """Test risk display service functionality"""

    def setup_method(self):
        """Set up test fixtures"""
        # Create temporary config file
        self.config_data = {
            'display_thresholds': {
                'min_show_phat': 0.01,
                'min_show_delta_pp': 1.0,
                'hide_floor_phat': 0.005,
                'hide_floor_delta_pp': 0.5,
                'confidence_hide': 'D',
                'top_overall': 3,
                'top_per_organ': 2
            },
            'priority_weights': {
                'w_phat': 0.50,
                'w_delta': 0.25,
                'w_conf': 0.15,
                'w_mod': 0.05,
                'w_time': 0.03,
                'w_cal': 0.02
            },
            'organ_systems': {
                'cardiovascular': ['MYOCARDIAL_INFARCTION', 'HYPOTENSION'],
                'respiratory': ['ASPIRATION', 'BRONCHOSPASM', 'LARYNGOSPASM']
            },
            'runtime_config': {'variant': 'B'}
        }

        self.temp_config = tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False)
        yaml.dump(self.config_data, self.temp_config)
        self.temp_config.close()

        self.service = RiskDisplayService(self.temp_config.name)

    def teardown_method(self):
        """Clean up test fixtures"""
        os.unlink(self.temp_config.name)

    def test_config_loading(self):
        """Test configuration loading"""
        assert self.service.config.min_show_phat == 0.01
        assert self.service.config.w_phat == 0.50
        assert self.service.config.variant == 'B'

    def test_organ_system_mapping(self):
        """Test outcome to organ system mapping"""
        assert self.service._get_organ_system('MYOCARDIAL_INFARCTION') == 'cardiovascular'
        assert self.service._get_organ_system('LARYNGOSPASM') == 'respiratory'
        assert self.service._get_organ_system('UNKNOWN_OUTCOME') == 'other'

    def test_rank_normalization(self):
        """Test rank normalization function"""
        values = [0.1, 0.3, 0.2, 0.5]
        normalized = self.service._rank_normalize(values)

        # Highest value (0.5) should get 1.0
        # Lowest value (0.1) should get 0.0
        assert normalized[3] == 1.0  # 0.5 is highest
        assert normalized[0] == 0.0  # 0.1 is lowest
        assert 0 <= normalized[1] <= 1  # All values in [0,1]
        assert 0 <= normalized[2] <= 1

    def test_priority_computation(self):
        """Test priority score computation"""
        outcome = RiskOutcome(
            outcome='MYOCARDIAL_INFARCTION',
            outcome_label='Heart Attack',
            window='periop',
            organ_system='cardiovascular',
            p0=0.01,
            p_hat=0.05,
            delta_pp=4.0,
            confidence_score=100,
            confidence_letter='A',
            has_mitigation=True,
            is_time_critical=False,
            is_applicable=True,
            is_calibrated=True,
            baseline_banner=False
        )

        priority = self.service._compute_priority(outcome, 1.0, 1.0)

        # Should be close to sum of weighted components
        expected = (0.50 * 1.0 +  # rank_phat
                   0.25 * 1.0 +  # rank_delta
                   0.15 * 1.0 +  # confidence
                   0.05 * 1.0 +  # mitigation
                   0.03 * 0.0 +  # time (not time-critical)
                   0.02 * 1.0)   # calibrated

        assert abs(priority - expected) < 0.001

    def test_high_phat_low_confidence_shown(self):
        """Test that high p̂ with low confidence is still shown if above threshold"""
        risk_data = [{
            'outcome': 'HIGH_RISK_LOW_CONF',
            'outcome_label': 'High Risk Low Confidence',
            'window': 'periop',
            'baseline_risk': 0.005,
            'adjusted_risk': 0.02,  # 2% - above min_show_phat
            'risk_difference': 0.015,
            'evidence_grade': 'D',  # Low confidence
            'has_mitigation': False,
            'is_time_critical': False,
            'is_applicable': True,
            'is_calibrated': False,
            'baseline_banner': False
        }]

        outcomes = self.service.compute_risk_priorities(risk_data)
        organized = self.service.organize_for_display(outcomes)

        # Should be shown in organ section despite low confidence
        shown_outcomes = (organized['top_strip'] +
                         [o for organ_outcomes in organized['organ_groups'].values()
                          for o in organ_outcomes])

        assert len(shown_outcomes) > 0
        assert any(o.outcome == 'HIGH_RISK_LOW_CONF' for o in shown_outcomes)

    def test_low_phat_high_delta_shown(self):
        """Test that low p̂ with high delta is shown"""
        risk_data = [{
            'outcome': 'LOW_RISK_HIGH_DELTA',
            'outcome_label': 'Low Risk High Increase',
            'window': 'periop',
            'baseline_risk': 0.002,
            'adjusted_risk': 0.007,  # 0.7% - below min_show_phat
            'risk_difference': 0.005,  # 0.5% = 50 pp - above min_show_delta_pp
            'evidence_grade': 'B',
            'has_mitigation': True,
            'is_time_critical': False,
            'is_applicable': True,
            'is_calibrated': False,
            'baseline_banner': False
        }]

        # Convert risk_difference to percentage points
        risk_data[0]['risk_difference'] = 0.012  # 1.2 pp to exceed threshold

        outcomes = self.service.compute_risk_priorities(risk_data)
        organized = self.service.organize_for_display(outcomes)

        shown_outcomes = (organized['top_strip'] +
                         [o for organ_outcomes in organized['organ_groups'].values()
                          for o in organ_outcomes])

        assert any(o.outcome == 'LOW_RISK_HIGH_DELTA' for o in shown_outcomes)

    def test_baseline_bannered_in_top_strip(self):
        """Test that baseline-bannered items appear in top strip"""
        risk_data = [{
            'outcome': 'BASELINE_BANNER',
            'outcome_label': 'Baseline Banner Item',
            'window': 'periop',
            'baseline_risk': 0.08,  # High baseline
            'adjusted_risk': 0.09,
            'risk_difference': 0.01,
            'evidence_grade': 'A',
            'has_mitigation': False,
            'is_time_critical': False,
            'is_applicable': True,
            'is_calibrated': False,
            'baseline_banner': True  # Should force into top strip
        }]

        outcomes = self.service.compute_risk_priorities(risk_data)
        organized = self.service.organize_for_display(outcomes)

        # Should be in top strip
        top_outcomes = [o.outcome for o in organized['top_strip']]
        assert 'BASELINE_BANNER' in top_outcomes

    def test_hidden_case_all_criteria_met(self):
        """Test that items meeting all hide criteria are hidden"""
        risk_data = [{
            'outcome': 'SHOULD_BE_HIDDEN',
            'outcome_label': 'Should Be Hidden',
            'window': 'periop',
            'baseline_risk': 0.001,
            'adjusted_risk': 0.002,  # 0.2% - below hide_floor_phat
            'risk_difference': 0.001,  # 0.1 pp - below hide_floor_delta_pp
            'evidence_grade': 'D',  # Low confidence
            'has_mitigation': False,  # No mitigation
            'is_time_critical': False,
            'is_applicable': True,
            'is_calibrated': False,
            'baseline_banner': False
        }]

        outcomes = self.service.compute_risk_priorities(risk_data)
        organized = self.service.organize_for_display(outcomes)

        # Should be hidden
        assert organized['hidden_count'] > 0

        shown_outcomes = (organized['top_strip'] +
                         [o for organ_outcomes in organized['organ_groups'].values()
                          for o in organ_outcomes])

        assert not any(o.outcome == 'SHOULD_BE_HIDDEN' for o in shown_outcomes)

    def test_organ_grouping(self):
        """Test that outcomes are properly grouped by organ system"""
        risk_data = [
            {
                'outcome': 'MYOCARDIAL_INFARCTION',
                'outcome_label': 'Heart Attack',
                'window': 'periop',
                'baseline_risk': 0.01,
                'adjusted_risk': 0.03,
                'risk_difference': 0.02,
                'evidence_grade': 'A',
                'has_mitigation': True,
                'is_time_critical': False,
                'is_applicable': True,
                'is_calibrated': True,
                'baseline_banner': False
            },
            {
                'outcome': 'LARYNGOSPASM',
                'outcome_label': 'Laryngospasm',
                'window': 'intraop',
                'baseline_risk': 0.005,
                'adjusted_risk': 0.02,
                'risk_difference': 0.015,
                'evidence_grade': 'B',
                'has_mitigation': True,
                'is_time_critical': True,
                'is_applicable': True,
                'is_calibrated': False,
                'baseline_banner': False
            }
        ]

        outcomes = self.service.compute_risk_priorities(risk_data)
        organized = self.service.organize_for_display(outcomes)

        # Should have cardiovascular and respiratory groups
        assert 'cardiovascular' in organized['organ_groups']
        assert 'respiratory' in organized['organ_groups']

        cardio_outcomes = [o.outcome for o in organized['organ_groups']['cardiovascular']]
        resp_outcomes = [o.outcome for o in organized['organ_groups']['respiratory']]

        assert 'MYOCARDIAL_INFARCTION' in cardio_outcomes
        assert 'LARYNGOSPASM' in resp_outcomes

    def test_top_3_selection(self):
        """Test that top 3 overall risks are selected correctly"""
        risk_data = []

        # Create 5 outcomes with different priorities
        for i in range(5):
            risk_data.append({
                'outcome': f'OUTCOME_{i}',
                'outcome_label': f'Outcome {i}',
                'window': 'periop',
                'baseline_risk': 0.01,
                'adjusted_risk': 0.01 + (i * 0.01),  # Increasing risk
                'risk_difference': i * 0.005,
                'evidence_grade': 'A',
                'has_mitigation': True,
                'is_time_critical': False,
                'is_applicable': True,
                'is_calibrated': True,
                'baseline_banner': False
            })

        outcomes = self.service.compute_risk_priorities(risk_data)
        organized = self.service.organize_for_display(outcomes)

        # Should have at most 3 in top strip (unless baseline bannered)
        top_outcomes = organized['top_strip']
        assert len(top_outcomes) <= 3

        # Top outcomes should have highest priorities
        top_priorities = [o.priority for o in top_outcomes]
        all_priorities = [o.priority for o in outcomes]

        # Top priorities should be among the highest overall
        for priority in top_priorities:
            assert priority >= sorted(all_priorities, reverse=True)[2]  # At least 3rd highest

    def test_weight_validation(self):
        """Test that weight validation works correctly"""
        assert self.service.validate_weights() == True

        # Test with invalid weights
        self.service.config.w_phat = 0.60  # Total > 1.0
        assert self.service.validate_weights() == False

    def test_search_hidden_outcomes(self):
        """Test searching hidden outcomes"""
        # Create outcome that will be hidden
        risk_data = [{
            'outcome': 'HIDDEN_SEARCHABLE',
            'outcome_label': 'Hidden Searchable Outcome',
            'window': 'periop',
            'baseline_risk': 0.001,
            'adjusted_risk': 0.002,
            'risk_difference': 0.001,
            'evidence_grade': 'D',
            'has_mitigation': False,
            'is_time_critical': False,
            'is_applicable': True,
            'is_calibrated': False,
            'baseline_banner': False
        }]

        outcomes = self.service.compute_risk_priorities(risk_data)
        organized = self.service.organize_for_display(outcomes)

        # Search for hidden outcome
        hidden_found = self.service.get_hidden_outcomes(outcomes, "searchable")
        assert len(hidden_found) > 0
        assert any(o.outcome == 'HIDDEN_SEARCHABLE' for o in hidden_found)

    def test_config_update(self):
        """Test runtime configuration updates"""
        original_threshold = self.service.config.min_show_phat

        # Update threshold
        updates = {'min_show_phat': 0.02}
        success = self.service.update_config(updates)

        assert success == True
        assert self.service.config.min_show_phat == 0.02
        assert self.service.config.min_show_phat != original_threshold

if __name__ == "__main__":
    pytest.main([__file__, "-v"])