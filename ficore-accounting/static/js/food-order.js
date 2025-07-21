let currentOrderId = null;
let offlineData = { orders: [], items: {} };

// CSRF Token Setup
let csrfToken = null;
function setupCSRF() {
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) {
        csrfToken = metaTag.getAttribute('content');
    } else {
        console.warn('CSRF token not found. Requests may fail if CSRF protection is enabled.');
    }
}

// Initialize Food Order
function initFoodOrder() {
    setupCSRF();
    const root = document.getElementById('food-order-root');
    if (!root) {
        console.error('Food order root element not found');
        return;
    }

    root.innerHTML = `
        <div class="mb-3">
            <h6>${window.foodOrderTranslations.food_order_create}</h6>
            <div class="input-group">
                <input type="text" class="form-control" id="newOrderName" placeholder="${window.foodOrderTranslations.food_order_name}">
                <input type="text" class="form-control" id="newOrderVendor" placeholder="${window.foodOrderTranslations.food_order_vendor}">
                <button class="btn btn-primary" onclick="createFoodOrder()">${window.foodOrderTranslations.food_order_create}</button>
            </div>
        </div>
        <div id="foodOrders"></div>
        <div id="foodOrderItems" class="mt-3"></div>
        <div class="mt-3">
            <h6>${window.foodOrderTranslations.food_order_add_item}</h6>
            <div class="input-group">
                <input type="text" class="form-control" id="newItemName" placeholder="${window.foodOrderTranslations.food_order_item_name}">
                <input type="number" class="form-control" id="newItemQuantity" placeholder="${window.foodOrderTranslations.food_order_quantity}" min="1">
                <input type="number" class="form-control" id="newItemPrice" placeholder="${window.foodOrderTranslations.food_order_price}" min="0" step="0.01">
                <button class="btn btn-primary" onclick="addFoodOrderItem()">${window.foodOrderTranslations.food_order_add}</button>
            </div>
        </div>
    `;

    loadFoodOrders();
}

// Fetch with CSRF token
async function fetchWithCSRF(url, options = {}) {
    const headers = {
        'Content-Type': 'application/json',
        ...(csrfToken && { 'X-CSRF-Token': csrfToken }),
        ...options.headers
    };
    return fetch(url, { ...options, headers });
}

// Validate UUID
function isValidUUID(id) {
    const uuidRegex = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
    return id && typeof id === 'string' && uuidRegex.test(id);
}

