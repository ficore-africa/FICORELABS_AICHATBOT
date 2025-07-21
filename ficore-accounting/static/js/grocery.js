let currentListId = null;
let currentMealPlanId = null;
let offlineData = { lists: [], items: {}, mealPlans: [], suggestions: {} };

// CSRF Token Setup
let csrfToken = null;
function setupCSRF() {
    const metaTag = document.querySelector('meta[name="csrf-token"]');
    if (metaTag) {
        csrfToken = metaTag.getAttribute('content');
    }
}

// Initialize Grocery Planner
function initGroceryPlanner() {
    setupCSRF();
    const root = document.getElementById('grocery-planner-root');
    if (!root) return;

    root.innerHTML = `
        <ul class="nav nav-tabs mb-3" id="groceryTabs" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="lists-tab" data-bs-toggle="tab" data-bs-target="#lists" type="button" role="tab">${window.groceryTranslations.grocery_lists}</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="meal-plans-tab" data-bs-toggle="tab" data-bs-target="#meal-plans" type="button" role="tab">${window.groceryTranslations.grocery_meal_plans}</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="suggestions-tab" data-bs-toggle="tab" data-bs-target="#suggestions" type="button" role="tab">${window.groceryTranslations.grocery_suggestions}</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="manage-list-tab" data-bs-toggle="tab" data-bs-target="#manage-list" type="button" role="tab">${window.groceryTranslations.grocery_manage_list}</button>
            </li>
        </ul>
        <div class="tab-content" id="groceryTabContent">
            <div class="tab-pane fade show active" id="lists" role="tabpanel" aria-labelledby="lists-tab">
                <div class="mb-3">
                    <h6>${window.groceryTranslations.grocery_create_list}</h6>
                    <div class="input-group">
                        <input type="text" class="form-control" id="newListName" placeholder="${window.groceryTranslations.grocery_list_name}">
                        <input type="number" class="form-control" id="newListBudget" placeholder="${window.groceryTranslations.grocery_budget}" min="0" step="0.01">
                        <button class="btn btn-primary" onclick="createGroceryList()">${window.groceryTranslations.grocery_create}</button>
                    </div>
                </div>
                <div id="groceryLists"></div>
                <div id="groceryItems" class="mt-3"></div>
                <div class="mt-3">
                    <h6>${window.groceryTranslations.grocery_add_item}</h6>
                    <div class="input-group">
                        <input type="text" class="form-control" id="newItemName" placeholder="${window.groceryTranslations.grocery_item_name}">
                        <input type="number" class="form-control" id="newItemQuantity" placeholder="${window.groceryTranslations.grocery_quantity}" min="1">
                        <input type="number" class="form-control" id="newItemPrice" placeholder="${window.groceryTranslations.grocery_price}" min="0" step="0.01">
                        <select class="form-select" id="newItemStatus">
                            <option value="to_buy">${window.groceryTranslations.grocery_to_buy}</option>
                            <option value="in_pantry">${window.groceryTranslations.grocery_in_pantry}</option>
                            <option value="bought">${window.groceryTranslations.grocery_bought}</option>
                        </select>
                        <input type="text" class="form-control" id="newItemStore" placeholder="${window.groceryTranslations.grocery_store}">
                        <button class="btn btn-primary" onclick="addGroceryItem()">${window.groceryTranslations.grocery_add}</button>
                    </div>
                </div>
                <div class="mt-3">
                    <h6>${window.groceryTranslations.grocery_share_list}</h6>
                    <div class="input-group">
                        <input type="email" class="form-control" id="shareListEmail" placeholder="${window.groceryTranslations.grocery_collaborator_email}">
                        <button class="btn btn-primary" onclick="shareGroceryList()">${window.groceryTranslations.grocery_share}</button>
                    </div>
                </div>
            </div>
            <div class="tab-pane fade" id="meal-plans" role="tabpanel" aria-labelledby="meal-plans-tab">
                <div class="mb-3">
                    <h6>${window.groceryTranslations.grocery_create_meal_plan}</h6>
                    <div class="input-group">
                        <input type="text" class="form-control" id="newMealPlanName" placeholder="${window.groceryTranslations.grocery_meal_name}">
                        <input type="number" class="form-control" id="newMealPlanBudget" placeholder="${window.groceryTranslations.grocery_budget}" min="0" step="0.01">
                        <button class="btn btn-primary" onclick="createMealPlan()">${window.groceryTranslations.grocery_create}</button>
                    </div>
                </div>
                <div id="mealPlans"></div>
                <div class="mt-3">
                    <h6>${window.groceryTranslations.grocery_add_ingredient}</h6>
                    <div class="input-group">
                        <input type="text" class="form-control" id="newIngredientName" placeholder="${window.groceryTranslations.grocery_ingredient_name}">
                        <input type="number" class="form-control" id="newIngredientQuantity" placeholder="${window.groceryTranslations.grocery_quantity}" min="1">
                        <input type="number" class="form-control" id="newIngredientPrice" placeholder="${window.groceryTranslations.grocery_price}" min="0" step="0.01">
                        <button class="btn btn-primary" onclick="addIngredient()">${window.groceryTranslations.grocery_add}</button>
                    </div>
                </div>
            </div>
            <div class="tab-pane fade" id="suggestions" role="tabpanel" aria-labelledby="suggestions-tab">
                <div class="mb-3">
                    <h6>${window.groceryTranslations.grocery_suggested_items}</h6>
                    <div id="predictiveSuggestions"></div>
                </div>
                <div class="mb-3">
                    <h6>${window.groceryTranslations.grocery_collaborator_suggestions}</h6>
                    <div id="collaboratorSuggestions"></div>
                </div>
                <div class="mt-3">
                    <h6>${window.groceryTranslations.grocery_suggest_item}</h6>
                    <div class="input-group">
                        <input type="text" class="form-control" id="suggestItemName" placeholder="${window.groceryTranslations.grocery_item_name}">
                        <input type="number" class="form-control" id="suggestItemQuantity" placeholder="${window.groceryTranslations.grocery_quantity}" min="1">
                        <input type="number" class="form-control" id="suggestItemPrice" placeholder="${window.groceryTranslations.grocery_price}" min="0" step="0.01">
                        <button class="btn btn-primary" onclick="suggestItem()">${window.groceryTranslations.grocery_suggest}</button>
                    </div>
                </div>
            </div>
            <div class="tab-pane fade" id="manage-list" role="tabpanel" aria-labelledby="manage-list-tab">
                <div class="mb-3">
                    <h6>${window.groceryTranslations.grocery_manage_list}</h6>
                    <div id="manageGroceryLists"></div>
                </div>
            </div>
        </div>
    `;

    loadGroceryLists();
    loadPredictiveSuggestions();
    loadManageLists();
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

// Grocery Planner Functions
function loadGroceryLists() {
    fetchWithCSRF(window.apiUrls.manageGroceryLists)
        .then(response => {
            if (response.status === 403) {
                showToast(window.groceryTranslations.insufficient_credits, 'error');
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
                <div>
                    <span class="text-muted">Budget: ${format_currency(list.budget)}</span>
                    <span class="ms-2">Spent: ${format_currency(list.total_spent)}</span>
                    <button class="btn btn-sm btn-outline-primary ms-2" onclick="loadGroceryItems('${list.id}')">${window.groceryTranslations.general_view_all}</button>
                </div>
            </div>
        `).join('');
        if (!currentListId && lists[0]) {
            loadGroceryItems(lists[0].id);
        }
    } else {
        groceryListsEl.innerHTML = `<div class="text-muted">${window.groceryTranslations.no_lists}</div>`;
    }
}

function loadManageLists() {
    fetchWithCSRF(window.apiUrls.manageGroceryLists)
        .then(response => {
            if (response.status === 403) {
                showToast(window.groceryTranslations.insufficient_credits, 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(lists => {
            offlineData.lists = lists;
            localStorage.setItem('groceryLists', JSON.stringify(lists));
            renderManageLists(lists);
        })
        .catch(error => {
            console.error('Error loading grocery lists for management:', error);
            renderManageLists([]);
        });
}

function renderManageLists(lists) {
    const manageListsEl = document.getElementById('manageGroceryLists');
    if (lists && lists.length > 0) {
        manageListsEl.innerHTML = lists.map(list => `
            <div class="grocery-item">
                <span class="fw-semibold">${list.name}</span>
                <div>
                    <span class="text-muted">Budget: ${format_currency(list.budget)}</span>
                    <button class="btn btn-sm btn-outline-danger ms-2" onclick="deleteGroceryList('${list.id}', '${list.name}')">${window.groceryTranslations.grocery_delete}</button>
                </div>
            </div>
        `).join('');
    } else {
        manageListsEl.innerHTML = `<div class="text-muted">${window.groceryTranslations.no_lists}</div>`;
    }
}

function deleteGroceryList(listId, listName) {
    if (!confirm(`${window.groceryTranslations.grocery_confirm_delete} "${listName}"? ${window.groceryTranslations.grocery_delete_cost}`)) {
        return;
    }
    fetchWithCSRF(window.apiUrls.deleteGroceryList.replace('{list_id}', listId), {
        method: 'DELETE'
    })
        .then(response => {
            if (response.status === 403) {
                showToast(window.groceryTranslations.insufficient_credits, 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(window.groceryTranslations.grocery_list_deleted, 'success');
                if (currentListId === listId) {
                    currentListId = null;
                    document.getElementById('groceryItems').innerHTML = '';
                }
                loadGroceryLists();
                loadManageLists();
                loadFinancialSummary();
            }
        })
        .catch(error => {
            console.error('Error deleting grocery list:', error);
            showToast(window.groceryTranslations.general_error, 'danger');
        });
}

function loadGroceryItems(listId) {
    currentListId = listId;
    fetchWithCSRF(window.apiUrls.manageGroceryItems.replace('{list_id}', listId))
        .then(response => {
            if (response.status === 403) {
                showToast(window.groceryTranslations.insufficient_credits, 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(items => {
            offlineData.items[listId] = items;
            localStorage.setItem('groceryItems', JSON.stringify(offlineData.items));
            renderGroceryItems(items);
            loadCollaboratorSuggestions(listId);
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
                    <input type="number" class="form-control" value="${item.quantity}" min="1" onchange="updateGroceryItem('${item.id}', 'quantity', this.value)">
                    <input type="number" class="form-control" value="${item.price}" min="0" step="0.01" onchange="updateGroceryItem('${item.id}', 'price', this.value)">
                    <select class="form-select" onchange="updateGroceryItem('${item.id}', 'status', this.value)">
                        <option value="to_buy" ${item.status === 'to_buy' ? 'selected' : ''}>${window.groceryTranslations.grocery_to_buy}</option>
                        <option value="in_pantry" ${item.status === 'in_pantry' ? 'selected' : ''}>${window.groceryTranslations.grocery_in_pantry}</option>
                        <option value="bought" ${item.status === 'bought' ? 'selected' : ''}>${window.groceryTranslations.grocery_bought}</option>
                    </select>
                    <button class="btn btn-sm btn-outline-info" onclick="showPriceHistory('${item.name}')">${window.groceryTranslations.grocery_price_history}</button>
                </div>
            </div>
        `).join('');
    } else {
        groceryItemsEl.innerHTML = `<div class="text-muted">${window.groceryTranslations.no_items}</div>`;
    }
}

function createGroceryList() {
    const name = document.getElementById('newListName').value;
    const budget = document.getElementById('newListBudget').value;
    if (!name || !budget) {
        showToast(window.groceryTranslations.general_please_provide, 'warning');
        return;
    }
    fetchWithCSRF(window.apiUrls.manageGroceryLists, {
        method: 'POST',
        body: JSON.stringify({ name, budget })
    })
        .then(response => {
            if (response.status === 403) {
                showToast(window.groceryTranslations.insufficient_credits, 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(window.groceryTranslations.grocery_list_created, 'success');
                document.getElementById('newListName').value = '';
                document.getElementById('newListBudget').value = '';
                loadGroceryLists();
                loadManageLists();
                loadFinancialSummary();
            }
        })
        .catch(error => {
            console.error('Error creating grocery list:', error);
            showToast(window.groceryTranslations.general_error, 'danger');
        });
}

function addGroceryItem() {
    if (!currentListId) {
        showToast(window.groceryTranslations.general_select_list, 'warning');
        return;
    }
    const name = document.getElementById('newItemName').value;
    const quantity = document.getElementById('newItemQuantity').value;
    const price = document.getElementById('newItemPrice').value;
    const status = document.getElementById('newItemStatus').value;
    const store = document.getElementById('newItemStore').value;
    if (!name || !quantity || !price) {
        showToast(window.groceryTranslations.general_please_provide, 'warning');
        return;
    }
    fetchWithCSRF(window.apiUrls.manageGroceryItems.replace('{list_id}', currentListId), {
        method: 'POST',
        body: JSON.stringify({ name, quantity, price, status, store })
    })
        .then(response => {
            if (response.status === 403) {
                showToast(window.groceryTranslations.insufficient_credits, 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(window.groceryTranslations.grocery_item_added, 'success');
                document.getElementById('newItemName').value = '';
                document.getElementById('newItemQuantity').value = '';
                document.getElementById('newItemPrice').value = '';
                document.getElementById('newItemStore').value = '';
                loadGroceryItems(currentListId);
                loadFinancialSummary();
            }
        })
        .catch(error => {
            console.error('Error adding grocery item:', error);
            showToast(window.groceryTranslations.general_error, 'danger');
        });
}

function updateGroceryItem(itemId, field, value) {
    fetchWithCSRF(window.apiUrls.manageGroceryItems.replace('{list_id}', currentListId), {
        method: 'PUT',
        body: JSON.stringify({ item_id: itemId, [field]: value })
    })
        .then(response => {
            if (response.status === 403) {
                showToast(window.groceryTranslations.insufficient_credits, 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(window.groceryTranslations.grocery_item_updated, 'success');
                loadGroceryItems(currentListId);
                loadFinancialSummary();
            }
        })
        .catch(error => {
            console.error('Error updating grocery item:', error);
            showToast(window.groceryTranslations.general_error, 'danger');
        });
}

function shareGroceryList() {
    if (!currentListId) {
        showToast(window.groceryTranslations.general_select_list, 'warning');
        return;
    }
    const email = document.getElementById('shareListEmail').value;
    if (!email) {
        showToast(window.groceryTranslations.general_please_provide_email, 'warning');
        return;
    }
    fetchWithCSRF(window.apiUrls.shareGroceryList.replace('{list_id}', currentListId), {
        method: 'POST',
        body: JSON.stringify({ email })
    })
        .then(response => {
            if (response.status === 403) {
                showToast(window.groceryTranslations.insufficient_credits, 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(window.groceryTranslations.grocery_list_shared, 'success');
                document.getElementById('shareListEmail').value = '';
                loadGroceryLists();
                loadManageLists();
            }
        })
        .catch(error => {
            console.error('Error sharing grocery list:', error);
            showToast(window.groceryTranslations.general_error, 'danger');
        });
}

function loadMealPlans() {
    fetchWithCSRF(window.apiUrls.manageMealPlans)
        .then(response => {
            if (response.status === 403) {
                showToast(window.groceryTranslations.insufficient_credits, 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(mealPlans => {
            offlineData.mealPlans = mealPlans;
            localStorage.setItem('mealPlans', JSON.stringify(mealPlans));
            renderMealPlans(mealPlans);
        })
        .catch(error => {
            console.error('Error loading meal plans:', error);
            renderMealPlans([]);
        });
}

function renderMealPlans(mealPlans) {
    const mealPlansEl = document.getElementById('mealPlans');
    if (mealPlans && mealPlans.length > 0) {
        mealPlansEl.innerHTML = mealPlans.map(plan => `
            <div class="meal-plan-item">
                <span class="fw-semibold">${plan.name}</span>
                <div>
                    <button class="btn btn-sm btn-outline-primary" onclick="loadMealPlanIngredients('${plan.id}')">${window.groceryTranslations.general_view_all}</button>
                    <button class="btn btn-sm btn-outline-success" onclick="generateGroceryListFromMealPlan('${plan.id}')">${window.groceryTranslations.generate_list}</button>
                </div>
            </div>
        `).join('');
        if (!currentMealPlanId && mealPlans[0]) {
            loadMealPlanIngredients(mealPlans[0].id);
        }
    } else {
        mealPlansEl.innerHTML = `<div class="text-muted">${window.groceryTranslations.no_meal_plans}</div>`;
    }
}

function loadMealPlanIngredients(mealPlanId) {
    currentMealPlanId = mealPlanId;
    fetchWithCSRF(window.apiUrls.manageMealPlans)
        .then(response => {
            if (response.status === 403) {
                showToast(window.groceryTranslations.insufficient_credits, 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(mealPlans => {
            const plan = mealPlans.find(p => p.id === mealPlanId);
            renderMealPlanIngredients(plan ? plan.ingredients : []);
        })
        .catch(error => {
            console.error('Error loading meal plan ingredients:', error);
            renderMealPlanIngredients([]);
        });
}

function renderMealPlanIngredients(ingredients) {
    const mealPlansEl = document.getElementById('mealPlans');
    if (ingredients && ingredients.length > 0) {
        mealPlansEl.innerHTML += ingredients.map(ingredient => `
            <div class="grocery-item">
                <span class="fw-semibold">${ingredient.name} (${ingredient.category})</span>
                <div>
                    <span>Qty: ${ingredient.quantity}</span>
                    <span class="ms-2">Price: ${format_currency(ingredient.price)}</span>
                </div>
            </div>
        `).join('');
    }
}

function createMealPlan() {
    const name = document.getElementById('newMealPlanName').value;
    const budget = document.getElementById('newMealPlanBudget').value;
    if (!name) {
        showToast(window.groceryTranslations.general_please_provide, 'warning');
        return;
    }
    fetchWithCSRF(window.apiUrls.manageMealPlans, {
        method: 'POST',
        body: JSON.stringify({ name, budget, auto_generate_list: !!budget, ingredients: [] })
    })
        .then(response => {
            if (response.status === 403) {
                showToast(window.groceryTranslations.insufficient_credits, 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(window.groceryTranslations.grocery_meal_plan_created, 'success');
                document.getElementById('newMealPlanName').value = '';
                document.getElementById('newMealPlanBudget').value = '';
                loadMealPlans();
                loadFinancialSummary();
            }
        })
        .catch(error => {
            console.error('Error creating meal plan:', error);
            showToast(window.groceryTranslations.general_error, 'danger');
        });
}

function addIngredient() {
    if (!currentMealPlanId) {
        showToast(window.groceryTranslations.general_select_meal_plan, 'warning');
        return;
    }
    const name = document.getElementById('newIngredientName').value;
    const quantity = document.getElementById('newIngredientQuantity').value;
    const price = document.getElementById('newIngredientPrice').value;
    if (!name || !quantity || !price) {
        showToast(window.groceryTranslations.general_please_provide, 'warning');
        return;
    }
    fetchWithCSRF(window.apiUrls.manageMealPlans, {
        method: 'POST',
        body: JSON.stringify({ 
            name: `Update for ${currentMealPlanId}`, 
            ingredients: [{ name, quantity, price }], 
            auto_generate_list: false 
        })
    })
        .then(response => {
            if (response.status === 403) {
                showToast(window.groceryTranslations.insufficient_credits, 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(window.groceryTranslations.grocery_item_added, 'success');
                document.getElementById('newIngredientName').value = '';
                document.getElementById('newIngredientQuantity').value = '';
                document.getElementById('newIngredientPrice').value = '';
                loadMealPlans();
            }
        })
        .catch(error => {
            console.error('Error adding ingredient:', error);
            showToast(window.groceryTranslations.general_error, 'danger');
        });
}

function generateGroceryListFromMealPlan(mealPlanId) {
    fetchWithCSRF(window.apiUrls.manageMealPlans)
        .then(response => {
            if (response.status === 403) {
                showToast(window.groceryTranslations.insufficient_credits, 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(mealPlans => {
            const plan = mealPlans.find(p => p.id === mealPlanId);
            if (plan) {
                fetchWithCSRF(window.apiUrls.manageGroceryLists, {
                    method: 'POST',
                    body: JSON.stringify({
                        name: `${plan.name} Grocery List`,
                        budget: plan.ingredients.reduce((sum, i) => sum + i.price * i.quantity, 0),
                        auto_generate_list: true
                    })
                })
                    .then(response => {
                        if (response.status === 403) {
                            showToast(window.groceryTranslations.insufficient_credits, 'error');
                            return Promise.reject(new Error('Unauthorized'));
                        }
                        return response.json();
                    })
                    .then(data => {
                        if (data.error) {
                            showToast(data.error, 'danger');
                        } else {
                            showToast(window.groceryTranslations.grocery_list_created, 'success');
                            loadGroceryLists();
                            loadManageLists();
                            loadFinancialSummary();
                        }
                    })
                    .catch(error => {
                        console.error('Error generating grocery list:', error);
                        showToast(window.groceryTranslations.general_error, 'danger');
                    });
            }
        })
        .catch(error => {
            console.error('Error fetching meal plan:', error);
            showToast(window.groceryTranslations.general_error, 'danger');
        });
}

function loadPredictiveSuggestions() {
    fetchWithCSRF(window.apiUrls.predictiveSuggestions)
        .then(response => {
            if (response.status === 403) {
                showToast(window.groceryTranslations.insufficient_credits, 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(suggestions => {
            offlineData.suggestions.predictive = suggestions;
            localStorage.setItem('predictiveSuggestions', JSON.stringify(suggestions));
            renderPredictiveSuggestions(suggestions);
        })
        .catch(error => {
            console.error('Error loading predictive suggestions:', error);
            renderPredictiveSuggestions([]);
        });
}

function renderPredictiveSuggestions(suggestions) {
    const suggestionsEl = document.getElementById('predictiveSuggestions');
    if (suggestions && suggestions.length > 0) {
        suggestionsEl.innerHTML = suggestions.map(s => `
            <div class="suggestion-item">
                <span class="fw-semibold">${s.name} (${s.category})</span>
                <div>
                    <span>Qty: ${s.suggested_quantity}</span>
                    <span class="ms-2">Price: ${format_currency(s.estimated_price)}</span>
                    <button class="btn btn-sm btn-outline-primary ms-2" onclick="addSuggestedItem('${s.name}', ${s.suggested_quantity}, ${s.estimated_price})">${window.groceryTranslations.grocery_add}</button>
                </div>
            </div>
        `).join('');
    } else {
        suggestionsEl.innerHTML = `<div class="text-muted">${window.groceryTranslations.no_suggestions}</div>`;
    }
}

function addSuggestedItem(name, quantity, price) {
    if (!currentListId) {
        showToast(window.groceryTranslations.general_select_list, 'warning');
        return;
    }
    fetchWithCSRF(window.apiUrls.manageGroceryItems.replace('{list_id}', currentListId), {
        method: 'POST',
        body: JSON.stringify({ name, quantity, price, status: 'to_buy' })
    })
        .then(response => {
            if (response.status === 403) {
                showToast(window.groceryTranslations.insufficient_credits, 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(window.groceryTranslations.grocery_item_added, 'success');
                loadGroceryItems(currentListId);
                loadFinancialSummary();
            }
        })
        .catch(error => {
            console.error('Error adding suggested item:', error);
            showToast(window.groceryTranslations.general_error, 'danger');
        });
}

function loadCollaboratorSuggestions(listId) {
    fetchWithCSRF(window.apiUrls.manageGrocerySuggestions.replace('{list_id}', listId))
        .then(response => {
            if (response.status === 403) {
                showToast(window.groceryTranslations.insufficient_credits, 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(suggestions => {
            offlineData.suggestions[listId] = suggestions;
            localStorage.setItem('collaboratorSuggestions', JSON.stringify(offlineData.suggestions));
            renderCollaboratorSuggestions(suggestions);
        })
        .catch(error => {
            console.error('Error loading collaborator suggestions:', error);
            renderCollaboratorSuggestions([]);
        });
}

function renderCollaboratorSuggestions(suggestions) {
    const suggestionsEl = document.getElementById('collaboratorSuggestions');
    if (suggestions && suggestions.length > 0) {
        suggestionsEl.innerHTML = suggestions.map(s => `
            <div class="suggestion-item">
                <span class="fw-semibold">${s.name} (${s.category})</span>
                <div>
                    <span>Qty: ${s.quantity}</span>
                    <span class="ms-2">Price: ${format_currency(s.price)}</span>
                    ${s.status === 'pending' ? `<button class="btn btn-sm btn-outline-success ms-2" onclick="approveSuggestion('${s.id}', '${currentListId}')">${window.groceryTranslations.grocery_suggestion_approve}</button>` : ''}
                </div>
            </div>
        `).join('');
    } else {
        suggestionsEl.innerHTML = `<div class="text-muted">${window.groceryTranslations.no_suggestions}</div>`;
    }
}

function suggestItem() {
    if (!currentListId) {
        showToast(window.groceryTranslations.general_select_list, 'warning');
        return;
    }
    const name = document.getElementById('suggestItemName').value;
    const quantity = document.getElementById('suggestItemQuantity').value;
    const price = document.getElementById('suggestItemPrice').value;
    if (!name || !quantity || !price) {
        showToast(window.groceryTranslations.general_please_provide, 'warning');
        return;
    }
    fetchWithCSRF(window.apiUrls.manageGrocerySuggestions.replace('{list_id}', currentListId), {
        method: 'POST',
        body: JSON.stringify({ name, quantity, price })
    })
        .then(response => {
            if (response.status === 403) {
                showToast(window.groceryTranslations.insufficient_credits, 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(window.groceryTranslations.grocery_suggestion_added, 'success');
                document.getElementById('suggestItemName').value = '';
                document.getElementById('suggestItemQuantity').value = '';
                document.getElementById('suggestItemPrice').value = '';
                loadCollaboratorSuggestions(currentListId);
            }
        })
        .catch(error => {
            console.error('Error suggesting item:', error);
            showToast(window.groceryTranslations.general_error, 'danger');
        });
}

function approveSuggestion(suggestionId, listId) {
    fetchWithCSRF(window.apiUrls.approveGrocerySuggestion.replace('{list_id}', listId).replace('{suggestion_id}', suggestionId), {
        method: 'POST'
    })
        .then(response => {
            if (response.status === 403) {
                showToast(window.groceryTranslations.insufficient_credits, 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(window.groceryTranslations.grocery_suggestion_approved, 'success');
                loadGroceryItems(currentListId);
                loadCollaboratorSuggestions(currentListId);
                loadFinancialSummary();
            }
        })
        .catch(error => {
            console.error('Error approving suggestion:', error);
            showToast(window.groceryTranslations.general_error, 'danger');
        });
}

function showPriceHistory(itemName) {
    fetchWithCSRF(window.apiUrls.priceHistory.replace('{item_name}', encodeURIComponent(itemName)))
        .then(response => {
            if (response.status === 403) {
                showToast(window.groceryTranslations.insufficient_credits, 'error');
                return Promise.reject(new Error('Unauthorized'));
            }
            return response.json();
        })
        .then(data => {
            const history = data.prices || [];
            const avgPrice = data.average_price || 0;
            const modalBody = document.querySelector('#groceryModal .modal-body');
            const historyHtml = history.length > 0 ? history.map(h => `
                <div class="grocery-item">
                    <span>${h.store}: ${format_currency(h.price)}</span>
                    <span class="text-muted">${formatTimeAgo(h.date)}</span>
                </div>
            `).join('') : `<div class="text-muted">${window.groceryTranslations.no_price_history}</div>`;
            modalBody.innerHTML += `
                <div class="mt-3">
                    <h6>${window.groceryTranslations.grocery_price_history_for} ${itemName} (Avg: ${format_currency(avgPrice)})</h6>
                    ${historyHtml}
                </div>
            `;
        })
        .catch(error => {
            console.error('Error loading price history:', error);
            showToast(window.groceryTranslations.general_error, 'danger');
        });
}

function loadOfflineData() {
    const cachedLists = localStorage.getItem('groceryLists');
    const cachedItems = localStorage.getItem('groceryItems');
    const cachedMealPlans = localStorage.getItem('mealPlans');
    const cachedSuggestions = localStorage.getItem('predictiveSuggestions');
    if (cachedLists) {
        offlineData.lists = JSON.parse(cachedLists);
        renderGroceryLists(offlineData.lists);
        renderManageLists(offlineData.lists);
    }
    if (cachedItems) {
        offlineData.items = JSON.parse(cachedItems);
        if (currentListId && offlineData.items[currentListId]) {
            renderGroceryItems(offlineData.items[currentListId]);
        }
    }
    if (cachedMealPlans) {
        offlineData.mealPlans = JSON.parse(cachedMealPlans);
        renderMealPlans(offlineData.mealPlans);
    }
    if (cachedSuggestions) {
        offlineData.suggestions.predictive = JSON.parse(cachedSuggestions);
        renderPredictiveSuggestions(offlineData.suggestions.predictive);
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

    if (diffMins < 1) return window.groceryTranslations.just_now;
    if (diffMins < 60) return `${diffMins} ${window.groceryTranslations.minutes_ago}`;
    if (diffHours < 24) return `${diffHours} ${window.groceryTranslations.hours_ago}`;
    return `${diffDays} ${window.groceryTranslations.days_ago}`;
}
