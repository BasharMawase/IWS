const socket = io();
const connectionStatus = document.getElementById('connection-status');
const statusText = document.getElementById('status-text');
const inventoryList = document.getElementById('inventory-list');
const lastScanStatus = document.getElementById('last-scan-status');
const historyBody = document.getElementById('history-body');

let scanBuffer = '';
let scanTimeout;
let selectedProductId = null;
let selectedProductName = '';
let currentBatchBarcode = '';

// --- Socket ---
socket.on('connect', () => {
    connectionStatus.classList.add('connected');
    statusText.textContent = 'מחובר';
    loadData();
});
socket.on('disconnect', () => {
    connectionStatus.classList.remove('connected');
    statusText.textContent = 'מנותק';
});
socket.on('scan_event', (data) => handleIncomingScan(data.barcode));
socket.on('history_update', () => {
    loadData();
});

socket.on('order_update', (data) => {
    console.log("Order update received:", data);
    loadOrders();
    // If order details modal is open for this order, refresh it
    const modal = document.getElementById('order-details-modal');
    if (modal.style.display === 'block' && modal.dataset.orderId == data.order_id) {
        viewOrderDetails(data.order_id);
    }
});

// --- Init ---
async function loadData() {
    await loadWarehouses();
    renderInventory();
    loadOrders();
    loadAnalytics();
}

async function renderInventory() {
    const res = await fetch('/api/products');
    const products = await res.json();
    let html = '';
    products.forEach(item => {
        const isSelected = selectedProductId === item.id;
        const breakdown = item.stock_breakdown || {};
        const q1 = breakdown[1] || 0;
        const q2 = breakdown[2] || 0;
        const q3 = breakdown[3] || 0;
        const packSize = item.pack_size || 1;
        const imgUrl = item.image_path ? `/static/${item.image_path}` : 'https://placehold.co/40x40?text=No+Img';

        html += `
        <tr class="${isSelected ? 'pending-row' : ''}">
            <td><img src="${imgUrl}" alt="img" style="width:40px; height:40px; object-fit: cover; border-radius: 4px;"></td>
            <td><a href="#" onclick="viewInstances(${item.id}, '${item.name}'); return false;" style="color: white; text-decoration: underline;">${item.name}</a></td>
            <td>₪${item.price.toFixed(2)}</td>
            <td><span style="color:#aaa; font-size:0.9em;">x${packSize}</span></td>
            <td><strong style="color:var(--secondary-color);">${(item.quantity || 0) * packSize}</strong></td>
            <!-- New Breakdown Columns -->
            <td style="color:#aaa; font-size:0.9rem;">${q1}</td>
            <td style="color:#aaa; font-size:0.9rem;">${q2}</td>
            <td style="color:#aaa; font-size:0.9rem;">${q3}</td>
            
            <td>
                <button class="btn-link ${isSelected ? 'listening' : ''}" onclick="selectForScanning(${item.id}, '${item.name}')">
                    ${isSelected ? 'סרוק עכשיו...' : '➕ הוסף פריטים'}
                </button>
            </td>
            <td>
                <div class="qty-control">
                    <button class="btn-qty" onclick="updateQuantity(${item.id}, -1)">-</button>
                    <span id="qty-${item.id}">${item.quantity || 0}</span>
                    <button class="btn-qty" onclick="updateQuantity(${item.id}, 1)">+</button>
                </div>
            </td>
        </tr>`;
    });
    inventoryList.innerHTML = html;
}

function updateHistoryTable(history) {
    if (!historyBody) return;
    historyBody.innerHTML = history.map(h => `
        <tr>
            <td>${new Date(h.timestamp).toLocaleTimeString('he-IL')}</td>
            <td><code style="color: #03dac6">${h.barcode}</code></td>
            <td>${h.name || 'לא ידוע'}</td>
            <td><span style="font-weight:bold; color:var(--secondary-color); font-size: 1.1em;">+${h.scanned_amount || 1}</span></td>
            <td><span class="status-badge">נסרק</span></td>
        </tr>
    `).join('');
}

