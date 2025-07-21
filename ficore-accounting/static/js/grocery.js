{% if current_user.is_authenticated %}
// Translation strings
const translations = {
    just_now: '{{ t("general_just_now", default="Just now") | e }}',
    minutes_ago: '{{ t("general_minutes_ago", default="m ago") | e }}',
    hours_ago: '{{ t("general_hours_ago", default="h ago") | e }}',
    days_ago: '{{ t("general_days_ago", default="d ago") | e }}',
    no_lists: '{{ t("grocery_no_lists", default="No grocery lists found") | e }}',
    no_items: '{{ t("grocery_no_items", default="No items in this list") | e }}',
    no_meal_plans: '{{ t("grocery_no_meal_plans", default="No meal plans found") | e }}',
    no_suggestions: '{{ t("grocery_no_suggestions", default="No suggestions available") | e }}',
    no_price_history: '{{ t("grocery_no_price_history", default="No price history available") | e }}',
    grocery_list_created: '{{ t("grocery_list_created", default="Grocery list created") | e }}',
    grocery_item_added: '{{ t("grocery_item_added", default="Item added to list") | e }}',
    grocery_item_updated: '{{ t("grocery_item_updated", default="Item updated") | e }}',
    grocery_list_shared: '{{ t("grocery_list_shared", default="List shared successfully") | e }}',
    grocery_suggestion_added: '{{ t("grocery_suggestion_added", default="Suggestion added") | e }}',
    grocery_suggestion_approved: '{{ t("grocery_suggestion_approved", default="Suggestion approved") | e }}',
    grocery_meal_plan_created: '{{ t("grocery_meal_plan_created", default="Meal plan created") | e }}',
    friday_reminder: '{{ t("grocery_friday_reminder", default="It's Friday! Time to prep your weekend grocery list.") | e }}'
};

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
                <button class="nav-link active" id="lists-tab" data-bs-toggle="tab" data-bs-target="#lists" type="button" role="tab">{{ t('grocery_lists', default='Lists') | e }}</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="meal-plans-tab" data-bs-toggle="tab" data-bs-target="#meal-plans" type="button" role="tab">{{ t('grocery_meal_plans', default='Meal Plans') | e }}</button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="suggestions-tab" data-bs-toggle="tab" data-bs-target="#suggestions" type="button" role="tab">{{ t('grocery_suggestions', default='Suggestions') | e }}</button>
            </li>
        </ul>
        <div class="tab-content" id="groceryTabContent">
            <div class="tab-pane fade show active" id="lists" role="tabpanel" aria-labelledby="lists-tab">
                <div class="mb-3">
                    <h6>{{ t('grocery_create_list', default='Create New List') | e }}</h6>
                    <div class="input-group">
                        <input type="text" class="form-control" id="newListName" placeholder="{{ t('grocery_list_name', default='List Name') | e }}">
                        <input type="number" class="form-control" id="newListBudget" placeholder="{{ t('grocery_budget', default='Budget') | e }}" min="0" step="0.01">
                        <button class="btn btn-primary" onclick="createGroceryList()">{{ t('grocery_create', default='Create') | e }}</button>
                    </div>
                </div>
                <div id="groceryLists"></div>
                <div id="groceryItems" class="mt-3"></div>
                <div class="mt-3">
                    <h6>{{ t('grocery_add_item', default='Add Item to List') | e }}</h6>
                    <div class="input-group">
                        <input type="text" class="form-control" id="newItemName" placeholder="{{ t('grocery_item_name', default='Item Name') | e }}">
                        <input type="number" class="form-control" id="newItemQuantity" placeholder="{{ t('grocery_quantity', default='Quantity') | e }}" min="1">
                        <input type="number" class="form-control" id="newItemPrice" placeholder="{{ t('grocery_price', default='Price') | e }}" min="0" step="0.01">
                        <select class="form-select" id="newItemStatus">
                            <option value="to_buy">{{ t('grocery_to_buy', default='To Buy') | e }}</option>
                            <option value="in_pantry">{{ t('grocery_in_pantry', default='In Pantry') | e }}</option>
                            <option value="bought">{{ t('grocery_bought', default='Bought') | e }}</option>
                        </select>
                        <input type="text" class="form-control" id="newItemStore" placeholder="{{ t('grocery_store', default='Store') | e }}">
                        <button class="btn btn-primary" onclick="addGroceryItem()">{{ t('grocery_add', default='Add') | e }}</button>
                    </div>
                </div>
                <div class="mt-3">
                    <h6>{{ t('grocery_share_list', default='Share List') | e }}</h6>
                    <div class="input-group">
                        <input type="email" class="form-control" id="shareListEmail" placeholder="{{ t('grocery_collaborator_email', default='Collaborator Email') | e }}">
                        <button class="btn btn-primary" onclick="shareGroceryList()">{{ t('grocery_share', default='Share') | e }}</button>
                    </div>
                </div>
            </div>
            <div class="tab-pane fade" id="meal-plans" role="tabpanel" aria-labelledby="meal-plans-tab">
                <div class="mb-3">
                    <h6>{{ t('grocery_create_meal_plan', default='Create Meal Plan') | e }}</h6>
                    <div class="input-group">
                        <input type="text" class="form-control" id="newMealPlanName" placeholder="{{ t('grocery_meal_name', default='Meal Name') | e }}">
                        <input type="number" class="form-control" id="newMealPlanBudget" placeholder="{{ t('grocery_budget', default='Budget') | e }}" min="0" step="0.01">
                        <button class="btn btn-primary" onclick="createMealPlan()">{{ t('grocery_create', default='Create') | e }}</button>
                    </div>
                </div>
                <div id="mealPlans"></div>
                <div class="mt-3">
                    <h6>{{ t('grocery_add_ingredient', default='Add Ingredient') | e }}</h6>
                    <div class="input-group">
                        <input type="text" class="form-control" id="newIngredientName" placeholder="{{ t('grocery_ingredient_name', default='Ingredient Name') | e }}">
                        <input type="number" class="form-control" id="newIngredientQuantity" placeholder="{{ t('grocery_quantity', default='Quantity') | e }}" min="1">
                        <input type="number" class="form-control" id="newIngredientPrice" placeholder="{{ t('grocery_price', default='Price') | e }}" min="0" step="0.01">
                        <button class="btn btn-primary" onclick="addIngredient()">{{ t('grocery_add', default='Add') | e }}</button>
                    </div>
                </div>
            </div>
            <div class="tab-pane fade" id="suggestions" role="tabpanel" aria-labelledby="suggestions-tab">
                <div class="mb-3">
                    <h6>{{ t('grocery_suggested_items', default='Suggested Items') | e }}</h6>
                    <div id="predictiveSuggestions"></div>
                </div>
                <div class="mb-3">
                    <h6>{{ t('grocery_collaborator_suggestions', default='Collaborator Suggestions') | e }}</h6>
                    <div id="collaboratorSuggestions"></div>
                </div>
                <div class="mt-3">
                    <h6>{{ t('grocery_suggest_item', default='Suggest Item') | e }}</h6>
                    <div class="input-group">
                        <input type="text" class="form-control" id="suggestItemName" placeholder="{{ t('grocery_item_name', default='Item Name') | e }}">
                        <input type="number" class="form-control" id="suggestItemQuantity" placeholder="{{ t('grocery_quantity', default='Quantity') | e }}" min="1">
                        <input type="number" class="form-control" id="suggestItemPrice" placeholder="{{ t('grocery_price', default='Price') | e }}" min="0" step="0.01">
                        <button class="btn btn-primary" onclick="suggestItem()">{{ t('grocery_suggest', default='Suggest') | e }}</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    loadGroceryLists();
    loadPredictiveSuggestions();
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
    fetchWithCSRF('{{ url_for("personal.grocery.manage_lists") | e }}')
        .then(response => response.json())
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
                    <button class="btn btn-sm btn-outline-primary ms-2" onclick="loadGroceryItems('${list.id}')">${translations.view_all}</button>
                </div>
            </div>
        `).join('');
        if (!currentListId && lists[0]) {
            loadGroceryItems(lists[0].id);
        }
    } else {
        groceryListsEl.innerHTML = `<div class="text-muted">${translations.no_lists}</div>`;
    }
}

function loadGroceryItems(listId) {
    currentListId = listId;
    fetchWithCSRF('{{ url_for("personal.grocery.manage_items", list_id="") | e }}' + listId)
        .then(response => response.json())
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
                        <option value="to_buy" ${item.status === 'to_buy' ? 'selected' : ''}>${translations.grocery_to_buy}</option>
                        <option value="in_pantry" ${item.status === 'in_pantry' ? 'selected' : ''}>${translations.grocery_in_pantry}</option>
                        <option value="bought" ${item.status === 'bought' ? 'selected' : ''}>${translations.grocery_bought}</option>
                    </select>
                    <button class="btn btn-sm btn-outline-info" onclick="showPriceHistory('${item.name}')">${translations.grocery_price_history}</button>
                </div>
            </div>
        `).join('');
    } else {
        groceryItemsEl.innerHTML = `<div class="text-muted">${translations.no_items}</div>`;
    }
}

