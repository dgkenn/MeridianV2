#!/usr/bin/env python3
"""
Test the production fix for OSA parsing and risk calculation
"""

import requests
import json

def test_production_api():
    """Test the production API with OSA case"""

    # Test case with OSA mention
    test_payload = {
        "hpi_text": "45-year-old male with history of obstructive sleep apnea on CPAP, presenting for elective surgery. Known difficult airway from prior procedures."
    }

    # Test local first
    print("Testing local API...")
    try:
        response = requests.post(
            "http://localhost:5000/api/analyze",
            json=test_payload,
            timeout=30
        )
        print(f"Local Response Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("Local API SUCCESS!")
            print(f"Found {len(data.get('risks', {}).get('risks', []))} risk assessments")
            for risk in data.get('risks', {}).get('risks', []):
                if 'INTUBATION' in risk.get('outcome', '').upper():
                    print(f"- {risk['outcome']}: {risk['adjusted_risk']:.3f}")
        else:
            print(f"Local API Error: {response.text}")
    except Exception as e:
        print(f"Local API Failed: {e}")

    print("\nTesting production API...")
    try:
        response = requests.post(
            "https://meridian-zr3e.onrender.com/api/analyze",
            json=test_payload,
            timeout=30
        )
        print(f"Production Response Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("Production API SUCCESS!")
            print(f"Found {len(data.get('risks', {}).get('risks', []))} risk assessments")
            for risk in data.get('risks', {}).get('risks', []):
                if 'INTUBATION' in risk.get('outcome', '').upper():
                    print(f"- {risk['outcome']}: {risk['adjusted_risk']:.3f}")
        else:
            print(f"Production API Error: {response.text}")
    except Exception as e:
        print(f"Production API Failed: {e}")

if __name__ == "__main__":
    test_production_api()