// --- Analytics & Orders ---

async function loadOrders() {
    const container = document.getElementById('orders-list-body');
    if (!container) return;

    try {
        const res = await fetch('/api/orders');
        const orders = await res.json();

        if (orders.length === 0) {
            container.innerHTML = '<tr><td colspan="6" style="text-align:center; padding: 2rem; color: #666;">אין הזמנות עדיין</td></tr>';
            return;
        }

        container.innerHTML = orders.map(o => `
            <tr>
                <td>${o.id}</td>
                <td><strong>${o.business_name}</strong></td>
                <td>${new Date(o.timestamp).toLocaleString('he-IL')}</td>
                <td><span class="status-badge status-${o.status}">${o.status}</span></td>
                <td>${o.total_qty ? (o.total_qty - (o.remaining_qty || 0)) + '/' + o.total_qty : o.item_count}</td>
                <td>
                    <button class="btn btn-sm" onclick="viewOrderDetails(${o.id})">📄 פרטים</button>
                </td>
            </tr>
        `).join('');
    } catch (e) {
        console.error("Error loading orders", e);
    }
}

async function viewOrderDetails(orderId) {
    try {
        const res = await fetch(`/api/orders/${orderId}`);
        const data = await res.json();
        const modal = document.getElementById('order-details-modal');
        modal.dataset.orderId = orderId;

        document.getElementById('details-order-id').textContent = orderId;
        const tbody = document.getElementById('order-details-body');

        // items is now part of the response dict
        const items = data.items || [];
        const allocations = data.allocations || [];

        // Group allocations by product for display
        const pickingStatus = {};
        allocations.forEach(a => {
            if (!pickingStatus[a.product_id]) pickingStatus[a.product_id] = { needed: 0, picked: 0 };
            pickingStatus[a.product_id].needed += a.quantity;
            pickingStatus[a.product_id].picked += a.picked_quantity;
        });

        tbody.innerHTML = items.map(i => `
            <tr>
                <td>${i.name}</td>
                <td>${i.quantity}</td>
                <td>${pickingStatus[i.product_id] ? pickingStatus[i.product_id].picked : 0}</td>
            </tr>
        `).join('');

        modal.style.display = 'block';
    } catch (e) {
        alert("שגיאה בטעינת פרטי הזמנה");
    }
}

function closeOrderDetailsModal() {
    document.getElementById('order-details-modal').classList.remove('show');
}

async function loadAnalytics() {
    try {
        const res = await fetch('/api/analytics');
        const data = await res.json();

        // Update Stats
        document.getElementById('stat-orders').textContent = data.total_orders;
        document.getElementById('stat-revenue').textContent = '₪' + data.total_revenue.toLocaleString();

        // New metrics
        // New metrics - Fixed selectors
        const statCards = document.querySelectorAll('.stat-card');

        // Inventory Value (3rd card)
        if (statCards[2]) {
            const valElem = statCards[2].querySelector('.stat-value');
            if (valElem) valElem.textContent = '₪' + (data.inventory_value || 0).toLocaleString();
        }

        // Low Stock (4th card)
        if (statCards[3]) {
            const alertElem = statCards[3].querySelector('.stat-value');
            if (alertElem) alertElem.textContent = data.low_stock_count || 0;
        }

        // 1. Top Products Chart
        if (data.top_products.length > 0) {
            const topData = [{
                x: data.top_products.map(p => p.name),
                y: data.top_products.map(p => p.total_sold),
                type: 'bar',
                marker: { color: '#03dac6' }
            }];
            const topLayout = {
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                font: { color: '#f0f0f0', family: 'Rubik' },
                margin: { t: 20, b: 40, l: 40, r: 20 },
                autosize: true,
                height: 300,
                xaxis: { title: 'Product', gridcolor: '#444' },
                yaxis: { gridcolor: '#444' }
            };
            Plotly.newPlot('chart-top-products', topData, topLayout, { displayModeBar: false, responsive: true });
        } else {
            document.getElementById('chart-top-products').innerHTML = '<p style="text-align:center; color:#666; padding-top:2rem;">אין נתונים עדיין</p>';
        }

    } catch (e) {
        console.error("Analytics error", e);
    }
}

