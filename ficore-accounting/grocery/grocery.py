from flask import Blueprint, jsonify, request, current_app, session
from flask_login import current_user, login_required
from datetime import datetime, date, timedelta
from bson import ObjectId
from models import get_bills, get_budgets
from utils import get_mongo_db, trans, requires_role, logger, format_currency, clean_currency
from decimal import Decimal
import re

grocery_bp = Blueprint('grocery', __name__, url_prefix='/grocery')

# Helper function to auto-categorize items
def auto_categorize_item(item_name):
    """Auto-categorize grocery items based on keywords."""
    item_name = item_name.lower().strip()
    categories = {
        'fruits': ['apple', 'banana', 'orange', 'mango', 'pineapple', 'berry', 'grape'],
        'vegetables': ['carrot', 'potato', 'tomato', 'onion', 'spinach', 'lettuce'],
        'dairy': ['milk', 'cheese', 'yogurt', 'butter', 'cream'],
        'meat': ['chicken', 'beef', 'pork', 'fish', 'egg'],
        'grains': ['rice', 'bread', 'pasta', 'flour', 'cereal'],
        'beverages': ['juice', 'soda', 'water', 'tea', 'coffee'],
        'household': ['detergent', 'soap', 'tissue', 'paper towel'],
        'other': []
    }
    for category, keywords in categories.items():
        if any(keyword in item_name for keyword in keywords):
            return category
    return 'other'

# Helper function to calculate predictive suggestions
def get_predictive_suggestions(user_id, db):
    """Suggest items based on purchase frequency and last bought date."""
    suggestions = []
    items = db.grocery_items.find({'user_id': str(user_id), 'status': 'bought'}).sort('updated_at', -1)
    today = date.today()
    for item in items:
        item_name = item.get('name', '').lower()
        last_bought = item.get('updated_at', datetime.utcnow()).date()
        frequency = item.get('frequency', 7)  # Default to weekly
        if (today - last_bought).days >= frequency:
            suggestions.append({
                'name': item.get('name'),
                'category': item.get('category', 'other'),
                'suggested_quantity': item.get('quantity', 1),
                'estimated_price': float(item.get('price', 0))
            })
    return suggestions[:5]  # Limit to top 5 suggestions

