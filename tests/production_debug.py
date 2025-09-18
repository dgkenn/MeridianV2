#!/usr/bin/env python3
"""
Fine-grained Production Debugging with Playwright
Debug the actual production website behavior step by step
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

# Configure UTF-8 encoding for Windows console
if sys.platform == "win32":
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

BASE_URL = "https://meridian-zr3e.onrender.com"
TIMEOUT_MS = 30000

class ProductionDebugger:
    def __init__(self):
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.screenshot_dir = Path("tests/screenshots")
        self.screenshot_dir.mkdir(exist_ok=True, parents=True)
        self.screenshot_count = 0

    async def take_screenshot(self, page, name):
        """Take a screenshot for debugging"""
        self.screenshot_count += 1
        filepath = self.screenshot_dir / f"{self.session_id}_{self.screenshot_count:02d}_{name}.png"
        await page.screenshot(path=str(filepath))
        print(f"Screenshot: {filepath}")
        return filepath

    async def debug_api_directly(self):
        """Test the API endpoints directly"""
        print("\n" + "="*60)
        print("STEP 1: DIRECT API TESTING")
        print("="*60)

        test_hpi = "58-year-old male presenting for urgent laparoscopic cholecystectomy secondary to acute cholecystitis"

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            # Test /api/analyze endpoint
            response = await page.evaluate("""
                async (data) => {
                    const response = await fetch('/api/analyze', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(data)
                    });
                    return {
                        status: response.status,
                        data: await response.json()
                    };
                }
            """, {"hpi_text": test_hpi})

            print(f"API Response Status: {response['status']}")
            print(f"API Response Data: {json.dumps(response['data'], indent=2)}")

            await browser.close()

    async def debug_frontend_interaction(self):
        """Debug the actual frontend user interaction"""
        print("\n" + "="*60)
        print("STEP 2: FRONTEND INTERACTION DEBUGGING")
        print("="*60)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False, slow_mo=2000)  # Visible debugging
            context = await browser.new_context()
            page = await context.new_page()

            # Enable detailed logging
            page.on("console", lambda msg: print(f"CONSOLE [{msg.type}]: {msg.text}"))
            page.on("response", lambda response: print(f"RESPONSE: {response.status} {response.url}"))

            # Navigate to the site
            print(f"Navigating to {BASE_URL}")
            await page.goto(BASE_URL)
            await self.take_screenshot(page, "homepage_loaded")

            # Check page title
            title = await page.title()
            print(f"Page title: {title}")

            # Find the HPI textarea
            hpi_textarea = page.locator('#hpiText')
            await hpi_textarea.wait_for(state="visible", timeout=TIMEOUT_MS)
            print("HPI textarea found")

            # Clear and enter test HPI
            test_hpi = "58-year-old male presenting for urgent laparoscopic cholecystectomy secondary to acute cholecystitis"
            await hpi_textarea.fill(test_hpi)
            await self.take_screenshot(page, "hpi_entered")
            print(f"Entered HPI: {test_hpi}")

            # Find and click the Analyze button
            analyze_button = page.locator("button:has-text('Analyze HPI')")
            await analyze_button.wait_for(state="visible", timeout=TIMEOUT_MS)
            print("Analyze button found")

            # Set up response monitoring before clicking
            async with page.expect_response("**/api/analyze") as response_info:
                await analyze_button.click()
                print("Analyze button clicked")

            response = await response_info.value
            response_data = await response.json()
            print(f"API Response: {json.dumps(response_data, indent=2)}")

            await self.take_screenshot(page, "analysis_complete")

            # Check what's displayed on the page
            await page.wait_for_timeout(3000)  # Wait for UI updates

            # Look for extracted factors
            factors_section = page.locator("#extractedFactors")
            if await factors_section.count() > 0:
                factors_text = await factors_section.text_content()
                print(f"Extracted factors displayed: {factors_text}")
            else:
                print("No extracted factors section found")

            # Look for error messages
            error_elements = page.locator(".alert-danger, .error, [class*='error']")
            error_count = await error_elements.count()
            if error_count > 0:
                for i in range(error_count):
                    error_text = await error_elements.nth(i).text_content()
                    print(f"Error message {i+1}: {error_text}")
            else:
                print("No error messages found on page")

            # Check console logs
            print("\nWaiting for any additional console logs...")
            await page.wait_for_timeout(2000)

            await self.take_screenshot(page, "final_state")
            print("\nDebugging complete. Check screenshots for visual state.")

            await browser.close()

    async def debug_database_connectivity(self):
        """Debug database connectivity issues"""
        print("\n" + "="*60)
        print("STEP 3: DATABASE CONNECTIVITY DEBUG")
        print("="*60)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(BASE_URL)

            # Test health endpoint
            health_response = await page.evaluate("""
                async () => {
                    const response = await fetch('/api/health');
                    return {
                        status: response.status,
                        data: await response.json()
                    };
                }
            """)

            print(f"Health endpoint: {json.dumps(health_response, indent=2)}")

            # Test example endpoint
            example_response = await page.evaluate("""
                async () => {
                    const response = await fetch('/api/example');
                    return {
                        status: response.status,
                        data: await response.json()
                    };
                }
            """)

            print(f"Example endpoint: {json.dumps(example_response, indent=2)}")

            await browser.close()

    async def run_full_debug(self):
        """Run complete debugging sequence"""
        print("="*60)
        print("PRODUCTION DEBUGGING SUITE")
        print(f"Session ID: {self.session_id}")
        print(f"Target URL: {BASE_URL}")
        print("="*60)

        try:
            await self.debug_api_directly()
            await self.debug_frontend_interaction()
            await self.debug_database_connectivity()

            print("\n" + "="*60)
            print("DEBUGGING COMPLETE")
            print("="*60)
            print(f"Screenshots saved to: {self.screenshot_dir}")

        except Exception as e:
            print(f"ERROR during debugging: {e}")
            import traceback
            traceback.print_exc()

async def main():
    debugger = ProductionDebugger()
    await debugger.run_full_debug()

if __name__ == "__main__":
    asyncio.run(main())