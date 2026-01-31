import requests
import sys

API_URL = "http://127.0.0.1:5000/api/import"
PLAN_URL = "http://127.0.0.1:5000/api/planned-products"

def test_import():
    try:
        # Upload
        with open('test_plan.csv', 'rb') as f:
            files = {'file': f}
            res = requests.post(API_URL, files=files)
            
        print(f"Import Status: {res.status_code}")
        print(f"Import Response: {res.text}")
        
        if res.status_code != 200:
            return False

        # Verify
        res = requests.get(PLAN_URL)
        items = res.json()
        
        bulk_item = next((i for i in items if i['name'] == 'Bulk Item 1'), None)
        if bulk_item:
            print("Found imported planned item: SUCCESS")
            return True
        else:
            print("Imported item not found: FAILED")
            return False

    except Exception as e:
        print(e)
        return False

if __name__ == "__main__":
    if test_import():
        sys.exit(0)
    else:
        sys.exit(1)
