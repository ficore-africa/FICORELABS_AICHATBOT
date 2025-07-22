(function () {
    // Private scope to avoid conflicts
    let currentListId = null;
    let offlineData = { lists: [], items: {} };
    let deletionTimer = null;

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

    // Debounce utility to prevent rapid API calls
    function debounce(func, delay) {
        let timeoutId;
        return function (...args) {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => func.apply(this, args), delay);
        };
    }

    // Initialize Grocery Planner
    function initGroceryPlanner() {
        setupCSRF();
        const root = document.getElementById('grocery-planner-root');
        if (!root) {
            console.error('Grocery planner root element not found');
            showToast(window.groceryTranslations.general_error || 'Error initializing grocery planner', 'danger');
            return;
        }

        root.innerHTML = `
            <ul class="nav nav-tabs mb-3" id="groceryTabs" role="tablist">
                <li class="nav-item" role="presentation">
                    <button class="nav-link active" id="lists-tab" data-bs-toggle="tab" data-bs-target="#lists" type="button" role="tab">${window.groceryTranslations.grocery_lists || 'Lists'}</button>
                </li>
                <li class="nav-item" role="presentation">
                    <button class="nav-link" id="manage-list-tab" data-bs-toggle="tab" data-bs-target="#manage-list" type="button" role="tab">${window.groceryTranslations.grocery_manage_list || 'Manage List'}</button>
                </li>
            </ul>
            <div class="tab-content" id="groceryTabContent">
                <div class="tab-pane fade show active" id="lists" role="tabpanel" aria-labelledby="lists-tab">
                    <div class="mb-3">
                        <h6>${window.groceryTranslations.grocery_create_list || 'Create New List'}</h6>
                        <div class="input-group">
                            <input type="text" class="form-control" id="newListName" placeholder="${window.groceryTranslations.grocery_list_name || 'List Name'}">
                            <input type="number" class="form-control" id="newListBudget" placeholder="${window.groceryTranslations.grocery_budget || 'Budget'}" min="0" step="0.01">
                            <button class="btn btn-primary" onclick="groceryModule.createGroceryList()">${window.groceryTranslations.grocery_create || 'Create'}</button>
                        </div>
                    </div>
                    <div id="groceryLists"></div>
                    <div id="groceryItems" class="mt-3"></div>
                    <div class="mt-3">
                        <h6>${window.groceryTranslations.grocery_add_item || 'Add Item'}</h6>
                        <div class="input-group">
                            <input type="text" class="form-control" id="newItemName" placeholder="${window.groceryTranslations.grocery_item_name || 'Item Name'}">
                            <input type="number" class="form-control" id="newItemQuantity" placeholder="${window.groceryTranslations.grocery_quantity || 'Quantity'}" min="1">
                            <input type="number" class="form-control" id="newItemPrice" placeholder="${window.groceryTranslations.grocery_price || 'Price'}" min="0" step="0.01">
                            <select class="form-select" id="newItemStatus">
                                <option value="to_buy">${window.groceryTranslations.grocery_to_buy || 'To Buy'}</option>
                                <option value="in_pantry">${window.groceryTranslations.grocery_in_pantry || 'In Pantry'}</option>
                                <option value="bought">${window.groceryTranslations.grocery_bought || 'Bought'}</option>
                            </select>
                            <input type="text" class="form-control" id="newItemStore" placeholder="${window.groceryTranslations.grocery_store || 'Store'}">
                            <button class="btn btn-primary" onclick="groceryModule.addGroceryItem()">${window.groceryTranslations.grocery_add || 'Add'}</button>
                        </div>
                    </div>
                    <div class="mt-3">
                        <h6>${window.groceryTranslations.grocery_share_list || 'Share List'}</h6>
                        <div class="input-group">
                            <input type="email" class="form-control" id="shareListEmail" placeholder="${window.groceryTranslations.grocery_collaborator_email || 'Collaborator Email'}">
                            <button class="btn btn-primary" onclick="groceryModule.shareGroceryList()">${window.groceryTranslations.grocery_share || 'Share'}</button>
                        </div>
                    </div>
                </div>
                <div class="tab-pane fade" id="manage-list" role="tabpanel" aria-labelledby="manage-list-tab">
                    <div class="mb-3">
                        <h6>${window.groceryTranslations.grocery_manage_list || 'Manage Lists'}</h6>
                        <div id="manageGroceryLists"></div>
                    </div>
                </div>
            </div>
            <div class="modal fade" id="listDetailsModal" tabindex="-1" aria-labelledby="listDetailsModalLabel" aria-hidden="true">
                <div class="modal-dialog modal-lg">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="listDetailsModalLabel">${window.groceryTranslations.grocery_list_details || 'List Details'}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body" id="listDetailsModalBody"></div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">${window.groceryTranslations.grocery_close || 'Close'}</button>
                        </div>
                    </div>
                </div>
            </div>
            <div class="modal fade" id="deleteConfirmModal" tabindex="-1" aria-labelledby="deleteConfirmModalLabel" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="deleteConfirmModalLabel">${window.groceryTranslations.grocery_confirm_delete || 'Confirm Delete'}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <p id="deleteConfirmMessage"></p>
                            <p id="countdownMessage"></p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">${window.groceryTranslations.grocery_cancel || 'Cancel'}</button>
                            <button type="button" class="btn btn-danger" id="confirmDeleteButton">${window.groceryTranslations.grocery_delete || 'Delete'}</button>
                        </div>
                    </div>
                </div>
            </div>
            <div class="modal fade" id="editListModal" tabindex="-1" aria-labelledby="editListModalLabel" aria-hidden="true">
                <div class="modal-dialog">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title" id="editListModalLabel">${window.groceryTranslations.grocery_edit_list || 'Edit List'}</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal" aria-label="Close"></button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-3">
                                <label for="editListName" class="form-label">${window.groceryTranslations.grocery_list_name || 'List Name'}</label>
                                <input type="text" class="form-control" id="editListName">
                            </div>
                            <div class="mb-3">
                                <label for="editListBudget" class="form-label">${window.groceryTranslations.grocery_budget || 'Budget'}</label>
                                <input type="number" class="form-control" id="editListBudget" min="0" step="0.01">
                            </div>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">${window.groceryTranslations.grocery_cancel || 'Cancel'}</button>
                            <button type="button" class="btn btn-primary" id="saveEditListButton">${window.groceryTranslations.grocery_save || 'Save'}</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        loadGroceryLists();
        loadManageLists();

        // Initialize Bootstrap tabs
        const tabEl = document.querySelector('#groceryTabs');
        if (tabEl) {
            new bootstrap.Tab(tabEl.querySelector('.nav-link.active')).show();
        }
    }

    // Fetch with CSRF token
    async function fetchWithCSRF(url, options = {}) {
        const headers = {
            'Content-Type': 'application/json',
            'X-CSRF-Token': csrfToken,
            ...options.headers
        };
        if (options.responseType === 'blob') {
            delete headers['Content-Type'];
        }
        return fetch(url, { ...options, headers });
    }

    // Grocery Planner Functions
    function loadGroceryLists() {
        fetchWithCSRF(`${window.apiUrls.manageGroceryLists}?status=active`)
            .then(response => {
                if (response.status === 403) {
                    showToast(window.groceryTranslations.insufficient_credits || 'Insufficient credits', 'error');
                    return Promise.reject(new Error('Unauthorized'));
                }
                return response.json();
            })
            .then(lists => {
                offlineData.lists = lists;
                localStorage.setItem('groceryLists', JSON.stringify(lists));
                renderGroceryLists(lists);
            })
            .catch(error => {
                console.error('Error loading grocery lists:', error);
                renderGroceryLists([]);
            });
    }

    function renderGroceryLists(lists) {
        const groceryListsEl = document.getElementById('groceryLists');
        if (lists && lists.length > 0) {
            groceryListsEl.innerHTML = lists.map(list => `
                <div class="grocery-item">
                    <span class="fw-semibold">${list.name}</span>
                    <div class="d-flex align-items-center gap-2">
                        <span class="text-muted">Budget: ${format_currency(list.budget)}</span>
                        <span class="ms-2">Spent: ${format_currency(list.total_spent)}</span>
                        <button class="btn btn-sm btn-outline-primary ms-2" onclick="groceryModule.loadGroceryItems('${list.id}')">${window.groceryTranslations.general_view_all || 'View All'}</button>
                        <button class="btn btn-sm btn-outline-info ms-2" onclick="groceryModule.showListDetails('${list.id}')">${window.groceryTranslations.grocery_view_details || 'View Details'}</button>
                        <button class="btn btn-sm btn-outline-success ms-2" onclick="groceryModule.saveGroceryList('${list.id}')" ${list.status === 'saved' ? 'disabled' : ''}>${window.groceryTranslations.grocery_save || 'Save'}</button>
                    </div>
                </div>
            `).join('');
            if (!currentListId && lists[0]) {
                loadGroceryItems(lists[0].id);
            }
        } else {
            groceryListsEl.innerHTML = `<div class="text-muted">${window.groceryTranslations.no_lists || 'No lists available'}</div>`;
        }
    }

    function loadManageLists() {
        fetchWithCSRF(`${window.apiUrls.manageGroceryLists}?status=saved`)
            .then(response => {
                if (response.status === 403) {
                    showToast(window.groceryTranslations.insufficient_credits || 'Insufficient credits', 'error');
                    return Promise.reject(new Error('Unauthorized'));
                }
                return response.json();
            })
            .then(lists => {
                offlineData.lists = lists;
                localStorage.setItem('manageGroceryLists', JSON.stringify(lists));
                renderManageLists(lists);
            })
            .catch(error => {
                console.error('Error loading manage lists:', error);
                renderManageLists([]);
            });
    }

    function renderManageLists(lists) {
        const manageListsEl = document.getElementById('manageGroceryLists');
        if (lists && lists.length > 0) {
            manageListsEl.innerHTML = lists.map(list => `
                <div class="grocery-item">
                    <span class="fw-semibold">${list.name}</span>
                    <div class="d-flex align-items-center gap-2">
                        <span class="text-muted">Budget: ${format_currency(list.budget)}</span>
                        <span class="ms-2">Created: ${formatTimeAgo(list.created_at)}</span>
                        <button class="btn btn-sm btn-outline-primary ms-2" onclick="groceryModule.editGroceryList('${list.id}', '${list.name}', ${list.budget})">${window.groceryTranslations.grocery_edit || 'Edit'}</button>
                        <button class="btn btn-sm btn-outline-info ms-2" onclick="groceryModule.showListDetails('${list.id}')">${window.groceryTranslations.grocery_view_details || 'View Details'}</button>
                        <button class="btn btn-sm btn-outline-info ms-2" onclick="groceryModule.exportGroceryListToPDF('${list.id}')">${window.groceryTranslations.grocery_export_pdf || 'Export to PDF'}</button>
                        <button class="btn btn-sm btn-outline-danger ms-2" onclick="groceryModule.initiateDeleteGroceryList('${list.id}', '${list.name}')">${window.groceryTranslations.grocery_delete || 'Delete'}</button>
                    </div>
                </div>
            `).join('');
        } else {
            manageListsEl.innerHTML = `<div class="text-muted">${window.groceryTranslations.no_lists || 'No lists available'}</div>`;
        }
    }

    const createGroceryList = debounce(function () {
        const name = document.getElementById('newListName').value;
        const budget = document.getElementById('newListBudget').value;
        if (!name || !budget) {
            showToast(window.groceryTranslations.general_please_provide || 'Please provide both name and budget', 'warning');
            return;
        }
        fetchWithCSRF(window.apiUrls.manageGroceryLists, {
            method: 'POST',
            body: JSON.stringify({ name, budget })
        })
            .then(response => {
                if (response.status === 403) {
                    showToast(window.groceryTranslations.insufficient_credits || 'Insufficient credits', 'error');
                    return Promise.reject(new Error('Unauthorized'));
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    showToast(data.error, 'danger');
                } else {
                    showToast(window.groceryTranslations.grocery_list_created || 'List created successfully', 'success');
                    document.getElementById('newListName').value = '';
                    document.getElementById('newListBudget').value = '';
                    loadGroceryLists();
                    loadManageLists();
                }
            })
            .catch(error => {
                console.error('Error creating grocery list:', error);
                showToast(window.groceryTranslations.general_error || 'An error occurred', 'danger');
            });
    }, 500);

    const saveGroceryList = debounce(function (listId) {
        fetchWithCSRF(`${window.apiUrls.manageGroceryLists}/${listId}/save`, {
            method: 'PUT'
        })
            .then(response => {
                if (response.status === 403) {
                    showToast(window.groceryTranslations.insufficient_credits || 'Insufficient credits', 'error');
                    return Promise.reject(new Error('Unauthorized'));
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    showToast(data.error, 'danger');
                } else {
                    showToast(window.groceryTranslations.grocery_list_saved || 'List saved successfully', 'success');
                    loadGroceryLists();
                    loadManageLists();
                }
            })
            .catch(error => {
                console.error('Error saving grocery list:', error);
                showToast(window.groceryTranslations.general_error || 'An error occurred', 'danger');
            });
    }, 500);

    const editGroceryList = debounce(function (listId, currentName, currentBudget) {
        const modal = new bootstrap.Modal(document.getElementById('editListModal'));
        const nameInput = document.getElementById('editListName');
        const budgetInput = document.getElementById('editListBudget');
        nameInput.value = currentName || '';
        budgetInput.value = currentBudget || 0;
        document.getElementById('saveEditListButton').onclick = () => {
            const name = nameInput.value.trim();
            const budget = parseFloat(budgetInput.value);
            if (!name || isNaN(budget) || budget < 0) {
                showToast(window.groceryTranslations.general_please_provide || 'Please provide a valid name and budget', 'warning');
                return;
            }
            fetchWithCSRF(`${window.apiUrls.manageGroceryLists}/${listId}/edit`, {
                method: 'PUT',
                body: JSON.stringify({ name, budget })
            })
                .then(response => {
                    if (response.status === 403) {
                        showToast(window.groceryTranslations.insufficient_credits || 'Insufficient credits', 'error');
                        return Promise.reject(new Error('Unauthorized'));
                    }
                    if (response.status === 400) {
                        return response.json().then(data => {
                            throw new Error(data.error || 'Invalid input');
                        });
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.error) {
                        showToast(data.error, 'danger');
                    } else {
                        showToast(window.groceryTranslations.grocery_list_updated || 'List updated successfully', 'success');
                        modal.hide();
                        loadGroceryLists();
                        loadManageLists();
                    }
                })
                .catch(error => {
                    console.error('Error editing grocery list:', error);
                    showToast(error.message || window.groceryTranslations.general_error || 'An error occurred', 'danger');
                });
        };
        modal.show();
    }, 500);

    const exportGroceryListToPDF = debounce(function (listId) {
        fetchWithCSRF(`${window.apiUrls.manageGroceryLists}/${listId}/export_pdf`, {
            method: 'GET',
            responseType: 'blob'
        })
            .then(response => {
                if (response.status === 403) {
                    showToast(window.groceryTranslations.insufficient_credits || 'Insufficient credits', 'error');
                    return Promise.reject(new Error('Unauthorized'));
                }
                return response.blob();
            })
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const link = document.createElement('a');
                link.href = url;
                link.download = `grocery_list_${listId}.pdf`;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                window.URL.revokeObjectURL(url);
                showToast(window.groceryTranslations.grocery_export_pdf_success || 'PDF exported successfully', 'success');
            })
            .catch(error => {
                console.error('Error exporting grocery list to PDF:', error);
                showToast(window.groceryTranslations.grocery_export_error || 'Error exporting to PDF', 'danger');
            });
    }, 500);

    function initiateDeleteGroceryList(listId, listName) {
        const modal = new bootstrap.Modal(document.getElementById('deleteConfirmModal'));
        document.getElementById('deleteConfirmMessage').innerText = `${window.groceryTranslations.grocery_confirm_delete_message || 'Are you sure you want to delete'} "${listName}"?`;
        document.getElementById('countdownMessage').innerText = '';
        document.getElementById('confirmDeleteButton').onclick = () => {
            fetchWithCSRF(`${window.apiUrls.manageGroceryLists}/${listId}/pending_delete`, {
                method: 'POST'
            })
                .then(response => {
                    if (response.status === 403) {
                        showToast(window.groceryTranslations.insufficient_credits || 'Insufficient credits', 'error');
                        return Promise.reject(new Error('Unauthorized'));
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.error) {
                        showToast(data.error, 'danger');
                        modal.hide();
                    } else {
                        showToast(window.groceryTranslations.grocery_list_deletion_initiated || 'Deletion initiated', 'info');
                        startDeletionCountdown(listId, modal);
                    }
                })
                .catch(error => {
                    console.error('Error initiating list deletion:', error);
                    showToast(window.groceryTranslations.general_error || 'An error occurred', 'danger');
                    modal.hide();
                });
        };
        modal.show();
    }

    function startDeletionCountdown(listId, modal) {
        let remainingSeconds = 20;
        document.getElementById('confirmDeleteButton').disabled = true;
        document.getElementById('countdownMessage').innerText = `${window.groceryTranslations.grocery_deleting_in || 'Deleting in'} ${remainingSeconds} ${window.groceryTranslations.grocery_seconds || 'seconds'}`;
        
        deletionTimer = setInterval(() => {
            fetchWithCSRF(`${window.apiUrls.manageGroceryLists}/${listId}/pending_delete/status`)
                .then(response => response.json())
                .then(data => {
                    if (!data.pending) {
                        clearInterval(deletionTimer);
                        modal.hide();
                        showToast(window.groceryTranslations.grocery_list_deleted || 'List deleted', 'success');
                        if (currentListId === listId) {
                            currentListId = null;
                            document.getElementById('groceryItems').innerHTML = '';
                        }
                        loadGroceryLists();
                        loadManageLists();
                    } else {
                        remainingSeconds = data.remaining_seconds;
                        document.getElementById('countdownMessage').innerText = `${window.groceryTranslations.grocery_deleting_in || 'Deleting in'} ${remainingSeconds} ${window.groceryTranslations.grocery_seconds || 'seconds'}`;
                        if (remainingSeconds <= 0) {
                            clearInterval(deletionTimer);
                            modal.hide();
                            showToast(window.groceryTranslations.grocery_list_deleted || 'List deleted', 'success');
                            if (currentListId === listId) {
                                currentListId = null;
                                document.getElementById('groceryItems').innerHTML = '';
                            }
                            loadGroceryLists();
                            loadManageLists();
                        }
                    }
                })
                .catch(error => {
                    console.error('Error checking deletion status:', error);
                    clearInterval(deletionTimer);
                    modal.hide();
                    showToast(window.groceryTranslations.general_error || 'An error occurred', 'danger');
                });
        }, 1000);
    }

    function loadGroceryItems(listId) {
        currentListId = listId;
        fetchWithCSRF(window.apiUrls.manageGroceryItems.replace('{list_id}', listId))
            .then(response => {
                if (response.status === 403) {
                    showToast(window.groceryTranslations.insufficient_credits || 'Insufficient credits', 'error');
                    return Promise.reject(new Error('Unauthorized'));
                }
                return response.json();
            })
            .then(items => {
                offlineData.items[listId] = items;
                localStorage.setItem('groceryItems', JSON.stringify(offlineData.items));
                renderGroceryItems(items);
            })
            .catch(error => {
                console.error('Error loading grocery items:', error);
                renderGroceryItems([]);
            });
    }

    function renderGroceryItems(items) {
        const groceryItemsEl = document.getElementById('groceryItems');
        if (items && items.length > 0) {
            groceryItemsEl.innerHTML = items.map(item => `
                <div class="grocery-item">
                    <span class="fw-semibold">${item.name} (${item.category})</span>
                    <div class="d-flex align-items-center gap-2">
                        <input type="number" class="form-control" value="${item.quantity}" min="1" onchange="groceryModule.updateGroceryItem('${item.id}', 'quantity', this.value)">
                        <input type="number" class="form-control" value="${item.price}" min="0" step="0.01" onchange="groceryModule.updateGroceryItem('${item.id}', 'price', this.value)">
                        <select class="form-select" onchange="groceryModule.updateGroceryItem('${item.id}', 'status', this.value)">
                            <option value="to_buy" ${item.status === 'to_buy' ? 'selected' : ''}>${window.groceryTranslations.grocery_to_buy || 'To Buy'}</option>
                            <option value="in_pantry" ${item.status === 'in_pantry' ? 'selected' : ''}>${window.groceryTranslations.grocery_in_pantry || 'In Pantry'}</option>
                            <option value="bought" ${item.status === 'bought' ? 'selected' : ''}>${window.groceryTranslations.grocery_bought || 'Bought'}</option>
                        </select>
                        <button class="btn btn-sm btn-outline-info" onclick="groceryModule.showPriceHistory('${item.name}')">${window.groceryTranslations.grocery_price_history || 'Price History'}</button>
                    </div>
                </div>
            `).join('');
        } else {
            groceryItemsEl.innerHTML = `<div class="text-muted">${window.groceryTranslations.no_items || 'No items available'}</div>`;
        }
    }

    const addGroceryItem = debounce(function () {
        if (!currentListId) {
            showToast(window.groceryTranslations.general_select_list || 'Please select a list', 'warning');
            return;
        }
        const name = document.getElementById('newItemName').value;
        const quantity = document.getElementById('newItemQuantity').value;
        const price = document.getElementById('newItemPrice').value;
        const status = document.getElementById('newItemStatus').value;
        const store = document.getElementById('newItemStore').value;
        if (!name || !quantity || !price) {
            showToast(window.groceryTranslations.general_please_provide || 'Please provide all required fields', 'warning');
            return;
        }
        fetchWithCSRF(window.apiUrls.manageGroceryItems.replace('{list_id}', currentListId), {
            method: 'POST',
            body: JSON.stringify({ name, quantity, price, status, store })
        })
            .then(response => {
                if (response.status === 403) {
                    showToast(window.groceryTranslations.insufficient_credits || 'Insufficient credits', 'error');
                    return Promise.reject(new Error('Unauthorized'));
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    showToast(data.error, 'danger');
                } else {
                    showToast(window.groceryTranslations.grocery_item_added || 'Item added successfully', 'success');
                    document.getElementById('newItemName').value = '';
                    document.getElementById('newItemQuantity').value = '';
                    document.getElementById('newItemPrice').value = '';
                    document.getElementById('newItemStore').value = '';
                    loadGroceryItems(currentListId);
                }
            })
            .catch(error => {
                console.error('Error adding grocery item:', error);
                showToast(window.groceryTranslations.general_error || 'An error occurred', 'danger');
            });
    }, 500);

    const updateGroceryItem = debounce(function (itemId, field, value) {
        fetchWithCSRF(window.apiUrls.manageGroceryItems.replace('{list_id}', currentListId), {
            method: 'PUT',
            body: JSON.stringify({ item_id: itemId, [field]: value })
        })
            .then(response => {
                if (response.status === 403) {
                    showToast(window.groceryTranslations.insufficient_credits || 'Insufficient credits', 'error');
                    return Promise.reject(new Error('Unauthorized'));
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    showToast(data.error, 'danger');
                } else {
                    showToast(window.groceryTranslations.grocery_item_updated || 'Item updated successfully', 'success');
                    loadGroceryItems(currentListId);
                }
            })
            .catch(error => {
                console.error('Error updating grocery item:', error);
                showToast(window.groceryTranslations.general_error || 'An error occurred', 'danger');
            });
    }, 500);

    const shareGroceryList = debounce(function () {
        if (!currentListId) {
            showToast(window.groceryTranslations.general_select_list || 'Please select a list', 'warning');
            return;
        }
        const email = document.getElementById('shareListEmail').value;
        if (!email) {
            showToast(window.groceryTranslations.general_please_provide_email || 'Please provide an email', 'warning');
            return;
        }
        fetchWithCSRF(window.apiUrls.shareGroceryList.replace('{list_id}', currentListId), {
            method: 'POST',
            body: JSON.stringify({ email })
        })
            .then(response => {
                if (response.status === 403) {
                    showToast(window.groceryTranslations.insufficient_credits || 'Insufficient credits', 'error');
                    return Promise.reject(new Error('Unauthorized'));
                }
                return response.json();
            })
            .then(data => {
                if (data.error) {
                    showToast(data.error, 'danger');
                } else {
                    showToast(window.groceryTranslations.grocery_list_shared || 'List shared successfully', 'success');
                    document.getElementById('shareListEmail').value = '';
                    loadGroceryLists();
                    loadManageLists();
                }
            })
            .catch(error => {
                console.error('Error sharing grocery list:', error);
                showToast(window.groceryTranslations.general_error || 'An error occurred', 'danger');
            });
    }, 500);

    function showListDetails(listId) {
        fetchWithCSRF(`${window.apiUrls.manageGroceryLists}/${listId}`)
            .then(response => {
                if (response.status === 403) {
                    showToast(window.groceryTranslations.insufficient_credits || 'Insufficient credits', 'error');
                    return Promise.reject(new Error('Unauthorized'));
                }
                return response.json();
            })
            .then(data => {
                const modalBody = document.getElementById('listDetailsModalBody');
                modalBody.innerHTML = `
                    <h6>${window.groceryTranslations.grocery_list_details || 'List Details'}</h6>
                    <p><strong>${window.groceryTranslations.grocery_list_name || 'Name'}:</strong> ${data.name}</p>
                    <p><strong>${window.groceryTranslations.grocery_budget || 'Budget'}:</strong> ${format_currency(data.budget)}</p>
                    <p><strong>${window.groceryTranslations.grocery_total_spent || 'Total Spent'}:</strong> ${format_currency(data.total_spent)}</p>
                    <p><strong>${window.groceryTranslations.grocery_status || 'Status'}:</strong> ${data.status}</p>
                    <p><strong>${window.groceryTranslations.grocery_created_at || 'Created At'}:</strong> ${formatTimeAgo(data.created_at)}</p>
                    <p><strong>${window.groceryTranslations.grocery_collaborators || 'Collaborators'}:</strong> ${data.collaborators.length > 0 ? data.collaborators.join(', ') : 'None'}</p>
                    <h6 class="mt-3">${window.groceryTranslations.grocery_items || 'Items'}</h6>
                    ${data.items.length > 0 ? data.items.map(item => `
                        <div class="grocery-item">
                            <span class="fw-semibold">${item.name} (${item.category})</span>
                            <div>
                                <span>Qty: ${item.quantity}</span>
                                <span class="ms-2">Price: ${format_currency(item.price)}</span>
                                <span class="ms-2">Status: ${window.groceryTranslations[item.status] || item.status}</span>
                                <span class="ms-2">Store: ${item.store}</span>
                            </div>
                        </div>
                    `).join('') : `<div class="text-muted">${window.groceryTranslations.no_items || 'No items available'}</div>`}
                `;
                const modal = new bootstrap.Modal(document.getElementById('listDetailsModal'));
                modal.show();
            })
            .catch(error => {
                console.error('Error loading list details:', error);
                showToast(window.groceryTranslations.grocery_list_error || 'Error loading list details', 'danger');
            });
    }

    function showPriceHistory(itemName) {
        fetchWithCSRF(window.apiUrls.groceryPriceHistory.replace('{item_name}', encodeURIComponent(itemName)))
            .then(response => {
                if (response.status === 403) {
                    showToast(window.groceryTranslations.insufficient_credits || 'Insufficient credits', 'error');
                    return Promise.reject(new Error('Unauthorized'));
                }
                return response.json();
            })
            .then(data => {
                const history = data.prices || [];
                const avgPrice = data.average_price || 0;
                const modalBody = document.getElementById('listDetailsModalBody');
                modalBody.innerHTML = `
                    <h6>${window.groceryTranslations.grocery_price_history_for || 'Price History for'} ${itemName} (Avg: ${format_currency(avgPrice)})</h6>
                    ${history.length > 0 ? history.map(h => `
                        <div class="grocery-item">
                            <span>${h.store}: ${format_currency(h.price)}</span>
                            <span class="text-muted">${formatTimeAgo(h.date)}</span>
                        </div>
                    `).join('') : `<div class="text-muted">${window.groceryTranslations.no_price_history || 'No price history available'}</div>`}
                `;
                const modal = new bootstrap.Modal(document.getElementById('listDetailsModal'));
                modal.show();
            })
            .catch(error => {
                console.error('Error loading price history:', error);
                showToast(window.groceryTranslations.grocery_price_history_error || 'Error loading price history', 'danger');
            });
    }

    function loadOfflineData() {
        const cachedLists = localStorage.getItem('groceryLists');
        const cachedManageLists = localStorage.getItem('manageGroceryLists');
        const cachedItems = localStorage.getItem('groceryItems');
        if (cachedLists) {
            offlineData.lists = JSON.parse(cachedLists);
            renderGroceryLists(offlineData.lists);
        }
        if (cachedManageLists) {
            offlineData.lists = JSON.parse(cachedManageLists);
            renderManageLists(offlineData.lists);
        }
        if (cachedItems) {
            offlineData.items = JSON.parse(cachedItems);
            if (currentListId && offlineData.items[currentListId]) {
                renderGroceryItems(offlineData.items[currentListId]);
            }
        }
    }

    function format_currency(value) {
        if (!value && value !== 0) return '₦0.00';
        value = parseFloat(value);
        if (isNaN(value)) return '₦0.00';
        return value.toLocaleString('en-NG', { style: 'currency', currency: 'NGN' });
    }

    function formatTimeAgo(dateStr) {
        const now = new Date();
        const date = new Date(dateStr);
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMins / 60);
        const diffDays = Math.floor(diffHours / 24);

        if (diffMins < 1) return window.groceryTranslations.just_now || 'Just now';
        if (diffMins < 60) return `${diffMins} ${window.groceryTranslations.minutes_ago || 'minutes ago'}`;
        if (diffHours < 24) return `${diffHours} ${window.groceryTranslations.hours_ago || 'hours ago'}`;
        return `${diffDays} ${window.groceryTranslations.days_ago || 'days ago'}`;
    }

    // Expose functions to the global scope with a namespace
    window.groceryModule = {
        initGroceryPlanner,
        createGroceryList,
        addGroceryItem,
        updateGroceryItem,
        shareGroceryList,
        loadGroceryItems,
        initiateDeleteGroceryList,
        saveGroceryList,
        exportGroceryListToPDF,
        showListDetails,
        editGroceryList,
        showPriceHistory
    };
})();
