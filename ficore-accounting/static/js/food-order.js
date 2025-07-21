{% if current_user.is_authenticated %}
// Translation strings
const translations = {
    no_orders: '{{ t("food_order_no_orders", default="No food orders found") | e }}',
    no_items: '{{ t("food_order_no_items", default="No items in this order") | e }}',
    order_created: '{{ t("food_order_created", default="Food order created") | e }}',
    item_added: '{{ t("food_order_item_added", default="Item added to order") | e }}',
    item_updated: '{{ t("food_order_item_updated", default="Item updated") | e }}'
};

let currentOrderId = null;
let offlineData = { orders: [], items: {} };

// CSRF Token Setup
let csrfToken = null;
function setupCSRF() {
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) {
        csrfToken = metaTag.getAttribute('content');
    }
}

// Initialize Food Order
function initFoodOrder() {
    setupCSRF();
    const root = document.getElementById('food-order-root');
    if (!root) return;

    root.innerHTML = `
        <div class="mb-3">
            <h6>{{ t('food_order_create', default='Create New Food Order') | e }}</h6>
            <div class="input-group">
                <input type="text" class="form-control" id="newOrderName" placeholder="{{ t('food_order_name', default='Order Name') | e }}">
                <input type="text" class="form-control" id="newOrderVendor" placeholder="{{ t('food_order_vendor', default='Vendor') | e }}">
                <button class="btn btn-primary" onclick="createFoodOrder()">{{ t('food_order_create', default='Create') | e }}</button>
            </div>
        </div>
        <div id="foodOrders"></div>
        <div id="foodOrderItems" class="mt-3"></div>
        <div class="mt-3">
            <h6>{{ t('food_order_add_item', default='Add Item to Order') | e }}</h6>
            <div class="input-group">
                <input type="text" class="form-control" id="newItemName" placeholder="{{ t('food_order_item_name', default='Item Name') | e }}">
                <input type="number" class="form-control" id="newItemQuantity" placeholder="{{ t('food_order_quantity', default='Quantity') | e }}" min="1">
                <input type="number" class="form-control" id="newItemPrice" placeholder="{{ t('food_order_price', default='Price') | e }}" min="0" step="0.01">
                <button class="btn btn-primary" onclick="addFoodOrderItem()">{{ t('food_order_add', default='Add') | e }}</button>
            </div>
        </div>
    `;

    loadFoodOrders();
}

// Fetch with CSRF token
async function fetchWithCSRF(url, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        'X-CSRF-Token': csrfToken,
        ...options.headers
    };
    return fetch(url, { ...options, headers });
}

