#!/usr/bin/env python3
"""
Test production website API to verify parsing fixes.
"""

import requests
import json

def test_production_parsing():
    """Test the production API parsing endpoint."""
    print("=" * 60)
    print("TESTING PRODUCTION PARSING API")
    print("=" * 60)

    url = "https://meridian-zr3e.onrender.com/api/hpi/parse"

    # Test case: Complex cardiac patient with CAD, diabetes, hypertension
    test_data = {
        "hpi_text": "65-year-old male with history of coronary artery disease status post cardiac catheterization with stent placement 2 years ago, diabetes mellitus type 2 on metformin, hypertension on lisinopril presenting for elective cardiac surgery.",
        "session_id": "test_cardiac_case_001"
    }

    print(f"Testing URL: {url}")
    print(f"Test case: Complex cardiac patient")
    print(f"Expected extractions: CAD, diabetes, hypertension")

    try:
        print("\nSending request...")
        response = requests.post(url, json=test_data, timeout=30)

        print(f"Status code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            # Extract factor tokens
            factors = data.get('extracted_factors', [])
            factor_tokens = [f['token'] for f in factors]

            print(f"\nExtracted {len(factors)} factors:")
            for factor in factors:
                print(f"  - {factor['token']}: {factor['plain_label']} (confidence: {factor['confidence']:.2f})")

            # Check for key conditions
            cad_found = any(token == "CORONARY_ARTERY_DISEASE" for token in factor_tokens)
            diabetes_found = any(token == "DIABETES" for token in factor_tokens)
            htn_found = any(token == "HYPERTENSION" for token in factor_tokens)

            print(f"\nKey conditions detected:")
            print(f"  CAD (Coronary Artery Disease): {'[YES]' if cad_found else '[NO]'}")
            print(f"  Diabetes: {'[YES]' if diabetes_found else '[NO]'}")
            print(f"  Hypertension: {'[YES]' if htn_found else '[NO]'}")

            # Verify risk summary
            risk_summary = data.get('risk_summary', {})
            print(f"\nRisk summary: {risk_summary}")

            if cad_found and diabetes_found and htn_found:
                print("\n✅ SUCCESS: All major cardiac conditions detected!")
                print("✅ Parsing fixes are working in production!")
                return True
            else:
                print("\n❌ FAILED: Some conditions still missing")
                return False

        else:
            print(f"❌ ERROR: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

def test_health_endpoint():
    """Test the health endpoint to check system status."""
    print("\n" + "=" * 60)
    print("TESTING HEALTH ENDPOINT")
    print("=" * 60)

    url = "https://meridian-zr3e.onrender.com/api/health"

    try:
        print(f"Testing: {url}")
        response = requests.get(url, timeout=15)

        print(f"Status code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Version: {data.get('version', 'Unknown')}")
            print(f"Status: {data.get('status', 'Unknown')}")

            database = data.get('database', {})
            print(f"Database status: {database.get('status', 'Unknown')}")
            print(f"Papers count: {database.get('papers', 0)}")
            print(f"Ontology terms: {database.get('ontology_terms', 0)}")

            services = data.get('services', {})
            print(f"NLP processor: {services.get('nlp_processor', 'Unknown')}")
            print(f"Risk engine: {services.get('risk_engine', 'Unknown')}")

            print("✅ Health check passed!")
            return True
        else:
            print(f"❌ Health check failed: HTTP {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

if __name__ == "__main__":
    print("Testing production website with parsing fixes...")

    # Test health endpoint first
    health_ok = test_health_endpoint()

    # Test parsing functionality
    parsing_ok = test_production_parsing()

    print("\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)

    if health_ok and parsing_ok:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Production parsing now correctly extracts CAD, diabetes, and hypertension")
        print("✅ System health is good")
        print("✅ Fixes are working on the live website!")
    else:
        print("❌ SOME TESTS FAILED")
        if not health_ok:
            print("❌ Health endpoint issues")
        if not parsing_ok:
            print("❌ Parsing issues persist")

    print("=" * 60)