@grocery_bp.route('/lists', methods=['GET', 'POST'])
@login_required
@requires_role(['personal', 'admin'])
def manage_lists():
    """Manage grocery lists (create, retrieve)."""
    db = get_mongo_db()
    try:
        if request.method == 'POST':
            data = request.get_json()
            if not data or not data.get('name') or not data.get('budget'):
                return jsonify({'error': trans('grocery_invalid_input', default='Invalid or missing list data')}), 400
            
            # Validate and clean data
            budget = clean_currency(data.get('budget', '0'))
            if budget <= 0:
                return jsonify({'error': trans('grocery_invalid_budget', default='Budget must be positive')}), 400

            # Check Ficore Credits for creating a list (e.g., 1 credit)
            user = db.users.find_one({'_id': current_user.id})
            if user.get('ficore_credit_balance', 0) < 1:
                return jsonify({'error': trans('grocery_insufficient_credits', default='Insufficient Ficore Credits')}), 403

            list_data = {
                'name': data.get('name'),
                'user_id': str(current_user.id),
                'budget': float(budget),
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'collaborators': data.get('collaborators', []),
                'items': [],
                'total_spent': 0.0,
                'status': 'active'
            }
            result = db.grocery_lists.insert_one(list_data)
            
            # Deduct Ficore Credits
            db.users.update_one(
                {'_id': current_user.id},
                {'$inc': {'ficore_credit_balance': -1}}
            )
            db.ficore_credit_transactions.insert_one({
                'user_id': str(current_user.id),
                'amount': -1,
                'action': 'create_grocery_list',
                'timestamp': datetime.utcnow()
            })

            logger.info(f"Created grocery list {result.inserted_id} for user {current_user.id}", 
                        extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'list_id': str(result.inserted_id), 'message': trans('grocery_list_created', default='Grocery list created')}), 201

        # GET: Retrieve all lists
        lists = db.grocery_lists.find({'user_id': str(current_user.id)}).sort('updated_at', -1)
        return jsonify([{
            'id': str(l['_id']),
            'name': l.get('name'),
            'budget': float(l.get('budget', 0)),
            'total_spent': float(l.get('total_spent', 0)),
            'status': l.get('status', 'active'),
            'created_at': l.get('created_at').isoformat(),
            'collaborators': l.get('collaborators', [])
        } for l in lists]), 200

    except Exception as e:
        logger.error(f"Error managing grocery lists for user {current_user.id}: {str(e)}", 
                     extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({'error': trans('grocery_list_error', default='Error managing grocery lists')}), 500

@grocery_bp.route('/lists/<list_id>/items', methods=['GET', 'POST', 'PUT'])
@login_required
@requires_role(['personal', 'admin'])
def manage_items(list_id):
    """Manage items in a grocery list."""
    db = get_mongo_db()
    try:
        grocery_list = db.grocery_lists.find_one({'_id': ObjectId(list_id), 'user_id': str(current_user.id)})
        if not grocery_list:
            return jsonify({'error': trans('grocery_list_not_found', default='Grocery list not found')}), 404

        if request.method == 'POST':
            data = request.get_json()
            if not data or not data.get('name') or not data.get('quantity') or not data.get('price'):
                return jsonify({'error': trans('grocery_invalid_item', default='Invalid or missing item data')}), 400

            quantity = int(data.get('quantity', 1))
            price = clean_currency(data.get('price', '0'))
            if quantity <= 0 or price < 0:
                return jsonify({'error': trans('grocery_invalid_item_data', default='Invalid quantity or price')}), 400

            item_data = {
                'list_id': list_id,
                'user_id': str(current_user.id),
                'name': data.get('name'),
                'quantity': quantity,
                'price': float(price),
                'category': auto_categorize_item(data.get('name')),
                'status': data.get('status', 'to_buy'),  # to_buy, in_pantry, bought
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'store': data.get('store', 'Unknown'),
                'frequency': int(data.get('frequency', 7))  # Default to weekly
            }
            result = db.grocery_items.insert_one(item_data)

            # Update total_spent in grocery list
            db.grocery_lists.update_one(
                {'_id': ObjectId(list_id)},
                {'$inc': {'total_spent': float(price * quantity)}, '$set': {'updated_at': datetime.utcnow()}}
            )

            logger.info(f"Added item {result.inserted_id} to list {list_id} for user {current_user.id}", 
                        extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'item_id': str(result.inserted_id), 'message': trans('grocery_item_added', default='Item added to list')}), 201

        if request.method == 'PUT':
            data = request.get_json()
            item_id = data.get('item_id')
            item = db.grocery_items.find_one({'_id': ObjectId(item_id), 'list_id': list_id, 'user_id': str(current_user.id)})
            if not item:
                return jsonify({'error': trans('grocery_item_not_found', default='Item not found')}), 404

            updates = {}
            if 'status' in data:
                updates['status'] = data['status']
            if 'quantity' in data:
                updates['quantity'] = int(data['quantity'])
            if 'price' in data:
                updates['price'] = float(clean_currency(data['price']))
            if updates:
                updates['updated_at'] = datetime.utcnow()
                db.grocery_items.update_one({'_id': ObjectId(item_id)}, {'$set': updates})

                # Recalculate total_spent
                items = db.grocery_items.find({'list_id': list_id, 'status': 'bought'})
                total_spent = sum(float(item.get('price', 0)) * item.get('quantity', 1) for item in items)
                db.grocery_lists.update_one(
                    {'_id': ObjectId(list_id)},
                    {'$set': {'total_spent': total_spent, 'updated_at': datetime.utcnow()}}
                )

            logger.info(f"Updated item {item_id} in list {list_id} for user {current_user.id}", 
                        extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'message': trans('grocery_item_updated', default='Item updated')}), 200

        # GET: Retrieve items
        items = db.grocery_items.find({'list_id': list_id}).sort('created_at', -1)
        return jsonify([{
            'id': str(i['_id']),
            'name': i.get('name'),
            'quantity': i.get('quantity', 1),
            'price': float(i.get('price', 0)),
            'category': i.get('category', 'other'),
            'status': i.get('status', 'to_buy'),
            'store': i.get('store', 'Unknown'),
            'frequency': i.get('frequency', 7)
        } for i in items]), 200

    except Exception as e:
        logger.error(f"Error managing items for list {list_id}: {str(e)}", 
                     extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({'error': trans('grocery_item_error', default='Error managing items')}), 500

@grocery_bp.route('/lists/<list_id>/share', methods=['POST'])
@login_required
@requires_role(['personal', 'admin'])
def share_list(list_id):
    """Share a grocery list with collaborators."""
    db = get_mongo_db()
    try:
        grocery_list = db.grocery_lists.find_one({'_id': ObjectId(list_id), 'user_id': str(current_user.id)})
        if not grocery_list:
            return jsonify({'error': trans('grocery_list_not_found', default='Grocery list not found')}), 404

        data = request.get_json()
        collaborator_email = data.get('email')
        if not collaborator_email or not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', collaborator_email):
            return jsonify({'error': trans('grocery_invalid_email', default='Invalid email address')}), 400

        collaborator = db.users.find_one({'email': collaborator_email})
        if not collaborator:
            return jsonify({'error': trans('grocery_user_not_found', default='User not found')}), 404

        db.grocery_lists.update_one(
            {'_id': ObjectId(list_id)},
            {'$addToSet': {'collaborators': collaborator_email}, '$set': {'updated_at': datetime.utcnow()}}
        )

        logger.info(f"Shared list {list_id} with {collaborator_email} by user {current_user.id}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({'message': trans('grocery_list_shared', default='List shared successfully')}), 200

    except Exception as e:
        logger.error(f"Error sharing list {list_id}: {str(e)}", 
                     extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({'error': trans('grocery_share_error', default='Error sharing list')}), 500

@grocery_bp.route('/lists/<list_id>/suggestions', methods=['GET', 'POST'])
@login_required
@requires_role(['personal', 'admin'])
def manage_suggestions(list_id):
    """Manage item suggestions for shared lists."""
    db = get_mongo_db()
    try:
        grocery_list = db.grocery_lists.find_one({'_id': ObjectId(list_id)})
        if not grocery_list or (str(current_user.id) not in [grocery_list['user_id']] + grocery_list.get('collaborators', [])):
            return jsonify({'error': trans('grocery_list_not_found', default='Grocery list not found or access denied')}), 404

        if request.method == 'POST':
            data = request.get_json()
            if not data or not data.get('name') or not data.get('quantity'):
                return jsonify({'error': trans('grocery_invalid_suggestion', default='Invalid or missing suggestion data')}), 400

            suggestion_data = {
                'list_id': list_id,
                'user_id': str(current_user.id),
                'name': data.get('name'),
                'quantity': int(data.get('quantity', 1)),
                'price': float(clean_currency(data.get('price', '0'))),
                'category': auto_categorize_item(data.get('name')),
                'status': 'pending',
                'created_at': datetime.utcnow()
            }
            result = db.grocery_suggestions.insert_one(suggestion_data)

            logger.info(f"Added suggestion {result.inserted_id} to list {list_id} by user {current_user.id}", 
                        extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'suggestion_id': str(result.inserted_id), 'message': trans('grocery_suggestion_added', default='Suggestion added')}), 201

        # GET: Retrieve suggestions
        suggestions = db.grocery_suggestions.find({'list_id': list_id}).sort('created_at', -1)
        return jsonify([{
            'id': str(s['_id']),
            'name': s.get('name'),
            'quantity': s.get('quantity', 1),
            'price': float(s.get('price', 0)),
            'category': s.get('category', 'other'),
            'status': s.get('status', 'pending'),
            'user_id': s.get('user_id')
        } for s in suggestions]), 200

    except Exception as e:
        logger.error(f"Error managing suggestions for list {list_id}: {str(e)}", 
                     extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({'error': trans('grocery_suggestion_error', default='Error managing suggestions')}), 500

@grocery_bp.route('/lists/<list_id>/suggestions/<suggestion_id>/approve', methods=['POST'])
@login_required
@requires_role(['personal', 'admin'])
def approve_suggestion(list_id, suggestion_id):
    """Approve a suggested item and add it to the list."""
    db = get_mongo_db()
    try:
        grocery_list = db.grocery_lists.find_one({'_id': ObjectId(list_id), 'user_id': str(current_user.id)})
        if not grocery_list:
            return jsonify({'error': trans('grocery_list_not_found', default='Grocery list not found or not owner')}), 404

        suggestion = db.grocery_suggestions.find_one({'_id': ObjectId(suggestion_id), 'list_id': list_id})
        if not suggestion:
            return jsonify({'error': trans('grocery_suggestion_not_found', default='Suggestion not found')}), 404

        item_data = {
            'list_id': list_id,
            'user_id': str(current_user.id),
            'name': suggestion.get('name'),
            'quantity': suggestion.get('quantity', 1),
            'price': suggestion.get('price', 0),
            'category': suggestion.get('category', 'other'),
            'status': 'to_buy',
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'store': suggestion.get('store', 'Unknown'),
            'frequency': suggestion.get('frequency', 7)
        }
        db.grocery_items.insert_one(item_data)
        db.grocery_suggestions.update_one(
            {'_id': ObjectId(suggestion_id)},
            {'$set': {'status': 'approved', 'updated_at': datetime.utcnow()}}
        )

        # Update total_spent
        db.grocery_lists.update_one(
            {'_id': ObjectId(list_id)},
            {'$inc': {'total_spent': float(suggestion.get('price', 0) * suggestion.get('quantity', 1))},
             '$set': {'updated_at': datetime.utcnow()}}
        )

        logger.info(f"Approved suggestion {suggestion_id} for list {list_id} by user {current_user.id}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({'message': trans('grocery_suggestion_approved', default='Suggestion approved and added to list')}), 200

    except Exception as e:
        logger.error(f"Error approving suggestion {suggestion_id} for list {list_id}: {str(e)}", 
                     extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({'error': trans('grocery_suggestion_error', default='Error approving suggestion')}), 500

@grocery_bp.route('/meal_plans', methods=['GET', 'POST'])
@login_required
@requires_role(['personal', 'admin'])
def manage_meal_plans():
    """Manage meal plans and auto-generate grocery lists."""
    db = get_mongo_db()
    try:
        if request.method == 'POST':
            data = request.get_json()
            if not data or not data.get('name') or not data.get('ingredients'):
                return jsonify({'error': trans('grocery_invalid_meal_plan', default='Invalid or missing meal plan data')}), 400

            meal_plan = {
                'user_id': str(current_user.id),
                'name': data.get('name'),
                'ingredients': [{
                    'name': i.get('name'),
                    'quantity': int(i.get('quantity', 1)),
                    'category': auto_categorize_item(i.get('name')),
                    'price': float(clean_currency(i.get('price', '0')))
                } for i in data.get('ingredients', [])],
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }
            result = db.meal_plans.insert_one(meal_plan)

            # Optionally auto-generate a grocery list
            if data.get('auto_generate_list'):
                list_data = {
                    'name': f"{data.get('name')} Grocery List",
                    'user_id': str(current_user.id),
                    'budget': float(clean_currency(data.get('budget', '0'))),
                    'created_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow(),
                    'collaborators': [],
                    'items': [],
                    'total_spent': 0.0,
                    'status': 'active'
                }
                list_result = db.grocery_lists.insert_one(list_data)
                for ingredient in meal_plan['ingredients']:
                    db.grocery_items.insert_one({
                        'list_id': str(list_result.inserted_id),
                        'user_id': str(current_user.id),
                        'name': ingredient['name'],
                        'quantity': ingredient['quantity'],
                        'price': ingredient['price'],
                        'category': ingredient['category'],
                        'status': 'to_buy',
                        'created_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow(),
                        'store': 'Unknown',
                        'frequency': 7
                    })
                list_data['total_spent'] = sum(i['price'] * i['quantity'] for i in meal_plan['ingredients'])
                db.grocery_lists.update_one(
                    {'_id': list_result.inserted_id},
                    {'$set': {'total_spent': list_data['total_spent'], 'updated_at': datetime.utcnow()}}
                )

            logger.info(f"Created meal plan {result.inserted_id} for user {current_user.id}", 
                        extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
            return jsonify({'meal_plan_id': str(result.inserted_id), 'message': trans('grocery_meal_plan_created', default='Meal plan created')}), 201

        # GET: Retrieve meal plans
        meal_plans = db.meal_plans.find({'user_id': str(current_user.id)}).sort('updated_at', -1)
        return jsonify([{
            'id': str(m['_id']),
            'name': m.get('name'),
            'ingredients': m.get('ingredients', []),
            'created_at': m.get('created_at').isoformat()
        } for m in meal_plans]), 200

    except Exception as e:
        logger.error(f"Error managing meal plans for user {current_user.id}: {str(e)}", 
                     extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({'error': trans('grocery_meal_plan_error', default='Error managing meal plans')}), 500

@grocery_bp.route('/price_history/<item_name>', methods=['GET'])
@login_required
@requires_role(['personal', 'admin'])
def price_history(item_name):
    """Retrieve price history for an item."""
    db = get_mongo_db()
    try:
        items = db.grocery_items.find({
            'user_id': str(current_user.id),
            'name': {'$regex': f'^{item_name}$', '$options': 'i'},
            'status': 'bought'
        }).sort('updated_at', -1).limit(10)
        prices = [{'price': float(i.get('price', 0)), 'store': i.get('store', 'Unknown'), 'date': i.get('updated_at').isoformat()} for i in items]
        if prices:
            avg_price = sum(p['price'] for p in prices) / len(prices)
            return jsonify({'prices': prices, 'average_price': float(avg_price)}), 200
        return jsonify({'prices': [], 'average_price': 0.0}), 200

    except Exception as e:
        logger.error(f"Error fetching price history for item {item_name}: {str(e)}", 
                     extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({'error': trans('grocery_price_history_error', default='Error fetching price history')}), 500

@grocery_bp.route('/suggestions', methods=['GET'])
@login_required
@requires_role(['personal', 'admin'])
def predictive_suggestions():
    """Get predictive item suggestions based on purchase history."""
    try:
        db = get_mongo_db()
        suggestions = get_predictive_suggestions(current_user.id, db)
        logger.info(f"Fetched {len(suggestions)} predictive suggestions for user {current_user.id}", 
                    extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify(suggestions), 200
    except Exception as e:
        logger.error(f"Error fetching predictive suggestions for user {current_user.id}: {str(e)}", 
                     extra={'session_id': session.get('sid', 'no-session-id'), 'ip_address': request.remote_addr})
        return jsonify({'error': trans('grocery_suggestions_error', default='Error fetching suggestions')}), 500