function updateAnalytics(history) {
    // OLD live update for "Recent Scans Activity"
    // We will keep this as a separate chart
    const activity = {};
    history.forEach(h => {
        const key = h.name || 'לא ידוע';
        activity[key] = (activity[key] || 0) + 1;
    });

    // Only show top 10 recent
    const keys = Object.keys(activity).slice(0, 10);
    const values = keys.map(k => activity[k]);

    const data = [{
        x: keys,
        y: values,
        type: 'bar',
        marker: {
            color: values,
            colorscale: 'Viridis',
            showscale: false
        }
    }];
    const layout = {
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        font: { color: '#f0f0f0', family: 'Rubik' },
        margin: { t: 20, b: 40, l: 40, r: 20 },
        autosize: true,
        height: 250,
        xaxis: { gridcolor: '#444' },
        yaxis: { gridcolor: '#444' }
    };
    Plotly.newPlot('chart-container', data, layout, { displayModeBar: false, responsive: true });

    // Also reload full analytics to keep stats fresh
    loadAnalytics();
}

// --- Interaction ---
function selectForScanning(id, name) {
    if (selectedProductId === id) {
        selectedProductId = null;
        selectedProductName = '';
        lastScanStatus.textContent = 'מצב סריקה: בדיקה (בחר מחלקה להוספה)';
        lastScanStatus.style.color = '#aaa';
    } else {
        selectedProductId = id;
        selectedProductName = name;
        lastScanStatus.textContent = `מוסיף מלאי: סרוק פריטים עבור "${name}"`;
        lastScanStatus.style.color = '#03dac6';
        lastScanStatus.style.fontWeight = 'bold';
    }
    renderInventory();
}

async function addProductClass() {
    const name = document.getElementById('plan-name').value;
    const price = document.getElementById('plan-price').value;
    const packSize = document.getElementById('plan-pack').value;
    const imageInput = document.getElementById('plan-image');

    if (!name) return alert('נא להזין שם');

    const formData = new FormData();
    formData.append('name', name);
    formData.append('price', price || 0);
    formData.append('pack_size', packSize || 1);

    if (imageInput.files[0]) {
        formData.append('image', imageInput.files[0]);
    }

    await fetch('/api/products', {
        method: 'POST',
        body: formData // No headers for FormData, browser sets boundary
    });

    document.getElementById('plan-name').value = '';
    document.getElementById('plan-image').value = ''; // Reset file input

    renderInventory();
}

async function updateQuantity(productId, change) {
    const warehouseId = document.getElementById('warehouse-selector').value || 1;
    await fetch('/api/products/quantity', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId, change, warehouse_id: warehouseId })
    });
    loadData();
}

// --- Batch Modal ---
const batchModal = document.getElementById('batch-modal');
const batchQuantityInput = document.getElementById('batch-quantity');

function openBatchModal(barcode, productName) {
    document.getElementById('batch-product-name').textContent = productName;
    document.getElementById('batch-barcode').textContent = barcode;
    batchQuantityInput.value = 1;
    currentBatchBarcode = barcode;
    batchModal.classList.add('show');
    batchQuantityInput.focus();
    batchQuantityInput.select();
}

function closeBatchModal() {
    batchModal.classList.remove('show');
    currentBatchBarcode = '';
    // Refocus on window for scanning?
}

async function confirmBatchAdd() {
    const quantity = parseInt(batchQuantityInput.value) || 1;
    const warehouseId = document.getElementById('warehouse-selector').value || 1;
    if (quantity < 1) return;
    const res = await fetch('/api/instances', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: selectedProductId, barcode: currentBatchBarcode, quantity, warehouse_id: warehouseId })
    });
    const result = await res.json();
    if (result.status === 'success') {
        const addedMsg = `נוסף ${quantity} x ${currentBatchBarcode}`;
        lastScanStatus.textContent = addedMsg;
        lastScanStatus.style.color = '#bb86fc';
        renderInventory();
        closeBatchModal();
    } else {
        alert('שגיאה: ' + result.message);
    }
}

