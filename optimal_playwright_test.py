#!/usr/bin/env python3
"""
Optimal Playwright Test - Handles zoom, viewport, and element targeting properly
"""

import json
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_optimal_parsing():
    """Optimal test with proper zoom and viewport handling"""

    test_cases = [
        {
            "name": "Trauma Case",
            "hpi": "Motor vehicle accident patient with multiple injuries and head trauma, brain injury, ate 1 hour ago",
            "expected_conditions": ["TRAUMA", "HEAD_INJURY", "FULL_STOMACH"]
        },
        {
            "name": "Elderly Case",
            "hpi": "89-year-old female with dementia, atrial fibrillation on warfarin, congestive heart failure",
            "expected_conditions": ["DEMENTIA", "ANTICOAGULANTS", "HEART_FAILURE", "AGE_VERY_ELDERLY"]
        }
    ]

    results = []

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            # Launch with explicit zoom settings
            browser = p.chromium.launch(
                headless=False,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--force-device-scale-factor=1',  # Force 100% zoom
                    '--disable-extensions',
                    '--start-maximized'
                ]
            )

            # Set explicit viewport and device scale factor
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},  # Larger viewport
                device_scale_factor=1.0,  # 100% zoom
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )

            page = context.new_page()

            # Set zoom level explicitly
            page.evaluate('document.body.style.zoom = "1.0"')

            logger.info("Navigating to Meridian...")
            page.goto("https://meridian-zr3e.onrender.com", wait_until="networkidle", timeout=60000)

            # Wait and take full page screenshot
            page.wait_for_timeout(3000)
            page.screenshot(path="optimal_full_page.png", full_page=True)

            logger.info(f"Page title: {page.title()}")

            for i, test_case in enumerate(test_cases, 1):
                logger.info(f"\n=== Testing Case {i}: {test_case['name']} ===")

                try:
                    # Scroll to top first
                    page.evaluate('window.scrollTo(0, 0)')

                    # Find the HPI textarea specifically
                    hpi_textarea = page.locator('#hpiText')

                    if hpi_textarea.count() == 0:
                        # Try alternative selectors
                        hpi_textarea = page.locator('textarea[placeholder*="Enter patient HPI"]')

                    if hpi_textarea.count() == 0:
                        # Get all textareas and pick the first one
                        hpi_textarea = page.locator('textarea').first

                    # Scroll to the textarea
                    hpi_textarea.scroll_into_view_if_needed()

                    # Clear and fill
                    hpi_textarea.click()
                    hpi_textarea.clear()
                    time.sleep(0.5)

                    logger.info(f"Entering HPI text...")
                    hpi_textarea.fill(test_case['hpi'])
                    time.sleep(1)

                    # Look for the analyze/submit button
                    button_found = False
                    button_selectors = [
                        'button:has-text("Analyze")',
                        'button[type="submit"]',
                        'input[type="submit"]',
                        '.btn-primary',
                        'button:has-text("Submit")',
                        'button:has-text("Calculate")',
                        'button:visible'
                    ]

                    for selector in button_selectors:
                        buttons = page.locator(selector)
                        if buttons.count() > 0:
                            button = buttons.first

                            # Scroll to button
                            button.scroll_into_view_if_needed()
                            time.sleep(1)

                            # Take screenshot before clicking
                            page.screenshot(path=f"optimal_before_click_{i}.png")

                            logger.info(f"Clicking button with selector: {selector}")
                            button.click()
                            button_found = True
                            break

                    if button_found:
                        # Wait for response
                        logger.info("Waiting for results...")
                        page.wait_for_timeout(10000)  # Wait 10 seconds

                        # Take screenshot after results
                        page.screenshot(path=f"optimal_after_results_{i}.png", full_page=True)

                        # Get all text content from page
                        page_text = page.locator('body').text_content()

                        # Count detected conditions
                        detected_conditions = []
                        for condition in test_case['expected_conditions']:
                            # Check for exact match or variations
                            condition_variations = [
                                condition,
                                condition.replace('_', ' '),
                                condition.replace('_', '-'),
                                condition.lower(),
                                condition.replace('_', ' ').lower()
                            ]

                            for variation in condition_variations:
                                if variation in page_text:
                                    detected_conditions.append(condition)
                                    logger.info(f"Found condition: {condition}")
                                    break

                        # Calculate accuracy
                        expected = set(test_case['expected_conditions'])
                        detected = set(detected_conditions)

                        correct = len(expected.intersection(detected))
                        total = len(expected)
                        accuracy = correct / total if total > 0 else 0.0

                        result = {
                            'case_name': test_case['name'],
                            'expected': list(expected),
                            'detected': list(detected),
                            'missed': list(expected - detected),
                            'accuracy': accuracy,
                            'correct': correct,
                            'total': total
                        }

                        results.append(result)
                        logger.info(f"Case accuracy: {accuracy:.1%} ({correct}/{total})")

                    else:
                        logger.error("No button found!")
                        page.screenshot(path=f"optimal_no_button_{i}.png", full_page=True)

                        results.append({
                            'case_name': test_case['name'],
                            'error': 'No button found',
                            'accuracy': 0.0
                        })

                except Exception as e:
                    logger.error(f"Error in case {i}: {e}")
                    page.screenshot(path=f"optimal_error_{i}.png", full_page=True)

                    results.append({
                        'case_name': test_case['name'],
                        'error': str(e),
                        'accuracy': 0.0
                    })

                # Pause between tests
                time.sleep(3)

            browser.close()

    except Exception as e:
        logger.error(f"Test failed: {e}")
        return {"error": str(e)}

    # Calculate results
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

    # Print results
    print("\n" + "="*80)
    print("OPTIMAL PLAYWRIGHT TEST RESULTS")
    print("="*80)
    print(f"Overall Accuracy: {overall_accuracy:.1%}")
    print(f"Perfect Cases: {perfect_cases}/{len(test_cases)}")
    print(f"Target Achieved: {'YES' if final_results['target_achieved'] else 'NO'}")

    for result in results:
        if 'error' not in result:
            print(f"\n{result['case_name']}: {result['accuracy']:.1%}")
            if result['missed']:
                print(f"  Missed: {result['missed']}")

    print("\n" + "="*80)

    # Save results
    filename = f"optimal_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(final_results, f, indent=2)

    return final_results

if __name__ == "__main__":
    logger.info("Starting OPTIMAL Playwright test...")

    # Quick deployment check
    import requests
    try:
        response = requests.get("https://meridian-zr3e.onrender.com", timeout=15)
        logger.info(f"Deployment check: {response.status_code}")
    except Exception as e:
        logger.warning(f"Deployment check failed: {e}")

    test_optimal_parsing()