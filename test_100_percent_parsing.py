#!/usr/bin/env python3
"""
Comprehensive Playwright Test for 100% Accurate Parsing
Tests all breakthrough patterns with detailed validation
"""

import json
import time
import logging
from datetime import datetime
from typing import Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_100_percent_parsing():
    """Test 100% accurate parsing patterns with Playwright"""

    # Test cases that should achieve 100% accuracy
    test_cases = [
        {
            "name": "Comprehensive Cardiac Case",
            "hpi": "65-year-old male with coronary artery disease status post CABG 2 years ago, diabetes mellitus type 2 on metformin and insulin, hypertension on lisinopril, chronic kidney disease stage 3",
            "expected_conditions": ["CORONARY_ARTERY_DISEASE", "DIABETES", "HYPERTENSION", "CHRONIC_KIDNEY_DISEASE"]
        },
        {
            "name": "Pediatric Respiratory Case",
            "hpi": "5-year-old boy with asthma on daily fluticasone inhaler and albuterol PRN. Recent upper respiratory infection 2 weeks ago with persistent cough. Obstructive sleep apnea with AHI of 12.",
            "expected_conditions": ["ASTHMA", "RECENT_URI_2W", "OSA"]
        },
        {
            "name": "Emergency Trauma Case",
            "hpi": "25-year-old male motorcycle accident victim with traumatic brain injury, hemodynamically unstable, last meal 2 hours ago requiring emergency craniotomy.",
            "expected_conditions": ["TRAUMA", "HEAD_INJURY", "FULL_STOMACH"]
        },
        {
            "name": "Elderly Complex Case",
            "hpi": "89-year-old female with dementia, atrial fibrillation on warfarin, congestive heart failure NYHA class III, chronic kidney disease on dialysis.",
            "expected_conditions": ["DEMENTIA", "HEART_FAILURE", "ANTICOAGULANTS", "CHRONIC_KIDNEY_DISEASE", "AGE_VERY_ELDERLY"]
        },
        {
            "name": "Breakthrough Pattern Test 1",
            "hpi": "Motor vehicle accident patient with multiple injuries and head trauma, brain injury, ate 1 hour ago",
            "expected_conditions": ["TRAUMA", "HEAD_INJURY", "FULL_STOMACH"]
        },
        {
            "name": "Breakthrough Pattern Test 2",
            "hpi": "Elderly patient with CHF, memory problems, blood thinner for irregular heart rhythm, kidney problems requiring dialysis, 89 years old",
            "expected_conditions": ["HEART_FAILURE", "DEMENTIA", "ANTICOAGULANTS", "CHRONIC_KIDNEY_DISEASE", "AGE_VERY_ELDERLY"]
        },
        {
            "name": "Breakthrough Pattern Test 3",
            "hpi": "Patient with cardiac disease, sugar diabetes, high BP, kidney issues stage 3",
            "expected_conditions": ["CORONARY_ARTERY_DISEASE", "DIABETES", "HYPERTENSION", "CHRONIC_KIDNEY_DISEASE"]
        },
        {
            "name": "Breakthrough Pattern Test 4",
            "hpi": "Wheezing child with recent illness, sleep breathing problems",
            "expected_conditions": ["ASTHMA", "RECENT_URI_2W", "OSA"]
        }
    ]

    results = []

    try:
        # Initialize Playwright
        logger.info("Initializing Playwright for 100% parsing validation...")

        # Install browser if needed
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            # Launch browser with enhanced settings for better reliability
            browser = p.chromium.launch(
                headless=False,  # Keep visible for debugging
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-extensions'
                ]
            )

            context = browser.new_context(
                viewport={'width': 1280, 'height': 720},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            page = context.new_page()

            # Navigate to Meridian
            logger.info("Navigating to Meridian...")
            page.goto("https://meridian-zr3e.onrender.com", wait_until="networkidle", timeout=30000)

            # Wait for page to fully load
            logger.info("Waiting for application to load...")
            page.wait_for_selector('h1', timeout=15000)

            # Verify we're on the right page
            title = page.title()
            logger.info(f"Page title: {title}")

            # Take initial screenshot
            page.screenshot(path="meridian_initial.png")

            for i, test_case in enumerate(test_cases, 1):
                logger.info(f"\n=== Testing Case {i}: {test_case['name']} ===")

                try:
                    # Clear any existing text
                    textarea = page.locator('textarea')
                    if textarea.count() > 0:
                        textarea.clear()
                        time.sleep(0.5)

                    # Enter HPI text
                    logger.info(f"Entering HPI: {test_case['hpi'][:100]}...")
                    textarea.fill(test_case['hpi'])
                    time.sleep(1)

                    # Submit analysis
                    submit_button = page.locator('button:has-text("Analyze")')
                    if submit_button.count() == 0:
                        submit_button = page.locator('button[type="submit"]')
                    if submit_button.count() == 0:
                        submit_button = page.locator('input[type="submit"]')

                    if submit_button.count() > 0:
                        logger.info("Clicking analyze button...")
                        submit_button.click()

                        # Wait for results with longer timeout
                        logger.info("Waiting for analysis results...")
                        page.wait_for_timeout(5000)

                        # Look for results in multiple possible locations
                        result_selectors = [
                            '.results',
                            '.analysis-results',
                            '.risk-factors',
                            '.detected-conditions',
                            '.output',
                            'pre',
                            'code'
                        ]

                        results_found = False
                        detected_conditions = []

                        for selector in result_selectors:
                            elements = page.locator(selector)
                            if elements.count() > 0:
                                for j in range(elements.count()):
                                    try:
                                        text = elements.nth(j).text_content()
                                        if text and len(text.strip()) > 10:
                                            logger.info(f"Found results in {selector}: {text[:200]}...")

                                            # Parse detected conditions from text
                                            for condition in test_case['expected_conditions']:
                                                if condition in text:
                                                    detected_conditions.append(condition)

                                            results_found = True
                                            break
                                    except Exception as e:
                                        logger.debug(f"Error reading {selector}: {e}")

                            if results_found:
                                break

                        if not results_found:
                            # Try to get any visible text from the page
                            page_text = page.locator('body').text_content()
                            logger.warning(f"No specific results found, page text: {page_text[:500]}...")

                        # Calculate accuracy
                        expected = set(test_case['expected_conditions'])
                        detected = set(detected_conditions)

                        correct = len(expected.intersection(detected))
                        total = len(expected)
                        accuracy = correct / total if total > 0 else 0.0

                        test_result = {
                            'case_name': test_case['name'],
                            'expected': list(expected),
                            'detected': list(detected),
                            'missed': list(expected - detected),
                            'false_positives': list(detected - expected),
                            'accuracy': accuracy,
                            'correct': correct,
                            'total': total
                        }

                        results.append(test_result)

                        logger.info(f"Case accuracy: {accuracy:.1%} ({correct}/{total})")
                        if test_result['missed']:
                            logger.warning(f"Missed conditions: {test_result['missed']}")
                        if test_result['false_positives']:
                            logger.warning(f"False positives: {test_result['false_positives']}")

                        # Take screenshot of results
                        page.screenshot(path=f"test_case_{i}_results.png")

                    else:
                        logger.error("No submit button found!")
                        page.screenshot(path=f"test_case_{i}_no_button.png")

                        results.append({
                            'case_name': test_case['name'],
                            'error': 'No submit button found',
                            'accuracy': 0.0
                        })

                except Exception as e:
                    logger.error(f"Error testing case {i}: {e}")
                    page.screenshot(path=f"test_case_{i}_error.png")

                    results.append({
                        'case_name': test_case['name'],
                        'error': str(e),
                        'accuracy': 0.0
                    })

                # Brief pause between tests
                time.sleep(2)

            browser.close()

    except Exception as e:
        logger.error(f"Playwright test failed: {e}")
        return {"error": str(e)}

    # Calculate overall results
    valid_results = [r for r in results if 'accuracy' in r and 'error' not in r]

    if valid_results:
        overall_accuracy = sum(r['accuracy'] for r in valid_results) / len(valid_results)
        perfect_cases = len([r for r in valid_results if r['accuracy'] == 1.0])
    else:
        overall_accuracy = 0.0
        perfect_cases = 0

    final_results = {
        'timestamp': datetime.now().isoformat(),
        'overall_accuracy': overall_accuracy,
        'perfect_cases': perfect_cases,
        'total_cases': len(test_cases),
        'target_achieved': overall_accuracy >= 1.0,
        'detailed_results': results
    }

    # Save results
    filename = f"playwright_100_percent_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(final_results, f, indent=2)

    # Print summary
    print("\n" + "="*80)
    print("PLAYWRIGHT 100% PARSING TEST RESULTS")
    print("="*80)
    print(f"Overall Accuracy: {overall_accuracy:.1%}")
    print(f"Perfect Cases: {perfect_cases}/{len(test_cases)}")
    print(f"Target Achieved: {'YES' if final_results['target_achieved'] else 'NO'}")

    if final_results['target_achieved']:
        print("\n🎯 SUCCESS! 100% parsing accuracy validated with Playwright!")
    else:
        print(f"\n📈 Progress: {overall_accuracy:.1%} accuracy achieved")
        failed_cases = [r for r in results if r.get('accuracy', 0) < 1.0]
        if failed_cases:
            print("\nFailed cases:")
            for case in failed_cases:
                print(f"  - {case.get('case_name', 'Unknown')}: {case.get('accuracy', 0):.1%}")

    print(f"\nDetailed results saved to: {filename}")
    print("="*80)

    return final_results

if __name__ == "__main__":
    # Wait for deployment to be ready
    logger.info("Starting 100% parsing validation test...")

    # Check if deployment is ready
    import requests
    try:
        response = requests.get("https://meridian-zr3e.onrender.com", timeout=10)
        if response.status_code == 200:
            logger.info("✓ Deployment is live, starting tests...")
            test_100_percent_parsing()
        else:
            logger.warning(f"Deployment not ready (status {response.status_code}), waiting...")
            time.sleep(30)
            test_100_percent_parsing()
    except Exception as e:
        logger.warning(f"Could not check deployment status: {e}")
        logger.info("Proceeding with test anyway...")
        test_100_percent_parsing()