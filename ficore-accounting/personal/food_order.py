from flask import Blueprint, jsonify, current_app, request, session
from flask_login import current_user, login_required
from utils import requires_role, get_mongo_db
from translations import trans
import logging
from datetime import datetime
import uuid

# Configure logging
logging.basicConfig(level=logging.DEBUG)

food_order_bp = Blueprint('food_order', __name__, url_prefix='/personal/food_order')

def init_app(app):
    """Initialize the food order blueprint."""
    try:
        current_app.logger.info("Food order blueprint initialized successfully", extra={'session_id': 'no-request-context'})
    except Exception as e:
        current_app.logger.error(f"Error initializing food order blueprint: {str(e)}", extra={'session_id': 'no-request-context'})
        raise

@food_order_bp.route('/manage_orders', methods=['GET', 'POST'])
@login_required
@requires_role(['personal', 'admin'])
def manage_orders():
    """Manage food orders: list all orders (GET) or create a new order (POST)."""
    try:
        db = get_mongo_db()
        collection = db.FoodOrder
        user_id = str(current_user.id)

        if request.method == 'GET':
            orders = list(collection.find({'user_id': user_id}, {'_id': 0}))
            current_app.logger.info(f"Retrieved {len(orders)} food orders for user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
            return jsonify(orders)

        elif request.method == 'POST':
            data = request.get_json()
            if not data or not data.get('name') or not data.get('vendor'):
                current_app.logger.warning(f"Invalid order data: {data}", extra={'session_id': session.get('sid', 'unknown')})
                return jsonify({'error': trans('food_order_invalid_data', default='Invalid order data')}), 400

            order = {
                'id': str(uuid.uuid4()),
                'user_id': user_id,
                'name': data['name'],
                'vendor': data['vendor'],
                'total_cost': 0.0,
                'created_at': datetime.utcnow(),
                'updated_at': datetime.utcnow(),
                'shared_with': [],  # For future sharing functionality
                'items': []
            }
            collection.insert_one(order)
            current_app.logger.info(f"Created food order {order['id']} for user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
            return jsonify({k: v for k, v in order.items() if k != '_id'})

    except Exception as e:
        current_app.logger.error(f"Error in manage_orders: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        return jsonify({'error': trans('general_error', default='An error occurred')}), 500

@food_order_bp.route('/manage_items/<order_id>', methods=['GET', 'POST', 'PUT'])
@login_required
@requires_role(['personal', 'admin'])
def manage_items(order_id):
    """Manage items in a food order: list items (GET), add item (POST), update item (PUT)."""
    try:
        db = get_mongo_db()
        collection = db.FoodOrder
        user_id = str(current_user.id)

        # Verify order exists and belongs to user
        order = collection.find_one({'id': order_id, 'user_id': user_id})
        if not order:
            current_app.logger.warning(f"Order {order_id} not found for user {user_id}", extra={'session_id': session.get('sid', 'unknown')})
            return jsonify({'error': trans('food_order_not_found', default='Order not found')}), 404

        if request.method == 'GET':
            items = order.get('items', [])
            current_app.logger.info(f"Retrieved {len(items)} items for order {order_id}", extra={'session_id': session.get('sid', 'unknown')})
            return jsonify(items)

        elif request.method == 'POST':
            data = request.get_json()
            if not data or not data.get('name') or not data.get('quantity') or not data.get('price'):
                current_app.logger.warning(f"Invalid item data: {data}", extra={'session_id': session.get('sid', 'unknown')})
                return jsonify({'error': trans('food_order_invalid_item_data', default='Invalid item data')}), 400

            item = {
                'item_id': str(uuid.uuid4()),
                'name': data['name'],
                'quantity': int(data['quantity']),
                'price': float(data['price']),
                'category': data.get('category', 'Uncategorized')
            }
            collection.update_one(
                {'id': order_id},
                {
                    '$push': {'items': item},
                    '$set': {
                        'total_cost': order['total_cost'] + (item['quantity'] * item['price']),
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            current_app.logger.info(f"Added item {item['item_id']} to order {order_id}", extra={'session_id': session.get('sid', 'unknown')})
            return jsonify(item)

        elif request.method == 'PUT':
            data = request.get_json()
            if not data or not data.get('item_id') or not data.get(data.get('field', '')):
                current_app.logger.warning(f"Invalid update data: {data}", extra={'session_id': session.get('sid', 'unknown')})
                return jsonify({'error': trans('food_order_invalid_update_data', default='Invalid update data')}), 400

            item_id = data['item_id']
            field = data.get('field')
            value = data[field]

            if field not in ['quantity', 'price']:
                return jsonify({'error': trans('food_order_invalid_field', default='Invalid field')}), 400

            # Find the item
            items = order.get('items', [])
            item_index = next((i for i, item in enumerate(items) if item['item_id'] == item_id), None)
            if item_index is None:
                current_app.logger.warning(f"Item {item_id} not found in order {order_id}", extra={'session_id': session.get('sid', 'unknown')})
                return jsonify({'error': trans('food_order_item_not_found', default='Item not found')}), 404

            # Update item
            items[item_index][field] = int(value) if field == 'quantity' else float(value)
            total_cost = sum(item['quantity'] * item['price'] for item in items)
            collection.update_one(
                {'id': order_id},
                {
                    '$set': {
                        'items': items,
                        'total_cost': total_cost,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            current_app.logger.info(f"Updated item {item_id} in order {order_id}", extra={'session_id': session.get('sid', 'unknown')})
            return jsonify({'success': True})

    except Exception as e:
        current_app.logger.error(f"Error in manage_items: {str(e)}", extra={'session_id': session.get('sid', 'unknown')})
        return jsonify({'error': trans('general_error', default='An error occurred')}), 500
