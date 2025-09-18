#!/usr/bin/env python3
"""
Quick test of the new risk scoring engine
Tests that we get realistic risk scores for pediatric cases
"""

import sys
import os
from pathlib import Path

# Add project root to path
sys.path.append(str(Path(__file__).parent))

# Test the new risk engine components
try:
    from risk_engine.schema import AgeBand, SurgeryType, Urgency, TimeWindow, RiskConfig
    from risk_engine.baseline import BaselineRiskEngine
    from risk_engine.convert import RiskConverter
    from risk_engine.confidence import ConfidenceScorer
    print("[OK] All risk engine modules imported successfully")
except ImportError as e:
    print(f"[ERROR] Import error: {e}")
    sys.exit(1)

def test_baseline_risks():
    """Test that baseline risks are realistic"""
    print("\n[TEST] Testing Baseline Risk Engine")

    config = RiskConfig()
    baseline_engine = BaselineRiskEngine(config)

    # Test case 1: Healthy 3-year-old for myringotomy (should be very low risk)
    baseline = baseline_engine.get_baseline_risk(
        outcome="LARYNGOSPASM",
        window=TimeWindow.INTRAOP,
        age_band=AgeBand.ONE_TO_3,
        surgery=SurgeryType.ENT,
        urgency=Urgency.ELECTIVE
    )

    if baseline:
        print(f"   3yo ENT Laryngospasm: {baseline.p0:.1%} (should be <1%)")
        if baseline.p0 < 0.01:
            print("   ✅ Realistic baseline risk")
        else:
            print("   ⚠️  Higher than expected")

    # Test case 2: 7-year-old dental (should be even lower)
    baseline = baseline_engine.get_baseline_risk(
        outcome="LARYNGOSPASM",
        window=TimeWindow.INTRAOP,
        age_band=AgeBand.SEVEN_TO_12,
        surgery=SurgeryType.DENTAL,
        urgency=Urgency.ELECTIVE
    )

    if baseline:
        print(f"   7yo Dental Laryngospasm: {baseline.p0:.1%} (should be <0.5%)")
        if baseline.p0 < 0.005:
            print("   ✅ Realistic dental baseline risk")
        else:
            print("   ⚠️  Higher than expected for dental")

    # Test case 3: Mortality for healthy pediatric (should be extremely low)
    baseline = baseline_engine.get_baseline_risk(
        outcome="MORTALITY_24H",
        window=TimeWindow.PERIOP,
        age_band=AgeBand.SEVEN_TO_12,
        surgery=SurgeryType.DENTAL,
        urgency=Urgency.ELECTIVE
    )

    if baseline:
        print(f"   7yo Dental 24h Mortality: {baseline.p0:.4%} (should be <0.01%)")
        if baseline.p0 < 0.0001:
            print("   ✅ Realistic mortality baseline")
        else:
            print("   ⚠️  Mortality baseline too high")

def test_risk_conversion():
    """Test risk conversion calculations"""
    print("\n🧪 Testing Risk Converter")

    converter = RiskConverter(mc_draws=1000, seed=42)

    # Test OR to probability conversion
    baseline_prob = 0.005  # 0.5% baseline
    or_value = 2.0  # OR = 2.0

    adjusted_prob = converter.log_or_to_prob(0.693, baseline_prob)  # log(2.0) ≈ 0.693

    print(f"   Baseline: {baseline_prob:.1%}, OR=2.0 → Adjusted: {adjusted_prob:.1%}")

    expected_range = (0.008, 0.012)  # Should roughly double the risk
    if expected_range[0] <= adjusted_prob <= expected_range[1]:
        print("   ✅ Realistic OR conversion")
    else:
        print(f"   ⚠️  Conversion outside expected range {expected_range}")

    # Test validation
    is_valid = converter.validate_conversion(or_value, baseline_prob)
    print(f"   Conversion validation: {'✅ PASS' if is_valid else '❌ FAIL'}")

