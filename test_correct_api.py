#!/usr/bin/env python3
"""
Test the correct production API endpoint.
"""

import requests
import json

def test_analyze_endpoint():
    """Test the /api/analyze endpoint."""
    url = "https://meridian-zr3e.onrender.com/api/analyze"

    # Test case: Complex cardiac patient
    test_data = {
        "hpi_text": "65-year-old male with coronary artery disease, diabetes mellitus, and hypertension presenting for cardiac surgery."
    }

    print(f"Testing: {url}")
    print("Test case: CAD + diabetes + hypertension")

    try:
        response = requests.post(url, json=test_data, timeout=30)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()

            # Check for parsed data
            if 'parsed' in data and 'extracted_factors' in data['parsed']:
                factors = data['parsed']['extracted_factors']
                print(f"Extracted {len(factors)} factors:")
                for factor in factors:
                    print(f"  - {factor['token']}: {factor['plain_label']}")

                # Check for key conditions
                tokens = [f['token'] for f in factors]
                cad_found = "CORONARY_ARTERY_DISEASE" in tokens
                diabetes_found = "DIABETES" in tokens
                htn_found = "HYPERTENSION" in tokens

                print(f"\nResults:")
                print(f"  CAD: {'YES' if cad_found else 'NO'}")
                print(f"  Diabetes: {'YES' if diabetes_found else 'NO'}")
                print(f"  Hypertension: {'YES' if htn_found else 'NO'}")

                if cad_found and diabetes_found and htn_found:
                    print("\nSUCCESS: All conditions detected!")
                    return True
                else:
                    print("\nPARTIAL: Some conditions detected")
                    return False
            else:
                print("No parsed factors found in response")
                print(f"Response keys: {list(data.keys())}")
                return False
        else:
            print(f"ERROR: HTTP {response.status_code}")
            print(response.text[:500])
            return False

    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    print("Testing production /api/analyze endpoint...")
    success = test_analyze_endpoint()
    print(f"\nResult: {'PASSED' if success else 'NEEDS_INVESTIGATION'}")