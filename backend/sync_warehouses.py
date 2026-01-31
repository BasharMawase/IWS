import sqlite3
import os

DB_NAME = "inventory.db"

def sync_data():
    if not os.path.exists(DB_NAME):
        print("Database not found!")
        return

    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 1. Get all products
        print("Fetching products...")
        cursor.execute("SELECT id, quantity FROM products")
        products = cursor.fetchall()

        # 2. Get all warehouses
        print("Fetching warehouses...")
        cursor.execute("SELECT id, name FROM warehouses")
        warehouses = cursor.fetchall()
        
        # 3. Iterate and Seed
        for p in products:
            pid = p['id']
            qty_total = p['quantity']
            
            # Check existing stock for this product
            cursor.execute("SELECT warehouse_id, quantity FROM warehouse_stock WHERE product_id = ?", (pid,))
            existing_stock = {row['warehouse_id']: row['quantity'] for row in cursor.fetchall()}
            
            # Calculate total in warehouse_stock
            current_warehouse_total = sum(existing_stock.values())
            
            print(f"Product {pid}: Total={qty_total}, Warehoused={current_warehouse_total}")
            
            if current_warehouse_total == 0 and qty_total > 0:
                # Case: Legacy Item (Has total stock, but no warehouse stock)
                # Assign ALL to Warehouse 1 (Default)
                print(f"  -> Migrating {qty_total} to Warehouse 1")
                cursor.execute('''
                    INSERT OR REPLACE INTO warehouse_stock (product_id, warehouse_id, quantity)
                    VALUES (?, ?, ?)
                ''', (pid, 1, qty_total))
                existing_stock[1] = qty_total
            
            elif current_warehouse_total != qty_total:
                 # Stock mismatch. Trust Total? Or Trust Warehouse?
                 # If we trust Total, we need to decide where the diff goes.
                 diff = qty_total - current_warehouse_total
                 if diff != 0:
                     print(f"  -> Mismatch! Diff={diff}. Adding to Warehouse 1.")
                     cursor.execute('''
                        INSERT INTO warehouse_stock (product_id, warehouse_id, quantity)
                        VALUES (?, ?, ?)
                        ON CONFLICT(product_id, warehouse_id)
                        DO UPDATE SET quantity = quantity + ?
                     ''', (pid, 1, diff, diff))

            # Ensure all warehouses have an entry (even 0)
            for w in warehouses:
                wid = w['id']
                if wid not in existing_stock: # and we didn't just add it above? existing_stock is stale for W1 if migrated
                    # Check again to be safe via insert ignore equivalent
                    cursor.execute('''
                        INSERT OR IGNORE INTO warehouse_stock (product_id, warehouse_id, quantity)
                        VALUES (?, ?, 0)
                    ''', (pid, wid))
                    
        conn.commit()
        print("Sync complete.")

    except Exception as e:
        print(f"Error during sync: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    sync_data()