// Food Order Functions
function loadFoodOrders() {
    fetchWithCSRF(window.apiUrls.manageFoodOrders)
        .then(response => {
            if (!response.ok) {
                if (response.status === 403) {
                    throw new Error(window.foodOrderTranslations.insufficient_credits);
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(orders => {
            offlineData.orders = orders;
            localStorage.setItem('foodOrders', JSON.stringify(orders));
            renderFoodOrders(orders);
        })
        .catch(error => {
            console.error('Error loading food orders:', error.message);
            showToast(error.message || window.foodOrderTranslations.general_error, 'danger');
            renderFoodOrders(offlineData.orders || []);
        });
}

function renderFoodOrders(orders) {
    const foodOrdersEl = document.getElementById('foodOrders');
    if (orders && orders.length > 0) {
        foodOrdersEl.innerHTML = orders.map(order => `
            <div class="food-order-item">
                <span class="fw-semibold">${order.name} (Vendor: ${order.vendor})</span>
                <div>
                    <span class="text-muted">Total: ${formatCurrency(order.total_cost)}</span>
                    <button class="btn btn-sm btn-outline-primary ms-2" onclick="loadFoodOrderItems('${order.id}')">${window.foodOrderTranslations.general_view_all}</button>
                </div>
            </div>
        `).join('');
        if (!currentOrderId && orders[0] && isValidUUID(orders[0].id)) {
            loadFoodOrderItems(orders[0].id);
        }
    } else {
        foodOrdersEl.innerHTML = `<div class="text-muted">${window.foodOrderTranslations.no_orders}</div>`;
    }
}

function loadFoodOrderItems(orderId) {
    if (!isValidUUID(orderId)) {
        showToast(window.foodOrderTranslations.general_select_order, 'warning');
        return;
    }
    currentOrderId = orderId;
    fetchWithCSRF(window.apiUrls.manageFoodOrderItems.replace('{order_id}', orderId))
        .then(response => {
            if (!response.ok) {
                if (response.status === 403) {
                    throw new Error(window.foodOrderTranslations.insufficient_credits);
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(items => {
            offlineData.items[orderId] = items;
            localStorage.setItem('foodOrderItems', JSON.stringify(offlineData.items));
            renderFoodOrderItems(items);
        })
        .catch(error => {
            console.error('Error loading food order items:', error.message);
            showToast(error.message || window.foodOrderTranslations.no_items, 'danger');
            renderFoodOrderItems(offlineData.items[orderId] || []);
        });
}

function renderFoodOrderItems(items) {
    const foodOrderItemsEl = document.getElementById('foodOrderItems');
    if (items && items.length > 0) {
        foodOrderItemsEl.innerHTML = items.map(item => `
            <div class="food-order-item">
                <span class="fw-semibold">${item.name}</span>
                <div class="d-flex align-items-center gap-2">
                    <input type="number" class="form-control" value="${item.quantity}" min="1" onchange="updateFoodOrderItem('${item.item_id}', 'quantity', this.value)">
                    <input type="number" class="form-control" value="${item.price}" min="0" step="0.01" onchange="updateFoodOrderItem('${item.item_id}', 'price', this.value)">
                </div>
            </div>
        `).join('');
    } else {
        foodOrderItemsEl.innerHTML = `<div class="text-muted">${window.foodOrderTranslations.no_items}</div>`;
    }
}

function createFoodOrder() {
    const name = document.getElementById('newOrderName').value.trim();
    const vendor = document.getElementById('newOrderVendor').value.trim();
    if (!name || !vendor) {
        showToast(window.foodOrderTranslations.general_please_provide, 'warning');
        return;
    }
    fetchWithCSRF(window.apiUrls.manageFoodOrders, {
        method: 'POST',
        body: JSON.stringify({ name, vendor })
    })
        .then(response => {
            if (!response.ok) {
                if (response.status === 403) {
                    throw new Error(window.foodOrderTranslations.insufficient_credits);
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(window.foodOrderTranslations.order_created, 'success');
                document.getElementById('newOrderName').value = '';
                document.getElementById('newOrderVendor').value = '';
                loadFoodOrders();
                loadFinancialSummary();
            }
        })
        .catch(error => {
            console.error('Error creating food order:', error.message);
            showToast(error.message || window.foodOrderTranslations.general_error, 'danger');
        });
}

function addFoodOrderItem() {
    if (!isValidUUID(currentOrderId)) {
        showToast(window.foodOrderTranslations.general_select_order, 'warning');
        return;
    }
    const name = document.getElementById('newItemName').value.trim();
    const quantity = parseInt(document.getElementById('newItemQuantity').value);
    const price = parseFloat(document.getElementById('newItemPrice').value);
    if (!name || !quantity || quantity <= 0 || !price || price < 0) {
        showToast(window.foodOrderTranslations.general_please_provide, 'warning');
        return;
    }
    fetchWithCSRF(window.apiUrls.manageFoodOrderItems.replace('{order_id}', currentOrderId), {
        method: 'POST',
        body: JSON.stringify({ name, quantity, price })
    })
        .then(response => {
            if (!response.ok) {
                if (response.status === 403) {
                    throw new Error(window.foodOrderTranslations.insufficient_credits);
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(window.foodOrderTranslations.item_added, 'success');
                document.getElementById('newItemName').value = '';
                document.getElementById('newItemQuantity').value = '';
                document.getElementById('newItemPrice').value = '';
                loadFoodOrderItems(currentOrderId);
                loadFinancialSummary();
            }
        })
        .catch(error => {
            console.error('Error adding food order item:', error.message);
            showToast(error.message || window.foodOrderTranslations.general_error, 'danger');
        });
}

function updateFoodOrderItem(itemId, field, value) {
    if (!isValidUUID(currentOrderId)) {
        showToast(window.foodOrderTranslations.general_select_order, 'warning');
        return;
    }
    const parsedValue = field === 'quantity' ? parseInt(value) : parseFloat(value);
    if (isNaN(parsedValue) || (field === 'quantity' && parsedValue <= 0) || (field === 'price' && parsedValue < 0)) {
        showToast(window.foodOrderTranslations.general_please_provide, 'warning');
        return;
    }
    fetchWithCSRF(window.apiUrls.manageFoodOrderItems.replace('{order_id}', currentOrderId), {
        method: 'PUT',
        body: JSON.stringify({ item_id: itemId, field, [field]: parsedValue })
    })
        .then(response => {
            if (!response.ok) {
                if (response.status === 403) {
                    throw new Error(window.foodOrderTranslations.insufficient_credits);
                }
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(window.foodOrderTranslations.item_updated, 'success');
                loadFoodOrderItems(currentOrderId);
                loadFinancialSummary();
            }
        })
        .catch(error => {
            console.error('Error updating food order item:', error.message);
            showToast(error.message || window.foodOrderTranslations.general_error, 'danger');
        });
}
