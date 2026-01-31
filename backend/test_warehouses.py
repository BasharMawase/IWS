import requests
import json
import time

BASE_URL = 'http://localhost:5001'

def reset_db():
    # Helper to ideally reset DB or just work with new products
    pass

def test_warehouse_logic():
    print("--- Starting Warehouse Logic Test ---")
    
    # 1. Create a Product
    test_num = int(time.time())
    prod_name = f"Test Product {test_num}"
    print(f"Creating product: {prod_name}")
    resp = requests.post(f"{BASE_URL}/api/products", json={
        "name": prod_name,
        "price": 10.0,
        "category": "Test",
        "pack_size": 1
    })
    assert resp.status_code == 200
    
    # Get Product ID
    products = requests.get(f"{BASE_URL}/api/products").json()
    product = next(p for p in products if p['name'] == prod_name)
    pid = product['id']
    print(f"Product ID: {pid}")
    
    # 2. Add Stock to Warehouse 1
    print("Adding 10 items to Warehouse 1...")
    resp = requests.post(f"{BASE_URL}/api/instances", json={
        "product_id": pid,
        "barcode": f"W1-{test_num}",
        "quantity": 10,
        "warehouse_id": 1
    })
    if resp.status_code != 200:
        print(f"Failed to add instance W1: {resp.text}")
    assert resp.status_code == 200
    
    # 3. Add Stock to Warehouse 2
    print("Adding 20 items to Warehouse 2...")
    resp = requests.post(f"{BASE_URL}/api/instances", json={
        "product_id": pid,
        "barcode": f"W2-{test_num}",
        "quantity": 20,
        "warehouse_id": 2
    })
    if resp.status_code != 200:
        print(f"Failed to add instance W2: {resp.text}")
    assert resp.status_code == 200

    # 4. Verify Total Quantity
    products = requests.get(f"{BASE_URL}/api/products").json()
    product = next(p for p in products if p['id'] == pid)
    print(f"Total Quantity (Should be 30): {product['quantity']}")
    assert product['quantity'] == 30
    
    # 5. Create Order (Small - Should come from W1)
    print("Creating order for 5 items (Should empty W1 to 5)...")
    resp = requests.post(f"{BASE_URL}/api/orders", json={
        "business_name": "Test Client 1",
        "items": [{"product_id": pid, "quantity": 5}]
    })
    assert resp.status_code == 200
    
    # Verify Total = 25
    products = requests.get(f"{BASE_URL}/api/products").json()
    product = next(p for p in products if p['id'] == pid)
    print(f"New Total Quantity (Should be 25): {product['quantity']}")
    assert product['quantity'] == 25
    
    # 6. Create Order (Spillover - 10 items: 5 from W1, 5 from W2)
    print("Creating order for 10 items (Should empty W1 and take 5 from W2)...")
    resp = requests.post(f"{BASE_URL}/api/orders", json={
        "business_name": "Test Client 2",
        "items": [{"product_id": pid, "quantity": 10}]
    })
    assert resp.status_code == 200
    
    # Verify Total = 15
    products = requests.get(f"{BASE_URL}/api/products").json()
    product = next(p for p in products if p['id'] == pid)
    print(f"New Total Quantity (Should be 15): {product['quantity']}")
    assert product['quantity'] == 15
    
    print("--- Test Passed ---")

if __name__ == "__main__":
    try:
        test_warehouse_logic()
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Test Failed: {e}")
