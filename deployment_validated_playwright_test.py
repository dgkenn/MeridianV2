#!/usr/bin/env python3
"""
Deployment-Validated Playwright Test
Includes deployment counter validation to ensure changes are actually live
"""

import json
import time
import logging
import requests
from datetime import datetime
from typing import Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_expected_deployment_version():
    """Get the expected deployment version from local file"""
    try:
        with open('deployment_version.txt', 'r') as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        logger.warning("Could not read deployment_version.txt, assuming version 1")
        return 1

def validate_deployment_version(expected_version):
    """Validate that the deployment version matches what we expect"""
    try:
        logger.info(f"Validating deployment version (expecting {expected_version})...")
        response = requests.get("https://meridian-zr3e.onrender.com/health", timeout=30)

        if response.status_code == 200:
            health_data = response.json()
            actual_version = health_data.get('deployment_version', 0)
            version_string = health_data.get('version', 'unknown')

            logger.info(f"Health check response:")
            logger.info(f"  Status: {health_data.get('status', 'unknown')}")
            logger.info(f"  Version: {version_string}")
            logger.info(f"  Deployment Version: {actual_version}")

            if actual_version == expected_version:
                logger.info(f"✅ Deployment version validated: {actual_version}")
                return True
            else:
                logger.error(f"❌ Deployment version mismatch! Expected {expected_version}, got {actual_version}")
                logger.error(f"   This means the latest code changes are NOT live yet")
                return False
        else:
            logger.error(f"Health check failed with status: {response.status_code}")
            return False

    except Exception as e:
        logger.error(f"Error validating deployment version: {e}")
        return False