def test_confidence_scoring():
    """Test confidence scoring system"""
    print("\n🧪 Testing Confidence Scorer")

    config = RiskConfig()
    scorer = ConfidenceScorer(config)

    # Create a mock pooled effect with good evidence
    from risk_engine.schema import PooledEffect, Study, StudyDesign, RiskOfBias

    # High-quality studies
    good_studies = [
        Study(
            pmid="test1", title="Test Study 1", first_author="Smith et al", pub_year=2023,
            design=StudyDesign.RCT, risk_of_bias=RiskOfBias.LOW,
            age_pop="pediatric", surgery_domain=SurgeryType.ENT, urgency=Urgency.ELECTIVE,
            outcome="LARYNGOSPASM", window=TimeWindow.INTRAOP, factor="ASTHMA",
            measure="OR", value=2.0, ci_lower=1.5, ci_upper=2.7,
            n_total=500, is_adjusted=True
        ),
        Study(
            pmid="test2", title="Test Study 2", first_author="Jones et al", pub_year=2022,
            design=StudyDesign.PROSPECTIVE, risk_of_bias=RiskOfBias.LOW,
            age_pop="pediatric", surgery_domain=SurgeryType.ENT, urgency=Urgency.ELECTIVE,
            outcome="LARYNGOSPASM", window=TimeWindow.INTRAOP, factor="ASTHMA",
            measure="OR", value=1.8, ci_lower=1.3, ci_upper=2.5,
            n_total=300, is_adjusted=True
        )
    ]

    good_effect = PooledEffect(
        factor="ASTHMA", outcome="LARYNGOSPASM", window=TimeWindow.INTRAOP,
        log_effect_raw=0.693, se_raw=0.15,
        k_studies=5, tau_squared=0.05, i_squared=20.0,
        q_statistic=3.2, p_heterogeneity=0.3,
        egger_p=0.7, trim_fill_added=0, loo_max_delta_pp=1.1,
        total_weight=25.0, studies=good_studies
    )

    confidence = scorer.calculate_confidence(good_effect)

    print(f"   Confidence Score: {confidence.total_score:.1f}/100 (Grade {confidence.letter_grade.value})")
    print(f"   Studies: {confidence.k_studies_score:.2f}, Design: {confidence.design_mix_score:.2f}")
    print(f"   Bias: {confidence.bias_score:.2f}, Freshness: {confidence.temporal_freshness_score:.2f}")

    if confidence.letter_grade.value in ['A', 'B']:
        print("   ✅ Good confidence grade")
    else:
        print("   ⚠️  Lower confidence than expected")

def test_realistic_scenario():
    """Test complete realistic scenario"""
    print("\n🧪 Testing Complete Realistic Scenario")
    print("   Scenario: 7-year-old with asthma for dental work")

    config = RiskConfig()
    baseline_engine = BaselineRiskEngine(config)
    converter = RiskConverter(mc_draws=1000, seed=42)

    # Get baseline for dental laryngospasm
    baseline = baseline_engine.get_baseline_risk(
        outcome="LARYNGOSPASM",
        window=TimeWindow.INTRAOP,
        age_band=AgeBand.SEVEN_TO_12,
        surgery=SurgeryType.DENTAL,
        urgency=Urgency.ELECTIVE
    )

    if not baseline:
        print("   ❌ No baseline data available")
        return

    print(f"   Baseline laryngospasm risk: {baseline.p0:.3%}")

    # Apply asthma effect (OR ≈ 2.0)
    asthma_log_or = 0.693  # log(2.0)
    adjusted_risk = converter.log_or_to_prob(asthma_log_or, baseline.p0)

    print(f"   With asthma (OR=2.0): {adjusted_risk:.3%}")

    # Check if results are realistic
    if baseline.p0 < 0.005 and adjusted_risk < 0.02:
        print("   ✅ Realistic risk levels for healthy child with asthma")
        print(f"   ✅ Much better than previous 28% failed intubation!")
    else:
        print("   ⚠️  Risks still seem high")

    # Test mortality
    mortality_baseline = baseline_engine.get_baseline_risk(
        outcome="MORTALITY_24H",
        window=TimeWindow.PERIOP,
        age_band=AgeBand.SEVEN_TO_12,
        surgery=SurgeryType.DENTAL,
        urgency=Urgency.ELECTIVE
    )

    if mortality_baseline:
        print(f"   24h mortality baseline: {mortality_baseline.p0:.4%}")
        if mortality_baseline.p0 < 0.001:
            print("   ✅ Realistic mortality risk (<0.1%)")
        else:
            print("   ⚠️  Mortality risk seems high")

def main():
    """Run all tests"""
    print("🔬 Testing New Risk Scoring Engine")
    print("=" * 50)

    try:
        test_baseline_risks()
        test_risk_conversion()
        test_confidence_scoring()
        test_realistic_scenario()

        print("\n" + "=" * 50)
        print("✅ All tests completed!")
        print("📊 The new system should give much more realistic risk scores")
        print("🩺 No more 28% failed intubation for healthy 3-year-olds!")

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()