function createGroceryList() {
    const name = document.getElementById('newListName').value;
    const budget = document.getElementById('newListBudget').value;
    if (!name || !budget) {
        showToast('Please provide list name and budget', 'warning');
        return;
    }
    fetchWithCSRF('{{ url_for("personal.grocery.manage_lists") | e }}', {
        method: 'POST',
        body: JSON.stringify({ name, budget })
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(translations.grocery_list_created, 'success');
                document.getElementById('newListName').value = '';
                document.getElementById('newListBudget').value = '';
                loadGroceryLists();
                loadFinancialSummary();
            }
        })
        .catch(error => {
            console.error('Error creating grocery list:', error);
            showToast(translations.grocery_list_error, 'danger');
        });
}

function addGroceryItem() {
    if (!currentListId) {
        showToast('Please select a list first', 'warning');
        return;
    }
    const name = document.getElementById('newItemName').value;
    const quantity = document.getElementById('newItemQuantity').value;
    const price = document.getElementById('newItemPrice').value;
    const status = document.getElementById('newItemStatus').value;
    const store = document.getElementById('newItemStore').value;
    if (!name || !quantity || !price) {
        showToast('Please provide item name, quantity, and price', 'warning');
        return;
    }
    fetchWithCSRF('{{ url_for("personal.grocery.manage_items", list_id="") | e }}' + currentListId, {
        method: 'POST',
        body: JSON.stringify({ name, quantity, price, status, store })
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(translations.grocery_item_added, 'success');
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
            showToast(translations.grocery_item_error, 'danger');
        });
}

