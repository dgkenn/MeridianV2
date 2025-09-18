#!/usr/bin/env python3
"""
Test the Medication API endpoint
"""

import requests
import json
import sys
from pathlib import Path

def test_medication_endpoint():
    """Test the /api/meds/recommend endpoint"""
    print("=== Testing Medication API Endpoint ===")

    # Test payload
    payload = {
        "hpi_text": "4-year-old male for tonsillectomy and adenoidectomy. Medical history significant for asthma with recent upper respiratory infection 5 days ago. Uses albuterol PRN. No other significant medical history. No known drug allergies. Vital signs stable. Physical exam appropriate for age. NPO since midnight.",
        "patient_params": {
            "age_years": 4,
            "weight_kg": 18,
            "height_cm": 100,
            "sex": "M",
            "urgency": "elective",
            "surgery_domain": "ENT",
            "allergies": [],
            "renal_function": None,
            "hepatic_function": None
        },
        "risk_assessment_params": {
            "age_band": "4-6",
            "surgery_type": "ENT",
            "urgency": "elective"
        }
    }

    try:
        # Make request to local server
        response = requests.post(
            "http://localhost:8084/api/meds/recommend",
            json=payload,
            timeout=30
        )

        if response.status_code == 200:
            data = response.json()
            print("✓ API request successful")

            # Validate response structure
            required_keys = ['patient', 'context', 'meds', 'summary']
            for key in required_keys:
                if key in data:
                    print(f"✓ Response contains '{key}'")
                else:
                    print(f"✗ Response missing '{key}'")

            # Show medication summary
            meds = data.get('meds', {})
            print(f"\nMedication Summary:")
            print(f"  Draw now: {len(meds.get('draw_now', []))} medications")
            print(f"  Standard: {len(meds.get('standard', []))} medications")
            print(f"  Consider: {len(meds.get('consider', []))} medications")
            print(f"  Contraindicated: {len(meds.get('contraindicated', []))} medications")

            # Show a sample medication
            draw_now = meds.get('draw_now', [])
            if draw_now:
                sample_med = draw_now[0]
                print(f"\nSample medication (draw now):")
                print(f"  Agent: {sample_med.get('agent')}")
                print(f"  Dose: {sample_med.get('dose')}")
                print(f"  Route: {sample_med.get('route')}")
                print(f"  Timing: {sample_med.get('timing')}")
                print(f"  Confidence: {sample_med.get('confidence')}")

            return True

        else:
            print(f"✗ API request failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print("✗ Connection failed - make sure the server is running on localhost:8084")
        return False
    except Exception as e:
        print(f"✗ API test failed: {e}")
        return False

def test_dose_calculator_endpoint():
    """Test the /api/meds/dose-calculator endpoint"""
    print("\n=== Testing Dose Calculator Endpoint ===")

    payload = {
        "agent": "Ondansetron",
        "weight_kg": 18,
        "age_years": 4,
        "indication": "PONV_prophylaxis",
        "route": "IV"
    }

    try:
        response = requests.post(
            "http://localhost:8084/api/meds/dose-calculator",
            json=payload,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            print("✓ Dose calculator successful")
            print(f"  Agent: {data.get('agent')}")
            calc = data.get('dose_calculation', {})
            print(f"  Dose: {calc.get('mg')} mg")
            print(f"  Volume: {calc.get('volume_ml')} mL")
            print(f"  Concentration: {calc.get('concentration')}")
            return True
        else:
            print(f"✗ Dose calculator failed with status {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print("✗ Connection failed - make sure the server is running")
        return False
    except Exception as e:
        print(f"✗ Dose calculator test failed: {e}")
        return False

def test_contraindication_endpoint():
    """Test the /api/meds/check-contraindications endpoint"""
    print("\n=== Testing Contraindication Endpoint ===")

    payload = {
        "agents": ["Succinylcholine", "Propofol"],
        "features": ["MH_HISTORY"],
        "allergies": ["EGG_SOY_ALLERGY"],
        "age_years": 4,
        "weight_kg": 18
    }

    try:
        response = requests.post(
            "http://localhost:8084/api/meds/check-contraindications",
            json=payload,
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            print("✓ Contraindication check successful")

            results = data.get('contraindication_results', {})
            for agent, result in results.items():
                contraindicated = result.get('contraindicated')
                reason = result.get('reason')
                print(f"  {agent}: {'Contraindicated' if contraindicated else 'Safe'}")
                if contraindicated and reason:
                    print(f"    Reason: {reason}")

            return True
        else:
            print(f"✗ Contraindication check failed with status {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print("✗ Connection failed - make sure the server is running")
        return False
    except Exception as e:
        print(f"✗ Contraindication test failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing Meridian Medication API Endpoints")
    print("=" * 50)
    print("Make sure the server is running: python app_simple.py")
    print()

    success = True

    # Test main recommendation endpoint
    if not test_medication_endpoint():
        success = False

    # Test dose calculator
    if not test_dose_calculator_endpoint():
        success = False

    # Test contraindication checker
    if not test_contraindication_endpoint():
        success = False

    if success:
        print("\n✓ All API endpoint tests passed!")
    else:
        print("\n✗ Some API tests failed!")

    print("\nTo test the API manually:")
    print("curl -X POST http://localhost:8084/api/meds/recommend \\")
    print("  -H 'Content-Type: application/json' \\")
    print("  -d '{\"hpi_text\": \"4-year-old for T&A with asthma\", \"patient_params\": {\"age_years\": 4, \"weight_kg\": 18}}'")