// Food Order Functions
function loadFoodOrders() {
    fetchWithCSRF('{{ url_for("personal.food_order.manage_orders") | e }}')
        .then(response => {
            if (response.status === 403) {
                showToast('Insufficient Ficore Credits. Please purchase more.', 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(orders => {
            offlineData.orders = orders;
            localStorage.setItem('foodOrders', JSON.stringify(orders));
            renderFoodOrders(orders);
        })
        .catch(error => {
            console.error('Error loading food orders:', error);
            renderFoodOrders([]);
        });
}

function renderFoodOrders(orders) {
    const foodOrdersEl = document.getElementById('foodOrders');
    if (orders && orders.length > 0) {
        foodOrdersEl.innerHTML = orders.map(order => `
            <div class="food-order-item">
                <span class="fw-semibold">${order.name} (Vendor: ${order.vendor})</span>
                <div>
                    <span class="text-muted">Total: ${format_currency(order.total_cost)}</span>
                    <button class="btn btn-sm btn-outline-primary ms-2" onclick="loadFoodOrderItems('${order.id}')">{{ t('general_view_all', default='View All') | e }}</button>
                </div>
            </div>
        `).join('');
        if (!currentOrderId && orders[0]) {
            loadFoodOrderItems(orders[0].id);
        }
    } else {
        foodOrdersEl.innerHTML = `<div class="text-muted">${translations.no_orders}</div>`;
    }
}

function loadFoodOrderItems(orderId) {
    currentOrderId = orderId;
    fetchWithCSRF('{{ url_for("personal.food_order.manage_items", order_id="") | e }}' + orderId)
        .then(response => {
            if (response.status === 403) {
                showToast('Insufficient Ficore Credits. Please purchase more.', 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(items => {
            offlineData.items[orderId] = items;
            localStorage.setItem('foodOrderItems', JSON.stringify(offlineData.items));
            renderFoodOrderItems(items);
        })
        .catch(error => {
            console.error('Error loading food order items:', error);
            renderFoodOrderItems([]);
        });
}

function renderFoodOrderItems(items) {
    const foodOrderItemsEl = document.getElementById('foodOrderItems');
    if (items && items.length > 0) {
        foodOrderItemsEl.innerHTML = items.map(item => `
            <div class="food-order-item">
                <span class="fw-semibold">${item.name}</span>
                <div class="d-flex align-items-center gap-2">
                    <input type="number" class="form-control" value="${item.quantity}" min="1" onchange="updateFoodOrderItem('${item.id}', 'quantity', this.value)">
                    <input type="number" class="form-control" value="${item.price}" min="0" step="0.01" onchange="updateFoodOrderItem('${item.id}', 'price', this.value)">
                </div>
            </div>
        `).join('');
    } else {
        foodOrderItemsEl.innerHTML = `<div class="text-muted">${translations.no_items}</div>`;
    }
}

function createFoodOrder() {
    const name = document.getElementById('newOrderName').value;
    const vendor = document.getElementById('newOrderVendor').value;
    if (!name || !vendor) {
        showToast('Please provide order name and vendor', 'warning');
        return;
    }
    fetchWithCSRF('{{ url_for("personal.food_order.manage_orders") | e }}', {
        method: 'POST',
        body: JSON.stringify({ name, vendor })
    })
        .then(response => {
            if (response.status === 403) {
                showToast('Insufficient Ficore Credits. Please purchase more.', 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(translations.order_created, 'success');
                document.getElementById('newOrderName').value = '';
                document.getElementById('newOrderVendor').value = '';
                loadFoodOrders();
                loadFinancialSummary();
            }
        })
        .catch(error => {
            console.error('Error creating food order:', error);
            showToast('Error creating food order', 'danger');
        });
}

function addFoodOrderItem() {
    if (!currentOrderId) {
        showToast('Please select an order first', 'warning');
        return;
    }
    const name = document.getElementById('newItemName').value;
    const quantity = document.getElementById('newItemQuantity').value;
    const price = document.getElementById('newItemPrice').value;
    if (!name || !quantity || !price) {
        showToast('Please provide item name, quantity, and price', 'warning');
        return;
    }
    fetchWithCSRF('{{ url_for("personal.food_order.manage_items", order_id="") | e }}' + currentOrderId, {
        method: 'POST',
        body: JSON.stringify({ name, quantity, price })
    })
        .then(response => {
            if (response.status === 403) {
                showToast('Insufficient Ficore Credits. Please purchase more.', 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(translations.item_added, 'success');
                document.getElementById('newItemName').value = '';
                document.getElementById('newItemQuantity').value = '';
                document.getElementById('newItemPrice').value = '';
                loadFoodOrderItems(currentOrderId);
                loadFinancialSummary();
            }
        })
        .catch(error => {
            console.error('Error adding food order item:', error);
            showToast('Error adding item', 'danger');
        });
}

function updateFoodOrderItem(itemId, field, value) {
    fetchWithCSRF('{{ url_for("personal.food_order.manage_items", order_id="") | e }}' + currentOrderId, {
        method: 'PUT',
        body: JSON.stringify({ item_id: itemId, [field]: value })
    })
        .then(response => {
            if (response.status === 403) {
                showToast('Insufficient Ficore Credits. Please purchase more.', 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(translations.item_updated, 'success');
                loadFoodOrderItems(currentOrderId);
                loadFinancialSummary();
            }
        })
        .catch(error => {
            console.error('Error updating food order item:', error);
            showToast('Error updating item', 'danger');
        });
}

function format_currency(value) {
    if (!value && value !== 0) return '0.00';
    value = parseFloat(value);
    if (isNaN(value)) return '0.00';
    return value.toLocaleString('en-NG', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
{% endif %}