def test_with_deployment_validation():
    """Test 100% accurate parsing with deployment version validation"""

    # First, validate deployment version
    expected_version = get_expected_deployment_version()
    logger.info(f"Expected deployment version: {expected_version}")

    if not validate_deployment_version(expected_version):
        logger.error("DEPLOYMENT VERSION VALIDATION FAILED!")
        logger.error("The test will continue but results may be unreliable")
        logger.error("Wait for deployment to complete or check deployment logs")

        return {
            'deployment_validation_failed': True,
            'expected_version': expected_version,
            'message': 'Deployment version mismatch - latest changes may not be live',
            'timestamp': datetime.now().isoformat()
        }

    logger.info("✅ Deployment version validated - proceeding with tests")

    # Test cases that should achieve 100% accuracy
    test_cases = [
        {
            "name": "OSA Adult Population Test",
            "hpi": "45-year-old male with obstructive sleep apnea on CPAP therapy",
            "expected_conditions": ["OSA"],
            "expected_population": "adult"
        },
        {
            "name": "Complex Adult Cardiac Case",
            "hpi": "65-year-old male with coronary artery disease status post CABG 2 years ago, diabetes mellitus type 2 on metformin",
            "expected_conditions": ["CORONARY_ARTERY_DISEASE", "DIABETES"],
            "expected_population": "adult"
        },
        {
            "name": "Elderly Complex Case",
            "hpi": "89-year-old female with dementia, atrial fibrillation on warfarin, congestive heart failure",
            "expected_conditions": ["DEMENTIA", "HEART_FAILURE", "ANTICOAGULANTS", "AGE_VERY_ELDERLY"],
            "expected_population": "adult"
        }
    ]

    results = []
    deployment_validation_passed = True

    try:
        # Initialize Playwright
        logger.info("Initializing Playwright for deployment-validated testing...")

        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(
                headless=False,
                args=['--no-sandbox', '--disable-dev-shm-usage']
            )

            context = browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            page = context.new_page()

            # Navigate to Meridian
            logger.info("Navigating to Meridian...")
            page.goto("https://meridian-zr3e.onrender.com", wait_until="networkidle", timeout=60000)

            # Wait for page to fully load
            logger.info("Waiting for application to load...")
            page.wait_for_selector('h1', timeout=15000)

            # Take initial screenshot
            page.screenshot(path="deployment_validated_initial.png")

            for i, test_case in enumerate(test_cases, 1):
                logger.info(f"\n=== Testing Case {i}: {test_case['name']} ===")

                try:
                    # Target the specific HPI textarea by ID
                    hpi_textarea = page.locator('#hpiText')

                    # Wait for the HPI textarea to be available
                    hpi_textarea.wait_for(state="visible", timeout=10000)

                    # Clear any existing text
                    hpi_textarea.clear()
                    time.sleep(0.5)

                    # Enter HPI text
                    logger.info(f"Entering HPI: {test_case['hpi']}")
                    hpi_textarea.fill(test_case['hpi'])
                    time.sleep(1)

                    # Look for analyze button
                    analyze_button = None
                    button_selectors = [
                        'button:has-text("Analyze")',
                        'button[type="submit"]',
                        'input[type="submit"]',
                        '.btn-primary',
                        '.analyze-btn'
                    ]

                    for selector in button_selectors:
                        button = page.locator(selector)
                        if button.count() > 0:
                            analyze_button = button.first
                            logger.info(f"Found analyze button with selector: {selector}")
                            break

                    if analyze_button:
                        logger.info("Clicking analyze button...")
                        analyze_button.click()

                        # Wait for results
                        logger.info("Waiting for analysis results...")
                        page.wait_for_timeout(8000)

                        # Intercept API calls to get the actual response
                        api_response = None

                        # Try to capture API response from network logs if available
                        # For now, look for results in the page
                        result_text = ""
                        detected_conditions = []
                        detected_population = "unknown"

                        # Look for results in multiple possible locations
                        result_selectors = [
                            '.results',
                            '.analysis-results',
                            '.risk-factors',
                            '.detected-conditions',
                            '.output',
                            '.result-section',
                            '#results',
                            '#output',
                            'pre',
                            'code',
                            '.card-body',
                            '.response'
                        ]

                        results_found = False

                        for selector in result_selectors:
                            elements = page.locator(selector)
                            if elements.count() > 0:
                                for j in range(elements.count()):
                                    try:
                                        text = elements.nth(j).text_content()
                                        if text and len(text.strip()) > 10:
                                            logger.info(f"Found results in {selector}: {text[:200]}...")
                                            result_text += text + " "

                                            # Check for population in response
                                            if 'population' in text.lower():
                                                if 'adult' in text.lower():
                                                    detected_population = "adult"
                                                elif 'mixed' in text.lower():
                                                    detected_population = "mixed"
                                                elif 'pediatric' in text.lower():
                                                    detected_population = "pediatric"

                                            # Parse detected conditions from text
                                            for condition in test_case['expected_conditions']:
                                                if condition in text or condition.replace('_', ' ') in text.upper():
                                                    detected_conditions.append(condition)

                                            results_found = True
                                    except Exception as e:
                                        logger.debug(f"Error reading {selector}: {e}")

                        # Also check page content for JSON responses
                        if not results_found:
                            try:
                                page_content = page.content()
                                if 'json' in page_content.lower() or '{' in page_content:
                                    logger.info("Found potential JSON response in page content")
                                    result_text = page_content

                                    # Parse population from JSON-like content
                                    if '"population"' in page_content:
                                        if '"adult"' in page_content:
                                            detected_population = "adult"
                                        elif '"mixed"' in page_content:
                                            detected_population = "mixed"

                                    # Parse conditions from JSON-like content
                                    for condition in test_case['expected_conditions']:
                                        if condition in page_content or condition.replace('_', ' ') in page_content.upper():
                                            detected_conditions.append(condition)

                                    results_found = True
                            except Exception as e:
                                logger.debug(f"Error parsing page content: {e}")

                        # Remove duplicates
                        detected_conditions = list(set(detected_conditions))

                        # Calculate accuracy
                        expected = set(test_case['expected_conditions'])
                        detected = set(detected_conditions)

                        correct = len(expected.intersection(detected))
                        total = len(expected)
                        accuracy = correct / total if total > 0 else 0.0

                        # Check population accuracy
                        population_correct = detected_population == test_case.get('expected_population', 'unknown')

                        test_result = {
                            'case_name': test_case['name'],
                            'expected_conditions': list(expected),
                            'detected_conditions': list(detected),
                            'expected_population': test_case.get('expected_population', 'unknown'),
                            'detected_population': detected_population,
                            'missed_conditions': list(expected - detected),
                            'false_positives': list(detected - expected),
                            'accuracy': accuracy,
                            'population_correct': population_correct,
                            'correct': correct,
                            'total': total,
                            'result_text': result_text[:500] if result_text else ""
                        }

                        results.append(test_result)

                        logger.info(f"Case accuracy: {accuracy:.1%} ({correct}/{total})")
                        logger.info(f"Population: expected '{test_case.get('expected_population')}', got '{detected_population}' {'✅' if population_correct else '❌'}")

                        if test_result['missed_conditions']:
                            logger.warning(f"Missed conditions: {test_result['missed_conditions']}")
                        if test_result['false_positives']:
                            logger.warning(f"False positives: {test_result['false_positives']}")

                        # Take screenshot of results
                        page.screenshot(path=f"deployment_validated_case_{i}_results.png")

                    else:
                        logger.error("No analyze button found!")
                        page.screenshot(path=f"deployment_validated_case_{i}_no_button.png")

                        results.append({
                            'case_name': test_case['name'],
                            'error': 'No analyze button found',
                            'accuracy': 0.0,
                            'population_correct': False
                        })

                except Exception as e:
                    logger.error(f"Error testing case {i}: {e}")
                    page.screenshot(path=f"deployment_validated_case_{i}_error.png")

                    results.append({
                        'case_name': test_case['name'],
                        'error': str(e),
                        'accuracy': 0.0,
                        'population_correct': False
                    })

                # Brief pause between tests
                time.sleep(3)

            browser.close()

    except Exception as e:
        logger.error(f"Playwright test failed: {e}")
        return {"error": str(e)}

    # Calculate overall results
    valid_results = [r for r in results if 'accuracy' in r and 'error' not in r]

    if valid_results:
        overall_accuracy = sum(r['accuracy'] for r in valid_results) / len(valid_results)
        perfect_cases = len([r for r in valid_results if r['accuracy'] == 1.0])
        population_correct_count = len([r for r in valid_results if r.get('population_correct', False)])
    else:
        overall_accuracy = 0.0
        perfect_cases = 0
        population_correct_count = 0

    final_results = {
        'timestamp': datetime.now().isoformat(),
        'deployment_version_validated': deployment_validation_passed,
        'expected_deployment_version': expected_version,
        'overall_accuracy': overall_accuracy,
        'perfect_cases': perfect_cases,
        'population_correct_cases': population_correct_count,
        'total_cases': len(test_cases),
        'target_achieved': overall_accuracy >= 1.0 and population_correct_count == len(test_cases),
        'detailed_results': results
    }

    # Save results
    filename = f"deployment_validated_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(final_results, f, indent=2)

    # Print summary
    print("\n" + "="*80)
    print("DEPLOYMENT-VALIDATED PLAYWRIGHT TEST RESULTS")
    print("="*80)
    print(f"Deployment Version: {expected_version} {'✅ VALIDATED' if deployment_validation_passed else '❌ FAILED'}")
    print(f"Overall Accuracy: {overall_accuracy:.1%}")
    print(f"Perfect Cases: {perfect_cases}/{len(test_cases)}")
    print(f"Population Correct: {population_correct_count}/{len(test_cases)}")
    print(f"Target Achieved: {'YES' if final_results['target_achieved'] else 'NO'}")

    if final_results['target_achieved']:
        print("\n[SUCCESS] 100% parsing accuracy and population classification validated!")
    else:
        print(f"\n[PROGRESS] {overall_accuracy:.1%} accuracy achieved")
        failed_cases = [r for r in results if r.get('accuracy', 0) < 1.0 or not r.get('population_correct', False)]
        if failed_cases:
            print("\nFailed cases:")
            for case in failed_cases:
                print(f"  - {case.get('case_name', 'Unknown')}: {case.get('accuracy', 0):.1%} accuracy, population {'✅' if case.get('population_correct', False) else '❌'}")

    print(f"\nDetailed results saved to: {filename}")
    print("="*80)

    return final_results

if __name__ == "__main__":
    logger.info("Starting DEPLOYMENT-VALIDATED Playwright test...")

    # Run the enhanced test with deployment validation
    test_with_deployment_validation()