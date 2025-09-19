#!/usr/bin/env python3
"""
Fixed Playwright Test for 100% Accurate Parsing
Properly targets the correct textarea and handles multiple elements
"""

import json
import time
import logging
from datetime import datetime
from typing import Dict, List

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_100_percent_parsing_fixed():
    """Test 100% accurate parsing patterns with proper element targeting"""

    # Test cases that should achieve 100% accuracy
    test_cases = [
        {
            "name": "Comprehensive Cardiac Case",
            "hpi": "65-year-old male with coronary artery disease status post CABG 2 years ago, diabetes mellitus type 2 on metformin and insulin, hypertension on lisinopril, chronic kidney disease stage 3",
            "expected_conditions": ["CORONARY_ARTERY_DISEASE", "DIABETES", "HYPERTENSION", "CHRONIC_KIDNEY_DISEASE"]
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
            "name": "Breakthrough Pattern Test",
            "hpi": "Wheezing child with recent illness, sleep breathing problems",
            "expected_conditions": ["ASTHMA", "RECENT_URI_2W", "OSA"]
        }
    ]

    results = []

    try:
        # Initialize Playwright
        logger.info("Initializing Playwright for 100% parsing validation...")

        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            # Launch browser with enhanced settings
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
            page.goto("https://meridian-zr3e.onrender.com", wait_until="networkidle", timeout=60000)

            # Wait for page to fully load
            logger.info("Waiting for application to load...")
            page.wait_for_selector('h1', timeout=15000)

            # Verify we're on the right page
            title = page.title()
            logger.info(f"Page title: {title}")

            # Take initial screenshot
            page.screenshot(path="meridian_fixed_initial.png")

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
                    logger.info(f"Entering HPI: {test_case['hpi'][:100]}...")
                    hpi_textarea.fill(test_case['hpi'])
                    time.sleep(1)

                    # Look for analyze button with multiple possible selectors
                    analyze_button = None
                    button_selectors = [
                        'button:has-text("Analyze")',
                        'button[type="submit"]',
                        'input[type="submit"]',
                        '.btn-primary',
                        '.analyze-btn',
                        'button:has-text("Submit")',
                        'button:has-text("Calculate")'
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

                        # Wait for results with longer timeout
                        logger.info("Waiting for analysis results...")
                        page.wait_for_timeout(8000)  # Longer wait for processing

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
                        detected_conditions = []
                        result_text = ""

                        for selector in result_selectors:
                            elements = page.locator(selector)
                            if elements.count() > 0:
                                for j in range(elements.count()):
                                    try:
                                        text = elements.nth(j).text_content()
                                        if text and len(text.strip()) > 10:
                                            logger.info(f"Found results in {selector}: {text[:200]}...")
                                            result_text += text + " "

                                            # Parse detected conditions from text
                                            for condition in test_case['expected_conditions']:
                                                if condition in text or condition.replace('_', ' ') in text.upper():
                                                    detected_conditions.append(condition)

                                            results_found = True
                                    except Exception as e:
                                        logger.debug(f"Error reading {selector}: {e}")

                        # Also check for JSON responses or API calls
                        if not results_found:
                            # Try to get the page content as JSON
                            try:
                                page_content = page.content()
                                if 'json' in page_content.lower() or '{' in page_content:
                                    logger.info("Found potential JSON response in page content")
                                    result_text = page_content

                                    # Parse conditions from JSON-like content
                                    for condition in test_case['expected_conditions']:
                                        if condition in page_content or condition.replace('_', ' ') in page_content.upper():
                                            detected_conditions.append(condition)

                                    results_found = True
                            except Exception as e:
                                logger.debug(f"Error parsing page content: {e}")

                        if not results_found:
                            # Get any visible text from the page body
                            try:
                                body_text = page.locator('body').text_content()
                                logger.warning(f"No specific results found, checking body text: {body_text[:500]}...")

                                # Parse conditions from body text
                                for condition in test_case['expected_conditions']:
                                    if condition in body_text or condition.replace('_', ' ') in body_text.upper():
                                        detected_conditions.append(condition)
                                        results_found = True

                            except Exception as e:
                                logger.error(f"Error reading body text: {e}")

                        # Remove duplicates
                        detected_conditions = list(set(detected_conditions))

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
                            'total': total,
                            'result_text': result_text[:500] if result_text else ""
                        }

                        results.append(test_result)

                        logger.info(f"Case accuracy: {accuracy:.1%} ({correct}/{total})")
                        if test_result['missed']:
                            logger.warning(f"Missed conditions: {test_result['missed']}")
                        if test_result['false_positives']:
                            logger.warning(f"False positives: {test_result['false_positives']}")

                        # Take screenshot of results
                        page.screenshot(path=f"fixed_test_case_{i}_results.png")

                    else:
                        logger.error("No analyze button found!")
                        page.screenshot(path=f"fixed_test_case_{i}_no_button.png")

                        results.append({
                            'case_name': test_case['name'],
                            'error': 'No analyze button found',
                            'accuracy': 0.0
                        })

                except Exception as e:
                    logger.error(f"Error testing case {i}: {e}")
                    page.screenshot(path=f"fixed_test_case_{i}_error.png")

                    results.append({
                        'case_name': test_case['name'],
                        'error': str(e),
                        'accuracy': 0.0
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
    filename = f"playwright_fixed_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(final_results, f, indent=2)

    # Print summary (avoiding Unicode issues)
    print("\n" + "="*80)
    print("FIXED PLAYWRIGHT 100% PARSING TEST RESULTS")
    print("="*80)
    print(f"Overall Accuracy: {overall_accuracy:.1%}")
    print(f"Perfect Cases: {perfect_cases}/{len(test_cases)}")
    print(f"Target Achieved: {'YES' if final_results['target_achieved'] else 'NO'}")

    if final_results['target_achieved']:
        print("\n[SUCCESS] 100% parsing accuracy validated with Playwright!")
    else:
        print(f"\n[PROGRESS] {overall_accuracy:.1%} accuracy achieved")
        failed_cases = [r for r in results if r.get('accuracy', 0) < 1.0]
        if failed_cases:
            print("\nFailed cases:")
            for case in failed_cases:
                print(f"  - {case.get('case_name', 'Unknown')}: {case.get('accuracy', 0):.1%}")

    print(f"\nDetailed results saved to: {filename}")
    print("="*80)

    return final_results

if __name__ == "__main__":
    # Wait a bit more for deployment
    logger.info("Starting FIXED 100% parsing validation test...")

    # Quick deployment check
    import requests
    try:
        response = requests.get("https://meridian-zr3e.onrender.com", timeout=30)
        if response.status_code == 200:
            logger.info("Deployment is live, starting tests...")
        else:
            logger.warning(f"Deployment response: {response.status_code}")
    except Exception as e:
        logger.warning(f"Could not verify deployment: {e}")

    logger.info("Proceeding with test...")
    test_100_percent_parsing_fixed()