function updateGroceryItem(itemId, field, value) {
    fetchWithCSRF('{{ url_for("personal.grocery.manage_items", list_id="") | e }}' + currentListId, {
        method: 'PUT',
        body: JSON.stringify({ item_id: itemId, [field]: value })
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(translations.grocery_item_updated, 'success');
                loadGroceryItems(currentListId);
                loadFinancialSummary();
            }
        })
        .catch(error => {
            console.error('Error updating grocery item:', error);
            showToast(translations.grocery_item_error, 'danger');
        });
}

function shareGroceryList() {
    if (!currentListId) {
        showToast('Please select a list first', 'warning');
        return;
    }
    const email = document.getElementById('shareListEmail').value;
    if (!email) {
        showToast('Please provide a collaborator email', 'warning');
        return;
    }
    fetchWithCSRF('{{ url_for("personal.grocery.share_list", list_id="") | e }}' + currentListId, {
        method: 'POST',
        body: JSON.stringify({ email })
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(translations.grocery_list_shared, 'success');
                document.getElementById('shareListEmail').value = '';
                loadGroceryLists();
            }
        })
        .catch(error => {
            console.error('Error sharing grocery list:', error);
            showToast(translations.grocery_share_error, 'danger');
        });
}

function loadMealPlans() {
    fetchWithCSRF('{{ url_for("personal.grocery.manage_meal_plans") | e }}')
        .then(response => response.json())
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
                    <button class="btn btn-sm btn-outline-primary" onclick="loadMealPlanIngredients('${plan.id}')">${translations.view_all}</button>
                    <button class="btn btn-sm btn-outline-success" onclick="generateGroceryListFromMealPlan('${plan.id}')">Generate List</button>
                </div>
            </div>
        `).join('');
        if (!currentMealPlanId && mealPlans[0]) {
            loadMealPlanIngredients(mealPlans[0].id);
        }
    } else {
        mealPlansEl.innerHTML = `<div class="text-muted">${translations.no_meal_plans}</div>`;
    }
}

function loadMealPlanIngredients(mealPlanId) {
    currentMealPlanId = mealPlanId;
    fetchWithCSRF('{{ url_for("personal.grocery.manage_meal_plans") | e }}')
        .then(response => response.json())
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
        showToast('Please provide meal plan name', 'warning');
        return;
    }
    fetchWithCSRF('{{ url_for("personal.grocery.manage_meal_plans") | e }}', {
        method: 'POST',
        body: JSON.stringify({ name, budget, auto_generate_list: !!budget, ingredients: [] })
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(translations.grocery_meal_plan_created, 'success');
                document.getElementById('newMealPlanName').value = '';
                document.getElementById('newMealPlanBudget').value = '';
                loadMealPlans();
                loadFinancialSummary();
            }
        })
        .catch(error => {
            console.error('Error creating meal plan:', error);
            showToast(translations.grocery_meal_plan_error, 'danger');
        });
}

function addIngredient() {
    if (!currentMealPlanId) {
        showToast('Please select a meal plan first', 'warning');
        return;
    }
    const name = document.getElementById('newIngredientName').value;
    const quantity = document.getElementById('newIngredientQuantity').value;
    const price = document.getElementById('newIngredientPrice').value;
    if (!name || !quantity || !price) {
        showToast('Please provide ingredient name, quantity, and price', 'warning');
        return;
    }
    fetchWithCSRF('{{ url_for("personal.grocery.manage_meal_plans") | e }}', {
        method: 'POST',
        body: JSON.stringify({ 
            name: `Update for ${currentMealPlanId}`, 
            ingredients: [{ name, quantity, price }], 
            auto_generate_list: false 
        })
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(translations.grocery_item_added, 'success');
                document.getElementById('newIngredientName').value = '';
                document.getElementById('newIngredientQuantity').value = '';
                document.getElementById('newIngredientPrice').value = '';
                loadMealPlans();
            }
        })
        .catch(error => {
            console.error('Error adding ingredient:', error);
            showToast(translations.grocery_item_error, 'danger');
        });
}

function generateGroceryListFromMealPlan(mealPlanId) {
    fetchWithCSRF('{{ url_for("personal.grocery.manage_meal_plans") | e }}')
        .then(response => response.json())
        .then(mealPlans => {
            const plan = mealPlans.find(p => p.id === mealPlanId);
            if (plan) {
                fetchWithCSRF('{{ url_for("personal.grocery.manage_lists") | e }}', {
                    method: 'POST',
                    body: JSON.stringify({
                        name: `${plan.name} Grocery List`,
                        budget: plan.ingredients.reduce((sum, i) => sum + i.price * i.quantity, 0),
                        auto_generate_list: true
                    })
                })
                    .then(response => response.json())
                    .then(data => {
                        if (data.error) {
                            showToast(data.error, 'danger');
                        } else {
                            showToast(translations.grocery_list_created, 'success');
                            loadGroceryLists();
                            loadFinancialSummary();
                        }
                    })
                    .catch(error => {
                        console.error('Error generating grocery list:', error);
                        showToast(translations.grocery_list_error, 'danger');
                    });
            }
        })
        .catch(error => {
            console.error('Error fetching meal plan:', error);
            showToast(translations.grocery_meal_plan_error, 'danger');
        });
}

function loadPredictiveSuggestions() {
    fetchWithCSRF('{{ url_for("personal.grocery.predictive_suggestions") | e }}')
        .then(response => response.json())
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
                    <button class="btn btn-sm btn-outline-primary ms-2" onclick="addSuggestedItem('${s.name}', ${s.suggested_quantity}, ${s.estimated_price})">Add</button>
                </div>
            </div>
        `).join('');
    } else {
        suggestionsEl.innerHTML = `<div class="text-muted">${translations.no_suggestions}</div>`;
    }
}

