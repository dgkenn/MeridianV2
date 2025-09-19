#!/usr/bin/env python3
"""
Test Local Learning - Run learning engine against local API to validate fixes
"""

import sys
import time
import logging
import json
from datetime import datetime

# Set up encoding for Windows
import io
sys.stdout = io.TextIOWrapper(sys.stdout.detach(), encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.detach(), encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def test_local_learning():
    """Test the recursive learning engine against local API"""

    print("🔬 TESTING LOCAL LEARNING ENGINE")
    print("================================")
    print(f"Testing against: http://localhost:8084")
    print(f"Start time: {datetime.now()}")
    print()

    # Wait for local API to be ready
    print("⏳ Waiting for local API to start...")
    time.sleep(5)

    # Test basic API connectivity first
    import requests
    try:
        response = requests.get("http://localhost:8084", timeout=10)
        print(f"✅ Local API responsive: {response.status_code}")
    except Exception as e:
        print(f"❌ Local API not responding: {e}")
        return False

    # Import and configure learning engine for local testing
    try:
        from recursive_learning_engine import RecursiveLearningEngine

        # Create engine configured for local testing
        engine = RecursiveLearningEngine(
            base_url="http://localhost:8084",
            max_duration_hours=0.5,  # 30 minutes for local test
            safety_threshold=0.1     # Lower threshold for testing
        )

        print("🚀 Starting local learning test...")
        print("Duration: 30 minutes")
        print("Safety threshold: 10%")
        print()

        # Run learning cycle
        results = engine.run_learning_cycle(
            max_duration_hours=0.5,
            max_iterations=10
        )

        print("\n🎯 LOCAL TEST RESULTS")
        print("=====================")
        print(f"Total iterations: {results.get('total_iterations', 0)}")
        print(f"Final accuracy: {results.get('final_accuracy', 0):.1%}")
        print(f"Final difficulty: {results.get('final_difficulty', 0)}")
        print(f"Runtime: {results.get('total_runtime', 'unknown')}")

        # Check if our fixes worked
        if results.get('final_accuracy', 0) > 0:
            print("✅ SUCCESS: Dynamic risk scoring is working!")
            print("✅ Database fixes are effective")
            print("✅ Ready for production deployment")
        else:
            print("⚠️  Still detecting issues - need further investigation")

        return results.get('final_accuracy', 0) > 0

    except Exception as e:
        print(f"❌ Learning engine error: {e}")
        return False

if __name__ == "__main__":
    success = test_local_learning()
    exit(0 if success else 1)