// --- Order Management ---
const orderModal = document.getElementById('order-modal');
const orderListContainer = document.getElementById('order-list-container');
let allProductsCache = [];
let orderQuantities = {}; // Map productId -> qty

async function openOrderModal() {
    orderModal.classList.add('show');
    document.getElementById('order-business').value = '';
    document.getElementById('order-search').value = '';
    orderQuantities = {};
    updateOrderTotal();

    // Fetch fresh products
    const res = await fetch('/api/products');
    allProductsCache = await res.json();
    renderOrderList(allProductsCache);
}

function closeOrderModal() {
    orderModal.classList.remove('show');
}



function renderOrderList(products) {
    if (products.length === 0) {
        orderListContainer.innerHTML = '<div style="padding:20px; text-align:center; color:#666;">לא נמצאו מוצרים</div>';
        return;
    }

    orderListContainer.innerHTML = products.map(p => {
        const qty = orderQuantities[p.id] || 0;
        const isSelected = qty > 0 ? 'selected-item' : '';
        const packSize = p.pack_size || 1;
        const totalUnits = p.quantity * packSize;

        return `
        <div class="order-item-row ${isSelected}">
            <div class="order-item-info">
                <span class="order-item-name">${p.name}</span>
                <span class="order-item-stock" style="font-size:0.85rem; color:#aaa;">
                    מלאי: <strong>${p.quantity}</strong> מארזים
                    <span style="display:block; font-size:0.8rem; color:#666;">
                        (סה"כ ${totalUnits} יח' | מארז x${packSize})
                    </span>
                </span>
            </div>
            <div class="order-qty-control">
                <input type="number" 
                       class="form-control" 
                       id="order-qty-${p.id}" 
                       value="${qty > 0 ? qty : ''}" 
                       placeholder="כמות (מארזים)"
                       min="0" 
                       max="${p.quantity}"
                       style="width: 100px; text-align: center; font-size: 1.1rem;"
                       oninput="setOrderQty(${p.id}, this.value, ${p.quantity})">
            </div>
        </div>
        `;
    }).join('');
}

function setOrderQty(id, val, maxStock) {
    let numericalVal = parseInt(val);

    if (isNaN(numericalVal) || numericalVal < 0) {
        numericalVal = 0;
    }

    // Optional: cap at max stock?
    // User might want to force an order even if stock is low (backorder), 
    // but our backend logic rejects it. Let's keep UI feedback generic or strict.
    if (numericalVal > maxStock) {
        // user feedback could be added here, e.g. red border
    }

    orderQuantities[id] = numericalVal;

    // Highlight row
    const input = document.getElementById(`order-qty-${id}`);
    const row = input.closest('.order-item-row');

    if (numericalVal > 0) {
        row.classList.add('selected-item');
        if (numericalVal > maxStock) input.style.borderColor = 'red';
        else input.style.borderColor = '#333';
    } else {
        row.classList.remove('selected-item');
        input.style.borderColor = '#333';
    }

    updateOrderTotal();
}

function filterOrderList() {
    const query = document.getElementById('order-search').value.toLowerCase();
    const filtered = allProductsCache.filter(p => p.name.toLowerCase().includes(query));
    renderOrderList(filtered);
}

function changeOrderQty(id, delta, maxStock) {
    const current = orderQuantities[id] || 0;
    let newVal = current + delta;
    if (newVal < 0) newVal = 0;
    if (newVal > maxStock) newVal = maxStock;

    orderQuantities[id] = newVal;

    // Update DOM directly for speed
    document.getElementById(`order-qty-${id}`).textContent = newVal;

    // Highlight row
    const row = document.getElementById(`order-qty-${id}`).closest('.order-item-row');
    if (newVal > 0) row.classList.add('selected-item');
    else row.classList.remove('selected-item');

    updateOrderTotal();
}

