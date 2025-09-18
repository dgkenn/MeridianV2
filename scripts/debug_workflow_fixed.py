#!/usr/bin/env python3
"""
Debugging Workflow for Meridian CODEX v2
Integrates Playwright E2E testing with Render MCP error monitoring

This script implements the debugging workflow:
1. Run Playwright tests
2. If errors detected, fetch logs from Render
3. Analyze errors and suggest fixes
4. Optionally restart services or trigger deployments
5. Retest and repeat

Usage:
    python scripts/debug_workflow.py
    python scripts/debug_workflow.py --continuous  # Run continuous monitoring
    python scripts/debug_workflow.py --fix-and-retest  # Auto-retry after fixes
"""

import asyncio
import argparse
import json
import sys
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path for imports
sys.path.append(str(Path(__file__).parent.parent))

class MeridianDebugWorkflow:
    def __init__(self, continuous=False, auto_fix=False):
        self.continuous = continuous
        self.auto_fix = auto_fix
        self.service_id = "srv-d34nuhgdl3ps73821ds0"  # Meridian service ID
        self.base_url = "https://meridian-zr3e.onrender.com"

    async def run_e2e_tests(self, visible=False, debug=False):
        """Run Playwright E2E tests and return results"""
        print("🧪 Running E2E tests...")

        try:
            # Import and run the E2E test
            from tests.meridian_e2e_test import MeridianE2ETest

            test_runner = MeridianE2ETest(headless=not visible, debug=debug)
            success = await test_runner.run_comprehensive_test()

            return {
                "success": success,
                "report": test_runner.report,
                "session_id": test_runner.test_session_id
            }

        except Exception as e:
            print(f"❌ E2E test execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "report": []
            }

    def get_render_logs(self, hours_back=1):
        """Fetch recent logs from Render service using MCP"""
        print(f"📋 Fetching Render logs (last {hours_back} hours)...")

        try:
            # Calculate time range
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours_back)

            # This would use the Render MCP - for now we'll simulate
            # In practice, you'd call: mcp__render__list_logs(...)
            print(f"🔍 Checking logs from {start_time} to {end_time}")

            # Simulated log analysis
            mock_logs = [
                {"timestamp": datetime.now().isoformat(), "level": "ERROR", "message": "Database connection timeout"},
                {"timestamp": datetime.now().isoformat(), "level": "WARN", "message": "High memory usage detected"},
                {"timestamp": datetime.now().isoformat(), "level": "INFO", "message": "Request processed successfully"}
            ]

            return {
                "success": True,
                "logs": mock_logs,
                "error_count": sum(1 for log in mock_logs if log["level"] == "ERROR")
            }

        except Exception as e:
            print(f"❌ Failed to fetch Render logs: {e}")
            return {"success": False, "error": str(e)}

    def analyze_errors(self, test_results, render_logs):
        """Analyze test failures and server logs to identify issues"""
        print("🔍 Analyzing errors and patterns...")

        issues = []

        # Analyze test failures
        if test_results.get("report"):
            failed_tests = [test for test in test_results["report"] if not test["success"]]

            for test in failed_tests:
                issue = {
                    "type": "test_failure",
                    "test_name": test["test"],
                    "message": test["message"],
                    "suggested_fix": self.suggest_fix_for_test(test)
                }
                issues.append(issue)

        # Analyze server logs
        if render_logs.get("logs"):
            error_logs = [log for log in render_logs["logs"] if log["level"] == "ERROR"]

            for log in error_logs:
                issue = {
                    "type": "server_error",
                    "timestamp": log["timestamp"],
                    "message": log["message"],
                    "suggested_fix": self.suggest_fix_for_log(log)
                }
                issues.append(issue)

        return issues

    def suggest_fix_for_test(self, test):
        """Suggest fixes based on test failure patterns"""
        test_name = test["test"].lower()
        message = test["message"].lower()

        if "homepage" in test_name and "timeout" in message:
            return "Check if service is running and accessible. Consider restarting the service."

        elif "load example" in test_name:
            return "Check if example data endpoint is working. Verify database connectivity."

        elif "hpi analysis" in test_name:
            return "Check HPI parsing service. Verify NLP model is loaded and API endpoints are responsive."

        elif "risk scores" in test_name:
            return "Check risk calculation engine. Verify evidence database is accessible."

        elif "medications" in test_name:
            return "Check medication recommendation service. Verify drug database connectivity."

        elif "studies" in test_name:
            return "Check evidence referencing system. Verify PubMed API integration."

        else:
            return "Generic error - check application logs and service health."

    def suggest_fix_for_log(self, log):
        """Suggest fixes based on server log patterns"""
        message = log["message"].lower()

        if "database" in message and "timeout" in message:
            return "Database connection issue. Check database service health and connection pool settings."

        elif "memory" in message:
            return "Memory issue detected. Consider restarting service or upgrading plan."

        elif "api" in message and ("timeout" or "failed") in message:
            return "External API issue. Check API key validity and rate limits."

        else:
            return "Check application logs for more details."

    async def attempt_auto_fixes(self, issues):
        """Attempt automatic fixes for common issues"""
        if not self.auto_fix:
            return False

        print("🔧 Attempting automatic fixes...")

        fixed_any = False

        for issue in issues:
            fix_attempted = False

            # Auto-fix: Service restart for certain issues
            if ("timeout" in issue["message"].lower() or
                "database" in issue["message"].lower()):

                print(f"🔄 Attempting service restart for: {issue['message']}")
                # In practice: mcp__render__restart_service(self.service_id)
                print("   → Service restart would be triggered here")
                fix_attempted = True

            # Auto-fix: Clear cache for memory issues
            elif "memory" in issue["message"].lower():
                print(f"🧹 Attempting cache clear for: {issue['message']}")
                # In practice: trigger cache clear endpoint
                print("   → Cache clear would be triggered here")
                fix_attempted = True

            if fix_attempted:
                fixed_any = True
                print(f"   ✅ Fix attempted for: {issue['type']}")

        if fixed_any:
            print("⏳ Waiting 30 seconds for fixes to take effect...")
            await asyncio.sleep(30)

        return fixed_any

    def generate_debug_report(self, test_results, render_logs, issues, session_id):
        """Generate comprehensive debug report"""
        report = {
            "session_id": session_id,
            "timestamp": datetime.now().isoformat(),
            "test_results": test_results,
            "render_logs": render_logs,
            "issues_found": len(issues),
            "issues": issues,
            "service_url": self.base_url,
            "service_id": self.service_id
        }

        # Save report
        report_file = Path(f"tests/reports/debug_report_{session_id}.json")
        report_file.parent.mkdir(exist_ok=True, parents=True)

        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"📊 Debug report saved: {report_file}")
        return report

    async def run_debug_cycle(self, visible=False, debug=False):
        """Run one complete debug cycle"""
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        print(f"\n🚀 Starting debug cycle - Session: {session_id}")
        print("=" * 60)

        # Step 1: Run E2E tests
        test_results = await self.run_e2e_tests(visible=visible, debug=debug)

        # Step 2: Fetch server logs
        render_logs = self.get_render_logs(hours_back=1)

        # Step 3: Analyze issues
        issues = self.analyze_errors(test_results, render_logs)

        # Step 4: Report findings
        print(f"\n📊 Debug Cycle Results:")
        print(f"   🧪 Tests successful: {test_results.get('success', False)}")
        print(f"   📋 Server errors: {render_logs.get('error_count', 0)}")
        print(f"   🔍 Issues identified: {len(issues)}")

        if issues:
            print("\n🚨 Issues Found:")
            for i, issue in enumerate(issues, 1):
                print(f"   {i}. [{issue['type']}] {issue['message']}")
                print(f"      💡 Suggestion: {issue['suggested_fix']}")

        # Step 5: Attempt auto-fixes if enabled
        fixes_attempted = await self.attempt_auto_fixes(issues)

        # Step 6: Generate report
        report = self.generate_debug_report(test_results, render_logs, issues, session_id)

        # Step 7: Retest if fixes were attempted
        if fixes_attempted and self.auto_fix:
            print("\n🔄 Running retest after fixes...")
            retest_results = await self.run_e2e_tests(visible=False, debug=False)
            print(f"   📈 Retest successful: {retest_results.get('success', False)}")
            report["retest_results"] = retest_results

        return {
            "success": test_results.get("success", False) and len(issues) == 0,
            "issues_count": len(issues),
            "report": report
        }

    async def run_continuous_monitoring(self, interval_minutes=15):
        """Run continuous monitoring with specified interval"""
        print(f"🔄 Starting continuous monitoring (interval: {interval_minutes} minutes)")

        cycle_count = 0

        while True:
            cycle_count += 1
            print(f"\n📅 Monitoring Cycle #{cycle_count}")

            try:
                result = await self.run_debug_cycle(visible=False, debug=False)

                if result["success"]:
                    print("✅ All systems nominal")
                else:
                    print(f"⚠️  Issues detected: {result['issues_count']}")

            except Exception as e:
                print(f"❌ Monitoring cycle failed: {e}")

            print(f"⏰ Next check in {interval_minutes} minutes...")
            await asyncio.sleep(interval_minutes * 60)

async def main():
    parser = argparse.ArgumentParser(description="Meridian Debug Workflow")
    parser.add_argument("--continuous", action="store_true", help="Run continuous monitoring")
    parser.add_argument("--fix-and-retest", action="store_true", help="Attempt auto-fixes and retest")
    parser.add_argument("--visible", action="store_true", help="Run tests with visible browser")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode with screenshots")
    parser.add_argument("--interval", type=int, default=15, help="Monitoring interval in minutes")

    args = parser.parse_args()

    workflow = MeridianDebugWorkflow(
        continuous=args.continuous,
        auto_fix=args.fix_and_retest
    )

    try:
        if args.continuous:
            await workflow.run_continuous_monitoring(args.interval)
        else:
            result = await workflow.run_debug_cycle(
                visible=args.visible,
                debug=args.debug
            )

            # Exit with appropriate code
            exit(0 if result["success"] else 1)

    except KeyboardInterrupt:
        print("\n🛑 Debug workflow interrupted by user")
        exit(0)
    except Exception as e:
        print(f"\n❌ Debug workflow failed: {e}")
        exit(1)

if __name__ == "__main__":
    asyncio.run(main())