function addSuggestedItem(name, quantity, price) {
    if (!currentListId) {
        showToast('Please select a list first', 'warning');
        return;
    }
    fetchWithCSRF('{{ url_for("personal.grocery.manage_items", list_id="") | e }}' + currentListId, {
        method: 'POST',
        body: JSON.stringify({ name, quantity, price, status: 'to_buy' })
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(translations.grocery_item_added, 'success');
                loadGroceryItems(currentListId);
                loadFinancialSummary();
            }
        })
        .catch(error => {
            console.error('Error adding suggested item:', error);
            showToast(translations.grocery_item_error, 'danger');
        });
}

function loadCollaboratorSuggestions(listId) {
    fetchWithCSRF('{{ url_for("personal.grocery.manage_suggestions", list_id="") | e }}' + listId)
        .then(response => response.json())
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
                    ${s.status === 'pending' ? `<button class="btn btn-sm btn-outline-success ms-2" onclick="approveSuggestion('${s.id}', '${currentListId}')">${translations.grocery_suggestion_approved}</button>` : ''}
                </div>
            </div>
        `).join('');
    } else {
        suggestionsEl.innerHTML = `<div class="text-muted">${translations.no_suggestions}</div>`;
    }
}

function suggestItem() {
    if (!currentListId) {
        showToast('Please select a list first', 'warning');
        return;
    }
    const name = document.getElementById('suggestItemName').value;
    const quantity = document.getElementById('suggestItemQuantity').value;
    const price = document.getElementById('suggestItemPrice').value;
    if (!name || !quantity || !price) {
        showToast('Please provide item name, quantity, and price', 'warning');
        return;
    }
    fetchWithCSRF('{{ url_for("personal.grocery.manage_suggestions", list_id="") | e }}' + currentListId, {
        method: 'POST',
        body: JSON.stringify({ name, quantity, price })
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(translations.grocery_suggestion_added, 'success');
                document.getElementById('suggestItemName').value = '';
                document.getElementById('suggestItemQuantity').value = '';
                document.getElementById('suggestItemPrice').value = '';
                loadCollaboratorSuggestions(currentListId);
            }
        })
        .catch(error => {
            console.error('Error suggesting item:', error);
            showToast(translations.grocery_suggestion_error, 'danger');
        });
}

function approveSuggestion(suggestionId, listId) {
    fetchWithCSRF('{{ url_for("personal.grocery.approve_suggestion", list_id=listId, suggestion_id=suggestionId) | e }}', {
        method: 'POST'
    })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showToast(data.error, 'danger');
            } else {
                showToast(translations.grocery_suggestion_approved, 'success');
                loadGroceryItems(currentListId);
                loadCollaboratorSuggestions(currentListId);
                loadFinancialSummary();
            }
        })
        .catch(error => {
            console.error('Error approving suggestion:', error);
            showToast(translations.grocery_suggestion_error, 'danger');
        });
}

function showPriceHistory(itemName) {
    fetchWithCSRF('{{ url_for("personal.grocery.price_history", item_name="") | e }}' + encodeURIComponent(itemName))
        .then(response => response.json())
        .then(data => {
            const history = data.prices || [];
            const avgPrice = data.average_price || 0;
            const modalBody = document.querySelector('#groceryModal .modal-body');
            const historyHtml = history.length > 0 ? history.map(h => `
                <div class="grocery-item">
                    <span>${h.store}: ${format_currency(h.price)}</span>
                    <span class="text-muted">${formatTimeAgo(h.date)}</span>
                </div>
            `).join('') : `<div class="text-muted">${translations.no_price_history}</div>`;
            modalBody.innerHTML += `
                <div class="mt-3">
                    <h6>Price History for ${itemName} (Avg: ${format_currency(avgPrice)})</h6>
                    ${historyHtml}
                </div>
            `;
        })
        .catch(error => {
            console.error('Error loading price history:', error);
            showToast(translations.grocery_price_history_error, 'danger');
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
    return value.toLocaleString('en-NG', {minimumFractionDigits: 2, maximumFractionDigits: 2});
}

function showToast(message, type) {
    const toastContainer = document.createElement('div');
    toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
    toastContainer.innerHTML = `
        <div class="toast align-items-center text-bg-${type} border-0" role="alert" aria-live="assertive" aria-atomic="true">
            <div class="d-flex">
                <div class="toast-body">${message}</div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
        </div>
    `;
    document.body.appendChild(toastContainer);
    const toast = new bootstrap.Toast(toastContainer.querySelector('.toast'));
    toast.show();
}
{% endif %}
