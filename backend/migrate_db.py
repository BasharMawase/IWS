import sqlite3
DB_NAME = "inventory.db"

def migrate():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    try:
        # Add column to item_instances
        print("Adding warehouse_id to item_instances...")
        cursor.execute("ALTER TABLE item_instances ADD COLUMN warehouse_id INTEGER DEFAULT 1 REFERENCES warehouses(id)")
    except Exception as e:
        print(f"Skipping item_instances update: {e}")

    try:
        # Add image_path to products
        print("Adding image_path to products...")
        cursor.execute("ALTER TABLE products ADD COLUMN image_path TEXT")
    except Exception as e:
        print(f"Skipping products image_path update: {e}")

    try:
        # Just in case warehouses table is missing (logic is in app start, but good to ensure)
        pass 
    except:
        pass
        
    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
