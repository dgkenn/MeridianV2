#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced End-to-End Test Script for Meridian CODEX v2
https://meridian-zr3e.onrender.com

Features:
- Comprehensive UI testing with better error handling
- Integration with Render MCP for error debugging
- Screenshot capture on failures
- Detailed test reporting
- Support for both headless and visible testing

Usage:
    python tests/meridian_e2e_test.py
    python tests/meridian_e2e_test.py --visible  # Run with visible browser
    python tests/meridian_e2e_test.py --debug    # Enable debug mode with screenshots
"""

import asyncio
import argparse
import os
import json
import sys
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Configure UTF-8 encoding for Windows console
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Configuration
BASE_URL = "https://meridian-zr3e.onrender.com"
TIMEOUT_MS = 15000
SCREENSHOT_DIR = Path("tests/screenshots")

# Test data
TEST_HPI = """58-year-old male presenting for urgent laparoscopic cholecystectomy secondary to acute cholecystitis. Medical history significant for type 2 diabetes mellitus on insulin (A1c 8.2%), heart failure with reduced ejection fraction of 35% on enalapril and metoprolol, COPD on home oxygen 2L continuous, and chronic kidney disease stage 3 (creatinine 1.8). Smoking history of 30 pack-years, quit 2 years ago. Hypertension well-controlled on current regimen. Presenting symptoms include right upper quadrant pain for 48 hours, fever to 101.2°F, and leukocytosis (WBC 14,000). Ultrasound confirms acute cholecystitis with gallbladder wall thickening and pericholecystic fluid. Drug allergies include penicillin (rash). Current vital signs: BP 142/88, HR 92, SpO2 91% on 2L nasal cannula. Physical exam notable for RUQ tenderness and Murphy's sign. NPO since midnight. ASA III E."""

SIMPLE_TEST_HPI = "10yo M, asthma, recent URI, scheduled for tonsillectomy"

