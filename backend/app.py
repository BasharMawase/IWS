from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from database import Database
from serial_monitor import SerialMonitor
import threading
import csv
import io
import os
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

socketio = SocketIO(app, cors_allowed_origins="*")

db = Database()

# Serial Configuration
SERIAL_PORT = os.environ.get('SERIAL_PORT', '/dev/tty.usbserial')
BAUD_RATE = int(os.environ.get('BAUD_RATE', 9600))

def handle_serial_scan(barcode):
    print(f"Serial Scan: {barcode}")
    process_scan(barcode)

# Start Serial Monitor
serial_monitor = SerialMonitor(SERIAL_PORT, BAUD_RATE, callback=handle_serial_scan)
# serial_monitor.start() 

def process_scan(barcode):
    # Log raw scan
    db.log_scan(barcode)
    
    # Check if this barcode belongs to an existing instance
    # We need a reverse lookup method or just query?
    # For now, let's just emit the raw barcode. 
    # The frontend will query if it needs details.
    
    scan_data = {
        'barcode': barcode,
        'timestamp': None
    }
    
    socketio.emit('scan_event', scan_data)
    update_dashboard()

def update_dashboard():
    history = db.get_scan_history()
    socketio.emit('history_update', history)

@app.route('/')
def admin_dashboard():
    return render_template('index.html')

# --- Product Class Management ---

@app.route('/api/products', methods=['GET'])
def get_products():
    return jsonify(db.get_all_products())

@app.route('/api/warehouses', methods=['GET'])
def get_warehouses():
    return jsonify(db.get_warehouses())

@app.route('/api/products', methods=['POST'])
def add_product():
    # Handle Form Data
    name = request.form.get('name')
    price = request.form.get('price', 0.0)
    category = request.form.get('category', 'Uncategorized')
    description = request.form.get('description', '')
    pack_size = request.form.get('pack_size', 1)
    
    image_path = None
    if 'image' in request.files:
        file = request.files['image']
        if file and file.filename != '':
            filename = secure_filename(f"{uuid.uuid4()}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_path = f"uploads/{filename}"

    if not name:
        return jsonify({"status": "error", "message": "Name is required"}), 400
        
    try:
        price = float(price)
        pack_size = int(pack_size)
    except:
        price = 0.0
        pack_size = 1

    if db.add_product(name, price, description, category, pack_size, image_path):
        return jsonify({"status": "success", "message": "Product Class added"})
    else:
        return jsonify({"status": "error", "message": "Failed to add product"}), 400

# --- Instance Management ---

@app.route('/api/instances', methods=['POST'])
def add_instance():
    data = request.json
    product_id = data.get('product_id')
    barcode = data.get('barcode')
    quantity = data.get('quantity', 1)
    notes = data.get('notes', '')
    
    warehouse_id = data.get('warehouse_id', 1)
    
    if not product_id or not barcode:
        return jsonify({"status": "error", "message": "Product ID and Barcode required"}), 400
        
    success, result = db.add_instance(product_id, barcode, int(quantity), notes, int(warehouse_id))
    if success:
        update_dashboard()
        return jsonify({"status": "success", "message": result})
    else:
        return jsonify({"status": "error", "message": result}), 400

@app.route('/api/products/<int:product_id>/instances', methods=['GET'])
def get_product_instances(product_id):
    instances = db.get_instances(product_id)
    return jsonify(instances)

@app.route('/api/products/quantity', methods=['POST'])
def update_quantity():
    # Manual override for quantity
    data = request.json
    product_id = data.get('product_id')
    change = data.get('change')
    warehouse_id = data.get('warehouse_id', 1)
    
    if not product_id or change is None:
        return jsonify({"status": "error", "message": "Product ID and change required"}), 400

    if db.update_quantity(product_id, int(change), int(warehouse_id)):
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": "Update failed"}), 500

# --- Order Management ---
@app.route('/api/workers', methods=['GET'])
def get_workers():
    return jsonify(db.get_workers())

@app.route('/api/workers', methods=['POST'])
def add_worker():
    data = request.json
    name = data.get('name')
    if not name:
        return jsonify({"status": "error", "message": "Name required"}), 400
    if db.add_worker(name):
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error", "message": "Could not add worker"}), 400

@app.route('/api/workers/<int:worker_id>', methods=['DELETE'])
def delete_worker(worker_id):
    if db.delete_worker(worker_id):
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "error"}), 400

