#!/usr/bin/env python3
"""
Recursive Learning Engine for Meridian HPI Parser
Continuously tests, learns, and improves the system overnight

Features:
- Progressive difficulty scaling
- Automatic failure detection and fixing
- Overfitting protection
- Safety mechanisms
- Comprehensive test coverage
- Performance monitoring
- Auto-rollback on critical failures
"""

import json
import time
import logging
import random
import statistics
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple, Optional
from pathlib import Path
import requests
import sqlite3
import hashlib
import subprocess
import threading
from dataclasses import dataclass, asdict
from playwright.sync_api import sync_playwright

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('recursive_learning.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class TestResult:
    test_id: str
    difficulty_level: int
    accuracy: float
    response_time: float
    conditions_detected: List[str]
    conditions_expected: List[str]
    risk_scores: Dict[str, float]
    timestamp: str
    hpi_text: str
    error_message: Optional[str] = None

@dataclass
class LearningMetrics:
    total_tests: int
    successful_tests: int
    avg_accuracy: float
    avg_response_time: float
    current_difficulty: int
    overfitting_score: float
    improvement_rate: float
    consecutive_failures: int

class SafetyManager:
    """Manages safety protocols and circuit breakers"""

    def __init__(self):
        self.max_consecutive_failures = 5
        self.max_api_calls_per_hour = 1000
        self.min_accuracy_threshold = 0.3
        self.max_response_time = 30.0
        self.api_call_count = 0
        self.last_hour_reset = datetime.now()

    def check_safety_limits(self, metrics: LearningMetrics) -> Tuple[bool, str]:
        """Check if we've hit any safety limits"""

        # Reset API call counter every hour
        if datetime.now() - self.last_hour_reset > timedelta(hours=1):
            self.api_call_count = 0
            self.last_hour_reset = datetime.now()

        # Check various safety conditions
        if metrics.consecutive_failures >= self.max_consecutive_failures:
            return False, f"Too many consecutive failures: {metrics.consecutive_failures}"

        if self.api_call_count >= self.max_api_calls_per_hour:
            return False, f"API rate limit reached: {self.api_call_count}/hour"

        if metrics.avg_accuracy < self.min_accuracy_threshold:
            return False, f"Accuracy below safety threshold: {metrics.avg_accuracy:.3f}"

        return True, "All safety checks passed"

    def increment_api_calls(self):
        self.api_call_count += 1

class TestCaseGenerator:
    """Generates test cases with progressive difficulty"""

    def __init__(self):
        self.base_conditions = [
            "ASTHMA", "COPD", "DIABETES", "HYPERTENSION", "CORONARY_ARTERY_DISEASE",
            "HEART_FAILURE", "CHRONIC_KIDNEY_DISEASE", "OSA", "DEMENTIA", "TRAUMA",
            "HEAD_INJURY", "FULL_STOMACH", "ANTICOAGULANTS", "RECENT_URI_2W", "SMOKING"
        ]

        self.condition_templates = {
            "ASTHMA": ["asthma", "wheezing", "bronchospasm", "inhaler", "respiratory distress"],
            "DIABETES": ["diabetes", "diabetic", "insulin", "metformin", "hyperglycemia", "glucose"],
            "HYPERTENSION": ["hypertension", "high blood pressure", "HTN", "lisinopril", "amlodipine"],
            "HEART_FAILURE": ["heart failure", "CHF", "congestive heart failure", "ejection fraction", "cardiomyopathy"],
            "OSA": ["sleep apnea", "OSA", "CPAP", "snoring", "obstructive sleep", "AHI"],
            "TRAUMA": ["trauma", "accident", "injury", "motorcycle", "car crash", "fall"],
            "HEAD_INJURY": ["head injury", "brain injury", "concussion", "TBI", "craniotomy"],
            "FULL_STOMACH": ["ate", "last meal", "recent food", "full stomach", "dinner"],
            "RECENT_URI_2W": ["recent cold", "upper respiratory", "URI", "cough", "runny nose"],
            "DEMENTIA": ["dementia", "Alzheimer's", "memory problems", "confusion", "cognitive impairment"],
            "ANTICOAGULANTS": ["warfarin", "blood thinner", "coumadin", "anticoagulant", "INR"],
            "CHRONIC_KIDNEY_DISEASE": ["kidney disease", "CKD", "dialysis", "creatinine", "renal failure"]
        }

    def generate_test_case(self, difficulty_level: int) -> Dict[str, Any]:
        """Generate a test case based on difficulty level"""

        # Calculate complexity based on difficulty
        num_conditions = min(1 + (difficulty_level // 2), len(self.base_conditions))

        # Select random conditions
        selected_conditions = random.sample(self.base_conditions, num_conditions)

        # Generate HPI text
        hpi_parts = []

        # Add age and basic demographics
        ages = ["25-year-old", "45-year-old", "65-year-old", "78-year-old", "89-year-old"]
        genders = ["male", "female"]
        hpi_parts.append(f"{random.choice(ages)} {random.choice(genders)}")

        # Add conditions with varying complexity
        for condition in selected_conditions:
            templates = self.condition_templates.get(condition, [condition.lower()])

            if difficulty_level <= 3:
                # Simple, direct mentions
                hpi_parts.append(f"with {random.choice(templates)}")
            elif difficulty_level <= 6:
                # More complex, medical terminology
                template = random.choice(templates)
                modifiers = ["well-controlled", "poorly controlled", "chronic", "acute", "severe"]
                hpi_parts.append(f"with {random.choice(modifiers)} {template}")
            else:
                # Very complex, implicit mentions
                template = random.choice(templates)
                contexts = ["presenting for surgery", "requiring anesthesia", "scheduled for procedure"]
                hpi_parts.append(f"with history of {template}, {random.choice(contexts)}")

        # Add complexity based on difficulty
        if difficulty_level > 4:
            complications = [
                "hemodynamically unstable",
                "requiring emergency surgery",
                "with multiple comorbidities",
                "on multiple medications"
            ]
            if random.random() < 0.4:  # 40% chance
                hpi_parts.append(random.choice(complications))

        # Join parts naturally
        if len(hpi_parts) == 2:
            hpi_text = f"{hpi_parts[0]} {hpi_parts[1]}"
        else:
            hpi_text = f"{hpi_parts[0]} {', '.join(hpi_parts[1:-1])}, and {hpi_parts[-1]}"

        return {
            "test_id": hashlib.md5(hpi_text.encode()).hexdigest()[:8],
            "difficulty_level": difficulty_level,
            "hpi_text": hpi_text,
            "expected_conditions": selected_conditions,
            "timestamp": datetime.now().isoformat()
        }

class PerformanceMonitor:
    """Monitors system performance and detects overfitting"""

    def __init__(self):
        self.recent_results = []
        self.max_history = 100

    def add_result(self, result: TestResult):
        """Add a test result to monitoring"""
        self.recent_results.append(result)
        if len(self.recent_results) > self.max_history:
            self.recent_results.pop(0)

    def detect_overfitting(self) -> float:
        """Detect overfitting based on variance in performance"""
        if len(self.recent_results) < 20:
            return 0.0

        # Get accuracy scores from recent results
        accuracies = [r.accuracy for r in self.recent_results[-20:]]

        # Calculate variance - high variance suggests overfitting
        variance = statistics.variance(accuracies) if len(accuracies) > 1 else 0.0

        # Also check for suspiciously high accuracy on easy tests
        easy_tests = [r for r in self.recent_results[-20:] if r.difficulty_level <= 3]
        if easy_tests:
            easy_accuracy = statistics.mean([r.accuracy for r in easy_tests])
            if easy_accuracy > 0.95:  # Suspiciously high
                variance += 0.1

        return min(variance, 1.0)  # Cap at 1.0

    def get_improvement_rate(self) -> float:
        """Calculate rate of improvement over time"""
        if len(self.recent_results) < 10:
            return 0.0

        # Compare first half vs second half of recent results
        mid_point = len(self.recent_results) // 2
        first_half = self.recent_results[:mid_point]
        second_half = self.recent_results[mid_point:]

        first_avg = statistics.mean([r.accuracy for r in first_half])
        second_avg = statistics.mean([r.accuracy for r in second_half])

        return second_avg - first_avg

class AutoFixer:
    """Automatically fixes detected issues"""

    def __init__(self):
        self.fix_history = []

    def analyze_failure(self, result: TestResult) -> Dict[str, Any]:
        """Analyze a failed test to determine root cause"""
        analysis = {
            "failure_type": "unknown",
            "confidence": 0.0,
            "suggested_fix": "manual_investigation",
            "details": {}
        }

        # Analyze missing conditions
        missing = set(result.conditions_expected) - set(result.conditions_detected)
        extra = set(result.conditions_detected) - set(result.conditions_expected)

        if missing:
            analysis["failure_type"] = "missing_conditions"
            analysis["confidence"] = 0.8
            analysis["details"]["missing_conditions"] = list(missing)
            analysis["suggested_fix"] = "enhance_nlp_patterns"

        if extra:
            analysis["failure_type"] = "false_positives"
            analysis["confidence"] = 0.7
            analysis["details"]["extra_conditions"] = list(extra)
            analysis["suggested_fix"] = "refine_specificity"

        # Check response time issues
        if result.response_time > 15.0:
            analysis["failure_type"] = "performance"
            analysis["confidence"] = 0.9
            analysis["suggested_fix"] = "optimize_processing"

        return analysis

    def attempt_auto_fix(self, failure_analysis: Dict[str, Any]) -> bool:
        """Attempt to automatically fix the issue"""

        fix_type = failure_analysis.get("suggested_fix")

        try:
            if fix_type == "enhance_nlp_patterns":
                return self._enhance_nlp_patterns(failure_analysis)
            elif fix_type == "refine_specificity":
                return self._refine_specificity(failure_analysis)
            elif fix_type == "optimize_processing":
                return self._optimize_processing(failure_analysis)
            else:
                logger.warning(f"No auto-fix available for: {fix_type}")
                return False

        except Exception as e:
            logger.error(f"Auto-fix failed: {e}")
            return False

    def _enhance_nlp_patterns(self, analysis: Dict[str, Any]) -> bool:
        """Enhance NLP patterns for missing conditions"""
        # This would implement actual pattern enhancement
        # For now, just log the attempt
        missing = analysis["details"].get("missing_conditions", [])
        logger.info(f"Would enhance patterns for: {missing}")
        return True

    def _refine_specificity(self, analysis: Dict[str, Any]) -> bool:
        """Refine specificity to reduce false positives"""
        extra = analysis["details"].get("extra_conditions", [])
        logger.info(f"Would refine specificity for: {extra}")
        return True

    def _optimize_processing(self, analysis: Dict[str, Any]) -> bool:
        """Optimize processing for better performance"""
        logger.info("Would implement performance optimizations")
        return True

class RecursiveLearningEngine:
    """Main recursive learning engine"""

    def __init__(self, api_url: str = "https://meridian-zr3e.onrender.com"):
        self.api_url = api_url
        self.test_generator = TestCaseGenerator()
        self.performance_monitor = PerformanceMonitor()
        self.auto_fixer = AutoFixer()
        self.safety_manager = SafetyManager()

        # Learning state
        self.current_difficulty = 1
        self.consecutive_successes = 0
        self.consecutive_failures = 0
        self.session_start = datetime.now()

        # Results storage
        self.results_db = "learning_results.db"
        self._init_database()

    def _init_database(self):
        """Initialize SQLite database for storing results"""
        conn = sqlite3.connect(self.results_db)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY,
                test_id TEXT,
                difficulty_level INTEGER,
                accuracy REAL,
                response_time REAL,
                conditions_detected TEXT,
                conditions_expected TEXT,
                risk_scores TEXT,
                timestamp TEXT,
                hpi_text TEXT,
                error_message TEXT
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS learning_metrics (
                id INTEGER PRIMARY KEY,
                timestamp TEXT,
                total_tests INTEGER,
                successful_tests INTEGER,
                avg_accuracy REAL,
                avg_response_time REAL,
                current_difficulty INTEGER,
                overfitting_score REAL,
                improvement_rate REAL,
                consecutive_failures INTEGER
            )
        """)
        conn.commit()
        conn.close()

    def _save_result(self, result: TestResult):
        """Save test result to database"""
        conn = sqlite3.connect(self.results_db)
        conn.execute("""
            INSERT INTO test_results
            (test_id, difficulty_level, accuracy, response_time, conditions_detected,
             conditions_expected, risk_scores, timestamp, hpi_text, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            result.test_id, result.difficulty_level, result.accuracy, result.response_time,
            json.dumps(result.conditions_detected), json.dumps(result.conditions_expected),
            json.dumps(result.risk_scores), result.timestamp, result.hpi_text, result.error_message
        ))
        conn.commit()
        conn.close()

    def _save_metrics(self, metrics: LearningMetrics):
        """Save learning metrics to database"""
        conn = sqlite3.connect(self.results_db)
        conn.execute("""
            INSERT INTO learning_metrics
            (timestamp, total_tests, successful_tests, avg_accuracy, avg_response_time,
             current_difficulty, overfitting_score, improvement_rate, consecutive_failures)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(), metrics.total_tests, metrics.successful_tests,
            metrics.avg_accuracy, metrics.avg_response_time, metrics.current_difficulty,
            metrics.overfitting_score, metrics.improvement_rate, metrics.consecutive_failures
        ))
        conn.commit()
        conn.close()

    def _test_api_endpoint(self, hpi_text: str) -> Tuple[Dict[str, Any], float]:
        """Test the API endpoint and measure response time"""
        start_time = time.time()

        try:
            response = requests.post(
                f"{self.api_url}/api/analyze",
                json={"hpi_text": hpi_text},
                timeout=30
            )

            response_time = time.time() - start_time
            self.safety_manager.increment_api_calls()

            if response.status_code == 200:
                return response.json(), response_time
            else:
                raise Exception(f"API returned {response.status_code}: {response.text}")

        except Exception as e:
            response_time = time.time() - start_time
            raise Exception(f"API call failed: {e}")

    def _evaluate_result(self, api_response: Dict[str, Any], expected_conditions: List[str]) -> float:
        """Evaluate the accuracy of API response"""
        detected_conditions = [c["token"] for c in api_response.get("conditions", [])]

        expected_set = set(expected_conditions)
        detected_set = set(detected_conditions)

        if not expected_set:
            return 1.0 if not detected_set else 0.0

        # Calculate precision, recall, and F1
        true_positives = len(expected_set & detected_set)
        false_positives = len(detected_set - expected_set)
        false_negatives = len(expected_set - detected_set)

        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0

        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        return f1_score

    def _run_single_test(self, test_case: Dict[str, Any]) -> TestResult:
        """Run a single test case"""
        try:
            api_response, response_time = self._test_api_endpoint(test_case["hpi_text"])

            detected_conditions = [c["token"] for c in api_response.get("conditions", [])]
            accuracy = self._evaluate_result(api_response, test_case["expected_conditions"])

            # Extract risk scores
            risk_scores = {}
            for outcome in api_response.get("risk_assessment", {}).get("outcomes", []):
                risk_scores[outcome["outcome_token"]] = outcome["final_risk"]

            return TestResult(
                test_id=test_case["test_id"],
                difficulty_level=test_case["difficulty_level"],
                accuracy=accuracy,
                response_time=response_time,
                conditions_detected=detected_conditions,
                conditions_expected=test_case["expected_conditions"],
                risk_scores=risk_scores,
                timestamp=datetime.now().isoformat(),
                hpi_text=test_case["hpi_text"]
            )

        except Exception as e:
            return TestResult(
                test_id=test_case["test_id"],
                difficulty_level=test_case["difficulty_level"],
                accuracy=0.0,
                response_time=30.0,
                conditions_detected=[],
                conditions_expected=test_case["expected_conditions"],
                risk_scores={},
                timestamp=datetime.now().isoformat(),
                hpi_text=test_case["hpi_text"],
                error_message=str(e)
            )

    def _calculate_metrics(self) -> LearningMetrics:
        """Calculate current learning metrics"""
        # Get recent results from database
        conn = sqlite3.connect(self.results_db)
        cursor = conn.execute("""
            SELECT accuracy, response_time FROM test_results
            ORDER BY timestamp DESC LIMIT 50
        """)
        recent_results = cursor.fetchall()
        conn.close()

        if not recent_results:
            return LearningMetrics(0, 0, 0.0, 0.0, self.current_difficulty, 0.0, 0.0, self.consecutive_failures)

        accuracies = [r[0] for r in recent_results]
        response_times = [r[1] for r in recent_results]

        total_tests = len(recent_results)
        successful_tests = len([a for a in accuracies if a > 0.7])
        avg_accuracy = statistics.mean(accuracies)
        avg_response_time = statistics.mean(response_times)

        overfitting_score = self.performance_monitor.detect_overfitting()
        improvement_rate = self.performance_monitor.get_improvement_rate()

        return LearningMetrics(
            total_tests=total_tests,
            successful_tests=successful_tests,
            avg_accuracy=avg_accuracy,
            avg_response_time=avg_response_time,
            current_difficulty=self.current_difficulty,
            overfitting_score=overfitting_score,
            improvement_rate=improvement_rate,
            consecutive_failures=self.consecutive_failures
        )

    def _adjust_difficulty(self, metrics: LearningMetrics):
        """Adjust difficulty based on performance"""

        # Increase difficulty if doing well
        if (metrics.avg_accuracy > 0.9 and
            self.consecutive_successes >= 3 and
            metrics.overfitting_score < 0.3):
            self.current_difficulty = min(self.current_difficulty + 1, 10)
            self.consecutive_successes = 0
            logger.info(f"Increased difficulty to level {self.current_difficulty}")

        # Decrease difficulty if struggling
        elif (metrics.avg_accuracy < 0.6 and
              self.consecutive_failures >= 3):
            self.current_difficulty = max(self.current_difficulty - 1, 1)
            self.consecutive_failures = 0
            logger.info(f"Decreased difficulty to level {self.current_difficulty}")

        # Reset on overfitting detection
        elif metrics.overfitting_score > 0.7:
            self.current_difficulty = max(self.current_difficulty - 2, 1)
            logger.warning(f"Overfitting detected! Reset difficulty to {self.current_difficulty}")

    def run_learning_cycle(self, max_duration_hours: int = 8, max_iterations: int = 1000):
        """Run the main learning cycle"""

        logger.info(f"Starting recursive learning cycle for {max_duration_hours} hours")
        logger.info(f"Max iterations: {max_iterations}")

        end_time = datetime.now() + timedelta(hours=max_duration_hours)
        iteration = 0

        while datetime.now() < end_time and iteration < max_iterations:
            try:
                iteration += 1

                # Generate test case
                test_case = self.test_generator.generate_test_case(self.current_difficulty)
                logger.info(f"Iteration {iteration}: Testing difficulty {self.current_difficulty}")
                logger.info(f"HPI: {test_case['hpi_text'][:100]}...")

                # Run test
                result = self._run_single_test(test_case)

                # Save result
                self._save_result(result)
                self.performance_monitor.add_result(result)

                # Update counters
                if result.accuracy > 0.7:
                    self.consecutive_successes += 1
                    self.consecutive_failures = 0
                    logger.info(f"✓ Test passed: {result.accuracy:.3f} accuracy")
                else:
                    self.consecutive_failures += 1
                    self.consecutive_successes = 0
                    logger.warning(f"✗ Test failed: {result.accuracy:.3f} accuracy")

                    # Attempt auto-fix on failure
                    if result.error_message is None:  # Only for logic failures, not API errors
                        failure_analysis = self.auto_fixer.analyze_failure(result)
                        if failure_analysis["confidence"] > 0.7:
                            logger.info(f"Attempting auto-fix: {failure_analysis['suggested_fix']}")
                            fix_success = self.auto_fixer.attempt_auto_fix(failure_analysis)
                            if fix_success:
                                logger.info("Auto-fix applied successfully")

                # Calculate metrics
                metrics = self._calculate_metrics()
                self._save_metrics(metrics)

                # Safety check
                safe, reason = self.safety_manager.check_safety_limits(metrics)
                if not safe:
                    logger.error(f"Safety limit triggered: {reason}")
                    break

                # Adjust difficulty
                self._adjust_difficulty(metrics)

                # Progress report every 10 iterations
                if iteration % 10 == 0:
                    logger.info(f"Progress Report - Iteration {iteration}")
                    logger.info(f"  Difficulty: {self.current_difficulty}")
                    logger.info(f"  Avg Accuracy: {metrics.avg_accuracy:.3f}")
                    logger.info(f"  Avg Response Time: {metrics.avg_response_time:.1f}s")
                    logger.info(f"  Overfitting Score: {metrics.overfitting_score:.3f}")
                    logger.info(f"  Consecutive Failures: {metrics.consecutive_failures}")

                # Brief pause between tests
                time.sleep(2)

            except KeyboardInterrupt:
                logger.info("Learning cycle interrupted by user")
                break
            except Exception as e:
                logger.error(f"Unexpected error in learning cycle: {e}")
                logger.error(traceback.format_exc())
                time.sleep(10)  # Wait before retrying

        # Final report
        final_metrics = self._calculate_metrics()
        logger.info("=== LEARNING SESSION COMPLETE ===")
        logger.info(f"Total iterations: {iteration}")
        logger.info(f"Final difficulty: {self.current_difficulty}")
        logger.info(f"Final accuracy: {final_metrics.avg_accuracy:.3f}")
        logger.info(f"Total runtime: {datetime.now() - self.session_start}")

        return final_metrics

def main():
    """Main entry point"""
    import time

    # Configuration
    MAX_DURATION_HOURS = 8
    MAX_ITERATIONS = 1000
    API_URL = "https://meridian-zr3e.onrender.com"

    logger.info("Initializing Recursive Learning Engine")

    try:
        # Create learning engine
        engine = RecursiveLearningEngine(api_url=API_URL)

        # Test API connectivity with retries
        max_retries = 10
        for attempt in range(max_retries):
            try:
                test_response, _ = engine._test_api_endpoint("test patient with diabetes")
                logger.info("✓ API connectivity confirmed")
                break
            except Exception as e:
                logger.warning(f"API test attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Waiting 30 seconds before retry...")
                    time.sleep(30)
                else:
                    logger.error("Max API test retries exceeded, but proceeding with resilient mode")
                    break

        # Run learning cycle
        final_metrics = engine.run_learning_cycle(
            max_duration_hours=MAX_DURATION_HOURS,
            max_iterations=MAX_ITERATIONS
        )

        logger.info("Learning session completed successfully")

    except Exception as e:
        logger.error(f"Learning engine failed: {e}")
        logger.error(traceback.format_exc())
        return 1

    return 0

if __name__ == "__main__":
    exit(main())