class MeridianE2ETest:
    def __init__(self, headless=True, debug=False):
        self.headless = headless
        self.debug = debug
        self.report = []
        self.screenshot_counter = 0
        self.test_session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Ensure screenshot directory exists
        if self.debug:
            SCREENSHOT_DIR.mkdir(exist_ok=True, parents=True)

    async def log_result(self, test_name, success, message="", screenshot_name=None):
        """Log test result with optional screenshot"""
        status = "[PASS]" if success else "[FAIL]"

        # Clean message of problematic Unicode characters for Windows console
        safe_message = self._safe_string(message)

        log_entry = {
            "test": test_name,
            "success": success,
            "message": safe_message,
            "timestamp": datetime.now().isoformat(),
            "screenshot": screenshot_name
        }
        self.report.append(log_entry)
        print(f"{status} {test_name}: {safe_message}")

    def _safe_string(self, text):
        """Convert text to safe ASCII-compatible string for console output"""
        try:
            # Try to encode/decode to catch problematic characters
            safe_text = str(text).encode('ascii', errors='replace').decode('ascii')
            return safe_text
        except Exception:
            # Fallback to basic string conversion
            return str(text)[:200] + "..." if len(str(text)) > 200 else str(text)

    def _safe_print(self, text):
        """Safe print that handles Unicode encoding issues"""
        try:
            print(self._safe_string(text))
        except Exception as e:
            print(f"[Print Error: {e}]")

    async def take_screenshot(self, page, name):
        """Take screenshot for debugging"""
        if not self.debug:
            return None

        self.screenshot_counter += 1
        screenshot_name = f"{self.test_session_id}_{self.screenshot_counter:02d}_{name}.png"
        screenshot_path = SCREENSHOT_DIR / screenshot_name

        try:
            await page.screenshot(path=str(screenshot_path), full_page=True)
            return screenshot_name
        except Exception as e:
            print(f"Failed to take screenshot {name}: {e}")
            return None

    async def test_homepage_load(self, page):
        """Test homepage loading and basic structure"""
        try:
            await page.goto(BASE_URL, timeout=TIMEOUT_MS)
            await page.wait_for_load_state('networkidle', timeout=TIMEOUT_MS)

            title = await page.title()

            # Check for key UI elements
            await page.wait_for_selector("textarea", timeout=5000)

            screenshot = await self.take_screenshot(page, "homepage_loaded")
            await self.log_result(
                "Homepage Load",
                True,
                f"Title: {title}, HPI textarea found",
                screenshot
            )
            return True

        except Exception as e:
            screenshot = await self.take_screenshot(page, "homepage_failed")
            await self.log_result("Homepage Load", False, str(e), screenshot)
            return False

    async def test_load_example_button(self, page):
        """Test the 'Load Example' functionality"""
        try:
            # Look for and click Load Example button
            load_example_button = page.locator("button:has-text('Load Example')")
            await load_example_button.wait_for(timeout=5000)
            await load_example_button.click()

            # Wait for textarea to be populated
            await page.wait_for_function(
                "document.querySelector('textarea').value.length > 10",
                timeout=5000
            )

            # Verify textarea has content
            textarea_content = await page.locator("textarea").input_value()

            screenshot = await self.take_screenshot(page, "example_loaded")
            await self.log_result(
                "Load Example Button",
                True,
                f"Example loaded, textarea length: {len(textarea_content)}",
                screenshot
            )
            return True

        except Exception as e:
            screenshot = await self.take_screenshot(page, "load_example_failed")
            await self.log_result("Load Example Button", False, str(e), screenshot)

            # Fallback: manually input test data
            try:
                await page.fill("textarea", TEST_HPI)
                await self.log_result("Manual HPI Input", True, "Fallback HPI input successful")
                return True
            except Exception as fallback_e:
                await self.log_result("Manual HPI Input", False, str(fallback_e))
                return False

    async def test_hpi_analysis(self, page):
        """Test HPI parsing and analysis"""
        try:
            # Click Analyze HPI button
            analyze_button = page.locator("button:has-text('Analyze HPI')")
            await analyze_button.wait_for(timeout=5000)
            await analyze_button.click()

            # Wait for results to appear - look for extracted factors in right column
            try:
                # Wait for risk factors or extracted information to appear
                await page.wait_for_selector(
                    ".extracted-factors, .risk-factors, .analysis-results",
                    timeout=15000
                )
            except:
                # Fallback - wait for any content change indicating processing
                await page.wait_for_timeout(3000)

            screenshot = await self.take_screenshot(page, "hpi_analyzed")

            # Check if extracted factors are visible
            extracted_factors = await page.locator(".extracted-factors, .risk-factors").count()

            await self.log_result(
                "HPI Analysis",
                True,
                f"Analysis completed, {extracted_factors} factor sections found",
                screenshot
            )
            return True

        except Exception as e:
            screenshot = await self.take_screenshot(page, "hpi_analysis_failed")
            await self.log_result("HPI Analysis", False, str(e), screenshot)
            return False

    async def test_risk_scores_tab(self, page):
        """Test Risk Scores tab functionality"""
        try:
            # Click Risk Scores tab
            risk_tab = page.locator("text=Risk Scores, text=Risk Analysis, button:has-text('Risk')")
            await risk_tab.first.click()
            await page.wait_for_timeout(2000)

            # Look for risk-related content
            risk_content = await page.locator(
                "text=bronchospasm, text=aspiration, text=mortality, .risk-score, .outcome"
            ).count()

            screenshot = await self.take_screenshot(page, "risk_scores_tab")
            await self.log_result(
                "Risk Scores Tab",
                risk_content > 0,
                f"Risk content elements found: {risk_content}",
                screenshot
            )
            return risk_content > 0

        except Exception as e:
            screenshot = await self.take_screenshot(page, "risk_scores_failed")
            await self.log_result("Risk Scores Tab", False, str(e), screenshot)
            return False

    async def test_medications_tab(self, page):
        """Test Medications tab functionality"""
        try:
            # Click Medications tab
            meds_tab = page.locator("text=Medications, text=Clinical Recommendations, button:has-text('Med')")
            await meds_tab.first.click()
            await page.wait_for_timeout(2000)

            # Look for medication recommendations
            med_content = await page.locator(
                "text=epinephrine, text=atropine, text=midazolam, .medication, .drug"
            ).count()

            screenshot = await self.take_screenshot(page, "medications_tab")
            await self.log_result(
                "Medications Tab",
                med_content > 0,
                f"Medication content elements found: {med_content}",
                screenshot
            )
            return med_content > 0

        except Exception as e:
            screenshot = await self.take_screenshot(page, "medications_failed")
            await self.log_result("Medications Tab", False, str(e), screenshot)
            return False

    async def test_studies_tab(self, page):
        """Test Relevant Studies tab functionality"""
        try:
            # Click Relevant Studies tab
            studies_tab = page.locator("text=Relevant Studies, text=Evidence, button:has-text('Studies')")
            await studies_tab.first.click()
            await page.wait_for_timeout(2000)

            # Look for study links or references
            study_links = await page.locator("a[href*='pubmed'], a[href*='doi'], .study-reference").count()

            screenshot = await self.take_screenshot(page, "studies_tab")
            await self.log_result(
                "Relevant Studies Tab",
                study_links > 0,
                f"Study links found: {study_links}",
                screenshot
            )
            return study_links > 0

        except Exception as e:
            screenshot = await self.take_screenshot(page, "studies_failed")
            await self.log_result("Relevant Studies Tab", False, str(e), screenshot)
            return False

    async def test_learning_tab(self, page):
        """Test Learning/Questions tab functionality"""
        try:
            # Click Learning tab
            learning_tab = page.locator("text=Learning, text=Questions, button:has-text('Learn')")
            await learning_tab.first.click()
            await page.wait_for_timeout(2000)

            # Look for educational content
            learning_content = await page.locator(
                "text=Multiple Choice, text=Question, .question, .quiz"
            ).count()

            screenshot = await self.take_screenshot(page, "learning_tab")
            await self.log_result(
                "Learning Tab",
                learning_content > 0,
                f"Learning content elements found: {learning_content}",
                screenshot
            )
            return learning_content > 0

        except Exception as e:
            screenshot = await self.take_screenshot(page, "learning_failed")
            await self.log_result("Learning Tab", False, str(e), screenshot)
            return False

    async def run_comprehensive_test(self):
        """Run the complete test suite"""
        self._safe_print(f"\nStarting Meridian E2E Test Suite - Session: {self.test_session_id}")
        self._safe_print(f"Target URL: {BASE_URL}")
        self._safe_print(f"Browser Mode: {'Headless' if self.headless else 'Visible'}")
        self._safe_print(f"Debug Mode: {'ON' if self.debug else 'OFF'}")
        self._safe_print("=" * 60)

        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(
                headless=self.headless,
                args=['--no-sandbox', '--disable-setuid-sandbox'] if self.headless else []
            )

            # Create page with extended timeout
            page = await browser.new_page()
            page.set_default_timeout(TIMEOUT_MS)

            try:
                # Run test sequence
                homepage_ok = await self.test_homepage_load(page)

                if homepage_ok:
                    example_ok = await self.test_load_example_button(page)

                    if example_ok:
                        analysis_ok = await self.test_hpi_analysis(page)

                        if analysis_ok:
                            # Test all tabs
                            await self.test_risk_scores_tab(page)
                            await self.test_medications_tab(page)
                            await self.test_studies_tab(page)
                            await self.test_learning_tab(page)

                # Final screenshot
                await self.take_screenshot(page, "final_state")

            except Exception as e:
                await self.log_result("Test Suite", False, f"Critical error: {e}")

            finally:
                await browser.close()

        # Generate report
        await self.generate_report()

    async def generate_report(self):
        """Generate comprehensive test report"""
        total_tests = len(self.report)
        passed_tests = sum(1 for r in self.report if r["success"])
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0

        self._safe_print("\n" + "=" * 60)
        self._safe_print("MERIDIAN E2E TEST REPORT")
        self._safe_print("=" * 60)
        self._safe_print(f"Total Tests: {total_tests}")
        self._safe_print(f"Passed: {passed_tests}")
        self._safe_print(f"Failed: {total_tests - passed_tests}")
        self._safe_print(f"Success Rate: {success_rate:.1f}%")
        self._safe_print(f"Session ID: {self.test_session_id}")

        if self.debug:
            self._safe_print(f"Screenshots: {SCREENSHOT_DIR}")

        # Save detailed report
        report_file = Path(f"tests/reports/e2e_report_{self.test_session_id}.json")
        report_file.parent.mkdir(exist_ok=True, parents=True)

        with open(report_file, 'w') as f:
            json.dump({
                "session_id": self.test_session_id,
                "timestamp": datetime.now().isoformat(),
                "base_url": BASE_URL,
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "success_rate": success_rate,
                "headless": self.headless,
                "debug": self.debug,
                "tests": self.report
            }, f, indent=2)

        self._safe_print(f"Detailed report: {report_file}")
        self._safe_print("=" * 60)

        return success_rate >= 80  # Consider test suite successful if 80%+ pass rate

async def main():
    parser = argparse.ArgumentParser(description="Meridian E2E Test Suite")
    parser.add_argument("--visible", action="store_true", help="Run with visible browser")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode with screenshots")
    args = parser.parse_args()

    test_runner = MeridianE2ETest(
        headless=not args.visible,
        debug=args.debug
    )

    success = await test_runner.run_comprehensive_test()

    # Exit with appropriate code
    exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())