@app.route('/api/scan/pick', methods=['POST'])
def record_pick():
    data = request.json
    order_id = data.get('order_id')
    barcode = data.get('barcode')
    warehouse_id = data.get('warehouse_id')
    worker_name = data.get('worker_name')
    
    if not all([order_id, barcode, warehouse_id, worker_name]):
        return jsonify({"status": "error", "message": "Missing data"}), 400
        
    success, message = db.record_pick(order_id, int(warehouse_id), barcode, worker_name)
    if success:
        # Emit update so admin/worker screens refresh
        socketio.emit('order_update', {'order_id': order_id})
        return jsonify({"status": "success", "message": message})
    else:
        return jsonify({"status": "error", "message": message}), 400

@app.route('/api/orders/active', methods=['GET'])
def get_active_orders():
    warehouse_id = request.args.get('warehouse_id')
    return jsonify(db.get_active_orders(warehouse_id))

@app.route('/api/orders/<int:order_id>/status', methods=['POST'])
def update_order_status(order_id):
    data = request.json
    status = data.get('status')
    worker = data.get('worker_name')
    
    if not status:
        return jsonify({'status': 'error', 'message': 'Status required'}), 400
        
    if db.update_order_status(order_id, status, worker):
        return jsonify({'status': 'success'})
    else:
        return jsonify({'status': 'error'}), 500


@app.route('/api/orders', methods=['GET'])
def get_orders():
    return jsonify(db.get_orders())

@app.route('/api/orders/<int:order_id>', methods=['GET'])
def get_order_details(order_id):
    details = db.get_order_details(order_id)
    return jsonify(details)

@app.route('/api/analytics', methods=['GET'])
def get_analytics():
    return jsonify(db.get_analytics_data())


@app.route('/api/orders', methods=['POST'])
def create_order():
    data = request.json
    business = data.get('business_name')
    items = data.get('items') # List of {product_id, quantity}
    
    if not business or not items:
        return jsonify({"status": "error", "message": "Business name and Items required"}), 400
        
    success, result = db.create_order(business, items)
    if success:
        # Stock has changed, broadcast update
        socketio.emit('history_update', db.get_scan_history()) # Refresh history just in case
        return jsonify({"status": "success", "order_id": result})
    else:
        return jsonify({"status": "error", "message": result}), 400

@app.route('/print/order/<int:order_id>')
def print_order(order_id):
    # Fetch details manually to pass to template
    conn = db._get_connection()
    cursor = conn.cursor()
    
    # Get Order Info
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    
    # Get Items
    cursor.execute('''
        SELECT oi.quantity, p.name, p.id as product_id 
        FROM order_items oi
        JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = ?
    ''', (order_id,))
    items = cursor.fetchall()
    conn.close()
    
    if not order:
        return "Order not found", 404
        
    return render_template('print_order.html', order=dict(order), items=[dict(i) for i in items])

# --- Import ---

@app.route('/api/import', methods=['POST'])
def import_data():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "No file selected"}), 400

    if file:
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        count = 0
        
        for row in csv_input:
            # Flexible Key Mapping
            name = row.get('name') or row.get('Name')
            if not name: continue
            
            try:
                price = float(row.get('price') or row.get('Price') or 0.0)
            except:
                price = 0.0
                
            category = row.get('category') or row.get('Category') or 'Uncategorized'
            
            # Create Product Class
            if db.add_product(name, price, "", category):
                count += 1
        
        return jsonify({
            "status": "success", 
            "imported_count": count, 
            "message": f"Imported {count} product classes."
        })

@socketio.on('connect')
def test_connect():
    print('Client connected')
    emit('history_update', db.get_scan_history())

if __name__ == '__main__':
    try:
        serial_monitor.start()
    except Exception as e:
        print(f"Could not start serial monitor: {e}")
        
    socketio.run(app, debug=False, host='0.0.0.0', port=5001)
