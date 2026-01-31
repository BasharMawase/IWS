import sqlite3
import datetime
import os

DB_NAME = "inventory.db"

class Database:
    def __init__(self):
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(DB_NAME, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Products (Classes)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT,
                price REAL,
                description TEXT,
                quantity INTEGER DEFAULT 0,
                pack_size INTEGER DEFAULT 1,
                image_path TEXT
            )
        ''')
        
        # Warehouses
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS warehouses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL
            )
        ''')

        # Initialize Default Warehouses if empty
        cursor.execute("SELECT COUNT(*) as count FROM warehouses")
        if cursor.fetchone()['count'] == 0:
            cursor.execute("INSERT INTO warehouses (name) VALUES ('Warehouse 1')")
            cursor.execute("INSERT INTO warehouses (name) VALUES ('Warehouse 2')")
            cursor.execute("INSERT INTO warehouses (name) VALUES ('Warehouse 3')")

        # Warehouse Stock (Intersection Table)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS warehouse_stock (
                product_id INTEGER NOT NULL,
                warehouse_id INTEGER NOT NULL,
                quantity INTEGER DEFAULT 0,
                PRIMARY KEY (product_id, warehouse_id),
                FOREIGN KEY(product_id) REFERENCES products(id),
                FOREIGN KEY(warehouse_id) REFERENCES warehouses(id)
            )
        ''')
        
        # Item Instances (Unique Assets)
        # Added warehouse_id
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS item_instances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                warehouse_id INTEGER DEFAULT 1,
                barcode TEXT NOT NULL,
                scan_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                notes TEXT,
                status TEXT DEFAULT 'In Stock',
                FOREIGN KEY(product_id) REFERENCES products(id),
                FOREIGN KEY(warehouse_id) REFERENCES warehouses(id)
            )
        ''')

        # Scans table (History log)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                barcode TEXT NOT NULL,
                quantity INTEGER DEFAULT 1,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Orders Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_name TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'PENDING',
                worker_name TEXT,
                completed_at DATETIME
            )
        ''')

        # Order Items Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                FOREIGN KEY(order_id) REFERENCES orders(id),
                FOREIGN KEY(product_id) REFERENCES products(id)
            )
        ''')
        
        # Order Item Allocations (Which warehouse provides what)
        # Added picked_quantity
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS order_item_allocations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                warehouse_id INTEGER NOT NULL,
                quantity INTEGER NOT NULL,
                picked_quantity INTEGER DEFAULT 0,
                FOREIGN KEY(order_id) REFERENCES orders(id),
                FOREIGN KEY(product_id) REFERENCES products(id),
                FOREIGN KEY(warehouse_id) REFERENCES warehouses(id)
            )
        ''')

        # Workers Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                status TEXT DEFAULT 'Active',
                last_active DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()

    def get_warehouses(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM warehouses")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    # --- Worker Management ---
    def get_workers(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM workers ORDER BY name ASC")
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def add_worker(self, name):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO workers (name) VALUES (?)", (name,))
            conn.commit()
            return True
        except:
            return False
        finally:
            conn.close()

    def delete_worker(self, worker_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM workers WHERE id = ?", (worker_id,))
            conn.commit()
            return True
        except:
            return False
        finally:
            conn.close()

    def add_product(self, name, price, description, category, pack_size=1, image_path=None):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO products (name, price, description, category, pack_size, image_path)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, price, description, category, pack_size, image_path))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error adding product: {e}")
            return False
        finally:
            conn.close()

    def get_all_products(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get basic products
        cursor.execute("SELECT * FROM products ORDER BY id DESC")
        products = [dict(row) for row in cursor.fetchall()]
        
        # Get breakdown
        cursor.execute("SELECT product_id, warehouse_id, quantity FROM warehouse_stock")
        stock_rows = cursor.fetchall()
        
        # Map breakdown
        stock_map = {} # pid -> {wid: qty}
        for row in stock_rows:
            pid = row['product_id']
            if pid not in stock_map: stock_map[pid] = {}
            stock_map[pid][row['warehouse_id']] = row['quantity']
            
        # Attach to products
        for p in products:
            p['stock_breakdown'] = stock_map.get(p['id'], {})
            
        conn.close()
        return products
    
    def get_product_by_id(self, pid):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM products WHERE id = ?", (pid,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def add_instance(self, product_id, barcode, quantity=1, notes='', warehouse_id=1):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # 1. Create instances
            for _ in range(quantity):
                cursor.execute('''
                    INSERT INTO item_instances (product_id, barcode, notes, warehouse_id)
                    VALUES (?, ?, ?, ?)
                ''', (product_id, barcode, notes, warehouse_id))
            
            # 2. Update TOTAL stock count
            cursor.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?", (quantity, product_id))
            
            # 3. Update Warehouse Stock
            # Upsert logic (Insert or Update)
            cursor.execute('''
                INSERT INTO warehouse_stock (product_id, warehouse_id, quantity) 
                VALUES (?, ?, ?)
                ON CONFLICT(product_id, warehouse_id) 
                DO UPDATE SET quantity = quantity + ?
            ''', (product_id, warehouse_id, quantity, quantity))

            # 4. Log the batch scan event
            cursor.execute("INSERT INTO scans (barcode, quantity) VALUES (?, ?)", (barcode, quantity))

            conn.commit()
            return True, f"Added {quantity} items"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    def get_instances(self, product_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM item_instances WHERE product_id = ? ORDER BY scan_time DESC", (product_id,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
        
    def update_quantity(self, product_id, change, warehouse_id=1):
        # Manual adjustment
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Update Total
            cursor.execute("UPDATE products SET quantity = quantity + ? WHERE id = ?", (change, product_id))
            
            # Update Warehouse
            cursor.execute('''
                INSERT INTO warehouse_stock (product_id, warehouse_id, quantity) 
                VALUES (?, ?, ?)
                ON CONFLICT(product_id, warehouse_id) 
                DO UPDATE SET quantity = quantity + ?
            ''', (product_id, warehouse_id, change, change))
            
            conn.commit()
            return True
        except:
            return False
        finally:
            conn.close()

    def log_scan(self, barcode, quantity=1):
        # Logging raw scan from wedge/serial
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO scans (barcode, quantity) VALUES (?, ?)", (barcode, quantity))
            conn.commit()
        except:
            pass
        finally:
            conn.close()

    def get_scan_history(self, limit=50):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT s.barcode, s.timestamp, p.name, s.quantity as scanned_amount
            FROM scans s
            LEFT JOIN item_instances i ON s.barcode = i.barcode
            LEFT JOIN products p ON i.product_id = p.id
            ORDER BY s.timestamp DESC
            LIMIT ?
        ''', (limit,))
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_orders(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT o.id, o.business_name, o.timestamp, o.status, COUNT(oi.id) as item_count, SUM(oi.quantity) as total_qty
            FROM orders o
            LEFT JOIN order_items oi ON o.id = oi.order_id
            GROUP BY o.id
            ORDER BY o.timestamp DESC
        ''')
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_order_details(self, order_id):
        conn = self._get_connection()
        cursor = conn.cursor()
        # Basic items
        cursor.execute('''
            SELECT oi.quantity, p.name, p.id as product_id
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = ?
        ''', (order_id,))
        items = [dict(row) for row in cursor.fetchall()]
        
        # Allocations (Warehouse picking status)
        cursor.execute('''
            SELECT oia.product_id, oia.warehouse_id, oia.quantity, oia.picked_quantity, p.name
            FROM order_item_allocations oia
            JOIN products p ON oia.product_id = p.id
            WHERE oia.order_id = ?
        ''', (order_id,))
        allocations = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return {"items": items, "allocations": allocations}

    def record_pick(self, order_id, warehouse_id, barcode, worker_name):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # 1. Find the product_id for this barcode (instance)
            cursor.execute("SELECT product_id FROM item_instances WHERE barcode = ? AND warehouse_id = ?", (barcode, warehouse_id))
            instance = cursor.fetchone()
            if not instance:
                return False, "פריט לא נמצא במחסן זה"
            
            pid = instance['product_id']
            
            # 2. Check if this product is in the order for this warehouse and not yet fully picked
            cursor.execute('''
                SELECT id, quantity, picked_quantity 
                FROM order_item_allocations 
                WHERE order_id = ? AND product_id = ? AND warehouse_id = ?
            ''', (order_id, pid, warehouse_id))
            allocation = cursor.fetchone()
            
            if not allocation:
                return False, "מוצר זה אינו חלק מהזמנה זו במחסן זה"
            
            if allocation['picked_quantity'] >= allocation['quantity']:
                return False, "המוצר כבר לוקט במלואו"
            
            # 3. Increment picked_quantity
            cursor.execute('''
                UPDATE order_item_allocations 
                SET picked_quantity = picked_quantity + 1 
                WHERE id = ?
            ''', (allocation['id'],))
            
            # 4. Mark instance as 'Picked' (optional, but good for traceability)
            cursor.execute("UPDATE item_instances SET status = 'Picked', notes = ? WHERE barcode = ?", (f"Picked for Order #{order_id} by {worker_name}", barcode))
            
            # 5. Update worker last_active
            cursor.execute("UPDATE workers SET last_active = CURRENT_TIMESTAMP WHERE name = ?", (worker_name,))
            
            conn.commit()
            return True, "הפריט לוקט בהצלחה"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()
    
    def get_active_orders(self, warehouse_id=None):
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if warehouse_id:
            query = '''
                SELECT o.id, o.business_name, o.timestamp, o.status, o.worker_name, 
                       COUNT(oia.id) as item_count, SUM(oia.quantity) as total_qty
                FROM orders o
                JOIN order_item_allocations oia ON o.id = oia.order_id
                WHERE o.status IN ('PENDING', 'PROCESSING') AND oia.warehouse_id = ?
                GROUP BY o.id
                ORDER BY o.timestamp ASC
            '''
            cursor.execute(query, (warehouse_id,))
        else:
            query = '''
                SELECT o.id, o.business_name, o.timestamp, o.status, o.worker_name, COUNT(oi.id) as item_count 
                FROM orders o
                LEFT JOIN order_items oi ON o.id = oi.order_id
                WHERE o.status IN ('PENDING', 'PROCESSING')
                GROUP BY o.id
                ORDER BY o.timestamp ASC
            '''
            cursor.execute(query)
            
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def update_order_status(self, order_id, status, worker_name=None):
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            if status == 'COMPLETED':
                cursor.execute('''
                    UPDATE orders 
                    SET status = ?, completed_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                ''', (status, order_id))
            else:
                cursor.execute('''
                    UPDATE orders 
                    SET status = ?, worker_name = COALESCE(?, worker_name)
                    WHERE id = ?
                ''', (status, worker_name, order_id))
            conn.commit()
            return True
        except Exception as e:
            print(f"Error updating order: {e}")
            return False
        finally:
            conn.close()

    def get_analytics_data(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        data = {}
        
        # 1. Total Orders
        cursor.execute("SELECT COUNT(*) as count FROM orders")
        data['total_orders'] = cursor.fetchone()['count']
        
        # 2. Total Revenue
        cursor.execute('''
            SELECT SUM(oi.quantity * p.price) as revenue
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
        ''')
        res = cursor.fetchone()
        data['total_revenue'] = res['revenue'] if res and res['revenue'] else 0.0
        
        # 3. Top Products
        cursor.execute('''
            SELECT p.name, SUM(oi.quantity) as total_sold
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            GROUP BY p.id
            ORDER BY total_sold DESC
            LIMIT 5
        ''')
        data['top_products'] = [dict(row) for row in cursor.fetchall()]

        # 4. Recent Orders
        cursor.execute('''
            SELECT id, business_name, timestamp 
            FROM orders 
            ORDER BY timestamp DESC 
            LIMIT 5
        ''')
        data['recent_orders'] = [dict(row) for row in cursor.fetchall()]

        # 5. Inventory Value & Low Stock
        cursor.execute("SELECT SUM(price * quantity * pack_size) as val FROM products")
        res = cursor.fetchone()
        data['inventory_value'] = res['val'] if res and res['val'] else 0.0

        cursor.execute("SELECT COUNT(*) as count FROM products WHERE quantity < 5")
        data['low_stock_count'] = cursor.fetchone()['count']

        conn.close()
        return data

    def create_order(self, business_name, items):
        # Items: [{'product_id': 1, 'quantity': 5}, ...]
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # 1. Create Order
            cursor.execute("INSERT INTO orders (business_name) VALUES (?)", (business_name,))
            order_id = cursor.lastrowid
            
            # 2. Process Items with Warehouse Priority Deduction
            warehouses_order = [1, 2, 3] # Priority: 1 -> 2 -> 3
            
            for item in items:
                pid = item['product_id']
                qty_needed = int(item['quantity']) 
                
                # Check Total Stock first for quick reject?
                cursor.execute("SELECT quantity FROM products WHERE id = ?", (pid,))
                row = cursor.fetchone()
                if not row or row['quantity'] < qty_needed:
                     raise Exception(f"Insufficient total stock for Product {pid}")

                # Deduct from Total
                cursor.execute("UPDATE products SET quantity = quantity - ? WHERE id = ?", (qty_needed, pid))
                
                # Deduct from Warehouses (Cascading)
                remaining_to_deduct = qty_needed
                
                for wid in warehouses_order:
                    if remaining_to_deduct <= 0:
                        break
                        
                    # Get stock in this warehouse
                    cursor.execute("SELECT quantity FROM warehouse_stock WHERE product_id = ? AND warehouse_id = ?", (pid, wid))
                    w_row = cursor.fetchone()
                    w_qty = w_row['quantity'] if w_row else 0
                    
                    if w_qty > 0:
                        deduct = min(w_qty, remaining_to_deduct)
                        # Update warehouse stock
                        cursor.execute("UPDATE warehouse_stock SET quantity = quantity - ? WHERE product_id = ? AND warehouse_id = ?", (deduct, pid, wid))
                        
                        # Add Allocation record
                        cursor.execute('''
                            INSERT INTO order_item_allocations (order_id, product_id, warehouse_id, quantity)
                            VALUES (?, ?, ?, ?)
                        ''', (order_id, pid, wid, deduct))
                        
                        remaining_to_deduct -= deduct
                
                # Note: If remaining_to_deduct > 0 here, it means mismatch between 'products.quantity' and sum of 'warehouse_stock'.
                # We trusted products.quantity earlier. We might have negative stock in warehouses if we force it, 
                # or just deduct from last warehouse to balance? 
                # Ideally we force deduct from W1 if we can't find it, or let it slide. 
                # For now, let's force deduct any remainder from W1 to ensure mathematically sound total.
                if remaining_to_deduct > 0:
                     cursor.execute('''
                        INSERT INTO warehouse_stock (product_id, warehouse_id, quantity) 
                        VALUES (?, ?, ?)
                        ON CONFLICT(product_id, warehouse_id) 
                        DO UPDATE SET quantity = quantity - ?
                    ''', (pid, 1, -remaining_to_deduct, remaining_to_deduct))

                # Add Order Item
                cursor.execute('''
                    INSERT INTO order_items (order_id, product_id, quantity)
                    VALUES (?, ?, ?)
                ''', (order_id, pid, qty_needed))
                
            conn.commit()
            return True, order_id
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