function updateOrderTotal() {
    const total = Object.values(orderQuantities).reduce((a, b) => a + b, 0);
    document.getElementById('order-total-count').textContent = total;
}

async function submitOrder() {
    const businessName = document.getElementById('order-business').value;
    if (!businessName) return alert("נא להזין שם עסק");

    const items = [];
    for (const [pid, qty] of Object.entries(orderQuantities)) {
        if (qty > 0) items.push({ product_id: pid, quantity: qty });
    }

    if (items.length === 0) return alert("נא לבחור לפחות פריט אחד.");

    // Bypass Pop-up Blocker: Open window immediately on click
    const printWin = window.open('', '_blank', 'width=900,height=800');
    if (printWin) {
        printWin.document.write('<div style="font-family:sans-serif; text-align:center; margin-top:50px;">Creating order... Please wait...</div>');
    }

    try {
        const res = await fetch('/api/orders', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ business_name: businessName, items: items })
        });
        const result = await res.json();

        if (result.status === 'success') {
            closeOrderModal();
            loadData();

            // Redirect the pre-opened window to the print invoice
            if (printWin) {
                printWin.location.href = `/print/order/${result.order_id}`;
            } else {
                alert("נא לאפשר חלונות קופצים (Pop-ups) כדי להדפיס את ההזמנה");
            }

        } else {
            if (printWin) printWin.close();
            alert("שגיאה: " + result.message);
        }
    } catch (e) {
        if (printWin) printWin.close();
        console.error(e);
        alert("הפעולה נכשלה");
    }
}

// --- Scan Logic ---
function handleIncomingScan(barcode) {
    if (batchModal.classList.contains('show') || orderModal.classList.contains('show')) return;

    if (selectedProductId) {
        openBatchModal(barcode, selectedProductName);
    } else {
        lastScanStatus.textContent = `נסרק: ${barcode} (בחר מחלקה להוספה)`;
        lastScanStatus.style.color = '#aaa';
    }
}

// --- Inputs ---
batchQuantityInput.addEventListener('keydown', (e) => { if (e.key === 'Enter') confirmBatchAdd(); });

// Wedge Listener
document.addEventListener('keydown', (e) => {
    if (e.target.tagName === 'INPUT') return;
    if (e.key === 'Enter') {
        if (scanBuffer.length > 2) handleIncomingScan(scanBuffer);
        scanBuffer = '';
    } else if (e.key.length === 1) {
        scanBuffer += e.key;
        clearTimeout(scanTimeout);
        scanTimeout = setTimeout(() => scanBuffer = '', 100);
    }
});

// Instance Viewer helpers
const instancesModal = document.getElementById('instances-modal');
const instancesList = document.getElementById('instances-list');
async function viewInstances(productId, name) {
    document.getElementById('instance-title').textContent = `היסטוריה: ${name}`;
    instancesModal.classList.add('show');
    const res = await fetch(`/api/products/${productId}/instances`);
    const instances = await res.json();
    instancesList.innerHTML = instances.length ? instances.map(inst => `
        <tr>
            <td>${new Date(inst.scan_time).toLocaleString('he-IL')}</td>
            <td><code style="color: #bb86fc;">${inst.barcode}</code></td>
            <td>${inst.notes || '-'}</td>
        </tr>`).join('') : '<tr><td colspan="3">אין רשומות</td></tr>';
}
function closeInstancesModal() { instancesModal.classList.remove('show'); }

function testScan() {
    const code = prompt("הכנס ברקוד להדמיה:");
    if (code) handleIncomingScan(code);
}

async function loadWarehouses() {
    try {
        const res = await fetch('/api/warehouses');
        const warehouses = await res.json();
        const selector = document.getElementById('warehouse-selector');
        selector.innerHTML = warehouses.map(w => `<option value="${w.id}">${w.name}</option>`).join('');
    } catch (e) {
        console.error("Failed to load warehouses");
    }
}
