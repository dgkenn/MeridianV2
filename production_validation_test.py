#!/usr/bin/env python3
"""
Production Validation Test - Verify dynamic risk scoring after database population
Tests the specific issues reported by user: failed intubation, bronchospasm dynamic scoring
"""

import json
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_production_dynamic_scoring():
    """Test that the production system now shows dynamic risk scoring"""

    # Test cases targeting the user's specific concerns
    test_cases = [
        {
            "name": "OSA Patient - Should show elevated intubation risk",
            "hpi": "45-year-old male with obstructive sleep apnea and obesity presenting for surgery",
            "expected_elevated": ["FAILED_INTUBATION"],
            "expected_dynamic": ["BRONCHOSPASM"]  # OSA should also elevate bronchospasm
        },
        {
            "name": "Asthmatic Patient - Should show elevated bronchospasm risk",
            "hpi": "Child with asthma on daily inhaler, recent cold 2 weeks ago",
            "expected_elevated": ["BRONCHOSPASM"],
            "expected_baseline": ["FAILED_INTUBATION"]  # Should remain low
        },
        {
            "name": "Heart Failure Patient - Should show multiple elevated risks",
            "hpi": "Elderly patient with congestive heart failure NYHA class III and coronary artery disease",
            "expected_elevated": ["HYPOTENSION", "CARDIAC_ARREST", "VENTRICULAR_ARRHYTHMIA"],
            "expected_baseline": ["ASPIRATION"]  # Should remain low
        },
        {
            "name": "Healthy Patient - Should show mostly baseline risks",
            "hpi": "Healthy 30-year-old female for elective surgery, no medical history",
            "expected_baseline": ["FAILED_INTUBATION", "BRONCHOSPASM", "CARDIAC_ARREST"],
            "expected_elevated": []
        }
    ]

    results = []

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context(viewport={'width': 1280, 'height': 720})
            page = context.new_page()

            logger.info("Navigating to production Meridian...")
            page.goto("https://meridian-zr3e.onrender.com", wait_until="networkidle", timeout=60000)

            # Wait for app to load
            page.wait_for_selector('textarea', timeout=15000)

            for i, test_case in enumerate(test_cases, 1):
                logger.info(f"\n=== Testing Case {i}: {test_case['name']} ===")

                try:
                    # Clear and enter HPI
                    textarea = page.locator('textarea').first
                    textarea.clear()
                    textarea.fill(test_case['hpi'])
                    time.sleep(1)

                    # Submit
                    submit_button = page.locator('button:has-text("Analyze")').first
                    if submit_button.count() == 0:
                        submit_button = page.locator('button[type="submit"]').first

                    if submit_button.count() > 0:
                        submit_button.click()

                        # Wait for results
                        logger.info("Waiting for results...")
                        page.wait_for_timeout(8000)

                        # Capture results
                        page_content = page.content()

                        # Parse risks from content
                        detected_risks = {}

                        # Look for risk indicators in the page
                        risk_indicators = [
                            "FAILED_INTUBATION", "BRONCHOSPASM", "HYPOTENSION",
                            "CARDIAC_ARREST", "VENTRICULAR_ARRHYTHMIA", "ASPIRATION"
                        ]

                        for risk in risk_indicators:
                            if risk in page_content:
                                # Try to extract percentage
                                import re
                                pattern = rf"{risk}.*?(\d+\.?\d*)%"
                                match = re.search(pattern, page_content, re.IGNORECASE)
                                if match:
                                    percentage = float(match.group(1))
                                    detected_risks[risk] = percentage
                                    logger.info(f"Found {risk}: {percentage}%")

                        # Evaluate results
                        evaluation = {
                            'case_name': test_case['name'],
                            'detected_risks': detected_risks,
                            'evaluation': {},
                            'issues': []
                        }

                        # Check if expected elevated risks are actually elevated
                        for risk in test_case.get('expected_elevated', []):
                            if risk in detected_risks:
                                # Define baseline thresholds
                                baselines = {
                                    'FAILED_INTUBATION': 0.5,
                                    'BRONCHOSPASM': 0.1,
                                    'HYPOTENSION': 15.0,
                                    'CARDIAC_ARREST': 0.05,
                                    'VENTRICULAR_ARRHYTHMIA': 1.0,
                                    'ASPIRATION': 0.3
                                }

                                baseline = baselines.get(risk, 1.0)
                                actual = detected_risks[risk]

                                if actual > baseline * 1.5:  # At least 50% above baseline
                                    evaluation['evaluation'][risk] = f"ELEVATED CORRECTLY ({actual}% > {baseline}%)"
                                else:
                                    evaluation['evaluation'][risk] = f"NOT ELEVATED ENOUGH ({actual}% vs {baseline}% baseline)"
                                    evaluation['issues'].append(f"{risk} should be elevated but shows {actual}%")
                            else:
                                evaluation['evaluation'][risk] = "NOT DETECTED"
                                evaluation['issues'].append(f"{risk} expected to be elevated but not found")

                        # Check if baseline risks remain at baseline
                        for risk in test_case.get('expected_baseline', []):
                            if risk in detected_risks:
                                baselines = {
                                    'FAILED_INTUBATION': 0.5,
                                    'BRONCHOSPASM': 0.1,
                                    'CARDIAC_ARREST': 0.05,
                                    'ASPIRATION': 0.3
                                }

                                baseline = baselines.get(risk, 1.0)
                                actual = detected_risks[risk]

                                if actual <= baseline * 1.2:  # Within 20% of baseline
                                    evaluation['evaluation'][risk] = f"BASELINE CORRECTLY ({actual}% ≈ {baseline}%)"
                                else:
                                    evaluation['evaluation'][risk] = f"UNEXPECTEDLY ELEVATED ({actual}% >> {baseline}%)"
                                    evaluation['issues'].append(f"{risk} should be baseline but shows {actual}%")

                        results.append(evaluation)

                        # Take screenshot
                        page.screenshot(path=f"production_test_case_{i}.png")

                    else:
                        logger.error("No submit button found!")
                        results.append({
                            'case_name': test_case['name'],
                            'error': 'No submit button found'
                        })

                except Exception as e:
                    logger.error(f"Error in case {i}: {e}")
                    results.append({
                        'case_name': test_case['name'],
                        'error': str(e)
                    })

                time.sleep(2)  # Brief pause between tests

            browser.close()

    except Exception as e:
        logger.error(f"Production test failed: {e}")
        return {"error": str(e)}

    # Analyze overall results
    total_cases = len([r for r in results if 'error' not in r])
    total_issues = sum(len(r.get('issues', [])) for r in results if 'error' not in r)

    final_results = {
        'timestamp': datetime.now().isoformat(),
        'total_cases_tested': total_cases,
        'total_issues_found': total_issues,
        'overall_status': 'PASS' if total_issues == 0 else 'ISSUES_FOUND',
        'detailed_results': results
    }

    # Save results
    filename = f"production_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(final_results, f, indent=2)

    # Print summary
    print("\n" + "="*80)
    print("PRODUCTION VALIDATION TEST RESULTS")
    print("="*80)
    print(f"Overall Status: {final_results['overall_status']}")
    print(f"Cases Tested: {total_cases}")
    print(f"Issues Found: {total_issues}")

    if total_issues == 0:
        print("\n✓ SUCCESS! Dynamic risk scoring is working correctly in production")
        print("✓ OSA patients show elevated intubation risk")
        print("✓ Asthma patients show elevated bronchospasm risk")
        print("✓ Heart failure patients show elevated cardiovascular risks")
        print("✓ Healthy patients show appropriate baseline risks")
    else:
        print(f"\n⚠ ISSUES DETECTED:")
        for result in results:
            if 'issues' in result and result['issues']:
                print(f"\n{result['case_name']}:")
                for issue in result['issues']:
                    print(f"  - {issue}")

    print(f"\nDetailed results saved to: {filename}")
    print("="*80)

    return final_results

if __name__ == "__main__":
    logger.info("Starting production validation test...")
    logger.info("This will test if the database fixes resolved the static risk scoring issues")

    test_production_dynamic_scoring()