(function () {
    // Private scope to avoid conflicts
    let currentOrderId = null;
    let offlineData = { orders: [], items: {} };

    // CSRF Token Setup
    let csrfToken = null;
    function setupCSRF() {
        const metaTag = document.querySelector('meta[name="csrf-token"]');
        if (metaTag) {
            csrfToken = metaTag.getAttribute('content');
        } else {
            console.warn('CSRF token not found in meta tag');
        }
    }

    // Initialize Food Order
    function initFoodOrder() {
        try {
            if (!window.foodOrderTranslations || !window.apiUrls) {
                console.error('Food order translations or API URLs not defined');
                showToast('Configuration error: Translations or APIs missing', 'danger');
                return;
            }

            const root = document.getElementById('food-order-root');
            if (!root) {
                console.error('Food order root element not found');
                showToast('Error: Food order container not found', 'danger');
                return;
            }

            root.innerHTML = `
                <ul class="nav nav-tabs mb-3" id="foodOrderTabs" role="tablist">
                    <li class="nav-item" role="presentation">
                        <button class="nav-link active" id="orders-tab" data-bs-toggle="tab" data-bs-target="#orders" type="button" role="tab">${window.foodOrderTranslations.food_order_create}</button>
                    </li>
                    <li class="nav-item" role="presentation">
                        <button class="nav-link" id="manage-orders-tab" data-bs-toggle="tab" data-bs-target="#manage-orders" type="button" role="tab">${window.foodOrderTranslations.general_view_all}</button>
                    </li>
                </ul>
                <div class="tab-content" id="foodOrderTabContent">
                    <div class="tab-pane fade show active" id="orders" role="tabpanel" aria-labelledby="orders-tab">
                        <div class="mb-3">
                            <h6>${window.foodOrderTranslations.food_order_create}</h6>
                            <div class="input-group">
                                <input type="text" class="form-control" id="newOrderName" placeholder="${window.foodOrderTranslations.food_order_name}">
                                <input type="text" class="form-control" id="newOrderVendor" placeholder="${window.foodOrderTranslations.food_order_vendor}">
                                <button class="btn btn-primary" onclick="foodOrderModule.createFoodOrder()">${window.foodOrderTranslations.food_order_create}</button>
                            </div>
                        </div>
                        <div id="foodOrders"></div>
                        <div id="foodOrderItems" class="mt-3"></div>
                        <div class="mt-3">
                            <h6>${window.foodOrderTranslations.food_order_add_item}</h6>
                            <div class="input-group">
                                <input type="text" class="form-control" id="newOrderItemName" placeholder="${window.foodOrderTranslations.food_order_item_name}">
                                <input type="number" class="form-control" id="newOrderItemQuantity" placeholder="${window.foodOrderTranslations.food_order_quantity}" min="1">
                                <input type="number" class="form-control" id="newOrderItemPrice" placeholder="${window.foodOrderTranslations.food_order_price}" min="0" step="0.01">
                                <button class="btn btn-primary" onclick="foodOrderModule.addFoodOrderItem()">${window.foodOrderTranslations.food_order_add}</button>
                            </div>
                        </div>
                    </div>
                    <div class="tab-pane fade" id="manage-orders" role="tabpanel" aria-labelledby="manage-orders-tab">
                        <div class="mb-3">
                            <h6>${window.foodOrderTranslations.general_view_all}</h6>
                            <div id="manageFoodOrders"></div>
                        </div>
                    </div>
                </div>
            `;

            loadFoodOrders();
            loadManageOrders();

            // Initialize Bootstrap tabs
            const tabEl = document.querySelector('#foodOrderTabs');
            if (tabEl) {
                new bootstrap.Tab(tabEl.querySelector('.nav-link.active')).show();
            }
        } catch (error) {
            console.error('Error initializing food order:', error);
            showToast(window.foodOrderTranslations.general_error, 'danger');
        }
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
        fetchWithCSRF(window.apiUrls.manageFoodOrders)
            .then(response => {
                if (response.status === 403) {
                    showToast(window.foodOrderTranslations.insufficient_credits, 'error');
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
                    <span class="fw-semibold">${order.name} (${order.vendor})</span>
                    <div>
                        <span class="text-muted">Total: ${format_currency(order.total_cost)}</span>
                        <button class="btn btn-sm btn-outline-primary ms-2" onclick="foodOrderModule.loadFoodOrderItems('${order.id}')">${window.foodOrderTranslations.general_view_all}</button>
                    </div>
                </div>
            `).join('');
            if (!currentOrderId && orders[0]) {
                loadFoodOrderItems(orders[0].id);
            }
        } else {
            foodOrdersEl.innerHTML = `<div class="text-muted">${window.foodOrderTranslations.no_orders}</div>`;
        }
    }

    function loadManageOrders() {
        fetchWithCSRF(window.apiUrls.manageFoodOrders)
            .then(response => {
                if (response.status === 403) {
                    showToast(window.foodOrderTranslations.insufficient_credits, 'error');
                    return Promise.reject(new Error('Unauthorized'));
                }
                return response.json();
            })
            .then(orders => {
                offlineData.orders = orders;
                localStorage.setItem('foodOrders', JSON.stringify(orders));
                renderManageOrders(orders);
            })
            .catch(error => {
                console.error('Error loading food orders for management:', error);
                renderManageOrders([]);
            });
    }

    function renderManageOrders(orders) {
        const manageOrdersEl = document.getElementById('manageFoodOrders');
        if (orders && orders.length > 0) {
            manageOrdersEl.innerHTML = orders.map(order => `
                <div class="food-order-item">
                    <span class="fw-semibold">${order.name} (${order.vendor})</span>
                    <div>
                        <span class="text-muted">Total: ${format_currency(order.total_cost)}</span>
                        <button class="btn btn-sm btn-outline-danger ms-2" onclick="foodOrderModule.deleteFoodOrder('${order.id}', '${order.name}')">Delete</button>
                    </div>
                </div>
            `).join('');
        } else {
            manageOrdersEl.innerHTML = `<div class="text-muted">${window.foodOrderTranslations.no_orders}</div>`;
        }
    }

    function deleteFoodOrder(orderId, orderName) {
        if (!confirm(`Delete food order "${orderName}"?`)) {
            return;
        }
        fetchWithCSRF(window.apiUrls.manageFoodOrders + `/${orderId}`, {
            method: 'DELETE'
        })
            .then(response => {
                if (response.status === 403) {
                    showToast(window.foodOrderTranslations.insufficient_credits, 'error');
                    return Promise.reject(new Error('Unauthorized'));
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    showToast(data.error, 'danger');
                } else {
                    showToast('Food order deleted', 'success');
                    if (currentOrderId === orderId) {
                        currentOrderId = null;
                        document.getElementById('foodOrderItems').innerHTML = '';
                    }
                    loadFoodOrders();
                    loadManageOrders();
                    loadFinancialSummary();
                }
            })
            .catch(error => {
                console.error('Error deleting food order:', error);
                showToast(window.foodOrderTranslations.general_error, 'danger');
            });
    }

    function loadFoodOrderItems(orderId) {
        currentOrderId = orderId;
        fetchWithCSRF(window.apiUrls.manageFoodOrderItems.replace('{order_id}', orderId))
            .then(response => {
                if (response.status === 403) {
                    showToast(window.foodOrderTranslations.insufficient_credits, 'error');
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
                        <input type="number" class="form-control" value="${item.quantity}" min="1" onchange="foodOrderModule.updateFoodOrderItem('${item.item_id}', 'quantity', this.value)">
                        <input type="number" class="form-control" value="${item.price}" min="0" step="0.01" onchange="foodOrderModule.updateFoodOrderItem('${item.item_id}', 'price', this.value)">
                    </div>
                </div>
            `).join('');
        } else {
            foodOrderItemsEl.innerHTML = `<div class="text-muted">${window.foodOrderTranslations.no_items}</div>`;
        }
    }

    function createFoodOrder() {
        const name = document.getElementById('newOrderName').value;
        const vendor = document.getElementById('newOrderVendor').value;
        if (!name || !vendor) {
            showToast(window.foodOrderTranslations.general_please_provide, 'warning');
            return;
        }
        fetchWithCSRF(window.apiUrls.manageFoodOrders, {
            method: 'POST',
            body: JSON.stringify({ name, vendor })
        })
            .then(response => {
                if (response.status === 403) {
                    showToast(window.foodOrderTranslations.insufficient_credits, 'error');
                    return Promise.reject(new Error('Unauthorized'));
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
                    loadManageOrders();
                    loadFinancialSummary();
                }
            })
            .catch(error => {
                console.error('Error creating food order:', error);
                showToast(window.foodOrderTranslations.general_error, 'danger');
            });
    }

    function addFoodOrderItem() {
        if (!currentOrderId) {
            showToast(window.foodOrderTranslations.general_select_order, 'warning');
            return;
        }
        const name = document.getElementById('newOrderItemName').value;
        const quantity = document.getElementById('newOrderItemQuantity').value;
        const price = document.getElementById('newOrderItemPrice').value;
        if (!name || !quantity || !price) {
            showToast(window.foodOrderTranslations.general_please_provide, 'warning');
            return;
        }
        fetchWithCSRF(window.apiUrls.manageFoodOrderItems.replace('{order_id}', currentOrderId), {
            method: 'POST',
            body: JSON.stringify({ name, quantity, price })
        })
            .then(response => {
                if (response.status === 403) {
                    showToast(window.foodOrderTranslations.insufficient_credits, 'error');
                    return Promise.reject(new Error('Unauthorized'));
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    showToast(data.error, 'danger');
                } else {
                    showToast(window.foodOrderTranslations.item_added, 'success');
                    document.getElementById('newOrderItemName').value = '';
                    document.getElementById('newOrderItemQuantity').value = '';
                    document.getElementById('newOrderItemPrice').value = '';
                    loadFoodOrderItems(currentOrderId);
                    loadFinancialSummary();
                }
            })
            .catch(error => {
                console.error('Error adding food order item:', error);
                showToast(window.foodOrderTranslations.general_error, 'danger');
            });
    }

    function updateFoodOrderItem(itemId, field, value) {
        fetchWithCSRF(window.apiUrls.manageFoodOrderItems.replace('{order_id}', currentOrderId), {
            method: 'PUT',
            body: JSON.stringify({ item_id: itemId, [field]: value })
        })
            .then(response => {
                if (response.status === 403) {
                    showToast(window.foodOrderTranslations.insufficient_credits, 'error');
                    return Promise.reject(new Error('Unauthorized'));
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
                console.error('Error updating food order item:', error);
                showToast(window.foodOrderTranslations.general_error, 'danger');
            });
    }

    function loadOfflineData() {
        const cachedOrders = localStorage.getItem('foodOrders');
        const cachedItems = localStorage.getItem('foodOrderItems');
        if (cachedOrders) {
            offlineData.orders = JSON.parse(cachedOrders);
            renderFoodOrders(offlineData.orders);
            renderManageOrders(offlineData.orders);
        }
        if (cachedItems) {
            offlineData.items = JSON.parse(cachedItems);
            if (currentOrderId && offlineData.items[currentOrderId]) {
                renderFoodOrderItems(offlineData.items[currentOrderId]);
            }
        }
    }

    function format_currency(value) {
        if (!value && value !== 0) return '0.00';
        value = parseFloat(value);
        if (isNaN(value)) return '0.00';
        return value.toLocaleString('en-NG', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function formatTimeAgo(dateStr) {
        const now = new Date();
        const date = new Date(dateStr);
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);

        if (diffMins < 1) return window.foodOrderTranslations.just_now;
        if (diffMins < 60) return `${diffMins} ${window.foodOrderTranslations.minutes_ago}`;
        if (diffHours < 24) return `${diffHours} ${window.foodOrderTranslations.hours_ago}`;
        return `${diffDays} ${window.foodOrderTranslations.days_ago}`;
    }

    // Expose functions to the global scope with a namespace
    window.foodOrderModule = {
        initFoodOrder,
        createFoodOrder,
        addFoodOrderItem,
        updateFoodOrderItem,
        loadFoodOrderItems,
        deleteFoodOrder
    };
})();
