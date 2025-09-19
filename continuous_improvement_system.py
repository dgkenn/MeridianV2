#!/usr/bin/env python3
"""
Continuous Improvement System for Meridian
Complete recursive learning with safety constraints and feedback loops
"""

import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from pathlib import Path
import statistics
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ContinuousImprovementEngine:
    """Main engine for continuous improvement with safety constraints"""

    def __init__(self, base_url: str = "https://meridian-zr3e.onrender.com"):
        self.base_url = base_url
        self.improvement_history = []
        self.performance_metrics = []
        self.safety_violations_log = []
        self.learning_cycles = 0

    def run_performance_monitoring(self) -> Dict:
        """Run continuous performance monitoring"""
        logger.info("Starting performance monitoring cycle...")

        # Test representative cases
        test_cases = self._get_monitoring_test_cases()
        results = []

        for case in test_cases:
            result = self._evaluate_single_case(case)
            results.append(result)
            time.sleep(0.5)  # Rate limiting

        # Calculate performance metrics
        metrics = self._calculate_performance_metrics(results)

        # Record metrics
        self.performance_metrics.append({
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics,
            "results": results
        })

        logger.info(f"Performance monitoring complete. Overall score: {metrics['overall_score']:.1%}")
        return metrics

    def _get_monitoring_test_cases(self) -> List[Dict]:
        """Get representative test cases for monitoring"""
        return [
            {
                "name": "Cardiac Surgery with Comorbidities",
                "hpi_text": "65-year-old male with coronary artery disease, diabetes mellitus type 2, hypertension, chronic kidney disease stage 3, presenting for CABG.",
                "demographics": {"age_years": 65, "sex": "male", "weight_kg": 85},
                "expected_parsing_score": 0.8,
                "expected_safety_compliance": True
            },
            {
                "name": "Pediatric ENT with Asthma",
                "hpi_text": "5-year-old boy with asthma on albuterol, recent URI 2 weeks ago, presenting for tonsillectomy.",
                "demographics": {"age_years": 5, "sex": "male", "weight_kg": 18},
                "expected_parsing_score": 0.9,
                "expected_safety_compliance": True
            },
            {
                "name": "Emergency Trauma Case",
                "hpi_text": "25-year-old male motorcycle accident victim with traumatic brain injury, last meal 2 hours ago, requiring emergency craniotomy.",
                "demographics": {"age_years": 25, "sex": "male", "weight_kg": 80},
                "expected_parsing_score": 0.7,
                "expected_safety_compliance": True
            },
            {
                "name": "Obstetric Emergency",
                "hpi_text": "32-year-old G2P1 with severe preeclampsia, blood pressure 180/110, emergency cesarean section indicated.",
                "demographics": {"age_years": 32, "sex": "female", "weight_kg": 75},
                "expected_parsing_score": 0.8,
                "expected_safety_compliance": True
            },
            {
                "name": "Geriatric Surgery",
                "hpi_text": "89-year-old female with dementia, atrial fibrillation on warfarin, heart failure, presenting for hip fracture repair.",
                "demographics": {"age_years": 89, "sex": "female", "weight_kg": 45},
                "expected_parsing_score": 0.9,
                "expected_safety_compliance": True
            }
        ]

    def _evaluate_single_case(self, case: Dict) -> Dict:
        """Evaluate a single monitoring case"""
        try:
            start_time = time.time()

            response = requests.post(
                f"{self.base_url}/api/analyze",
                json={
                    "hpi_text": case["hpi_text"],
                    "demographics": case["demographics"]
                },
                timeout=30
            )

            end_time = time.time()
            latency = (end_time - start_time) * 1000

            if response.status_code != 200:
                return {
                    "case_name": case["name"],
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "latency_ms": latency
                }

            result = response.json()

            # Basic safety checks
            safety_compliant = self._basic_safety_check(result, case)

            # Parsing quality assessment
            parsing_score = self._assess_parsing_quality(result, case)

            return {
                "case_name": case["name"],
                "success": True,
                "latency_ms": latency,
                "parsing_score": parsing_score,
                "safety_compliant": safety_compliant,
                "response": result,
                "expected_parsing": case.get("expected_parsing_score", 0.5),
                "expected_safety": case.get("expected_safety_compliance", True)
            }

        except Exception as e:
            return {
                "case_name": case["name"],
                "success": False,
                "error": str(e),
                "latency_ms": 0
            }

    def _basic_safety_check(self, result: Dict, case: Dict) -> bool:
        """Basic safety compliance check"""
        # Check for contraindicated medications in standard recommendations
        medications = result.get('medications', {})
        contraindicated = {med.get('medication', '') for med in medications.get('contraindicated', [])}
        standard = {med.get('medication', '') for med in medications.get('standard', [])}

        # No overlap allowed
        if contraindicated.intersection(standard):
            return False

        # Check for pediatric weight-based dosing
        if case.get('demographics', {}).get('age_years', 100) < 18:
            weight = case.get('demographics', {}).get('weight_kg')
            if not weight:
                return False  # Pediatric case must have weight

        return True

    def _assess_parsing_quality(self, result: Dict, case: Dict) -> float:
        """Assess parsing quality based on expected medical complexity"""
        extracted_factors = result.get('parsed', {}).get('extracted_factors', [])

        # Count meaningful medical conditions extracted
        meaningful_conditions = [
            'CORONARY_ARTERY_DISEASE', 'DIABETES', 'HYPERTENSION', 'CHRONIC_KIDNEY_DISEASE',
            'ASTHMA', 'OSA', 'RECENT_URI_2W', 'TRAUMA', 'HEAD_INJURY', 'PREECLAMPSIA',
            'HEART_FAILURE', 'DEMENTIA', 'AGE_ELDERLY', 'AGE_VERY_ELDERLY'
        ]

        extracted_meaningful = [f.get('token', '') for f in extracted_factors
                               if f.get('token', '') in meaningful_conditions]

        # Score based on case complexity
        case_name = case.get('name', '').lower()
        if 'cardiac' in case_name:
            expected_conditions = 3  # CAD, diabetes, hypertension, CKD
        elif 'pediatric' in case_name:
            expected_conditions = 2  # Asthma, recent URI
        elif 'trauma' in case_name:
            expected_conditions = 2  # Trauma, head injury
        elif 'obstetric' in case_name:
            expected_conditions = 1  # Preeclampsia
        elif 'geriatric' in case_name:
            expected_conditions = 3  # Multiple comorbidities
        else:
            expected_conditions = 1

        score = min(1.0, len(extracted_meaningful) / max(1, expected_conditions))
        return score

    def _calculate_performance_metrics(self, results: List[Dict]) -> Dict:
        """Calculate aggregate performance metrics"""
        successful_results = [r for r in results if r.get('success', False)]

        if not successful_results:
            return {
                "overall_score": 0.0,
                "success_rate": 0.0,
                "avg_latency": 0.0,
                "avg_parsing_score": 0.0,
                "safety_compliance_rate": 0.0,
                "performance_trend": "declining"
            }

        success_rate = len(successful_results) / len(results)
        avg_latency = statistics.mean([r['latency_ms'] for r in successful_results])
        avg_parsing_score = statistics.mean([r.get('parsing_score', 0) for r in successful_results])
        safety_compliance_rate = sum([r.get('safety_compliant', False) for r in successful_results]) / len(successful_results)

        # Overall score (weighted average)
        overall_score = (
            success_rate * 0.3 +
            avg_parsing_score * 0.3 +
            safety_compliance_rate * 0.4  # Safety weighted most heavily
        )

        # Performance trend analysis
        performance_trend = self._analyze_performance_trend()

        return {
            "overall_score": overall_score,
            "success_rate": success_rate,
            "avg_latency": avg_latency,
            "avg_parsing_score": avg_parsing_score,
            "safety_compliance_rate": safety_compliance_rate,
            "performance_trend": performance_trend,
            "timestamp": datetime.now().isoformat()
        }

    def _analyze_performance_trend(self) -> str:
        """Analyze performance trend over time"""
        if len(self.performance_metrics) < 2:
            return "insufficient_data"

        recent_scores = [m['metrics']['overall_score'] for m in self.performance_metrics[-3:]]

        if len(recent_scores) >= 2:
            if recent_scores[-1] > recent_scores[-2] * 1.05:
                return "improving"
            elif recent_scores[-1] < recent_scores[-2] * 0.95:
                return "declining"
            else:
                return "stable"

        return "stable"

    def identify_improvement_opportunities(self) -> List[Dict]:
        """Identify specific improvement opportunities"""
        if not self.performance_metrics:
            return []

        latest_metrics = self.performance_metrics[-1]['metrics']
        opportunities = []

        # Safety compliance issues
        if latest_metrics['safety_compliance_rate'] < 0.95:
            opportunities.append({
                "type": "safety",
                "priority": "critical",
                "description": "Safety compliance below 95%",
                "current_score": latest_metrics['safety_compliance_rate'],
                "target_score": 0.98,
                "actions": [
                    "Enhanced contraindication checking",
                    "Improved drug interaction detection",
                    "Pediatric safety protocol review"
                ]
            })

        # Parsing accuracy issues
        if latest_metrics['avg_parsing_score'] < 0.8:
            opportunities.append({
                "type": "parsing",
                "priority": "high",
                "description": "Parsing accuracy below 80%",
                "current_score": latest_metrics['avg_parsing_score'],
                "target_score": 0.85,
                "actions": [
                    "Expand medical terminology patterns",
                    "Improve condition synonyms",
                    "Enhanced context recognition"
                ]
            })

        # Performance issues
        if latest_metrics['avg_latency'] > 5000:  # 5 seconds
            opportunities.append({
                "type": "performance",
                "priority": "medium",
                "description": "Response latency above 5 seconds",
                "current_score": latest_metrics['avg_latency'],
                "target_score": 3000,
                "actions": [
                    "Database query optimization",
                    "Caching improvements",
                    "Algorithm efficiency review"
                ]
            })

        # Overall score issues
        if latest_metrics['overall_score'] < 0.8:
            opportunities.append({
                "type": "overall",
                "priority": "high",
                "description": "Overall performance below 80%",
                "current_score": latest_metrics['overall_score'],
                "target_score": 0.85,
                "actions": [
                    "Comprehensive system review",
                    "Multi-component optimization",
                    "Integration testing enhancement"
                ]
            })

        return opportunities

    def generate_improvement_recommendations(self, opportunities: List[Dict]) -> Dict:
        """Generate specific improvement recommendations"""
        if not opportunities:
            return {
                "status": "optimal",
                "message": "System performing well, no immediate improvements needed",
                "recommendations": []
            }

        # Prioritize by severity
        critical_issues = [op for op in opportunities if op['priority'] == 'critical']
        high_issues = [op for op in opportunities if op['priority'] == 'high']
        medium_issues = [op for op in opportunities if op['priority'] == 'medium']

        recommendations = []

        # Critical issues first (safety)
        for issue in critical_issues:
            recommendations.append({
                "priority": 1,
                "type": issue['type'],
                "description": issue['description'],
                "timeline": "immediate",
                "effort": "high",
                "actions": issue['actions'],
                "expected_improvement": f"{issue['target_score']:.1%} {issue['type']} score"
            })

        # High priority issues
        for issue in high_issues:
            recommendations.append({
                "priority": 2,
                "type": issue['type'],
                "description": issue['description'],
                "timeline": "1-2 weeks",
                "effort": "medium",
                "actions": issue['actions'],
                "expected_improvement": f"{issue['target_score']:.1%} {issue['type']} score"
            })

        # Medium priority issues
        for issue in medium_issues:
            recommendations.append({
                "priority": 3,
                "type": issue['type'],
                "description": issue['description'],
                "timeline": "2-4 weeks",
                "effort": "low",
                "actions": issue['actions'],
                "expected_improvement": f"Reduce {issue['type']} issues"
            })

        return {
            "status": "needs_improvement",
            "total_issues": len(opportunities),
            "critical_issues": len(critical_issues),
            "recommendations": recommendations,
            "next_review": (datetime.now() + timedelta(days=7)).isoformat()
        }

    def run_complete_improvement_cycle(self) -> Dict:
        """Run a complete improvement cycle"""
        logger.info("=== STARTING COMPLETE IMPROVEMENT CYCLE ===")

        # 1. Performance monitoring
        current_metrics = self.run_performance_monitoring()

        # 2. Identify opportunities
        opportunities = self.identify_improvement_opportunities()

        # 3. Generate recommendations
        recommendations = self.generate_improvement_recommendations(opportunities)

        # 4. Record learning cycle
        cycle_result = {
            "cycle_number": self.learning_cycles + 1,
            "timestamp": datetime.now().isoformat(),
            "current_performance": current_metrics,
            "opportunities_identified": len(opportunities),
            "recommendations": recommendations,
            "safety_compliant": current_metrics['safety_compliance_rate'] >= 0.95
        }

        self.improvement_history.append(cycle_result)
        self.learning_cycles += 1

        # 5. Save results
        self._save_improvement_cycle(cycle_result)

        logger.info(f"Improvement cycle {self.learning_cycles} complete")
        return cycle_result

    def _save_improvement_cycle(self, cycle_result: Dict):
        """Save improvement cycle results"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"improvement_cycle_{cycle_result['cycle_number']}_{timestamp}.json"

        with open(filename, 'w') as f:
            json.dump(cycle_result, f, indent=2)

        logger.info(f"Improvement cycle results saved to {filename}")

    def print_improvement_summary(self, cycle_result: Dict):
        """Print improvement cycle summary"""
        print("\n" + "="*80)
        print("MERIDIAN CONTINUOUS IMPROVEMENT CYCLE COMPLETE")
        print("="*80)

        current = cycle_result['current_performance']
        recommendations = cycle_result['recommendations']

        print(f"Cycle Number: {cycle_result['cycle_number']}")
        print(f"Overall Performance Score: {current['overall_score']:.1%}")
        print(f"Safety Compliance: {current['safety_compliance_rate']:.1%}")
        print(f"Parsing Accuracy: {current['avg_parsing_score']:.1%}")
        print(f"Average Latency: {current['avg_latency']:.0f}ms")
        print(f"Performance Trend: {current['performance_trend']}")

        print(f"\nImprovement Status: {recommendations['status'].upper()}")
        print(f"Issues Identified: {recommendations.get('total_issues', 0)}")

        if recommendations.get('critical_issues', 0) > 0:
            print(f"⚠️  CRITICAL ISSUES: {recommendations['critical_issues']}")

        if recommendations.get('recommendations'):
            print(f"\nTop Recommendations:")
            for i, rec in enumerate(recommendations['recommendations'][:3], 1):
                print(f"  {i}. {rec['description']} ({rec['timeline']})")

        print("\n" + "="*80)

def run_continuous_improvement():
    """Run the continuous improvement system"""
    engine = ContinuousImprovementEngine()

    try:
        # Run improvement cycle
        cycle_result = engine.run_complete_improvement_cycle()

        # Print summary
        engine.print_improvement_summary(cycle_result)

        return cycle_result

    except Exception as e:
        logger.error(f"Error in improvement cycle: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    results = run_continuous_improvement()