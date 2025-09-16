#!/usr/bin/env python3
"""
Meridian Comprehensive Test Suite
=================================

Automated testing script for all Meridian website functionality.
Run this script after making changes to verify everything works.

Usage:
    python test_meridian.py

Features tested:
- API endpoints (health, example, analyze)
- HPI parsing accuracy
- Risk calculation correctness
- Medication recommendations
- Evidence citations
- Database connectivity
- Response times
- Error handling

Add new tests when functionality is added.
"""

import requests
import json
import time
import sys
from datetime import datetime
from typing import Dict, List, Any, Tuple

# Configuration
BASE_URL = "http://localhost:8084"
TIMEOUT = 10
VERBOSE = True

class MeridianTester:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.start_time = time.time()

    def log(self, message: str, level: str = "INFO"):
        """Log messages with timestamp and level"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        colors = {
            "INFO": "\033[94m",    # Blue
            "PASS": "\033[92m",    # Green
            "FAIL": "\033[91m",    # Red
            "WARN": "\033[93m",    # Yellow
            "RESET": "\033[0m"     # Reset
        }
        if VERBOSE:
            print(f"[{timestamp}] {colors.get(level, '')}{level}{colors['RESET']}: {message}")

    def assert_test(self, condition: bool, test_name: str, details: str = ""):
        """Assert test result and track statistics"""
        if condition:
            self.passed += 1
            self.log(f"PASS: {test_name}", "PASS")
            if details and VERBOSE:
                self.log(f"   {details}", "INFO")
        else:
            self.failed += 1
            self.log(f"FAIL: {test_name}", "FAIL")
            if details:
                self.log(f"   {details}", "FAIL")

    def warn(self, message: str):
        """Log warning"""
        self.warnings += 1
        self.log(f"WARN: {message}", "WARN")

    def test_server_connectivity(self) -> bool:
        """Test if server is running and accessible"""
        self.log("Testing server connectivity...")
        try:
            response = requests.get(f"{BASE_URL}/", timeout=5)
            self.assert_test(
                response.status_code == 200,
                "Server connectivity",
                f"Status: {response.status_code}"
            )
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            self.assert_test(False, "Server connectivity", f"Error: {str(e)}")
            return False

    def test_health_endpoint(self) -> Dict[str, Any]:
        """Test /api/health endpoint"""
        self.log("Testing health endpoint...")
        try:
            response = requests.get(f"{BASE_URL}/api/health", timeout=TIMEOUT)
            data = response.json()

            # Test response structure
            self.assert_test(
                response.status_code == 200,
                "Health endpoint status",
                f"Status: {response.status_code}"
            )

            required_fields = ["status", "version", "papers", "timestamp"]
            for field in required_fields:
                self.assert_test(
                    field in data,
                    f"Health endpoint field: {field}",
                    f"Value: {data.get(field)}"
                )

            # Test database connectivity
            self.assert_test(
                data.get("status") == "healthy",
                "Database health",
                f"Status: {data.get('status')}"
            )

            # Test paper count
            papers_count = data.get("papers", 0)
            self.assert_test(
                papers_count >= 0,
                "Database papers count",
                f"Papers: {papers_count}"
            )

            return data

        except Exception as e:
            self.assert_test(False, "Health endpoint", f"Error: {str(e)}")
            return {}

    def test_example_endpoint(self) -> str:
        """Test /api/example endpoint"""
        self.log("Testing example endpoint...")
        try:
            response = requests.get(f"{BASE_URL}/api/example", timeout=TIMEOUT)
            data = response.json()

            self.assert_test(
                response.status_code == 200,
                "Example endpoint status",
                f"Status: {response.status_code}"
            )

            self.assert_test(
                "hpi" in data,
                "Example endpoint has HPI field"
            )

            hpi_text = data.get("hpi", "")
            self.assert_test(
                len(hpi_text) > 50,
                "Example HPI length",
                f"Length: {len(hpi_text)} chars"
            )

            # Test HPI quality
            quality_indicators = ["age", "procedure", "history", "patient"]
            quality_score = sum(1 for indicator in quality_indicators if indicator.lower() in hpi_text.lower())
            self.assert_test(
                quality_score >= 2,
                "Example HPI quality",
                f"Quality indicators found: {quality_score}/4"
            )

            return hpi_text

        except Exception as e:
            self.assert_test(False, "Example endpoint", f"Error: {str(e)}")
            return ""

    def test_analyze_endpoint(self, hpi_text: str = None) -> Dict[str, Any]:
        """Test /api/analyze endpoint with comprehensive validation"""
        self.log("Testing analyze endpoint...")

        if not hpi_text:
            hpi_text = "5-year-old male for tonsillectomy with asthma and recent URI"

        try:
            payload = {"hpi_text": hpi_text}
            response = requests.post(
                f"{BASE_URL}/api/analyze",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=TIMEOUT
            )

            self.assert_test(
                response.status_code == 200,
                "Analyze endpoint status",
                f"Status: {response.status_code}"
            )

            data = response.json()

            # Test top-level structure
            required_sections = ["parsed", "risks", "medications"]
            for section in required_sections:
                self.assert_test(
                    section in data,
                    f"Analyze response has {section} section"
                )

            # Test parsed section
            if "parsed" in data:
                self.test_parsed_section(data["parsed"], hpi_text)

            # Test risks section
            if "risks" in data:
                self.test_risks_section(data["risks"])

            # Test medications section
            if "medications" in data:
                self.test_medications_section(data["medications"])

            return data

        except Exception as e:
            self.assert_test(False, "Analyze endpoint", f"Error: {str(e)}")
            return {}

    def test_parsed_section(self, parsed_data: Dict[str, Any], original_hpi: str):
        """Test HPI parsing results"""
        self.log("Validating HPI parsing...")

        # Test structure
        required_fields = ["extracted_factors", "demographics", "confidence_score"]
        for field in required_fields:
            self.assert_test(
                field in parsed_data,
                f"Parsed section has {field}"
            )

        # Test demographics
        demographics = parsed_data.get("demographics", {})
        if "5-year-old male" in original_hpi.lower():
            self.assert_test(
                demographics.get("sex") == "SEX_MALE",
                "Gender extraction",
                f"Extracted: {demographics.get('sex')}"
            )
            self.assert_test(
                demographics.get("age_years") == 5,
                "Age extraction",
                f"Extracted: {demographics.get('age_years')} years"
            )

        # Test extracted factors
        factors = parsed_data.get("extracted_factors", [])
        self.assert_test(
            len(factors) > 0,
            "Risk factors extraction",
            f"Extracted {len(factors)} factors"
        )

        # Test confidence scores
        for factor in factors:
            self.assert_test(
                0 <= factor.get("confidence", 0) <= 1,
                f"Factor confidence score: {factor.get('token', 'Unknown')}",
                f"Confidence: {factor.get('confidence')}"
            )

        # Test asthma detection if present
        if "asthma" in original_hpi.lower():
            asthma_detected = any(f.get("token") == "ASTHMA" for f in factors)
            self.assert_test(
                asthma_detected,
                "Asthma risk factor detection"
            )

    def test_risks_section(self, risks_data: Dict[str, Any]):
        """Test risk calculation results"""
        self.log("Validating risk calculations...")

        # Test structure
        self.assert_test(
            "risks" in risks_data,
            "Risks section has risks array"
        )

        self.assert_test(
            "summary" in risks_data,
            "Risks section has summary"
        )

        risks = risks_data.get("risks", [])
        for risk in risks:
            # Test risk structure
            required_fields = ["outcome", "baseline_risk", "adjusted_risk", "category"]
            for field in required_fields:
                self.assert_test(
                    field in risk,
                    f"Risk item has {field}",
                    f"Risk: {risk.get('outcome', 'Unknown')}"
                )

            # Test risk values
            baseline = risk.get("baseline_risk", 0)
            adjusted = risk.get("adjusted_risk", 0)

            self.assert_test(
                0 <= baseline <= 1,
                f"Baseline risk range: {risk.get('outcome')}",
                f"Value: {baseline}"
            )

            self.assert_test(
                0 <= adjusted <= 1,
                f"Adjusted risk range: {risk.get('outcome')}",
                f"Value: {adjusted}"
            )

            # Test specific outcomes
            if "specific_outcomes" in risk:
                self.test_specific_outcomes(risk["specific_outcomes"], risk.get("outcome"))

    def test_specific_outcomes(self, outcomes: List[Dict], parent_outcome: str):
        """Test specific outcome details"""
        for outcome in outcomes:
            required_fields = ["name", "risk", "explanation", "management"]
            for field in required_fields:
                self.assert_test(
                    field in outcome,
                    f"Specific outcome {outcome.get('name', 'Unknown')} has {field}"
                )

            # Test citations
            if "citations" in outcome:
                citations = outcome["citations"]
                self.assert_test(
                    len(citations) > 0,
                    f"Specific outcome {outcome.get('name')} has citations",
                    f"Citations: {len(citations)}"
                )

                # Validate citation format
                for citation in citations:
                    valid_citation = (
                        citation.startswith("PMID:") or
                        "Guidelines" in citation or
                        citation.startswith("DOI:")
                    )
                    self.assert_test(
                        valid_citation,
                        f"Citation format: {citation[:20]}..."
                    )

    def test_medications_section(self, medications_data: Dict[str, Any]):
        """Test medication recommendations"""
        self.log("Validating medication recommendations...")

        # Test structure
        expected_categories = ["contraindicated", "draw_now", "consider", "standard"]
        for category in expected_categories:
            self.assert_test(
                category in medications_data,
                f"Medications section has {category} category"
            )

        # Test each medication category
        for category, meds in medications_data.items():
            for med in meds:
                self.test_medication_item(med, category)

    def test_medication_item(self, med: Dict[str, Any], category: str):
        """Test individual medication item"""
        required_fields = ["generic_name", "evidence_grade"]

        # Category-specific required fields
        if category == "contraindicated":
            required_fields.extend(["contraindication_reason", "justification"])
        else:
            required_fields.extend(["indication", "dose"])

        for field in required_fields:
            self.assert_test(
                field in med,
                f"Medication {med.get('generic_name', 'Unknown')} has {field}"
            )

        # Test evidence grade
        grade = med.get("evidence_grade", "")
        self.assert_test(
            grade in ["A", "B", "C", "D"],
            f"Medication evidence grade: {med.get('generic_name')}",
            f"Grade: {grade}"
        )

        # Test citations
        citations = med.get("citations", [])
        self.assert_test(
            len(citations) > 0,
            f"Medication {med.get('generic_name')} has citations",
            f"Citations: {len(citations)}"
        )

    def test_error_handling(self):
        """Test error handling scenarios"""
        self.log("Testing error handling...")

        # Test empty HPI
        try:
            response = requests.post(
                f"{BASE_URL}/api/analyze",
                json={"hpi_text": ""},
                headers={"Content-Type": "application/json"},
                timeout=TIMEOUT
            )
            self.assert_test(
                response.status_code == 400,
                "Empty HPI error handling",
                f"Status: {response.status_code}"
            )
        except Exception as e:
            self.assert_test(False, "Empty HPI error handling", f"Error: {str(e)}")

        # Test missing HPI field
        try:
            response = requests.post(
                f"{BASE_URL}/api/analyze",
                json={},
                headers={"Content-Type": "application/json"},
                timeout=TIMEOUT
            )
            self.assert_test(
                response.status_code == 400,
                "Missing HPI field error handling",
                f"Status: {response.status_code}"
            )
        except Exception as e:
            self.assert_test(False, "Missing HPI field error handling", f"Error: {str(e)}")

    def test_performance(self):
        """Test response times"""
        self.log("Testing performance...")

        # Test analyze endpoint performance
        hpi_text = "25-year-old female for laparoscopic appendectomy with diabetes"

        start_time = time.time()
        try:
            response = requests.post(
                f"{BASE_URL}/api/analyze",
                json={"hpi_text": hpi_text},
                headers={"Content-Type": "application/json"},
                timeout=TIMEOUT
            )
            end_time = time.time()

            response_time = end_time - start_time
            self.assert_test(
                response_time < 5.0,
                "Analyze endpoint response time",
                f"Time: {response_time:.2f}s"
            )

            if response_time > 2.0:
                self.warn(f"Slow response time: {response_time:.2f}s (consider optimization)")

        except Exception as e:
            self.assert_test(False, "Performance test", f"Error: {str(e)}")

    def test_comprehensive_scenarios(self):
        """Test comprehensive clinical scenarios"""
        self.log("Testing comprehensive clinical scenarios...")

        test_cases = [
            {
                "name": "Pediatric asthma case",
                "hpi": "3-year-old boy for tonsillectomy with severe asthma on albuterol, recent pneumonia",
                "expected_factors": ["ASTHMA", "AGE_1_5", "SEX_MALE"],
                "expected_medications": ["albuterol", "contraindicated"]
            },
            {
                "name": "Adult cardiac case",
                "hpi": "65-year-old woman for hip replacement with history of MI, heart failure, on metoprolol",
                "expected_factors": ["HEART_FAILURE", "MYOCARDIAL_INFARCTION", "AGE_65_PLUS"],
                "expected_medications": ["metoprolol", "contraindicated"]
            },
            {
                "name": "Emergency trauma case",
                "hpi": "30-year-old male trauma patient for emergency laparotomy, full stomach, hypotensive",
                "expected_factors": ["EMERGENCY_SURGERY", "HYPOVOLEMIA"],
                "expected_medications": ["draw_now"]
            }
        ]

        for case in test_cases:
            self.log(f"Testing {case['name']}...")
            result = self.test_analyze_endpoint(case["hpi"])

            if result:
                # Check expected factors
                factors = result.get("parsed", {}).get("extracted_factors", [])
                factor_tokens = [f.get("token") for f in factors]

                for expected_factor in case["expected_factors"]:
                    self.assert_test(
                        expected_factor in factor_tokens,
                        f"{case['name']} - {expected_factor} detection",
                        f"Detected factors: {factor_tokens}"
                    )

    def run_all_tests(self):
        """Run complete test suite"""
        self.log("=" * 60)
        self.log("Starting Meridian Comprehensive Test Suite")
        self.log("=" * 60)

        # Check server connectivity first
        if not self.test_server_connectivity():
            self.log("❌ Server not accessible. Ensure app is running on localhost:8081", "FAIL")
            return False

        # Core API tests
        health_data = self.test_health_endpoint()
        example_hpi = self.test_example_endpoint()

        # Analyze endpoint tests
        analyze_data = self.test_analyze_endpoint()
        if example_hpi:
            self.test_analyze_endpoint(example_hpi)  # Test with example HPI

        # Error handling tests
        self.test_error_handling()

        # Performance tests
        self.test_performance()

        # Comprehensive scenario tests
        self.test_comprehensive_scenarios()

        # Print results
        self.print_results()

        return self.failed == 0

    def print_results(self):
        """Print test results summary"""
        total_time = time.time() - self.start_time
        total_tests = self.passed + self.failed

        self.log("=" * 60)
        self.log("TEST RESULTS SUMMARY")
        self.log("=" * 60)
        self.log(f"Total Tests: {total_tests}")
        self.log(f"Passed: {self.passed}", "PASS")
        self.log(f"Failed: {self.failed}", "FAIL" if self.failed > 0 else "INFO")
        self.log(f"Warnings: {self.warnings}", "WARN" if self.warnings > 0 else "INFO")
        self.log(f"Success Rate: {(self.passed/total_tests*100):.1f}%" if total_tests > 0 else "0%")
        self.log(f"Total Time: {total_time:.2f}s")
        self.log("=" * 60)

        if self.failed == 0:
            self.log("ALL TESTS PASSED! Meridian is working correctly.", "PASS")
        else:
            self.log("SOME TESTS FAILED! Please review and fix issues.", "FAIL")

        if self.warnings > 0:
            self.log(f"{self.warnings} warnings detected. Consider reviewing.", "WARN")

def main():
    """Main test execution"""
    print("Meridian Comprehensive Test Suite")
    print("=================================")
    print(f"Target URL: {BASE_URL}")
    print(f"Timeout: {TIMEOUT}s")
    print()

    tester = MeridianTester()
    success = tester.run_all_tests()

    # Exit with appropriate code
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()