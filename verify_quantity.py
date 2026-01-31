import requests
import sys

API_URL = "http://127.0.0.1:5000/api/products"
QTY_URL = "http://127.0.0.1:5000/api/products/quantity"

def test_quantity():
    # 1. Create a product if not exists
    product = {
        "barcode": "QTY_TEST_01",
        "name": "Quantity Test Item",
        "price": 10.0,
        "category": "Test"
    }
    requests.post(API_URL, json=product)

    # 2. Update Quantity (+5)
    print("Testing Update (+5)...")
    res = requests.post(QTY_URL, json={"barcode": "QTY_TEST_01", "change": 5})
    if res.status_code != 200:
        print(f"Failed to update quantity: {res.text}")
        return False
    
    new_qty = res.json().get('new_quantity')
    print(f"New Quantity: {new_qty}")
    
    # 3. Verify
    if new_qty is not None and new_qty >= 5:
        print("Quantity Update SUCCESS")
        return True
    else:
        print("Quantity Update FAILED")
        return False

if __name__ == "__main__":
    if test_quantity():
        sys.exit(0)
    else:
        sys.exit(1)
