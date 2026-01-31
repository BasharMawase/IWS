import requests
import json
import sys

# Verification of the registration flow API side
API_URL = "http://127.0.0.1:5000/api/products"

def test_add_product():
    new_product = {
        "barcode": "TEST_REG_001",
        "name": "Verified Product",
        "price": 5.55,
        "category": "Test",
        "description": "Added via verification script"
    }
    
    try:
        # 1. Add Product
        response = requests.post(API_URL, json=new_product)
        if response.status_code == 200:
            print("POST /api/products: SUCCESS")
        else:
            print(f"POST /api/products: FAILED ({response.text})")
            return False

        # 2. Add Duplicate (Should Fail)
        response = requests.post(API_URL, json=new_product)
        if response.status_code == 400:
            print("Duplicate Check: SUCCESS")
        else:
            print(f"Duplicate Check: FAILED ({response.status_code})")
            return False
            
        return True

    except Exception as e:
        print(f"Connection Error: {e}")
        return False

if __name__ == "__main__":
    if test_add_product():
        print("VERIFICATION PASSED")
        sys.exit(0)
    else:
        print("VERIFICATION FAILED")
        sys.exit(1)
