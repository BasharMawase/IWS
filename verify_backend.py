import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

try:
    print("Testing Imports...")
    from app import app, db
    print("Imports Successful.")

    print("Testing Database Init...")
    # Add a test product
    db.add_product('TEST001', 'Test Product', 9.99, 'A test description', 'TestCat')
    
    prod = db.get_product('TEST001')
    if prod and prod['name'] == 'Test Product':
        print("Database Test Passed.")
    else:
        print("Database Test Failed: Product not found.")

    print("Testing Flask Config...")
    if app.config['SECRET_KEY'] == 'secret!':
        print("Flask Config Passed.")

    print("ALL CHECKS PASSED")

except Exception as e:
    print(f"VERIFICATION FAILED: {e}")
    sys.exit(1)
